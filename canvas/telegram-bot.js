/**
 * JARVIS Telegram Bot — Thin Bridge vers Canvas Direct Proxy
 *
 * Long polling Telegram → POST /chat sur direct-proxy (18800) → sendMessage
 * Toute l'intelligence est dans agenticChat() du proxy.
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { exec, execSync } = require('child_process');
const os = require('os');

// ─── Config ───────────────────────────────────────────────────────────────────

// Charge .env manuellement (pas de dépendance dotenv)
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, 'utf-8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}
loadEnv();

const TOKEN = process.env.TELEGRAM_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT;
const PROXY_URL = 'http://127.0.0.1:18800';
const POLL_TIMEOUT = 30; // secondes (long polling Telegram)
const MAX_MSG_LEN = 4096; // limite Telegram
const RECONNECT_DELAY = 5000; // ms avant retry si proxy down
const TTS_SCRIPT = 'F:/BUREAU/turbo/cowork/dev/win_tts.py';
const VOICE_MODE = true; // Toujours répondre en vocal
const CLUSTER_RACE = true; // Utiliser tout le cluster en parallèle
const ALERTS_FLAG_FILE = path.join(__dirname, '..', 'data', '.trading_alerts_off');
let TRADING_ALERTS = !fs.existsSync(ALERTS_FLAG_FILE); // Lit le flag persistant au demarrage

// ─── Cluster nodes (direct, sans passer par le proxy) ─────────────────────────
const CLUSTER_NODES = [
  { id: 'M1', url: 'http://127.0.0.1:1234/v1/chat/completions', model: 'qwen3-8b', weight: 1.8 },
  { id: 'M2', url: 'http://192.168.1.26:1234/v1/chat/completions', model: 'deepseek-r1-0528-qwen3-8b', weight: 1.5 },
  { id: 'OL1', url: 'http://127.0.0.1:11434/api/chat', model: 'qwen3:1.7b', isOllama: true, weight: 1.3 },
  { id: 'M3', url: 'http://192.168.1.113:1234/v1/chat/completions', model: 'deepseek-r1-0528-qwen3-8b', weight: 1.2 },
];

if (!TOKEN) { console.error('[FATAL] TELEGRAM_TOKEN manquant dans .env'); process.exit(1); }
if (!CHAT_ID) { console.error('[FATAL] TELEGRAM_CHAT manquant dans .env'); process.exit(1); }

// ─── Single Instance Lock ─────────────────────────────────────────────────────

const LOCK_FILE = path.join(__dirname, '.telegram-bot.lock');
function acquireLock() {
  try {
    // Check if lock exists and process is still alive
    if (fs.existsSync(LOCK_FILE)) {
      const oldPid = parseInt(fs.readFileSync(LOCK_FILE, 'utf-8').trim());
      try {
        process.kill(oldPid, 0); // test if alive
        console.error(`[FATAL] Another telegram-bot is running (PID ${oldPid}). Exiting.`);
        process.exit(1);
      } catch (e) {
        // Process is dead, stale lock — remove it
        fs.unlinkSync(LOCK_FILE);
      }
    }
    fs.writeFileSync(LOCK_FILE, String(process.pid));
  } catch (e) {
    console.error('[WARN] Could not acquire lock:', e.message);
  }
}
function releaseLock() {
  try { fs.unlinkSync(LOCK_FILE); } catch (e) {}
}
acquireLock();
process.on('exit', releaseLock);

// ─── State ────────────────────────────────────────────────────────────────────

let offset = 0;
let running = true;
let stats = { started: new Date().toISOString(), messages_in: 0, messages_out: 0, errors: 0 };
let messageHistory = []; // derniers messages reçus (max 50)

// ─── RBAC — Role-Based Access Control ────────────────────────────────────────

const ADMIN_COMMANDS = new Set(['/jarvis', '/exec', '/improve', '/gpu', '/voice']);

function isAdminCommand(cmd) {
  return ADMIN_COMMANDS.has(cmd);
}

// Rate limiter pour non-admins (max 10 msgs/min)
const userRateMap = new Map(); // chatId → { count, resetAt }
const RATE_LIMIT = 10;
const RATE_WINDOW = 60000; // 1 min

function checkRateLimit(chatId) {
  const now = Date.now();
  let entry = userRateMap.get(chatId);
  if (!entry || now > entry.resetAt) {
    entry = { count: 0, resetAt: now + RATE_WINDOW };
    userRateMap.set(chatId, entry);
  }
  entry.count++;
  return entry.count <= RATE_LIMIT;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ts() { return new Date().toISOString().slice(11, 19); }
function log(...args) { console.log(`[${ts()}]`, ...args); }
function logErr(...args) { console.error(`[${ts()}] ERROR`, ...args); }

/** HTTP request helper (retourne Promise<string>) */
function httpRequest(url, options = {}, body = null) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    if (options.timeout) req.setTimeout(options.timeout, () => { req.destroy(); reject(new Error('timeout')); });
    if (body) req.write(body);
    req.end();
  });
}

/** Appel Telegram Bot API */
async function telegramAPI(method, params = {}) {
  const url = `https://api.telegram.org/bot${TOKEN}/${method}`;
  const body = JSON.stringify(params);
  const res = await httpRequest(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    timeout: (method === 'getUpdates' ? (POLL_TIMEOUT + 10) * 1000 : 15000),
  }, body);
  const json = JSON.parse(res.body);
  if (!json.ok) throw new Error(`Telegram API ${method}: ${json.description || 'unknown error'}`);
  return json.result;
}

/** POST vers canvas proxy /chat — supporte text simple ou messages array */
async function proxyChat(text, agentId = 'telegram', chatId = null) {
  const payload = { agent: agentId, text };
  // Enrichir avec memoire conversation si chatId fourni
  if (chatId) {
    const mem = getMemoryMessages(chatId);
    if (mem.length > 0) {
      payload.messages = mem.slice(-5).map(m => ({ role: m.role, content: m.content }));
      payload.messages.push({ role: 'user', content: text });
    }
  }
  const body = JSON.stringify(payload);
  const res = await httpRequest(`${PROXY_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    timeout: 120000, // 2min max
  }, body);
  return JSON.parse(res.body);
}

/** GET vers canvas proxy */
async function proxyGet(endpoint) {
  const res = await httpRequest(`${PROXY_URL}${endpoint}`, { timeout: 10000 });
  return JSON.parse(res.body);
}

/** Split un message long en chunks <= MAX_MSG_LEN */
function splitMessage(text) {
  if (text.length <= MAX_MSG_LEN) return [text];
  const chunks = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= MAX_MSG_LEN) {
      chunks.push(remaining);
      break;
    }
    // Coupe au dernier \n avant la limite
    let cut = remaining.lastIndexOf('\n', MAX_MSG_LEN);
    if (cut < MAX_MSG_LEN * 0.3) cut = MAX_MSG_LEN; // pas de \n raisonnable, coupe brut
    chunks.push(remaining.slice(0, cut));
    remaining = remaining.slice(cut).trimStart();
  }
  return chunks;
}

/** Envoie un message Telegram (gère le split) */
async function sendMessage(chatId, text, parseMode = null) {
  const chunks = splitMessage(text);
  for (const chunk of chunks) {
    const params = { chat_id: chatId, text: chunk };
    if (parseMode) params.parse_mode = parseMode;
    try {
      await telegramAPI('sendMessage', params);
      stats.messages_out++;
    } catch (e) {
      // Fallback sans parse_mode si Markdown échoue
      if (parseMode) {
        try {
          await telegramAPI('sendMessage', { chat_id: chatId, text: chunk });
          stats.messages_out++;
        } catch (e2) {
          logErr('sendMessage failed:', e2.message);
          stats.errors++;
        }
      } else {
        logErr('sendMessage failed:', e.message);
        stats.errors++;
      }
    }
  }
}

// ─── Commandes spéciales ──────────────────────────────────────────────────────

async function handleCommand(chatId, cmd, args, isAdmin) {
  // Block admin-only commands for non-admin users
  if (isAdminCommand(cmd) && !isAdmin) {
    return sendMessage(chatId, '⛔ Cette commande est reservee a l\'administrateur.');
  }

  switch (cmd) {
    case '/start':
    case '/help': {
      const lines = [
        '*JARVIS Telegram Bot*',
        '',
        'Commandes:',
        '`/status` - Health check cluster',
        '`/health` - Etat detaille des noeuds',
        '`/consensus <q>` - Vote pondere multi-noeuds',
        '`/model <id> <q>` - Forcer un noeud (M1/M2/OL1...)',
        '`/scan [N]` - Sniper scan top N coins (breakouts, TP1/2/3, SL)',
        '`/deepscan [N]` - Deep scan 800+ coins entonnoir 3 passes (GPU+cluster)',
        '`/hot [N]` - Top N coins chauds (historique DB)',
        '`/scanstats` - Stats scanner (scans, snapshots, registry)',
        '`/sniper` - Statut du scanner permanent',
        '`/perf` - Performance des signaux emis (TP/SL)',
        '`/realtime` - Statut scanner temps reel',
        '`/loop` - Statut Super Loop amelioration',
        '`/backtest` - Resultats micro-backtest',
        '`/market` - Resume marche actuel (movers + trend)',
        '`/signals` - Signaux ouverts en temps reel',
        '`/alerton` - Activer les alertes trading (TP/SL)',
        '`/alertoff` - Desactiver les alertes trading',
        '`/openclaw <q>` - Question via proxy complet (reflexive chain)',
        '`/compare BTC SOL` - Comparer deux coins',
        '`/whales` - Gros mouvements detectes (DB)',
        '`/news` - Actualites crypto du jour',
        '`/stats` - Statistiques du bot',
        '`/menu` - Dashboard avec boutons interactifs',
        '`/help` - Cette aide',
      ];
      if (isAdmin) {
        lines.push(
          '',
          '*Admin:*',
          '`/gpu` - Temperatures et VRAM GPU',
          '`/jarvis <cmd>` - Executer commande vocale JARVIS',
          '`/exec <cmd>` - Alias de /jarvis',
          '`/improve [N]` - Lancer N cycles amelioration (def: 10)',
          '`/superloop [N]` - Lancer Super Loop (trading+code+repair)',
          '`/killscanner` - Arreter le scanner REALTIME',
          '`/voice [texte]` - Test reponse vocale',
        );
      }
      lines.push('', 'Texte libre: dispatch cluster IA.');
      lines.push('🎤 Audio: envoyez un vocal → transcription Whisper → reponse vocale automatique.');
      return sendMessage(chatId, lines.join('\n'), 'Markdown');
    }

    case '/status': {
      try {
        const h = await proxyGet('/health');
        if (!h.ok) throw new Error('proxy unhealthy');
        const lines = ['✅ *Cluster Status*', ''];
        for (const n of (h.nodes || [])) {
          const icon = n.status === 'online' ? '🟢' : '🔴';
          lines.push(`${icon} *${n.nodeId}* — ${n.model} (${n.latency || '?'}ms)`);
        }
        return sendMessage(chatId, lines.join('\n'), 'Markdown');
      } catch (e) {
        return sendMessage(chatId, `🔴 Proxy non joignable: ${e.message}`);
      }
    }

    case '/health': {
      try {
        const h = await proxyGet('/health');
        const al = await proxyGet('/autolearn/scores');
        const lines = ['📊 *Health détaillé*', ''];
        for (const n of (h.nodes || [])) {
          lines.push(`*${n.nodeId}*: ${n.status} | ${n.model} | ${n.latency || '?'}ms`);
        }
        if (al && al.ok !== false) {
          lines.push('', '*Autolearn Scores:*');
          const scores = al.scores || al;
          for (const [node, cats] of Object.entries(scores)) {
            if (typeof cats === 'object') {
              const avg = Object.values(cats).reduce((a, b) => a + (b || 0), 0) / Math.max(Object.values(cats).length, 1);
              lines.push(`  ${node}: avg ${avg.toFixed(1)}`);
            }
          }
        }
        return sendMessage(chatId, lines.join('\n'), 'Markdown');
      } catch (e) {
        return sendMessage(chatId, `🔴 Erreur: ${e.message}`);
      }
    }

    case '/consensus': {
      if (!args) return sendMessage(chatId, '⚠️ Usage: `/consensus <question>`', 'Markdown');
      await sendMessage(chatId, '🔄 Consensus en cours...');
      try {
        const res = await proxyChat(`[CONSENSUS] ${args}`, 'consensus');
        if (res.ok && res.data) {
          const d = res.data;
          const text = `🗳️ *Consensus*\n\n${d.text}\n\n_${d.model} via ${d.provider} (${d.turns} turns)_`;
          return sendMessage(chatId, text, 'Markdown');
        }
        return sendMessage(chatId, `⚠️ ${res.error || 'Erreur consensus'}`);
      } catch (e) {
        return sendMessage(chatId, `🔴 Erreur: ${e.message}`);
      }
    }

    case '/model': {
      const parts = (args || '').split(' ');
      const modelId = parts[0];
      const query = parts.slice(1).join(' ');
      if (!modelId || !query) return sendMessage(chatId, '⚠️ Usage: `/model M1 ta question`', 'Markdown');
      try {
        const res = await proxyChat(query, modelId.toLowerCase());
        if (res.ok && res.data) {
          return sendMessage(chatId, `*[${res.data.model}]*\n\n${res.data.text}`, 'Markdown');
        }
        return sendMessage(chatId, `⚠️ ${res.error || 'Erreur'}`);
      } catch (e) {
        return sendMessage(chatId, `🔴 Erreur: ${e.message}`);
      }
    }

    case '/stats':
      return sendMessage(chatId, [
        '*Bot Stats*',
        `Demarre: ${stats.started}`,
        `Messages recus: ${stats.messages_in}`,
        `Messages envoyes: ${stats.messages_out}`,
        `Erreurs: ${stats.errors}`,
      ].join('\n'), 'Markdown');

    case '/jarvis':
    case '/exec': {
      if (!args) return sendMessage(chatId, 'Usage: /jarvis <commande vocale>\nEx: /jarvis ouvre chrome');
      return handleJarvisCommand(chatId, args);
    }

    case '/improve': {
      const cycles = parseInt(args) || 10;
      return handleImproveLoop(chatId, cycles);
    }

    case '/gpu': {
      return handleGpuStatus(chatId);
    }

    case '/voice': {
      // Force a voice reply test
      const testText = args || 'JARVIS est operationnel. Tous les systemes fonctionnent.';
      const sent = await sendVoiceReply(chatId, testText);
      if (!sent) await sendMessage(chatId, 'Voice reply failed - check TTS script');
      return;
    }

    case '/scan': {
      const topN = parseInt(args) || 50;
      await sendMessage(chatId, `🎯 Sniper scan en cours (top ${topN} coins)... ~60s`);
      return handleSniperScan(chatId, topN);
    }

    case '/deepscan': {
      const finalN = parseInt(args) || 10;
      await sendMessage(chatId, `🔬 Deep scan 800+ coins en cours (3 passes, entonnoir → ${finalN} finaux)... ~3-5min`);
      return handleDeepScan(chatId, finalN);
    }

    case '/compare': {
      return handleSmartIntent(chatId, `compare ${args} usdt`, { intent: 'compare', handler: 'compare' });
    }

    case '/whales': {
      return handleSmartIntent(chatId, 'whale gros mouvement', { intent: 'whales', handler: 'whales' });
    }

    case '/news': {
      return handleSmartIntent(chatId, 'news actualites crypto', { intent: 'news', handler: 'news' });
    }

    case '/scanstats': {
      return handleScanStats(chatId);
    }

    case '/hot': {
      const limit = parseInt(args) || 10;
      return handleHotCoins(chatId, limit);
    }

    case '/sniper': {
      return handleSniperStatus(chatId);
    }

    case '/perf': {
      return handlePerformance(chatId);
    }

    case '/realtime': {
      return handleRealtimeStatus(chatId);
    }

    case '/loop': {
      return handleLoopStatus(chatId);
    }

    case '/backtest': {
      return handleBacktestResults(chatId);
    }

    case '/market': {
      return handleMarketSummary(chatId);
    }

    case '/superloop': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      const cycles = parseInt(args) || 100;
      return handleStartSuperLoop(chatId, cycles);
    }

    case '/killscanner': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      return handleKillScanner(chatId);
    }

    case '/menu':
    case '/dashboard': {
      return sendMenuKeyboard(chatId);
    }

    case '/signals': {
      return handleOpenSignals(chatId);
    }

    case '/alerton': {
      TRADING_ALERTS = true;
      try { fs.unlinkSync(ALERTS_FLAG_FILE); } catch {}
      await sendMessage(chatId, 'Alertes trading ACTIVEES. Vous recevrez les notifications TP/SL en temps reel.\n(Tous les scripts cowork respecteront ce choix)');
      if (VOICE_MODE) await sendVoiceReply(chatId, 'Les alertes trading sont maintenant activees.');
      return;
    }

    case '/alertoff': {
      TRADING_ALERTS = false;
      try { fs.writeFileSync(ALERTS_FLAG_FILE, new Date().toISOString()); } catch {}
      await sendMessage(chatId, 'Alertes trading DESACTIVEES. Plus de notifications TP/SL.\n(Tous les scripts cowork respecteront ce choix)');
      if (VOICE_MODE) await sendVoiceReply(chatId, 'Les alertes trading sont desactivees.');
      return;
    }

    case '/openclaw': {
      if (!args) return sendMessage(chatId, 'Usage: `/openclaw <question>`\nForce le passage par le proxy complet (Query Enhancer + reflexive chain).', 'Markdown');
      return handleOpenClawQuery(chatId, args);
    }

    default:
      return null; // pas une commande reconnue
  }
}

// ─── Sniper Scanner (via Python subprocess) ──────────────────────────────────

async function handleSniperScan(chatId, topN) {
  const scanScript = path.join(__dirname, '..', 'cowork', 'dev', 'sniper_scanner.py');
  try {
    const proc = exec(
      `python "${scanScript}" --once --top ${topN} --notify --chat-id=${chatId}`,
      { timeout: 180000, cwd: path.join(__dirname, '..') }
    );
    proc.stdout.on('data', d => log(`[scan] ${d.trim()}`));
    proc.stderr.on('data', d => logErr(`[scan] ${d.trim()}`));
    proc.on('close', (code) => {
      if (code !== 0) {
        sendMessage(chatId, `⚠️ Scan termine avec code ${code}`);
      }
    });
  } catch (e) {
    await sendMessage(chatId, `🔴 Erreur scan: ${e.message.slice(0, 200)}`);
  }
}

async function handleDeepScan(chatId, finalN) {
  const deepScript = path.join(__dirname, '..', 'cowork', 'dev', 'sniper_deep.py');
  try {
    const proc = exec(
      `python "${deepScript}" --top ${finalN} --notify --chat-id=${chatId}`,
      { timeout: 600000, cwd: path.join(__dirname, '..') }
    );
    proc.stdout.on('data', d => log(`[deepscan] ${d.trim()}`));
    proc.stderr.on('data', d => logErr(`[deepscan] ${d.trim()}`));
    proc.on('close', (code) => {
      if (code !== 0) {
        sendMessage(chatId, `Deep scan termine avec code ${code}`);
      }
    });
  } catch (e) {
    await sendMessage(chatId, `Erreur deep scan: ${e.message.slice(0, 200)}`);
  }
}

// ─── Scan Stats & Hot Coins ──────────────────────────────────────────────────

async function handleScanStats(chatId) {
  try {
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
scans = db.execute('SELECT COUNT(*) FROM scan_runs').fetchone()[0]
snaps = db.execute('SELECT COUNT(*) FROM coin_snapshots').fetchone()[0]
reg = db.execute('SELECT COUNT(*) FROM coin_registry').fetchone()[0]
sigs = db.execute('SELECT COUNT(*) FROM scan_signals').fetchone()[0]
last = db.execute('SELECT id,ts,coins_scanned,signals_found,breakouts,duration_s FROM scan_runs ORDER BY id DESC LIMIT 1').fetchone()
print(json.dumps({'scans':scans,'snapshots':snaps,'registry':reg,'signals':sigs,'last':{'id':last[0],'ts':last[1],'coins':last[2],'sigs':last[3],'breaks':last[4],'dur':last[5]} if last else None}))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    const l = d.last;
    const lines = [
      '📊 *Scanner Stats*',
      '',
      `Scans effectues: ${d.scans}`,
      `Snapshots: ${d.snapshots}`,
      `Coins registres: ${d.registry}`,
      `Signaux totaux: ${d.signals}`,
    ];
    if (l) {
      lines.push('', `*Dernier scan #${l.id}*`,
        `${l.ts}`,
        `${l.coins} coins | ${l.sigs} signaux | ${l.breaks} breakouts | ${l.dur.toFixed(1)}s`);
    }
    // Check if sniper is running
    try {
      const ps = execSync('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH', { encoding: 'utf-8', timeout: 5000 });
      const sniperRunning = ps.includes('sniper_scanner');
      lines.push('', sniperRunning ? '🟢 Scanner permanent ACTIF' : '🔴 Scanner permanent INACTIF');
    } catch (e) { /* ignore */ }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `🔴 Erreur: ${e.message.slice(0, 200)}`);
  }
}

async function handleHotCoins(chatId, limit) {
  try {
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
rows = db.execute('SELECT clean_name, scan_count, avg_score, best_score, best_direction, last_price, last_change FROM coin_registry WHERE best_score > 50 ORDER BY avg_score DESC LIMIT ?', (${limit},)).fetchall()
print(json.dumps([{'name':r[0],'scans':r[1],'avg':r[2],'best':r[3],'dir':r[4],'price':r[5],'chg':r[6]} for r in rows]))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const coins = JSON.parse(result.trim());
    if (!coins.length) return sendMessage(chatId, 'Pas encore de coins chauds (besoin de plus de scans).');
    const lines = ['🔥 *Top Coins Chauds*', ''];
    for (const c of coins) {
      const dir = c.dir === 'LONG' ? '🟢' : c.dir === 'SHORT' ? '🔴' : '⚪';
      lines.push(`${dir} *${c.name}* — avg ${c.avg.toFixed(0)} | best ${c.best.toFixed(0)} | ${c.scans} scans | ${c.chg > 0 ? '+' : ''}${c.chg.toFixed(1)}%`);
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `🔴 Erreur: ${e.message.slice(0, 200)}`);
  }
}

async function handleSniperStatus(chatId) {
  try {
    const ps = execSync('wmic process where "name=\'python.exe\'" get processid,commandline /FORMAT:CSV', { encoding: 'utf-8', timeout: 5000 });
    const sniperLine = ps.split('\n').find(l => l.includes('sniper_scanner'));
    if (sniperLine) {
      const pid = sniperLine.trim().split(',').pop();
      return sendMessage(chatId, `🟢 *Scanner Sniper ACTIF*\nPID: ${pid}\nMode: permanent, scan toutes les 60s\nFiltre: score >= 80, 3+ validations\n\nUtilisez /scanstats pour les stats detaillees.`, 'Markdown');
    } else {
      return sendMessage(chatId, '🔴 Scanner permanent INACTIF.\n\nPour le lancer: double-cliquez sur `JARVIS_SNIPER.bat`');
    }
  } catch (e) {
    return sendMessage(chatId, `⚠️ Cannot check: ${e.message.slice(0, 100)}`);
  }
}

async function handlePerformance(chatId) {
  try {
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
total = db.execute('SELECT COUNT(*) FROM signal_tracker').fetchone()[0]
if total == 0:
    print(json.dumps({'total':0}))
else:
    tp1 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1').fetchone()[0]
    tp2 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp2_hit=1').fetchone()[0]
    tp3 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp3_hit=1').fetchone()[0]
    sl = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1').fetchone()[0]
    opened = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE status=\\"OPEN\\"').fetchone()[0]
    avg_pnl = db.execute('SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != \\"OPEN\\"').fetchone()[0] or 0
    best = db.execute('SELECT symbol, pnl_pct, direction, score FROM signal_tracker ORDER BY pnl_pct DESC LIMIT 3').fetchall()
    worst = db.execute('SELECT symbol, pnl_pct, direction, score FROM signal_tracker ORDER BY pnl_pct ASC LIMIT 2').fetchall()
    print(json.dumps({'total':total,'tp1':tp1,'tp2':tp2,'tp3':tp3,'sl':sl,'open':opened,'avg_pnl':avg_pnl,'best':[{'s':r[0].replace('_USDT',''),'pnl':r[1],'d':r[2],'sc':r[3]} for r in best],'worst':[{'s':r[0].replace('_USDT',''),'pnl':r[1],'d':r[2],'sc':r[3]} for r in worst]}))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    if (d.total === 0) return sendMessage(chatId, 'Aucun signal tracke pour le moment. Le scanner sniper doit emettre des alertes.');
    const lines = [
      '📈 *Performance Signaux Sniper*',
      '',
      `Total signaux: ${d.total} (${d.open} ouverts)`,
      `TP1: ${d.tp1} (${(d.tp1*100/d.total).toFixed(0)}%)`,
      `TP2: ${d.tp2} (${(d.tp2*100/d.total).toFixed(0)}%)`,
      `TP3: ${d.tp3} (${(d.tp3*100/d.total).toFixed(0)}%)`,
      `SL: ${d.sl} (${(d.sl*100/d.total).toFixed(0)}%)`,
      `PnL moyen: ${d.avg_pnl > 0 ? '+' : ''}${d.avg_pnl.toFixed(2)}%`,
    ];
    if (d.best && d.best.length) {
      lines.push('', '*Meilleurs:*');
      for (const b of d.best) lines.push(`  ${b.s} ${b.d} +${b.pnl.toFixed(2)}% (score ${b.sc.toFixed(0)})`);
    }
    if (d.worst && d.worst.length) {
      lines.push('', '*Pires:*');
      for (const w of d.worst) lines.push(`  ${w.s} ${w.d} ${w.pnl.toFixed(2)}% (score ${w.sc.toFixed(0)})`);
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `🔴 Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── JARVIS Command Execution ─────────────────────────────────────────────────

const TURBO_ROOT = path.join(__dirname, '..');

async function handleJarvisCommand(chatId, voiceText) {
  try {
    // Match voice command via Python
    const matchResult = execSync(
      `python -c "import sys;sys.path.insert(0,'.');from src.commands import match_command;cmd,p,s=match_command(sys.stdin.read().strip());import json;print(json.dumps({'name':cmd.name if cmd else None,'action':cmd.action if cmd else None,'action_type':cmd.action_type if cmd else None,'params':p,'score':s,'desc':cmd.description if cmd else None}))"`,
      { timeout: 10000, encoding: 'utf-8', input: voiceText, cwd: TURBO_ROOT, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const match = JSON.parse(matchResult.trim());

    if (!match.name || match.score < 0.5) {
      // No match — fallback to cluster chat
      await sendMessage(chatId, `Commande non reconnue (score ${(match.score * 100).toFixed(0)}%). Dispatch au cluster...`);
      return null; // will fallback to cluster race
    }

    const msg = `JARVIS: ${match.desc || match.name}\nAction: ${match.action_type} → ${(match.action || '').slice(0, 100)}\nScore: ${(match.score * 100).toFixed(0)}%`;
    await sendMessage(chatId, msg);

    // Execute the command
    if (match.action_type === 'browser' && match.action) {
      execSync(`start "" "${match.action.replace('navigate:', '').replace('search:', 'https://www.google.com/search?q=')}"`, { timeout: 5000, shell: true });
      await sendVoiceReply(chatId, `${match.desc || match.name} execute`);
    } else if (match.action_type === 'app_open' && match.action) {
      execSync(`start "" "${match.action}"`, { timeout: 5000, shell: true });
      await sendVoiceReply(chatId, `Application ${match.name} lancee`);
    } else if (match.action_type === 'hotkey' && match.action) {
      // Use PowerShell to send keys
      const keys = match.action.replace(/\+/g, ',');
      execSync(`powershell -Command "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class KBD{[DllImport(\\\"user32.dll\\\")]public static extern void keybd_event(byte b,byte s,uint f,UIntPtr e);}'"`, { timeout: 5000 });
      await sendVoiceReply(chatId, `Raccourci ${match.action} execute`);
    } else if (match.action_type === 'powershell' && match.action) {
      const psResult = execSync(`powershell -NoProfile -Command "${match.action.replace(/"/g, '\\"')}"`, { timeout: 15000, encoding: 'utf-8' });
      const output = psResult.trim().slice(0, 500) || 'OK';
      await sendMessage(chatId, `Resultat:\n${output}`);
      await sendVoiceReply(chatId, `Commande executee: ${match.desc || match.name}`);
    } else {
      await sendMessage(chatId, `Type ${match.action_type} - execution manuelle requise`);
    }

    return true;
  } catch (e) {
    logErr('JARVIS command failed:', e.message);
    await sendMessage(chatId, `Erreur JARVIS: ${e.message.slice(0, 200)}`);
    return false;
  }
}

// ─── GPU Status ───────────────────────────────────────────────────────────────

async function handleGpuStatus(chatId) {
  try {
    const r = execSync(
      'nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader',
      { timeout: 5000, encoding: 'utf-8' }
    );
    const lines = ['*GPU Status*', ''];
    for (const line of r.trim().split('\n')) {
      const [idx, name, temp, used, total, util] = line.split(',').map(s => s.trim());
      const icon = parseInt(temp) > 75 ? '🔴' : parseInt(temp) > 60 ? '🟡' : '🟢';
      lines.push(`${icon} GPU${idx}: ${temp}C | ${used}/${total} MiB | ${util}% | ${name}`);
    }
    await sendMessage(chatId, lines.join('\n'), 'Markdown');
    await sendVoiceReply(chatId, `${lines.length - 2} GPU detectees. Temperature maximale ${Math.max(...r.trim().split('\n').map(l => parseInt(l.split(',')[2])))} degres`);
  } catch (e) {
    await sendMessage(chatId, `Erreur GPU: ${e.message.slice(0, 200)}`);
  }
}

// ─── Improve Loop (via Telegram) ──────────────────────────────────────────────

async function handleImproveLoop(chatId, cycles) {
  await sendMessage(chatId, `Lancement amelioration JARVIS: ${cycles} cycles...\nRapport toutes les 5 cycles.`);
  await sendVoiceReply(chatId, `Lancement de ${cycles} cycles d amelioration JARVIS. Je vous tiendrai informe de la progression.`);

  try {
    // Run improve loop in background (non-blocking)
    const proc = exec(
      `python "${path.join(TURBO_ROOT, 'scripts', 'improve_loop_100.py')}" --cycles ${cycles} --report-every 5`,
      { timeout: cycles * 120000, cwd: TURBO_ROOT }
    );
    proc.stdout.on('data', (data) => log(`[improve] ${data.trim()}`));
    proc.stderr.on('data', (data) => logErr(`[improve] ${data.trim()}`));
    proc.on('close', (code) => {
      log(`[improve] Process exited with code ${code}`);
      sendMessage(chatId, `Boucle amelioration terminee (code ${code}). Voir data/improve_loop_report.json`);
      sendVoiceReply(chatId, `La boucle d amelioration de ${cycles} cycles est terminee.`);
    });
  } catch (e) {
    await sendMessage(chatId, `Erreur improve loop: ${e.message.slice(0, 200)}`);
  }
}

// ─── Realtime Scanner Status ──────────────────────────────────────────────────

async function handleRealtimeStatus(chatId) {
  try {
    // Check if realtime scanner is running
    const ps = execSync('wmic process where "name=\'python.exe\'" get processid,commandline /FORMAT:CSV', { encoding: 'utf-8', timeout: 5000 });
    const rtLine = ps.split('\n').find(l => l.includes('sniper_scanner') && l.includes('--realtime'));

    // Get recent signal tracker data
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
total = db.execute('SELECT COUNT(*) FROM signal_tracker').fetchone()[0]
recent_open = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE status=\\"OPEN\\"').fetchone()[0]
tp1 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1').fetchone()[0]
sl = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1').fetchone()[0]
expired = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE status=\\"EXPIRED\\"').fetchone()[0]
# Last 5 signals
last5 = db.execute('SELECT symbol, direction, score, validations, status, pnl_pct FROM signal_tracker ORDER BY id DESC LIMIT 5').fetchall()
print(json.dumps({'total':total,'open':recent_open,'tp1':tp1,'sl':sl,'expired':expired,'last5':[{'s':r[0].replace('_USDT',''),'d':r[1],'sc':r[2],'v':r[3],'st':r[4],'pnl':r[5]} for r in last5]}))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());

    const lines = ['*Scanner Realtime*', ''];
    if (rtLine) {
      const pid = rtLine.trim().split(',').pop();
      lines.push(`Status: ACTIF (PID ${pid})`);
      lines.push('Mode: 30s cycles, 18 indicateurs');
      lines.push(`Min move: 0.4%, score min: 75`);
    } else {
      lines.push('Status: INACTIF');
    }
    lines.push('');
    lines.push(`Signaux: ${d.total} total | ${d.open} ouverts | ${d.expired} expires`);
    lines.push(`TP1: ${d.tp1} (${d.total > 0 ? (d.tp1*100/d.total).toFixed(0) : 0}%) | SL: ${d.sl} (${d.total > 0 ? (d.sl*100/d.total).toFixed(0) : 0}%)`);

    if (d.last5 && d.last5.length) {
      lines.push('', '*Derniers signaux:*');
      for (const s of d.last5) {
        const icon = s.st === 'TP1_HIT' || s.st === 'TP2_HIT' || s.st === 'TP3_HIT' ? '+' : s.st === 'SL_HIT' ? '-' : '?';
        lines.push(`  ${s.d === 'LONG' ? 'L' : 'S'} ${s.s} ${s.sc.toFixed(0)}pts ${s.v}v → ${s.st} ${s.pnl ? (s.pnl > 0 ? '+' : '') + s.pnl.toFixed(2) + '%' : ''}`);
      }
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Super Loop Status ──────────────────────────────────────────────────────

async function handleLoopStatus(chatId) {
  try {
    const ps = execSync('wmic process where "name=\'python.exe\'" get processid,commandline /FORMAT:CSV', { encoding: 'utf-8', timeout: 5000 });
    const loopLine = ps.split('\n').find(l => l.includes('super_loop') || l.includes('improve_loop'));

    let d;
    try {
      const result = execSync(`python -c "
import sqlite3, json, os
db_path = 'data/super_loop.db'
if not os.path.exists(db_path):
    print(json.dumps({'exists': False}))
else:
    db = sqlite3.connect(db_path)
    try:
        cycles = db.execute('SELECT COUNT(*) FROM loop_cycles').fetchone()[0]
    except: cycles = 0
    try:
        issues = db.execute('SELECT COUNT(*) FROM discovered_issues WHERE fix_applied=0').fetchone()[0]
    except: issues = 0
    try:
        suggestions = db.execute('SELECT COUNT(*) FROM code_suggestions WHERE applied=0').fetchone()[0]
    except: suggestions = 0
    try:
        last = db.execute('SELECT cycle, domain, duration_s, ts FROM loop_cycles ORDER BY id DESC LIMIT 1').fetchone()
    except: last = None
    try:
        domains = db.execute('SELECT domain, COUNT(*), AVG(duration_s) FROM loop_cycles GROUP BY domain').fetchall()
    except: domains = []
    print(json.dumps({'exists':True,'cycles':cycles,'issues':issues,'suggestions':suggestions,
        'last':{'cycle':last[0],'domain':last[1],'dur':last[2],'ts':last[3]} if last else None,
        'domains':[{'d':r[0],'count':r[1],'avg_dur':r[2]} for r in domains]}))
    db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
      d = JSON.parse(result.trim());
    } catch (parseErr) {
      d = { exists: false };
    }

    const lines = ['*Super Loop Status*', ''];
    if (loopLine) {
      const pid = loopLine.trim().split(',').pop();
      lines.push(`Status: ACTIF (PID ${pid})`);
    } else {
      lines.push('Status: INACTIF');
    }

    if (!d.exists) {
      lines.push('DB: pas encore creee');
    } else {
      lines.push(`Cycles: ${d.cycles}`);
      lines.push(`Issues non resolues: ${d.issues}`);
      lines.push(`Suggestions code: ${d.suggestions}`);
      if (d.last) {
        lines.push('', `Dernier: cycle #${d.last.cycle} [${d.last.domain}] ${d.last.dur.toFixed(1)}s`);
        lines.push(`  ${d.last.ts}`);
      }
      if (d.domains && d.domains.length) {
        lines.push('', '*Par domaine:*');
        for (const dm of d.domains) {
          lines.push(`  ${dm.d}: ${dm.count} cycles, avg ${dm.avg_dur.toFixed(1)}s`);
        }
      }
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Backtest Results ────────────────────────────────────────────────────────

async function handleBacktestResults(chatId) {
  try {
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
# Count signals with backtest patterns
total = db.execute('SELECT COUNT(*) FROM scan_signals').fetchone()[0]
bt_ok = db.execute('SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE \\"%%BACKTEST_OK%%\\"').fetchone()[0]
bt_warn = db.execute('SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE \\"%%BACKTEST_WARN%%\\"').fetchone()[0]
# Compare TP1 hit rate for backtest-validated vs non-validated
bt_tp1 = db.execute('SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern LIKE \\"%%BACKTEST_OK%%\\" AND st.tp1_hit=1').fetchone()[0]
bt_total_t = db.execute('SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern LIKE \\"%%BACKTEST_OK%%\\"').fetchone()[0]
nobt_tp1 = db.execute('SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern NOT LIKE \\"%%BACKTEST%%\\" AND st.tp1_hit=1').fetchone()[0]
nobt_total = db.execute('SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern NOT LIKE \\"%%BACKTEST%%\\"').fetchone()[0]
# VWAP stats
vwap = db.execute('SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE \\"%%VWAP%%\\"').fetchone()[0]
# Streak stats
streak = db.execute('SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE \\"%%STREAK%%\\" OR pattern LIKE \\"%%streak%%\\"').fetchone()[0]
print(json.dumps({'total':total,'bt_ok':bt_ok,'bt_warn':bt_warn,'bt_tp1':bt_tp1,'bt_total_t':bt_total_t,'nobt_tp1':nobt_tp1,'nobt_total':nobt_total,'vwap':vwap,'streak':streak}))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    const btRate = d.bt_total_t > 0 ? (d.bt_tp1 * 100 / d.bt_total_t).toFixed(1) : 'N/A';
    const nobtRate = d.nobt_total > 0 ? (d.nobt_tp1 * 100 / d.nobt_total).toFixed(1) : 'N/A';
    const lines = [
      '*Resultats Backtest & Indicateurs*', '',
      `Total signaux: ${d.total}`,
      `Backtest OK: ${d.bt_ok} | Backtest WARN: ${d.bt_warn}`,
      `VWAP valides: ${d.vwap} | Streaks detectes: ${d.streak}`, '',
      '*TP1 hit rate comparison:*',
      `  Avec backtest OK: ${btRate}% (${d.bt_tp1}/${d.bt_total_t})`,
      `  Sans backtest: ${nobtRate}% (${d.nobt_tp1}/${d.nobt_total})`,
    ];
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Market Summary ─────────────────────────────────────────────────────────

async function handleMarketSummary(chatId) {
  try {
    const result = execSync(`python -c "
import sqlite3, json, urllib.request
# Fetch current tickers
data = json.loads(urllib.request.urlopen('https://contract.mexc.com/api/v1/contract/ticker', timeout=10).read().decode())
tickers = [t for t in data.get('data', []) if t.get('symbol', '').endswith('_USDT')]
# Sort by 24h change
tickers.sort(key=lambda t: abs(float(t.get('riseFallRate', 0))), reverse=True)
top_movers = tickers[:10]
# Market stats
up = sum(1 for t in tickers if float(t.get('riseFallRate', 0)) > 0)
down = len(tickers) - up
avg_change = sum(float(t.get('riseFallRate', 0)) for t in tickers) / len(tickers) * 100 if tickers else 0
# BTC price
btc = next((t for t in tickers if t['symbol'] == 'BTC_USDT'), None)
btc_price = float(btc.get('lastPrice', 0)) if btc else 0
btc_change = float(btc.get('riseFallRate', 0)) * 100 if btc else 0
result = {
    'total': len(tickers), 'up': up, 'down': down, 'avg_change': avg_change,
    'btc_price': btc_price, 'btc_change': btc_change,
    'movers': [{'s': t['symbol'].replace('_USDT',''), 'p': float(t.get('lastPrice',0)), 'c': float(t.get('riseFallRate',0))*100} for t in top_movers]
}
print(json.dumps(result))
"`, { timeout: 15000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    const trend = d.up > d.down ? 'HAUSSIER' : 'BAISSIER';
    const lines = [
      `*Marche Crypto — Resume*`, '',
      `BTC: $${d.btc_price.toFixed(0)} (${d.btc_change > 0 ? '+' : ''}${d.btc_change.toFixed(1)}%)`,
      `Tendance: ${trend} (${d.up} en hausse / ${d.down} en baisse)`,
      `Change moyen 24h: ${d.avg_change > 0 ? '+' : ''}${d.avg_change.toFixed(2)}%`,
      `Total paires: ${d.total}`, '',
      '*Top movers 24h:*',
    ];
    for (const m of d.movers) {
      const icon = m.c > 0 ? '+' : '';
      lines.push(`  ${m.s}: ${icon}${m.c.toFixed(1)}%`);
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Start Super Loop from Telegram ─────────────────────────────────────────

async function handleStartSuperLoop(chatId, cycles) {
  await sendMessage(chatId, `Lancement Super Loop: ${cycles} cycles, 5 domaines, 6 noeuds cluster...`);
  await sendVoiceReply(chatId, `Lancement du super loop, ${cycles} cycles d amelioration continue avec tout le cluster.`);
  try {
    const proc = exec(
      `python "${path.join(TURBO_ROOT, 'cowork', 'dev', 'jarvis_super_loop.py')}" --cycles ${cycles} --interval 120 --notify`,
      { timeout: cycles * 180000, cwd: TURBO_ROOT }
    );
    proc.stdout.on('data', d => log(`[superloop] ${d.trim()}`));
    proc.stderr.on('data', d => logErr(`[superloop] ${d.trim()}`));
    proc.on('close', (code) => {
      sendMessage(chatId, `Super Loop termine (code ${code}). ${cycles} cycles executes.`);
      sendVoiceReply(chatId, `Le super loop de ${cycles} cycles est termine.`);
    });
  } catch (e) {
    await sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Kill Scanner from Telegram ─────────────────────────────────────────────

async function handleKillScanner(chatId) {
  try {
    const ps = execSync('wmic process where "name=\'python.exe\'" get processid,commandline /FORMAT:CSV', { encoding: 'utf-8', timeout: 5000 });
    const scannerLines = ps.split('\n').filter(l => l.includes('sniper_scanner') && l.includes('--realtime'));
    if (!scannerLines.length) {
      return sendMessage(chatId, 'Aucun scanner REALTIME en cours.');
    }
    for (const line of scannerLines) {
      const pid = line.trim().split(',').pop();
      try {
        execSync(`taskkill /PID ${pid} /F`, { timeout: 5000 });
        await sendMessage(chatId, `Scanner PID ${pid} arrete.`);
      } catch (e) {
        await sendMessage(chatId, `Erreur arret PID ${pid}: ${e.message.slice(0, 100)}`);
      }
    }
    await sendVoiceReply(chatId, 'Scanner temps reel arrete.');
  } catch (e) {
    return sendMessage(chatId, `Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── Open Signals (via proxy /signals endpoint) ──────────────────────────────

async function handleOpenSignals(chatId) {
  try {
    const res = await proxyGet('/signals');
    if (!res.ok) throw new Error(res.error || 'signals endpoint error');
    const d = res.data;
    const lines = ['*Signaux en Temps Reel*', ''];
    lines.push(`Total: ${d.total} | Ouverts: ${d.open} | Expires: ${d.expired}`);
    lines.push(`TP1: ${d.tp1} | TP2: ${d.tp2} | SL: ${d.sl}`);
    lines.push(`PnL moyen: ${d.avg_pnl > 0 ? '+' : ''}${d.avg_pnl.toFixed(2)}%`);
    lines.push(`Alertes: ${TRADING_ALERTS ? 'ACTIVES' : 'DESACTIVEES'}`);

    if (d.open_signals && d.open_signals.length) {
      lines.push('', '*Signaux ouverts:*');
      for (const s of d.open_signals) {
        const sym = s.s.replace('_USDT', '');
        const dir = s.d === 'LONG' ? 'L' : 'S';
        lines.push(`  ${dir} *${sym}* ${s.sc.toFixed(0)}pts ${s.v}v | Entry: ${s.entry} | TP1: ${s.tp1} | SL: ${s.sl}`);
      }
    } else {
      lines.push('', 'Aucun signal ouvert.');
    }

    if (d.recent && d.recent.length) {
      lines.push('', '*Derniers signaux:*');
      for (const r of d.recent) {
        const sym = r.s.replace('_USDT', '');
        const icon = r.st.includes('TP') ? '+' : r.st === 'SL_HIT' ? '-' : '?';
        lines.push(`  ${icon} ${sym} ${r.d} ${r.sc.toFixed(0)}pts -> ${r.st} ${r.pnl ? (r.pnl > 0 ? '+' : '') + r.pnl.toFixed(2) + '%' : ''}`);
      }
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return handleRealtimeStatus(chatId);
  }
}

// ─── OpenClaw Query (force proxy reflexive chain) ──────────────────────────────

async function handleOpenClawQuery(chatId, question) {
  await sendMessage(chatId, 'OpenClaw reflexive chain en cours...');
  try {
    // Build enriched prompt with conversation memory + context
    const memMsgs = getMemoryMessages(chatId);
    const hour = new Date().getHours();
    let enriched = `[Telegram, ${hour}h, MEXC Futures 10x]\n`;
    if (memMsgs.length > 0) {
      const ctx = memMsgs.slice(-5).map(m => `${m.role}: ${m.content}`).join('\n');
      enriched += `Contexte:\n${ctx}\n\n`;
    }
    enriched += `Question: ${question}`;

    const res = await proxyChat(enriched, 'main');
    if (res.ok && res.data) {
      const d = res.data;
      const mode = d.mode || 'simple';
      const turns = d.turns || 1;
      let chainInfo = '';
      if (d.chain && d.chain.length) {
        chainInfo = '\n_Chain: ' + d.chain.map(c => `${c.node}(${c.role},${c.duration_ms}ms)`).join(' -> ') + '_';
      }
      const tools = d.tools_used && d.tools_used.length ? `\n_Tools: ${d.tools_used.map(t => t.tool).join(', ')}_` : '';
      const attr = `\n\n_[${d.model}] mode=${mode} turns=${turns}_${tools}${chainInfo}`;

      addToMemory(chatId, 'user', question);
      addToMemory(chatId, 'assistant', d.text.slice(0, 500));

      // Smart voice: skip for code/JSON
      const skipVoice = /```|^\s*[\[{]/.test(d.text) || d.text.length > 1500;
      if (VOICE_MODE && !skipVoice) await sendVoiceReply(chatId, d.text);
      return sendMessage(chatId, d.text + attr, 'Markdown');
    }
    return sendMessage(chatId, `Erreur: ${res.error || 'reponse vide'}`);
  } catch (e) {
    return sendMessage(chatId, `OpenClaw offline: ${e.message.slice(0, 200)}`);
  }
}

// ─── Smart Router — Detecte l'intent et route vers le bon outil ─────────────

const INTENT_PATTERNS = [
  // Scan / deep scan
  { intent: 'scan',    rx: /\b(scan|scanner|deepscan|analyse[rz]?\s+(tous|all|march[eé]|coin))/i, handler: 'scan' },
  // Analyse coin specifique
  { intent: 'analyze', rx: /\b(analyse|analyze|tp\??|entr[eé]e|breakout)\b.*\b([a-z]{2,10})\s*\/?\s*usdt\b/i, handler: 'analyze' },
  { intent: 'analyze', rx: /\b(btc|eth|sol|sui|xrp|ada|doge|pepe|link|avax|chz|river|bnb|dot|shib|wif|arb|matic|apt|op|inj|fet|ondo|render|trump)\s*\/?\s*usdt?\b/i, handler: 'analyze' },
  // Comparaison multi-coins
  { intent: 'compare', rx: /\b(compare[rz]?|vs|versus|mieux|meilleur)\b.*\b([a-z]{2,10})\b.*\b([a-z]{2,10})\b/i, handler: 'compare' },
  // Funding / liquidation
  { intent: 'funding', rx: /\b(funding|taux\s+de\s+financement|liquidation|open\s*interest|oi\b|liq)/i, handler: 'funding' },
  // Whales / gros mouvements
  { intent: 'whales',  rx: /\b(whale|baleine|gros\s+(mouvement|volume|ordre)|accumulation|distribution)/i, handler: 'whales' },
  // Trading: positions, PnL, strategies
  { intent: 'trading', rx: /\b(trading|position|portfolio|pnl|profit|perte|levier|futures|mexc|long|short|strat[eé]gie|risk|risque|taille|size)/i, handler: 'trading' },
  // Systeme: GPU, cluster, monitoring
  { intent: 'system',  rx: /\b(gpu|vram|temp[eé]rature|cpu|ram|disque|cluster|noeud|node|health|service|process|nvidia)/i, handler: 'system' },
  // News / actualites
  { intent: 'news',    rx: /\b(news|actualit[eé]|info|rumeur|annonce|r[eé]gulation|sec\b|etf\b)/i, handler: 'news' },
];

function detectIntent(text) {
  for (const p of INTENT_PATTERNS) {
    if (p.rx.test(text)) return p;
  }
  return null;
}

// ─── Conversation Memory per chat ───────────────────────────────────────────

const chatMemory = new Map();
const MEMORY_MAX = 10;

function addToMemory(chatId, role, content) {
  const key = String(chatId);
  if (!chatMemory.has(key)) chatMemory.set(key, []);
  const mem = chatMemory.get(key);
  mem.push({ role, content: content.slice(0, 500), ts: Date.now() });
  if (mem.length > MEMORY_MAX) mem.shift();
}

function getMemoryMessages(chatId) {
  return chatMemory.get(String(chatId)) || [];
}

// ─── Smart handlers per intent ──────────────────────────────────────────────

async function handleSmartIntent(chatId, text, intent) {
  const cwd = path.join(__dirname, '..');

  switch (intent.handler) {
    case 'scan': {
      const match = text.match(/(\d+)\s*(coin|paire)/i);
      const n = match ? parseInt(match[1]) : 10;
      if (text.match(/deep|all|tous|800|750|complet/i)) {
        await sendMessage(chatId, `Deep scan entonnoir 800+ coins -> ${n} finaux... ~3min`);
        return handleDeepScan(chatId, n);
      }
      await sendMessage(chatId, `Scan top ${n} coins...`);
      return handleSniperScan(chatId, n);
    }

    case 'analyze': {
      const coinMatch = text.match(/\b([A-Z]{2,10})\s*\/?\s*USDT\b/i)
        || text.match(/\b(btc|eth|sol|sui|xrp|ada|doge|pepe|link|avax|chz|river|bnb|dot|shib|wif|arb|matic|apt|op|inj|fet|ondo|render|trump)\b/i);
      if (coinMatch) {
        const coin = coinMatch[1].toUpperCase();
        await sendMessage(chatId, `Analyse ${coin}/USDT en cours...`);
        return new Promise((resolve) => {
          const script = `
import sys; sys.stdout.reconfigure(encoding='utf-8',errors='replace'); sys.path.insert(0,'cowork/dev')
from sniper_scanner import fetch_klines, fetch_all_tickers, analyze_coin, format_signal
tickers = fetch_all_tickers()
t = next((t for t in tickers if t.get('symbol')=='${coin}_USDT'),{})
k = fetch_klines('${coin}_USDT', interval='Min15', limit=200)
if k:
    sig = analyze_coin('${coin}_USDT', k, t, None)
    if sig: print(format_signal(sig, 1))
    else: print('Pas de signal fort pour ${coin}/USDT')
else: print('${coin}/USDT non trouve sur MEXC Futures')
`;
          exec(`python -c "${script.replace(/"/g, '\\"')}"`, { timeout: 30000, cwd }, (err, stdout) => {
            const result = stdout ? stdout.trim() : `Erreur analyse ${coin}`;
            // Send text + action keyboard
            const keyboard = {
              inline_keyboard: [
                [
                  { text: `Scan ${coin}`, callback_data: `analyze_${coin}` },
                  { text: 'Deep Scan', callback_data: 'cmd_scan' },
                ],
                [
                  { text: 'Hot Coins', callback_data: 'cmd_hot' },
                  { text: 'Menu', callback_data: 'cmd_menu' },
                ],
              ]
            };
            telegramAPI('sendMessage', {
              chat_id: chatId,
              text: result,
              reply_markup: JSON.stringify(keyboard),
            });
            if (VOICE_MODE) sendVoiceReply(chatId, result);
            resolve(true);
          });
        });
      }
      return null;
    }

    case 'compare': {
      // Extract two coins from text
      const coins = [...text.matchAll(/\b([a-z]{2,10})\b/gi)]
        .map(m => m[1].toUpperCase())
        .filter(c => c !== 'VS' && c !== 'USDT' && c !== 'ET' && c !== 'OU' && c.length >= 2);
      if (coins.length >= 2) {
        const [a, b] = [coins[0], coins[1]];
        await sendMessage(chatId, `Comparaison ${a} vs ${b} en cours...`);
        return new Promise((resolve) => {
          const script = `
import sys; sys.stdout.reconfigure(encoding='utf-8',errors='replace'); sys.path.insert(0,'cowork/dev')
from sniper_scanner import fetch_klines, fetch_all_tickers, analyze_coin, format_signal
tickers = fetch_all_tickers()
results = []
for coin in ['${a}','${b}']:
    t = next((t for t in tickers if t.get('symbol')==coin+'_USDT'),{})
    k = fetch_klines(coin+'_USDT', interval='Min15', limit=200)
    if k:
        sig = analyze_coin(coin+'_USDT', k, t, None)
        if sig: results.append(sig)
if len(results)==2:
    best = results[0] if results[0]['score']>=results[1]['score'] else results[1]
    for i,sig in enumerate(results):
        print(format_signal(sig, i+1))
        print()
    winner = results[0]['symbol'].replace('_USDT','') if results[0]['score']>=results[1]['score'] else results[1]['symbol'].replace('_USDT','')
    print(f"Verdict: {winner} est plus fort (score {best['score']}/100)")
elif len(results)==1:
    print(format_signal(results[0], 1))
    print("L'autre coin n'a pas de signal assez fort")
else:
    print('Aucun signal fort pour ces deux coins')
`;
          exec(`python -c "${script.replace(/"/g, '\\"')}"`, { timeout: 45000, cwd }, (err, stdout) => {
            const result = stdout ? stdout.trim() : `Erreur comparaison ${a} vs ${b}`;
            sendMessage(chatId, result);
            if (VOICE_MODE) sendVoiceReply(chatId, result);
            resolve(true);
          });
        });
      }
      return null;
    }

    case 'trading': {
      // Routing intelligent: question trading → cluster avec prompt enrichi trading
      const tradingPrompt = `CONTEXTE TRADING MEXC Futures:
- Levier 10x | Paires USDT | Size 10 USDT par position
- Params: TP1 0.4%, TP2 0.8%, TP3 1.5% | SL 0.25%
- Score minimum signal: 70/100

QUESTION UTILISATEUR: ${text}

Reponds avec des donnees concretes: prix, pourcentages, niveaux, R:R.`;
      log('  INTENT trading → cluster race avec prompt enrichi');
      const result = await clusterRace(tradingPrompt);
      if (result) {
        const attr = `\n\n_[${result.node}/${result.model} ${result.latency}ms]_`;
        await sendMessage(chatId, result.text + attr, 'Markdown');
        if (VOICE_MODE && result.text.length < 1000) sendVoiceReply(chatId, result.text);
        return true;
      }
      return null; // fallback to generic
    }

    case 'system': {
      // GPU + cluster status rapide
      await sendMessage(chatId, 'Diagnostic systeme en cours...');
      return new Promise((resolve) => {
        exec('nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits', { timeout: 10000 }, (err, stdout) => {
          if (err || !stdout) {
            sendMessage(chatId, 'nvidia-smi indisponible');
            resolve(true);
            return;
          }
          const gpus = stdout.trim().split('\n').map((line, i) => {
            const [name, temp, util, memUsed, memTotal] = line.split(',').map(s => s.trim());
            return `GPU${i}: ${name} | ${temp}C | ${util}% | ${memUsed}/${memTotal} MB`;
          });
          const msg = `*Systeme*\n\`\`\`\n${gpus.join('\n')}\`\`\``;
          const keyboard = {
            inline_keyboard: [[
              { text: 'Refresh', callback_data: 'cmd_gpu' },
              { text: 'Cluster', callback_data: 'cmd_realtime' },
              { text: 'Menu', callback_data: 'cmd_menu' },
            ]]
          };
          telegramAPI('sendMessage', {
            chat_id: chatId, text: msg, parse_mode: 'Markdown',
            reply_markup: JSON.stringify(keyboard),
          });
          if (VOICE_MODE) sendVoiceReply(chatId, `${gpus.length} GPU detectees, temperature maximale ${Math.max(...stdout.trim().split('\n').map(l => parseInt(l.split(',')[1])))} degres`);
          resolve(true);
        });
      });
    }

    case 'funding': {
      // Funding rates via cluster (web search capable nodes)
      const fundingPrompt = `Recherche les taux de funding actuels sur MEXC Futures pour les top 10 coins (BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK).
Indique: coin, funding rate (%), next funding time, direction implicite (positif=shorts paient, negatif=longs paient).
Reponds en francais, format tableau concis.`;
      log('  INTENT funding → cluster race');
      const result = await clusterRace(fundingPrompt);
      if (result) {
        await sendMessage(chatId, result.text + `\n\n_[${result.node} ${result.latency}ms]_`, 'Markdown');
        return true;
      }
      return null;
    }

    case 'whales': {
      // Whale detection via DB hot coins + cluster enrichment
      await sendMessage(chatId, 'Detection gros mouvements...');
      return new Promise((resolve) => {
        const script = `
import sys,sqlite3; sys.stdout.reconfigure(encoding='utf-8',errors='replace')
db = sqlite3.connect('data/sniper_scan.db')
rows = db.execute("SELECT symbol, last_price, avg_score, scan_count, best_score, last_direction FROM coin_registry WHERE avg_score>60 ORDER BY avg_score DESC LIMIT 15").fetchall()
db.close()
if rows:
    print("*Top mouvements detectes:*")
    for r in rows:
        sym = r[0].replace('_USDT','')
        print(f"  {sym}: score {r[2]:.0f} (best {r[4]}) | {r[5]} | {r[3]} scans")
else:
    print("Aucun mouvement majeur detecte")
`;
        exec(`python -c "${script.replace(/"/g, '\\"')}"`, { timeout: 15000, cwd }, (err, stdout) => {
          const result = stdout ? stdout.trim() : 'Erreur detection whales';
          sendMessage(chatId, result, 'Markdown');
          resolve(true);
        });
      });
    }

    case 'news': {
      // News via web-capable cluster node (minimax has web search)
      const newsPrompt = `Donne les 5 dernieres actualites crypto importantes d'aujourd'hui.
Pour chaque: titre, impact marche (haussier/baissier/neutre), coins concernes.
Format concis, francais uniquement.`;
      log('  INTENT news → cluster race (web)');
      const result = await clusterRace(newsPrompt);
      if (result) {
        await sendMessage(chatId, result.text + `\n\n_[${result.node} ${result.latency}ms]_`, 'Markdown');
        return true;
      }
      return null;
    }

    default:
      return null;
  }
}

// Helper: envoyer un message avec inline keyboard d'actions
async function sendWithActions(chatId, text, actions) {
  const rows = [];
  for (let i = 0; i < actions.length; i += 3) {
    rows.push(actions.slice(i, i + 3).map(a => ({ text: a.label, callback_data: a.cmd })));
  }
  await telegramAPI('sendMessage', {
    chat_id: chatId,
    text,
    parse_mode: 'Markdown',
    reply_markup: JSON.stringify({ inline_keyboard: rows }),
  });
}

// ─── Cluster Race — Query all nodes in parallel, first good response wins ─────

function buildSystemPrompt() {
  const hour = new Date().getHours();
  const period = hour < 6 ? 'nuit' : hour < 12 ? 'matin' : hour < 18 ? 'apres-midi' : 'soir';
  return `Tu es JARVIS, assistant IA expert en trading crypto et systemes.

REGLES ABSOLUES:
1. Reponds TOUJOURS en francais. Zero anglais.
2. Concis et direct. Max 400 mots. Utilise le Markdown.
3. Trading: donne Entry, TP1/2/3, SL, ratio R:R avec prix exacts.
4. Utilise des donnees concretes (prix, pourcentages, niveaux).
5. Config trading: MEXC Futures 10x, size 10 USDT, TP 0.4-1.5%, SL 0.25%.
6. Suggere des actions concretes (ex: /scan, /deepscan, /hot).

CONTEXTE: Il est ${hour}h (${period}). Repondre via Telegram (max 4000 chars).`;
}

function queryNode(node, prompt) {
  const sysPrompt = buildSystemPrompt();
  return new Promise((resolve, reject) => {
    const start = Date.now();
    let body, headers;
    if (node.isOllama) {
      body = JSON.stringify({
        model: node.model,
        messages: [{ role: 'system', content: sysPrompt }, { role: 'user', content: prompt }],
        stream: false, think: false
      });
      headers = { 'Content-Type': 'application/json' };
    } else {
      // LM Studio (OpenAI-compatible)
      body = JSON.stringify({
        model: node.model,
        messages: [{ role: 'system', content: sysPrompt }, { role: 'user', content: '/nothink\n' + prompt }],
        temperature: 0.2, max_tokens: 1024, stream: false
      });
      headers = { 'Content-Type': 'application/json' };
    }
    httpRequest(node.url, { method: 'POST', headers, timeout: 60000 }, body)
      .then(res => {
        const d = JSON.parse(res.body);
        let text = '';
        if (node.isOllama) {
          text = (d.message && d.message.content) || '';
        } else {
          text = (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content) || '';
        }
        // Clean thinking tokens
        text = text.replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/^\/no_?think\s*/i, '').trim();
        if (!text || text.length < 5) return reject(new Error('empty response'));
        resolve({ text, node: node.id, model: node.model, latency: Date.now() - start });
      })
      .catch(reject);
  });
}

async function clusterRace(prompt) {
  // Launch all nodes in parallel, first good response wins
  const promises = CLUSTER_NODES.map(node =>
    queryNode(node, prompt).catch(e => {
      log(`  [${node.id}] failed: ${e.message}`);
      return null;
    })
  );
  // Race: return first non-null result
  return new Promise((resolve) => {
    let resolved = false;
    let results = [];
    let done = 0;
    promises.forEach((p, i) => {
      p.then(r => {
        done++;
        if (r && !resolved) {
          resolved = true;
          log(`  WINNER: [${r.node}] ${r.latency}ms — ${r.text.slice(0, 60)}...`);
          resolve(r);
        }
        if (r) results.push(r);
        if (done === promises.length && !resolved) {
          // All failed — try proxy fallback
          resolve(null);
        }
      });
    });
    // Safety timeout
    setTimeout(() => { if (!resolved) { resolved = true; resolve(null); } }, 65000);
  });
}

// ─── Voice: download Telegram voice → transcribe via Whisper ──────────────────

async function transcribeVoice(fileId) {
  // 1. Get file path from Telegram
  const fileInfo = await telegramAPI('getFile', { file_id: fileId });
  const filePath = fileInfo.file_path;
  const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${filePath}`;

  // 2. Download to temp
  const tmpOgg = path.join(os.tmpdir(), `tg_voice_${Date.now()}.ogg`);
  const tmpWav = tmpOgg.replace('.ogg', '.wav');

  await new Promise((resolve, reject) => {
    const file = require('fs').createWriteStream(tmpOgg);
    https.get(fileUrl, (res) => { res.pipe(file); file.on('finish', () => { file.close(); resolve(); }); })
      .on('error', reject);
  });

  // 3. Convert OGG → WAV via ffmpeg
  try {
    execSync(`ffmpeg -y -i "${tmpOgg}" -ar 16000 -ac 1 "${tmpWav}"`, { timeout: 15000, stdio: 'pipe' });
  } catch (e) {
    try { fs.unlinkSync(tmpOgg); } catch (_) {}
    return '[Erreur conversion audio]';
  }

  // 4. Transcribe via python_ws Whisper endpoint or local faster-whisper
  let text = '';
  try {
    const result = execSync(
      `faster-whisper "${tmpWav}" --model tiny --language fr --output_format txt`,
      { timeout: 15000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    ).trim();
    text = result;
  } catch (e) {
    // Fallback: try Groq API or just return error
    text = '[Transcription indisponible]';
  }

  // Cleanup
  try { fs.unlinkSync(tmpOgg); } catch (_) {}
  try { fs.unlinkSync(tmpWav); } catch (_) {}

  return text || '[Audio vide]';
}

// ─── Voice: send response as Telegram voice message ──────────────────────────

const TTS_STDIN_SCRIPT = path.join(__dirname, '..', 'scripts', 'tts_stdin.py');

async function sendVoiceReply(chatId, text) {
  try {
    const cleanText = text.replace(/[\r\n]+/g, ' ').slice(0, 2000);
    const result = execSync(
      `python "${TTS_STDIN_SCRIPT}" --telegram --chat-id=${chatId}`,
      { timeout: 30000, encoding: 'utf-8', input: cleanText, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const data = JSON.parse(result.trim());
    if (data.ok) {
      log(`  VOICE sent: ${data.duration || '?'}s OGG via DeniseNeural`);
      stats.messages_out++;
      return true;
    } else {
      logErr('TTS failed:', data.error || 'unknown');
    }
  } catch (e) {
    logErr('sendVoiceReply failed:', e.message);
  }
  return false;
}

// ─── Traitement des messages ──────────────────────────────────────────────────

async function processMessage(msg) {
  if (!msg) return;

  const chatId = msg.chat.id;
  const from = msg.from ? (msg.from.username || msg.from.first_name || 'unknown') : 'unknown';

  // RBAC: identifier admin vs user
  const isAdmin = String(chatId) === String(CHAT_ID);

  // Rate limit pour non-admins
  if (!isAdmin && !checkRateLimit(String(chatId))) {
    log(`[RATE_LIMIT] ${from} (${chatId}) — bloque`);
    return sendMessage(chatId, '⚠️ Trop de messages. Reessayez dans 1 minute.');
  }

  // ── Handle voice messages (NEW) ──
  let text = '';
  let isVoice = false;
  if (msg.voice || msg.audio) {
    isVoice = true;
    const fileId = (msg.voice || msg.audio).file_id;
    log(`[${from}] VOICE ${(msg.voice || msg.audio).duration || '?'}s — transcribing...`);
    text = await transcribeVoice(fileId);
    log(`  Transcription: ${text.slice(0, 80)}`);
    if (text.startsWith('[')) {
      await sendMessage(chatId, text); // Error message
      return;
    }
  } else if (msg.text) {
    text = msg.text.trim();
  } else {
    return; // Unsupported message type
  }

  if (!text) return;

  stats.messages_in++;
  messageHistory.push({ from, text, ts: new Date().toISOString(), voice: isVoice, chatId: String(chatId), admin: isAdmin });
  if (messageHistory.length > 50) messageHistory.shift();

  log(`[${from}] (${isAdmin ? 'ADMIN' : 'USER'}) ${text.slice(0, 80)}${text.length > 80 ? '...' : ''}`);

  // Record action for prediction engine (fire-and-forget)
  try {
    const now = new Date();
    const body = JSON.stringify({
      action: 'telegram_query',
      context: { source: 'telegram', text: text.slice(0, 100), from, hour: now.getHours(), weekday: now.getDay() === 0 ? 6 : now.getDay() - 1 }
    });
    httpRequest(`${PROXY_URL.replace(':18800', ':9742')}/api/record_action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    }, body).catch(() => {});
  } catch (e) { /* ignore prediction recording errors */ }

  // Commande spéciale ?
  if (text.startsWith('/')) {
    const spaceIdx = text.indexOf(' ');
    const cmd = spaceIdx > 0 ? text.slice(0, spaceIdx).toLowerCase() : text.toLowerCase();
    const args = spaceIdx > 0 ? text.slice(spaceIdx + 1).trim() : '';
    const handled = await handleCommand(chatId, cmd, args, isAdmin);
    if (handled !== null) return;
  }

  // ── Smart Router: detect intent and route to specialized handler ──
  const intent = detectIntent(text);
  if (intent) {
    log(`  INTENT: ${intent.intent} → ${intent.handler}`);
    const smartResult = await handleSmartIntent(chatId, text, intent);
    if (smartResult !== null) {
      addToMemory(chatId, 'user', text);
      addToMemory(chatId, 'assistant', `[${intent.handler}] handled`);
      return;
    }
  }

  // ── Try JARVIS command match first — ADMIN ONLY (system execution) ──
  if (isAdmin) {
    const jarvisResult = await handleJarvisCommand(chatId, text);
    if (jarvisResult === true) return; // Command matched and executed
  }

  // ── Dispatch: cluster race (all nodes parallel) ou proxy fallback ──
  let reply = '';
  let model = '';
  const start = Date.now();

  // Build context-enriched prompt with conversation memory
  const memMsgs = getMemoryMessages(chatId);
  let enrichedPrompt = text;
  if (memMsgs.length > 0) {
    const ctx = memMsgs.map(m => `${m.role}: ${m.content}`).join('\n');
    enrichedPrompt = `Contexte conversation:\n${ctx}\n\nNouveau message: ${text}`;
  }

  if (CLUSTER_RACE) {
    log(`  CLUSTER RACE: dispatching to ${CLUSTER_NODES.length} nodes...`);
    const result = await clusterRace(enrichedPrompt);
    if (result) {
      reply = result.text;
      model = `${result.node}/${result.model} (${result.latency}ms)`;
    }
  }

  // Fallback to proxy if race failed
  if (!reply) {
    try {
      const res = await proxyChat(text);
      if (res.ok && res.data) {
        reply = res.data.text || '(réponse vide)';
        model = res.data.model || 'proxy';
      }
    } catch (e) {
      logErr('Proxy fallback failed:', e.message);
    }
  }

  if (!reply) {
    await sendMessage(chatId, '🔴 Aucun noeud du cluster ne répond.');
    stats.errors++;
    return;
  }

  const totalMs = Date.now() - start;
  log(`  REPLY (${totalMs}ms) [${model}]: ${reply.slice(0, 80)}...`);

  // Save to conversation memory
  addToMemory(chatId, 'user', text);
  addToMemory(chatId, 'assistant', reply.slice(0, 500));

  // ── Send response: voice + text (all users) ──
  const attr = model ? `\n\n_[${model}] ${totalMs}ms_` : '';

  // Smart voice: skip TTS for code blocks, JSON, or very long text
  const isCodeOrJson = /```|^\s*[\[{]/.test(reply) || /\{[\s\S]{50,}\}/.test(reply);
  const isTooLong = reply.length > 1500;
  if (VOICE_MODE && !isCodeOrJson && !isTooLong) {
    await sendVoiceReply(chatId, reply);
  }

  await sendMessage(chatId, reply + attr, 'Markdown');
}

// ─── Inline Keyboard Menu ────────────────────────────────────────────────────

async function sendMenuKeyboard(chatId) {
  const keyboard = {
    inline_keyboard: [
      [
        { text: 'Scanner RT', callback_data: 'cmd_realtime' },
        { text: 'Performance', callback_data: 'cmd_perf' },
        { text: 'Marche', callback_data: 'cmd_market' },
      ],
      [
        { text: 'Hot Coins', callback_data: 'cmd_hot' },
        { text: 'Super Loop', callback_data: 'cmd_loop' },
        { text: 'GPU', callback_data: 'cmd_gpu' },
      ],
      [
        { text: 'Scan Now', callback_data: 'cmd_scan' },
        { text: 'Deep Scan', callback_data: 'cmd_deepscan' },
        { text: 'Backtest', callback_data: 'cmd_backtest' },
      ],
      [
        { text: 'Signaux', callback_data: 'cmd_signals' },
        { text: TRADING_ALERTS ? 'Alertes OFF' : 'Alertes ON', callback_data: TRADING_ALERTS ? 'cmd_alertoff' : 'cmd_alerton' },
        { text: 'Stats Bot', callback_data: 'cmd_stats' },
      ],
    ]
  };
  await telegramAPI('sendMessage', {
    chat_id: chatId,
    text: `*JARVIS Dashboard*\nAlertes trading: ${TRADING_ALERTS ? 'ACTIVES' : 'DESACTIVEES'}\nSelectionnez une action:`,
    parse_mode: 'Markdown',
    reply_markup: JSON.stringify(keyboard),
  });
}

async function handleCallback(query) {
  const chatId = query.message.chat.id;
  const data = query.data;
  const isAdmin = String(chatId) === String(CHAT_ID);

  // Acknowledge the callback immediately
  await telegramAPI('answerCallbackQuery', { callback_query_id: query.id }).catch(() => {});

  switch (data) {
    case 'cmd_realtime': return handleRealtimeStatus(chatId);
    case 'cmd_perf': return handlePerformance(chatId);
    case 'cmd_market': return handleMarketSummary(chatId);
    case 'cmd_hot': return handleHotCoins(chatId, 10);
    case 'cmd_loop': return handleLoopStatus(chatId);
    case 'cmd_gpu': if (isAdmin) return handleGpuStatus(chatId); break;
    case 'cmd_scan': return handleSniperScan(chatId, 50);
    case 'cmd_backtest': return handleBacktestResults(chatId);
    case 'cmd_menu': return sendMenuKeyboard(chatId);
    case 'cmd_deepscan': return handleDeepScan(chatId, 10);
    case 'cmd_signals': return handleOpenSignals(chatId);
    case 'cmd_alerton': {
      TRADING_ALERTS = true;
      try { fs.unlinkSync(ALERTS_FLAG_FILE); } catch {}
      await sendMessage(chatId, 'Alertes trading ACTIVEES (global).');
      return;
    }
    case 'cmd_alertoff': {
      TRADING_ALERTS = false;
      try { fs.writeFileSync(ALERTS_FLAG_FILE, new Date().toISOString()); } catch {}
      await sendMessage(chatId, 'Alertes trading DESACTIVEES (global).');
      return;
    }
    case 'cmd_stats':
      return sendMessage(chatId, [
        '*Bot Stats*',
        `Demarre: ${stats.started}`,
        `Messages recus: ${stats.messages_in}`,
        `Messages envoyes: ${stats.messages_out}`,
        `Erreurs: ${stats.errors}`,
      ].join('\n'), 'Markdown');
    default:
      // Dynamic callbacks: analyze_COIN → relance analyse
      if (data.startsWith('analyze_')) {
        const coin = data.replace('analyze_', '').toUpperCase();
        return handleSmartIntent(chatId, `analyse ${coin} usdt`, { intent: 'analyze', handler: 'analyze' });
      }
      log(`Unknown callback: ${data}`);
  }
}

// ─── Long Polling Loop ────────────────────────────────────────────────────────

async function pollLoop() {
  log('Démarrage long polling Telegram...');

  while (running) {
    try {
      const updates = await telegramAPI('getUpdates', {
        offset,
        timeout: POLL_TIMEOUT,
        allowed_updates: ['message', 'callback_query'],
      });

      for (const update of updates) {
        offset = update.update_id + 1;
        if (update.message) {
          processMessage(update.message).catch(e => logErr('processMessage:', e.message));
        } else if (update.callback_query) {
          handleCallback(update.callback_query).catch(e => logErr('callback:', e.message));
        }
      }
    } catch (e) {
      logErr('getUpdates failed:', e.message);
      stats.errors++;
      // Attend avant retry
      await new Promise(r => setTimeout(r, RECONNECT_DELAY));
    }
  }
}

// ─── API locale pour MCP ──────────────────────────────────────────────────────

/** Exposé pour interrogation externe (MCP handlers) */
function getStats() { return { ...stats, history_count: messageHistory.length }; }
function getHistory(limit = 20) { return messageHistory.slice(-limit); }

// ─── Proactive Alerts ─────────────────────────────────────────────────────────

let lastProactiveCheck = 0;
let notifiedSignals = new Set(); // track already notified signal IDs

async function checkProactiveAlerts() {
  if (!TRADING_ALERTS) return; // Alertes desactivees par /alertoff
  try {
    const result = execSync(`python -c "
import sqlite3, json
db = sqlite3.connect('data/sniper_scan.db')
# Find recently hit TPs (last 5 min)
hits = db.execute(
    'SELECT id, symbol, direction, entry_price, tp1, pnl_pct, score, status, checked_at '
    'FROM signal_tracker WHERE status IN (\\"TP1_HIT\\",\\"TP2_HIT\\",\\"TP3_HIT\\") '
    'AND checked_at > datetime(\\"now\\", \\"-5 minutes\\") '
    'ORDER BY id DESC LIMIT 5'
).fetchall()
# Find recently hit SLs
sl_hits = db.execute(
    'SELECT id, symbol, direction, entry_price, sl, pnl_pct, score, checked_at '
    'FROM signal_tracker WHERE status = \\"SL_HIT\\" '
    'AND checked_at > datetime(\\"now\\", \\"-5 minutes\\") '
    'ORDER BY id DESC LIMIT 3'
).fetchall()
print(json.dumps({
    'tp_hits': [{'id':r[0],'s':r[1].replace('_USDT',''),'d':r[2],'entry':r[3],'tp1':r[4],'pnl':r[5],'sc':r[6],'st':r[7]} for r in hits],
    'sl_hits': [{'id':r[0],'s':r[1].replace('_USDT',''),'d':r[2],'entry':r[3],'sl':r[4],'pnl':r[5],'sc':r[6]} for r in sl_hits]
}))
db.close()
"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());

    // Notify TP hits (only new ones)
    for (const hit of d.tp_hits) {
      if (notifiedSignals.has(hit.id)) continue;
      notifiedSignals.add(hit.id);
      const msg = `TP TOUCHE ${hit.s} ${hit.d}\nEntry: ${hit.entry} → ${hit.st}\nPnL: ${hit.pnl > 0 ? '+' : ''}${hit.pnl.toFixed(2)}% | Score: ${hit.sc.toFixed(0)}`;
      await sendMessage(CHAT_ID, msg);
      await sendVoiceReply(CHAT_ID, `Objectif touche sur ${hit.s}, ${hit.d === 'LONG' ? 'achat' : 'vente'}, plus ${Math.abs(hit.pnl).toFixed(1)} pour cent de profit.`);
    }

    // Notify SL hits (only new ones)
    for (const hit of d.sl_hits) {
      if (notifiedSignals.has(hit.id)) continue;
      notifiedSignals.add(hit.id);
      const msg = `SL TOUCHE ${hit.s} ${hit.d}\nPerte: ${hit.pnl.toFixed(2)}% | Score: ${hit.sc.toFixed(0)}`;
      await sendMessage(CHAT_ID, msg);
    }

    // Cleanup old notification IDs (keep last 200)
    if (notifiedSignals.size > 200) {
      const arr = [...notifiedSignals];
      notifiedSignals = new Set(arr.slice(-100));
    }
  } catch (e) {
    // Silently ignore (scanner might not be running)
  }
}

// ─── Startup ──────────────────────────────────────────────────────────────────

async function main() {
  log('='.repeat(50));
  log('JARVIS Telegram Bot — Thin Bridge');
  log(`Token: ...${TOKEN.slice(-6)}`);
  log(`Chat ID: ${CHAT_ID}`);
  log(`Proxy: ${PROXY_URL}`);
  log('='.repeat(50));

  // Vérifie la connexion Telegram
  try {
    const me = await telegramAPI('getMe');
    log(`Bot connecté: @${me.username} (${me.first_name})`);
  } catch (e) {
    logErr('Impossible de se connecter à Telegram:', e.message);
    process.exit(1);
  }

  // Vérifie le proxy (non bloquant)
  try {
    const h = await proxyGet('/health');
    if (h.ok || h.nodes) {
      log(`Proxy OK — ${(h.nodes || []).length} nœuds disponibles`);
    }
  } catch (e) {
    log('⚠️  Proxy non joignable — le bot démarrera quand même et réessaiera');
  }

  // Enregistre dans le service registry (python_ws)
  registerService();
  setInterval(heartbeat, 60000); // heartbeat toutes les 60s

  // Proactive notifications: check signal tracker every 2 min
  setInterval(() => checkProactiveAlerts().catch(e => logErr('proactive:', e.message)), 120000);

  // Notifie l'utilisateur
  await sendMessage(CHAT_ID, 'JARVIS Telegram Bot demarre. Envoyez /help ou /menu pour les commandes.');

  // Lance le polling
  await pollLoop();
}

/** Enregistre le bot dans le service registry JARVIS (port 9742) */
function registerService() {
  const body = JSON.stringify({
    name: 'telegram-bot', url: `${PROXY_URL}/chat`,
    service_type: 'notification',
  });
  httpRequest('http://127.0.0.1:9742/api/services/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, timeout: 5000,
  }, body).then(() => log('Service enregistré dans le registry'))
    .catch(() => {}); // silencieux si WS backend pas up
}

/** Heartbeat périodique */
function heartbeat() {
  httpRequest('http://127.0.0.1:9742/api/services/heartbeat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, timeout: 3000,
  }, JSON.stringify({ name: 'telegram-bot' })).catch(() => {});
}

// Graceful shutdown
process.on('SIGINT', () => { running = false; log('Arrêt...'); process.exit(0); });
process.on('SIGTERM', () => { running = false; log('Arrêt...'); process.exit(0); });

// Export pour tests et MCP
module.exports = { splitMessage, sendMessage, getStats, getHistory, processMessage, loadEnv };

// Run
main().catch(e => { logErr('FATAL:', e.message); process.exit(1); });
