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
const VENV_PYTHON = 'F:/BUREAU/turbo/.venv/Scripts/python.exe';
const VOICE_MODE = false; // Texte uniquement — WhisperFlow gère le vocal séparément
const CLUSTER_RACE = true; // Utiliser tout le cluster en parallèle
const ALERTS_FLAG_FILE = path.join(__dirname, '..', 'data', '.trading_alerts_off');
let TRADING_ALERTS = !fs.existsSync(ALERTS_FLAG_FILE); // Lit le flag persistant au demarrage

// ─── Cluster nodes (direct, sans passer par le proxy) ─────────────────────────
const CLUSTER_NODES = [
  { id: 'M1', url: 'http://127.0.0.1:1234/v1/chat/completions', model: 'qwen3-8b', weight: 1.8, timeout: 8000 },
  { id: 'OL1', url: 'http://127.0.0.1:11434/api/chat', model: 'qwen3:1.7b', isOllama: true, weight: 1.3, timeout: 5000 },
  // M2 (192.168.1.26) retiré — OFFLINE | M3 retiré — trop lent (30s+)
];

if (!TOKEN) { console.error('[FATAL] TELEGRAM_TOKEN manquant dans .env'); process.exit(1); }
if (!CHAT_ID) { console.error('[FATAL] TELEGRAM_CHAT manquant dans .env'); process.exit(1); }

// ─── Single Instance Lock ─────────────────────────────────────────────────────

const LOCK_FILE = path.join(__dirname, '.telegram-bot.lock');
function acquireLock() {
  try {
    if (fs.existsSync(LOCK_FILE)) {
      const lockData = fs.readFileSync(LOCK_FILE, 'utf-8').trim();
      const oldPid = parseInt(lockData);
      if (!isNaN(oldPid)) {
        // Check if process is alive AND is actually a node process (not PID reuse)
        try {
          process.kill(oldPid, 0);
          // PID alive — check age of lock (>5min = likely stale after restart)
          const lockAge = Date.now() - fs.statSync(LOCK_FILE).mtimeMs;
          if (lockAge > 300000) {
            console.log(`[WARN] Stale lock (PID ${oldPid}, age ${Math.round(lockAge/1000)}s) — removing`);
            fs.unlinkSync(LOCK_FILE);
          } else {
            console.error(`[FATAL] Another telegram-bot is running (PID ${oldPid}). Exiting.`);
            process.exit(1);
          }
        } catch (e) {
          // Process dead — stale lock
          console.log(`[INFO] Stale lock removed (PID ${oldPid} dead)`);
          fs.unlinkSync(LOCK_FILE);
        }
      } else {
        fs.unlinkSync(LOCK_FILE); // Corrupted lock
      }
    }
    fs.writeFileSync(LOCK_FILE, `${process.pid}\n${new Date().toISOString()}`);
  } catch (e) {
    console.error('[WARN] Could not acquire lock:', e.message);
  }
}
function releaseLock() {
  try {
    // Only remove if WE own the lock
    const content = fs.readFileSync(LOCK_FILE, 'utf-8').trim();
    if (content.startsWith(String(process.pid))) {
      fs.unlinkSync(LOCK_FILE);
    }
  } catch (e) {}
}
acquireLock();
process.on('exit', releaseLock);
process.on('uncaughtException', (err) => { console.error('[CRASH]', err); releaseLock(); process.exit(1); });

// ─── State ────────────────────────────────────────────────────────────────────

let offset = 0;
let running = true;
let stats = { started: new Date().toISOString(), messages_in: 0, messages_out: 0, errors: 0 };
let messageHistory = []; // derniers messages reçus (max 50)

// ─── RBAC — Role-Based Access Control ────────────────────────────────────────

const ADMIN_COMMANDS = new Set(['/jarvis', '/exec', '/improve', '/gpu', '/voice', '/reload', '/correct', '/broadcast', '/linkedin', '/post']);

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

/** Health check direct des noeuds du cluster (sans proxy) */
/** Check if WhisperFlow Electron process is running */
async function checkWhisperFlow() {
  return new Promise((resolve) => {
    exec('tasklist /FI "IMAGENAME eq electron.exe" /FO CSV /NH', { timeout: 5000 }, (err, stdout) => {
      if (err) return resolve(false);
      resolve(stdout.toLowerCase().includes('electron.exe'));
    });
  });
}

async function directClusterHealth() {
  const results = [];
  for (const node of CLUSTER_NODES) {
    const start = Date.now();
    try {
      if (node.isOllama) {
        const r = await httpRequest(`http://127.0.0.1:11434/api/tags`, { timeout: 5000 });
        const data = JSON.parse(r.body);
        const models = (data.models || []).map(m => m.name).join(', ');
        results.push({ nodeId: node.id, status: 'online', model: models || node.model, latency: Date.now() - start });
      } else {
        const url = node.url.replace('/v1/chat/completions', '/v1/models');
        const r = await httpRequest(url, { timeout: 5000 });
        const data = JSON.parse(r.body);
        const loaded = (data.data || data.models || []).filter(m => m.loaded_instances).map(m => m.id);
        results.push({ nodeId: node.id, status: 'online', model: loaded.join(', ') || node.model, latency: Date.now() - start });
      }
    } catch (e) {
      results.push({ nodeId: node.id, status: 'offline', model: node.model, latency: 0, error: e.message });
    }
  }
  return { ok: true, nodes: results };
}

/** Normalise les noeuds du proxy ou du direct health check */
function normalizeNodes(nodes) {
  return (nodes || []).map(n => ({
    nodeId: n.nodeId || n.name || n.id || '?',
    status: n.status || (n.ok ? 'online' : 'offline'),
    model: n.model || CLUSTER_NODES.find(c => c.id === (n.nodeId || n.name || n.id))?.model || '',
    latency: n.latency || 0,
  }));
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
        '*JARVIS — Commandes*',
        '',
        '*Poser une question:*',
        '`/ask <question>` — Poser une question au cluster IA',
        '`/consensus <question>` — Demander a tous les noeuds (vote)',
        '`/model M1 <question>` — Forcer un noeud precis',
        '',
        '*Trading:*',
        '`/market` — Prix BTC + tendance + top movers',
        '`/scan` — Scanner rapide top 50 coins',
        '`/deepscan` — Scanner profond 800+ coins',
        '`/hot` — Coins les plus chauds du moment',
        '`/signals` — Mes signaux ouverts',
        '`/perf` — Resultats: combien de TP et SL touches',
        '`/compare BTC SOL` — Comparer deux coins',
        '`/whales` — Gros mouvements detectes',
        '`/news` — Actus crypto',
        '`/backtest` — Resultats des backtests',
        '`/alerton` / `/alertoff` — Alertes ON/OFF',
        '',
        '*Systeme:*',
        '`/status` — Quels noeuds IA sont en ligne',
        '`/gpu` — Temperatures GPU',
        '`/disk` — Espace disque libre',
        '`/ping` — Test rapide (le bot repond?)',
        '`/sniper` — Le scanner tourne-t-il?',
        '`/loop` — Amelioration auto en cours?',
        '',
        '*Dictionnaire & Commandes:*',
        '`/dict [mot]` — Rechercher dans le dictionnaire vocal',
        '`/cmd [categorie]` — Lister commandes (systeme/trading/nav)',
        '`/pipeline [nom]` — Voir/lancer un pipeline',
        '',
        '*Dominos (automatisations):*',
        '`/domino` — Voir toutes les automatisations',
        '`/domino matin` — Lancer un domino par nom',
        '',
        '`/menu` — Boutons interactifs',
        '`/stats` — Chiffres du bot',
      ];
      if (isAdmin) {
        lines.push(
          '',
          '*Admin:*',
          '`/jarvis <cmd>` — Executer commande vocale',
          '`/improve [N]` — Lancer N cycles amelioration',
          '`/superloop [N]` — Super Loop complet',
          '`/killscanner` — Stopper le scanner',
          '`/voice [texte]` — Tester la voix',
          '`/reload` — Recharger le dictionnaire vocal',
          '`/correct a → b` — Ajouter correction phonetique',
          '`/broadcast <msg>` — Envoyer via API',
          '`/linkedin prompts|research|stats` — Growth LinkedIn',
        );
      }
      lines.push('', '`/tghistory [N]` — Derniers N messages');
      lines.push('', 'Ecris directement ta question, JARVIS repond.');
      lines.push('Envoie un vocal, JARVIS transcrit et repond en vocal.');
      return sendMessage(chatId, lines.join('\n'), 'Markdown');
    }

    case '/status': {
      try {
        let h;
        try {
          h = await proxyGet('/health');
          if (!h.ok) throw new Error('proxy unhealthy');
        } catch {
          h = await directClusterHealth();
        }
        const nodes = normalizeNodes(h.nodes);
        const onlineCount = nodes.filter(n => n.status === 'online').length;
        const lines = [`${onlineCount === nodes.length ? '✅' : '⚠️'} *Cluster* (${onlineCount}/${nodes.length} en ligne)`, ''];
        for (const n of nodes) {
          const icon = n.status === 'online' ? '🟢' : '🔴';
          lines.push(`${icon} *${n.nodeId}* ${n.model ? '— ' + n.model + ' ' : ''}(${n.latency || '?'}ms)`);
        }
        // WhisperFlow process check
        try {
          const wf = await checkWhisperFlow();
          lines.push(`${wf ? '🟢' : '🔴'} *WhisperFlow* — ${wf ? 'actif' : 'inactif'}`);
        } catch { /* ignore */ }
        // Telegram bot status via WS API
        try {
          const tgRes = await httpRequest('http://127.0.0.1:9742/api/telegram/status', { timeout: 5000 });
          const tg = JSON.parse(tgRes.body);
          if (tg.bot_name) lines.push(`🤖 *Bot* — ${tg.bot_name}`);
        } catch { /* ignore */ }
        return sendMessage(chatId, lines.join('\n'), 'Markdown');
      } catch (e) {
        return sendMessage(chatId, '🔴 Erreur health check: ' + e.message);
      }
    }

    case '/health': {
      try {
        let h, al = null;
        try {
          h = await proxyGet('/health');
          al = await proxyGet('/autolearn/scores');
        } catch {
          h = await directClusterHealth();
        }
        const nodes = normalizeNodes(h.nodes);
        const lines = ['📊 *Cluster detaille*', ''];
        for (const n of nodes) {
          const icon = n.status === 'online' ? '🟢' : '🔴';
          lines.push(`${icon} *${n.nodeId}*: ${n.status} | ${n.model || '-'} | ${n.latency || '?'}ms`);
        }
        if (al && al.ok !== false) {
          // Autolearn: show routing preferences per category
          const routing = al.routing || {};
          const routeEntries = Object.entries(routing).filter(([k]) => k !== 'default');
          if (routeEntries.length) {
            lines.push('', '*Autolearn routing:*');
            for (const [cat, order] of routeEntries.slice(0, 8)) {
              if (Array.isArray(order)) lines.push(`  ${cat}: ${order.join(' > ')}`);
            }
          }
          if (al.last_cycle) lines.push(`Dernier cycle: ${new Date(al.last_cycle).toLocaleTimeString('fr-FR')}`);
        }
        return sendMessage(chatId, lines.join('\n'), 'Markdown');
      } catch (e) {
        return sendMessage(chatId, '🔴 Erreur: ' + e.message);
      }
    }

    case '/consensus': {
      if (!args) return sendMessage(chatId, '⚠️ Usage: `/consensus <question>`', 'Markdown');
      await sendMessage(chatId, '🔄 Consensus en cours...');
      try {
        // Try proxy first, fallback to direct cluster race
        let res;
        try {
          res = await proxyChat(`[CONSENSUS] ${args}`, 'consensus');
          if (res.ok && res.data) {
            const d = res.data;
            const text = `🗳 *Consensus*\n\n${d.text}\n\n_${d.model} via ${d.provider} (${d.turns} turns)_`;
            return sendMessage(chatId, text, 'Markdown');
          }
        } catch {}
        // Fallback: direct cluster race
        const raceResult = await clusterRace(args);
        if (raceResult) {
          return sendMessage(chatId, `🗳 *Consensus (direct)*\n\n${raceResult.text}\n\n_${raceResult.model} [${raceResult.nodeId}]_`, 'Markdown');
        }
        return sendMessage(chatId, '⚠️ Aucun noeud n\'a repondu');
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
        // Try proxy first
        try {
          const res = await proxyChat(query, modelId.toLowerCase());
          if (res.ok && res.data) {
            return sendMessage(chatId, `*[${res.data.model}]*\n\n${res.data.text}`, 'Markdown');
          }
        } catch {}
        // Fallback: direct query to matching node
        const node = CLUSTER_NODES.find(n => n.id.toLowerCase() === modelId.toLowerCase());
        if (!node) return sendMessage(chatId, `⚠️ Noeud ${modelId} inconnu. Disponibles: ${CLUSTER_NODES.map(n => n.id).join(', ')}`);
        const result = await queryNodeDirect(node, query);
        if (result) {
          return sendMessage(chatId, `*[${node.id}/${node.model}]*\n\n${result}`, 'Markdown');
        }
        return sendMessage(chatId, `🔴 ${node.id} n'a pas repondu`);
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

    case '/domino': {
      const dominoName = args || '';
      return handleDominos(chatId, dominoName);
    }

    case '/dict': {
      // Recherche dans le dictionnaire vocal (pipeline_dictionary + voice_commands + corrections)
      return handleDictSearch(chatId, args || '');
    }

    case '/voice': {
      if (!args) return sendMessage(chatId, 'Usage: `/voice <commande>`\nExecute une commande vocale JARVIS.\nExemple: `/voice ouvre chrome`', 'Markdown');
      return handleVoiceCommand(chatId, args);
    }

    case '/cmd': {
      // Liste les commandes par categorie ou recherche
      return handleCmdList(chatId, args || '');
    }

    case '/pipeline': {
      // Affiche/lance un pipeline d'actions
      return handlePipelineAction(chatId, args || '');
    }

    case '/ask': {
      if (!args) return sendMessage(chatId, 'Usage: /ask <ta question>');
      // Dispatch direct au cluster via race
      await sendMessage(chatId, 'Je reflechis...');
      const result = await clusterRace(args);
      if (result) {
        addToMemory(chatId, 'user', args);
        addToMemory(chatId, 'assistant', result.text.slice(0, 500));
        const attr = '\n\n_[' + result.node + '/' + result.model + ' ' + result.latency + 'ms]_';
        if (VOICE_MODE && result.text.length < 1500) await sendVoiceReply(chatId, result.text);
        return sendMessage(chatId, result.text + attr, 'Markdown');
      }
      return sendMessage(chatId, 'Aucun noeud ne repond. Verifiez /status');
    }

    case '/ping': {
      const uptime = Math.floor((Date.now() - new Date(stats.started).getTime()) / 1000);
      const h = Math.floor(uptime / 3600);
      const m = Math.floor((uptime % 3600) / 60);
      return sendMessage(chatId, 'Pong! Bot actif depuis ' + h + 'h' + m + 'm | ' + stats.messages_in + ' msgs recus | ' + stats.errors + ' erreurs');
    }

    case '/disk': {
      try {
        const helper = path.join(__dirname, 'bot-helpers.py');
        const r = execSync(`python "${helper}" disk`, { timeout: 5000, encoding: 'utf-8' });
        const d = JSON.parse(r.trim());
        return sendMessage(chatId, `Espace disque:\nC: ${d.C_free} GB libres / ${d.C_total} GB\nF: ${d.F_free} GB libres / ${d.F_total} GB`);
      } catch (e) {
        return sendMessage(chatId, 'Erreur disque: ' + e.message.slice(0, 100));
      }
    }

    case '/reload': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      try {
        const res = await httpRequest(`http://127.0.0.1:9742/api/dictionary/reload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000,
        }, '{}');
        const data = JSON.parse(res.body);
        return sendMessage(chatId, data.ok ? '✅ Dictionnaire rechargé.' : '⚠️ Reload: ' + (data.error || 'erreur'));
      } catch (e) {
        return sendMessage(chatId, '🔴 Erreur reload: ' + e.message);
      }
    }

    case '/correct': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      // Format: /correct crome → chrome
      const match = (args || '').match(/^(.+?)\s*→\s*(.+)$/);
      if (!match) return sendMessage(chatId, 'Usage: `/correct mot_faux → mot_correct`', 'Markdown');
      const [, wrong, correct] = match;
      try {
        const body = JSON.stringify({ wrong: wrong.trim(), correct: correct.trim() });
        const res = await httpRequest(`http://127.0.0.1:9742/api/dictionary/correction`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000,
        }, body);
        const data = JSON.parse(res.body);
        return sendMessage(chatId, data.ok
          ? `✅ Correction ajoutée: "${wrong.trim()}" → "${correct.trim()}"`
          : '⚠️ ' + (data.error || 'erreur'));
      } catch (e) {
        return sendMessage(chatId, '🔴 Erreur correction: ' + e.message);
      }
    }

    case '/linkedin': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      const subCmd = (args || '').split(' ')[0] || 'prompts';
      const sector = (args || '').split(' ').slice(1).join(' ') || 'tech/IA';
      const script = path.join(__dirname, '..', 'cowork', 'dev', 'linkedin_growth_engine.py');

      if (subCmd === 'prompts') {
        await sendMessage(chatId, '📝 Export prompt bank LinkedIn...');
        try {
          const r = execSync(`python "${script}" --prompts-only --sector "${sector}" --json`, {
            timeout: 15000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          const data = JSON.parse(r.trim());
          const lines = ['*LinkedIn Prompt Bank*', ''];
          for (const [cat, prompts] of Object.entries(data)) {
            lines.push(`*${cat}*: ${Object.keys(prompts).join(', ')}`);
          }
          lines.push('', 'Fichier exporte dans data/linkedin/');
          return sendMessage(chatId, lines.join('\n'), 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (subCmd === 'research') {
        await sendMessage(chatId, '🔍 Recherche tendances LinkedIn...');
        try {
          const proc = exec(
            `python "${script}" --research --sector "${sector}"`,
            { timeout: 120000, cwd: path.join(__dirname, '..') }
          );
          proc.on('close', (code) => {
            sendMessage(chatId, code === 0 ? '✅ Recherche terminée — voir data/linkedin/' : '⚠️ Erreur recherche');
          });
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
        return;
      } else if (subCmd === 'stats') {
        try {
          const r = execSync(`python "${script}" --analytics --json`, {
            timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          const d = JSON.parse(r.trim());
          return sendMessage(chatId, `📊 *LinkedIn Stats*\nTotal: ${d.total_generated}\nCette semaine: ${d.this_week}`, 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else {
        return sendMessage(chatId, [
          '*LinkedIn Growth Engine*',
          '`/linkedin prompts [sector]` — Exporter la banque de prompts',
          '`/linkedin research [sector]` — Recherche tendances (web)',
          '`/linkedin stats` — Analytics',
        ].join('\n'), 'Markdown');
      }
    }

    case '/post': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      const postSubCmd = (args || '').split(' ')[0] || '';
      const postArgs = (args || '').split(' ').slice(1).join(' ');
      const publishScript = path.join(__dirname, '..', 'scripts', 'linkedin_auto_publish.py');

      if (postSubCmd === 'generate' || postSubCmd === 'gen' || !postSubCmd) {
        // /post generate [theme] — generer + publier via cluster
        const theme = postArgs || 'IA distribuee sur cluster GPU local';
        await sendMessage(chatId, `📝 Generation post LinkedIn...\nTheme: ${theme}`);
        try {
          const r = execSync(
            `python "${publishScript}" --generate --theme "${theme}" --dry-run`,
            { timeout: 60000, encoding: 'utf-8', cwd: path.join(__dirname, '..') }
          );
          const contentMatch = r.match(/POST LINKEDIN:\n={50}\n([\s\S]*?)\n={50}/);
          const content = contentMatch ? contentMatch[1].trim() : r.slice(0, 500);
          return sendMessage(chatId, `📝 *Post genere (dry-run):*\n\n${content}\n\nPour publier: \`/post publish\``, 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 Generation: ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'publish' || postSubCmd === 'now') {
        // /post publish [texte] — publier directement
        const content = postArgs || '';
        if (!content) return sendMessage(chatId, 'Usage: `/post publish <texte du post>`', 'Markdown');
        await sendMessage(chatId, '🚀 Publication LinkedIn en cours...');
        try {
          // Save to DB first
          const dbScript = `python -c "
import sqlite3, time
conn = sqlite3.connect('data/jarvis.db')
conn.execute('INSERT INTO linkedin_posts (content, status, source) VALUES (?, \\'pending\\', \\'telegram\\')', ('${content.replace(/'/g, "\\'")}',))
conn.commit(); conn.close(); print('saved')
"`;
          execSync(dbScript, { timeout: 5000, cwd: path.join(__dirname, '..') });
          return sendMessage(chatId, '✅ Post sauvegarde en DB (status: pending).\nPublication auto via pipeline Playwright.\nUtilise Claude Code pour lancer: `python scripts/linkedin_auto_publish.py --file post.txt`');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'history' || postSubCmd === 'hist') {
        // /post history — voir les derniers posts
        try {
          const r = execSync(
            `python -c "
import sqlite3, json
conn = sqlite3.connect('data/jarvis.db')
rows = conn.execute('SELECT content, status, post_url, created_at FROM linkedin_posts ORDER BY id DESC LIMIT 5').fetchall()
for r in rows:
    print(f'{r[3]} [{r[1]}] {r[0][:60]}...')
    if r[2]: print(f'  URL: {r[2]}')
conn.close()
"`,
            { timeout: 5000, encoding: 'utf-8', cwd: path.join(__dirname, '..') }
          );
          return sendMessage(chatId, `📋 *Derniers posts LinkedIn:*\n\n${r.trim()}`, 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'comment') {
        // /post comment <url> <texte> — commenter un post
        const parts = postArgs.match(/^(https?:\/\/\S+)\s+(.+)$/);
        if (!parts) return sendMessage(chatId, 'Usage: `/post comment <url_post> <commentaire>`', 'Markdown');
        return sendMessage(chatId, `💬 Commentaire programme:\nURL: ${parts[1]}\nTexte: ${parts[2]}\n\n⚠️ Publication automatique de commentaires via Playwright (non implemente — necessite session active).`);
      } else if (postSubCmd === 'group') {
        // /post group — lister les groupes LinkedIn
        return sendMessage(chatId, [
          '👥 *Groupes LinkedIn actifs:*',
          '• AI, ML, Data Science, Python (7039829)',
          '',
          'Usage: `/post group <id> <texte>` pour poster dans un groupe',
          '⚠️ Posting dans les groupes necessite navigation Playwright specifique.',
        ].join('\n'), 'Markdown');
      } else if (postSubCmd === 'notif') {
        // /post notif — voir les notifications LinkedIn
        return sendMessage(chatId, '🔔 Notifications LinkedIn: utilise `/post history` pour les posts + check via pipeline Playwright.');
      } else if (postSubCmd === 'batch') {
        // /post batch [count] — generer plusieurs posts d'avance
        const count = parseInt(postArgs) || 5;
        await sendMessage(chatId, `📝 Generation de ${count} posts d'avance via cluster...`);
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const proc = exec(
            `python "${pipelineScript}" batch --count ${count}`,
            { timeout: 120000, cwd: path.join(__dirname, '..') }
          );
          proc.on('close', (code) => {
            sendMessage(chatId, code === 0 ? `✅ ${count} posts generes. Voir: \`/post list\`` : '⚠️ Erreur batch');
          });
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
        return;
      } else if (postSubCmd === 'list' || postSubCmd === 'ls') {
        // /post list — lister les posts planifies
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const r = execSync(`python "${pipelineScript}" list`, {
            timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          return sendMessage(chatId, `📋 *Posts LinkedIn:*\n\`\`\`\n${r.trim()}\n\`\`\``, 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'validate' || postSubCmd === 'val') {
        // /post validate <id> — valider un post par consensus cluster
        const postId = parseInt(postArgs);
        if (!postId) return sendMessage(chatId, 'Usage: `/post validate <id>`', 'Markdown');
        await sendMessage(chatId, `🔍 Validation cluster du post #${postId}...`);
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const r = execSync(`python "${pipelineScript}" validate --id ${postId}`, {
            timeout: 90000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          return sendMessage(chatId, `✅ *Validation:*\n\`\`\`\n${r.trim()}\n\`\`\``, 'Markdown');
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'schedule' || postSubCmd === 'sched') {
        // /post schedule <id> [YYYY-MM-DD HH:MM] — planifier un post
        const parts = postArgs.match(/^(\d+)\s*(.*)$/);
        if (!parts) return sendMessage(chatId, 'Usage: `/post schedule <id> [date heure]`', 'Markdown');
        const postId = parts[1];
        const schedAt = parts[2] || '';
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const atArg = schedAt ? `--at "${schedAt}"` : '';
          const r = execSync(`python "${pipelineScript}" schedule --id ${postId} ${atArg}`, {
            timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          return sendMessage(chatId, `📅 ${r.trim()}`);
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'routine' || postSubCmd === 'status') {
        // /post routine — statut de la routine du jour
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const r = execSync(`python "${pipelineScript}" status`, {
            timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          return sendMessage(chatId, `📊 ${r.trim()}`);
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'check') {
        // /post check — verifier posts planifies a publier maintenant
        try {
          const pipelineScript = path.join(__dirname, '..', 'scripts', 'linkedin_pipeline.py');
          const r = execSync(`python "${pipelineScript}" check`, {
            timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..')
          });
          return sendMessage(chatId, `⏰ ${r.trim()}`);
        } catch (e) {
          return sendMessage(chatId, '🔴 ' + e.message.slice(0, 200));
        }
      } else if (postSubCmd === 'scheduler') {
        // /post scheduler [start|stop|status] — gerer le LinkedIn Scheduler daemon
        const schedAction = postArgs.trim().split(' ')[0] || 'status';
        const schedulerScript = path.join(__dirname, '..', 'scripts', 'linkedin_scheduler.py');
        const lockFile = path.join(__dirname, '..', 'data', '.linkedin-scheduler.lock');
        const fs = require('fs');

        if (schedAction === 'status') {
          let alive = false;
          try {
            if (fs.existsSync(lockFile)) {
              const pid = parseInt(fs.readFileSync(lockFile, 'utf-8').trim());
              process.kill(pid, 0); // signal 0 = check if alive
              alive = true;
            }
          } catch (e) { alive = false; }
          return sendMessage(chatId, alive
            ? '🟢 *LinkedIn Scheduler* actif (PID: ' + fs.readFileSync(lockFile, 'utf-8').trim() + ')'
            : '🔴 *LinkedIn Scheduler* inactif\nLancer: `/post scheduler start`', 'Markdown');
        } else if (schedAction === 'start') {
          // Check if already running
          let alive = false;
          try {
            if (fs.existsSync(lockFile)) {
              const pid = parseInt(fs.readFileSync(lockFile, 'utf-8').trim());
              process.kill(pid, 0);
              alive = true;
            }
          } catch (e) { alive = false; }
          if (alive) return sendMessage(chatId, '🟢 Scheduler deja actif.');

          const { spawn } = require('child_process');
          const child = spawn('python', [schedulerScript], {
            cwd: path.join(__dirname, '..'),
            detached: true,
            stdio: 'ignore',
          });
          child.unref();
          return sendMessage(chatId, `🚀 *LinkedIn Scheduler* demarre (PID: ${child.pid})\nInterval: 60s | Routine: 8h, 12h, 18h`, 'Markdown');
        } else if (schedAction === 'stop') {
          try {
            if (fs.existsSync(lockFile)) {
              const pid = parseInt(fs.readFileSync(lockFile, 'utf-8').trim());
              process.kill(pid, 'SIGTERM');
              fs.unlinkSync(lockFile);
              return sendMessage(chatId, `🛑 Scheduler arrete (PID: ${pid})`);
            }
            return sendMessage(chatId, '⚠️ Aucun scheduler actif.');
          } catch (e) {
            return sendMessage(chatId, '⚠️ ' + e.message.slice(0, 200));
          }
        } else {
          return sendMessage(chatId, [
            '*LinkedIn Scheduler*',
            '`/post scheduler` — Statut',
            '`/post scheduler start` — Demarrer',
            '`/post scheduler stop` — Arreter',
          ].join('\n'), 'Markdown');
        }
      } else {
        return sendMessage(chatId, [
          '📱 *LinkedIn Publisher Pipeline*',
          '',
          '*Generation:*',
          '`/post` ou `/post gen [theme]` — Generer 1 post',
          '`/post batch [n]` — Generer n posts d\'avance',
          '',
          '*Validation & Planning:*',
          '`/post list` — Lister tous les posts',
          '`/post validate <id>` — Valider par consensus cluster',
          '`/post schedule <id> [date]` — Planifier publication',
          '`/post check` — Verifier posts a publier',
          '',
          '*Publication:*',
          '`/post publish <texte>` — Publier directement',
          '`/post history` — Historique',
          '',
          '*Interactions:*',
          '`/post comment <url> <texte>` — Commenter',
          '`/post routine` — Statut routine du jour',
          '`/post notif` — Notifications',
          '',
          '*Scheduler:*',
          '`/post scheduler` — Statut du daemon',
          '`/post scheduler start` — Demarrer le daemon',
          '`/post scheduler stop` — Arreter le daemon',
          '',
          `Pipeline: Cluster M1+OL1+M2 → Validation → Playwright MCP`,
        ].join('\n'), 'Markdown');
      }
    }

    case '/tghistory': {
      const limit = parseInt(args) || 20;
      const recent = messageHistory.slice(-limit);
      if (recent.length === 0) return sendMessage(chatId, 'Aucun message en mémoire.');
      const lines = ['*Derniers messages*', ''];
      for (const m of recent) {
        const ts = new Date(m.date * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        lines.push(`[${ts}] ${(m.text || '').slice(0, 80)}`);
      }
      return sendMessage(chatId, lines.join('\n'), 'Markdown');
    }

    case '/broadcast': {
      if (!isAdmin) return sendMessage(chatId, 'Admin only.');
      if (!args) return sendMessage(chatId, 'Usage: `/broadcast <message>`', 'Markdown');
      try {
        const body = JSON.stringify({ chat_id: CHAT_ID, text: args });
        const res = await httpRequest(`http://127.0.0.1:9742/api/telegram/send`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000,
        }, body);
        const data = JSON.parse(res.body);
        return sendMessage(chatId, data.ok ? '✅ Message envoyé via API.' : '⚠️ ' + (data.error || 'erreur'));
      } catch (e) {
        return sendMessage(chatId, '🔴 Erreur broadcast: ' + e.message);
      }
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
  const helper = path.join(__dirname, 'bot-helpers.py');
  try {
    const result = execSync(`python "${helper}" scan-stats`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    const l = d.last;
    const lines = [
      '*Scanner Stats*',
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
    try {
      const ps = execSync('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH', { encoding: 'utf-8', timeout: 5000 });
      const sniperRunning = ps.includes('sniper_scanner');
      lines.push('', sniperRunning ? 'Scanner permanent ACTIF' : 'Scanner permanent INACTIF');
    } catch (e) { /* ignore */ }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, 'Erreur scan stats: ' + e.message.slice(0, 200));
  }
}

async function handleHotCoins(chatId, limit) {
  const helper = path.join(__dirname, 'bot-helpers.py');
  try {
    const result = execSync(`python "${helper}" hot-coins ${limit}`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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
  const helper = path.join(__dirname, 'bot-helpers.py');
  try {
    const result = execSync(`python "${helper}" perf`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const d = JSON.parse(result.trim());
    if (d.total === 0) return sendMessage(chatId, 'Aucun signal tracke pour le moment. Le scanner sniper doit emettre des alertes.');
    const lines = [
      '📈 *Performance Signaux Sniper*',
      '',
      `Total signaux: ${d.total} (${d.open || 0} ouverts)`,
      `TP1: ${d.tp1} (${(d.tp1*100/d.total).toFixed(0)}%)`,
      `TP2: ${d.tp2} (${(d.tp2*100/d.total).toFixed(0)}%)`,
      d.tp3 ? `TP3: ${d.tp3} (${(d.tp3*100/d.total).toFixed(0)}%)` : null,
      `SL: ${d.sl} (${(d.sl*100/d.total).toFixed(0)}%)`,
      `Expires: ${d.expired || 0}`,
      `PnL moyen: ${d.avg_pnl > 0 ? '+' : ''}${(d.avg_pnl || 0).toFixed(2)}%`,
    ];
    if (d.best && d.best.length) {
      lines.push('', '*Meilleurs:*');
      for (const b of d.best) lines.push(`  ${b.s} ${b.d} +${(b.pnl||0).toFixed(2)}% (score ${(b.sc||0).toFixed(0)})`);
    }
    if (d.worst && d.worst.length) {
      lines.push('', '*Pires:*');
      for (const w of d.worst) lines.push(`  ${w.s} ${w.d} ${(w.pnl||0).toFixed(2)}% (score ${(w.sc||0).toFixed(0)})`);
    }
    return sendMessage(chatId, lines.filter(l => l !== null).join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `🔴 Erreur: ${e.message.slice(0, 200)}`);
  }
}

// ─── JARVIS Command Execution ─────────────────────────────────────────────────

const TURBO_ROOT = path.join(__dirname, '..');

async function handleJarvisCommand(chatId, voiceText) {
  try {
    // Match voice command via Python helper
    const helper = path.join(__dirname, 'bot-helpers.py');
    const matchResult = execSync(
      `python "${helper}" match-cmd ${voiceText.replace(/"/g, '').replace(/[&|<>]/g, '').slice(0, 200)}`,
      { timeout: 3000, encoding: 'utf-8', cwd: TURBO_ROOT, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    // Extract JSON line (skip warnings printed to stdout by src.commands)
    const jsonLine = matchResult.trim().split('\n').reverse().find(l => l.startsWith('{'));
    const match = JSON.parse(jsonLine || '{}');

    // Smart threshold: app_open/browser/hotkey need 0.80+, jarvis_tool/powershell need 0.95+
    const actionThreshold = (match.action_type === 'app_open' || match.action_type === 'browser' || match.action_type === 'hotkey') ? 0.80 : 0.95;
    if (!match.name || match.score < actionThreshold) {
      // Fallback: search voice dictionary API (11000+ entries incl. corrections)
      try {
        const dictResp = await fetch(`${WS_API}/api/dictionary/search?q=${encodeURIComponent(voiceText)}&limit=3`);
        const dictData = await dictResp.json();
        const results = dictData.data || dictData.results || [];
        const best = results.find(r => r.action || r.correct || r.steps);
        if (best) {
          const corrected = best.correct || best.name || best.pipeline_id;
          const label = best.action_type || (best.correct ? 'correction' : 'pipeline');
          await sendMessage(chatId, `Dict match: *${corrected}* [${label}]`, 'Markdown');
          if (best.correct) {
            // Re-run with corrected text
            return handleJarvisCommand(chatId, best.correct);
          }
          if (best.action) {
            await sendVoiceReply(chatId, `${corrected} execute`);
            return true;
          }
        }
      } catch (_) { /* dict API unavailable, continue to cluster */ }
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
      // Unhandled action type — don't block, let cluster respond naturally
      log(`  JARVIS: unhandled action_type=${match.action_type}, falling through to cluster`);
      return null;
    }

    return true;
  } catch (e) {
    logErr('JARVIS command failed:', e.message.slice(0, 80));
    return null; // Silently fall through to cluster for a proper response
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
      const usedClean = used.replace(' MiB', '').trim();
      const totalClean = total.replace(' MiB', '').trim();
      const utilClean = util.replace(' %', '').trim();
      lines.push(`${icon} GPU${idx}: ${temp}C | ${usedClean}/${totalClean} MiB | ${utilClean}% | ${name}`);
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
      `python "${path.join(TURBO_ROOT, 'scripts', 'benchmarks', 'improve_loop_100.py')}" --cycles ${cycles} --report-every 5`,
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
    const helper = path.join(__dirname, 'bot-helpers.py');
    const result = execSync(`python "${helper}" realtime`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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
      const helperLoop = path.join(__dirname, 'bot-helpers.py');
      const result = execSync(`python "${helperLoop}" loop-status`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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
    const helperBT = path.join(__dirname, 'bot-helpers.py');
    const result = execSync(`python "${helperBT}" backtest`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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
    const helperMkt = path.join(__dirname, 'bot-helpers.py');
    const result = execSync(`python "${helperMkt}" market`, { timeout: 15000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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

// ─── Dominos (pipeline execution) ────────────────────────────────────────────

async function handleDominos(chatId, name) {
  const helper = path.join(__dirname, 'bot-helpers.py');
  try {
    if (!name) {
      const result = execSync(`python "${helper}" domino-list`, { timeout: 15000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
      const data = JSON.parse(result.trim());
      const s = data.stats;
      const lines = [
        `*Dominos JARVIS* (${s.total_dominos} automatisations, ${s.total_steps} etapes)`,
        '',
        'Tape `/domino <nom>` pour lancer',
        '',
      ];
      const catEntries = Object.entries(data.categories);
      for (const [cat, ids] of catEntries) {
        lines.push(`*${cat}* (${ids.length}+):`);
        lines.push('  ' + ids.map(id => '`' + id + '`').join(', '));
      }
      if (s.categories_count > catEntries.length) lines.push(`\n... et ${s.categories_count - catEntries.length} autres categories`);
      lines.push('', 'Exemples: /domino matin, /domino trading, /domino cleanup');
      return sendMessage(chatId, lines.join('\n'), 'Markdown');
    }

    const safeName = name.replace(/'/g, '').replace(/"/g, '').replace(/;/g, '').slice(0, 100);
    await sendMessage(chatId, `Recherche domino: *${safeName}*...`, 'Markdown');

    const findResult = execSync(`python "${helper}" domino-find "${safeName}"`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
    const found = JSON.parse(findResult.trim());

    if (!found.found) {
      return sendMessage(chatId, `Domino "${safeName}" non trouve. Tapez /domino pour voir la liste.`);
    }

    await sendMessage(chatId, `Lancement: *${found.id}* (${found.category}, ${found.steps} etapes, ${found.priority})...`, 'Markdown');

    const proc = exec(
      `python "${helper}" domino-run "${safeName}"`,
      { timeout: 180000, encoding: 'utf-8', cwd: path.join(__dirname, '..') }
    );

    let output = '';
    proc.stdout.on('data', d => output += d);
    proc.stderr.on('data', d => logErr(`[domino] ${d.trim()}`));
    proc.on('close', async (code) => {
      try {
        const r = JSON.parse(output.trim());
        const icon = r.success ? '✅' : '🔴';
        const stepLines = (r.steps || []).map(s => `  ${s.status === 'PASS' ? '✅' : s.status === 'SKIP' ? '⏭' : '❌'} ${s.name}`).join('\n');
        await sendMessage(chatId, `${icon} *${found.id}*\nResultat: ${r.passed} OK / ${r.failed} KO / ${r.skipped} skip (${(r.duration || 0).toFixed(1)}s)\n${stepLines}`, 'Markdown');
      } catch {
        if (code === 0) {
          await sendMessage(chatId, `Domino *${found.id}* termine.\n${output.slice(0, 2000)}`);
        } else {
          await sendMessage(chatId, `Domino *${found.id}* echoue (code ${code}).\n${output.slice(0, 500)}`);
        }
      }
    });
  } catch (e) {
    return sendMessage(chatId, `Erreur dominos: ${e.message.slice(0, 300)}`);
  }
}

// ─── Dictionary / Voice / Commands / Pipeline handlers ─────────────────────────

const WS_API = 'http://127.0.0.1:9742';

async function handleDictSearch(chatId, query) {
  try {
    if (!query) {
      // Stats globales
      const resp = await fetch(`${WS_API}/api/dictionary/stats`);
      const stats = await resp.json();
      const s = stats.data || stats;
      return sendMessage(chatId, [
        '*Dictionnaire JARVIS*',
        `Commandes vocales: *${s.voice_commands || '?'}*`,
        `Corrections: *${s.voice_corrections || '?'}*`,
        `Pipelines: *${s.pipeline_commands || '?'}*`,
        `Dominos: *${s.domino_chains || '?'}*`,
        `Scenarios: *${s.scenarios || '?'}*`,
        '',
        'Recherche: `/dict <mot>`',
        'Ex: `/dict btc`, `/dict chrome`, `/dict trading`',
      ].join('\n'), 'Markdown');
    }
    // Recherche
    const resp = await fetch(`${WS_API}/api/dictionary/search?q=${encodeURIComponent(query)}&limit=15`);
    const data = await resp.json();
    const results = data.data || data.results || [];
    if (!results.length) return sendMessage(chatId, `Aucun resultat pour "${query}".`);
    const lines = [`*Recherche: "${query}"* (${results.length} resultats)\n`];
    for (const r of results.slice(0, 10)) {
      const name = r.name || r.command || r.pipeline_id || r.wrong || '?';
      const cat = r.category || '';
      const triggers = r.triggers ? (typeof r.triggers === 'string' ? r.triggers : JSON.stringify(r.triggers)).slice(0, 100) : '';
      const correct = r.correct ? ` -> ${r.correct}` : '';
      lines.push(`• *${name}* [${cat}] ${triggers}${correct}`);
    }
    if (results.length > 10) lines.push(`\n... +${results.length - 10} autres`);
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur dict: ${e.message.slice(0, 300)}`);
  }
}

async function handleVoiceCommand(chatId, text) {
  // Envoie la commande vocale via WS backend ou OpenClaw
  try {
    const resp = await fetch(`${WS_API}/api/telegram/forward`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, source: 'telegram-voice-cmd' }),
    });
    // Also forward to OpenClaw for execution
    try {
      const oc = await fetch(`${PROXY_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: `tg-${chatId}` }),
      });
      const data = await oc.json();
      const reply = data.response || data.message || data.text || JSON.stringify(data).slice(0, 1000);
      return sendMessage(chatId, `*Commande:* \`${text}\`\n\n${reply}`, 'Markdown');
    } catch {
      return sendMessage(chatId, `Commande "${text}" envoyee au backend. OpenClaw non disponible pour reponse.`);
    }
  } catch (e) {
    return sendMessage(chatId, `Erreur voice cmd: ${e.message.slice(0, 300)}`);
  }
}

async function handleCmdList(chatId, query) {
  try {
    const resp = await fetch(`${WS_API}/api/dictionary/search?q=${encodeURIComponent(query || 'systeme')}&limit=20`);
    const data = await resp.json();
    const results = (data.data || data.results || []).filter(r => r.action_type || r.action);
    if (!results.length) return sendMessage(chatId, `Aucune commande pour "${query}". Essayez: /cmd navigation, /cmd trading, /cmd systeme`);
    const lines = [`*Commandes "${query || 'systeme'}"* (${results.length})\n`];
    for (const r of results.slice(0, 15)) {
      const name = r.name || r.pipeline_id || '?';
      const desc = (r.description || '').slice(0, 60);
      lines.push(`• \`${name}\` — ${desc}`);
    }
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur cmd: ${e.message.slice(0, 300)}`);
  }
}

async function handlePipelineAction(chatId, query) {
  try {
    if (!query) {
      return sendMessage(chatId, [
        '*Pipelines JARVIS*',
        'Usage: `/pipeline <nom>` pour voir/lancer',
        'Ex: `/pipeline matin`, `/pipeline trading`, `/pipeline cleanup`',
        '',
        'Voir aussi: `/domino` pour les automatisations',
      ].join('\n'), 'Markdown');
    }
    // Search pipeline in dictionary
    const resp = await fetch(`${WS_API}/api/dictionary/search?q=${encodeURIComponent(query)}&limit=5`);
    const data = await resp.json();
    const pipelines = (data.data || data.results || []).filter(r => r.steps || r.action_type === 'pipeline');
    if (!pipelines.length) {
      // Fallback to domino
      return handleDominos(chatId, query);
    }
    const p = pipelines[0];
    const lines = [
      `*Pipeline: ${p.name || p.pipeline_id}*`,
      `Categorie: ${p.category || '?'}`,
      `Steps: \`${(p.steps || '').slice(0, 200)}\``,
      `Type: ${p.action_type || '?'}`,
      '',
      `Lancez avec: \`/voice ${p.name || p.pipeline_id}\``,
    ];
    return sendMessage(chatId, lines.join('\n'), 'Markdown');
  } catch (e) {
    return sendMessage(chatId, `Erreur pipeline: ${e.message.slice(0, 300)}`);
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
  // JARVIS Tools — direct tool invocations via #tags or keywords
  { intent: 'jarvis_tool', rx: /\b(#boot|boot\s*status|statut\s*boot|d[eé]marrage)/i, handler: 'jarvis_tool', tool: 'jarvis_boot_status' },
  { intent: 'jarvis_tool', rx: /\b(#audit|diagnostic\s*(rapide|quick)|diag\s*rapide)/i, handler: 'jarvis_tool', tool: 'jarvis_diagnostics_quick' },
  { intent: 'jarvis_tool', rx: /\b(#health|sant[eé]\s*cluster|cluster\s*health)/i, handler: 'jarvis_tool', tool: 'jarvis_cluster_health' },
  { intent: 'jarvis_tool', rx: /\b(#autonome|boucle\s*autonome|taches?\s*autonome)/i, handler: 'jarvis_tool', tool: 'jarvis_autonomous_status' },
  { intent: 'jarvis_tool', rx: /\b(#alerts?|alerte[s]?\s*active)/i, handler: 'jarvis_tool', tool: 'jarvis_alerts_active' },
  { intent: 'jarvis_tool', rx: /\b(#gpu[\s-]*status|gpu\s*status|statut\s*gpu)/i, handler: 'jarvis_tool', tool: 'jarvis_gpu_status' },
  { intent: 'jarvis_tool', rx: /\b(#db[\s-]*health|sant[eé]\s*base|db\s*health)/i, handler: 'jarvis_tool', tool: 'jarvis_db_health' },
  { intent: 'jarvis_tool', rx: /\b(#orchestr|orchestrat(eur|or)\s*health)/i, handler: 'jarvis_tool', tool: 'jarvis_orchestrator_health' },
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
const MEMORY_MAX = 4;

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
          const helperPath = path.join(__dirname, 'bot-helpers.py');
          exec(`python "${helperPath}" analyze ${coin}`, { timeout: 30000, cwd }, (err, stdout) => {
            let result = `Erreur analyse ${coin}`;
            try {
              const d = JSON.parse((stdout || '').trim());
              result = d.text || result;
            } catch { result = (stdout || '').trim() || result; }
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
          const helperPath = path.join(__dirname, 'bot-helpers.py');
          exec(`python "${helperPath}" compare ${a} ${b}`, { timeout: 45000, cwd }, (err, stdout) => {
            let result = `Erreur comparaison ${a} vs ${b}`;
            try {
              const d = JSON.parse((stdout || '').trim());
              result = d.text || result;
            } catch { result = (stdout || '').trim() || result; }
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

    case 'jarvis_tool': {
      // Route to JARVIS WS tool via /api/tools/execute
      const toolName = intent.tool || 'jarvis_diagnostics_quick';
      await sendMessage(chatId, `Tool ${toolName}...`);
      try {
        const resp = await fetch('http://127.0.0.1:9742/api/tools/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool_name: toolName, arguments: {} }),
          signal: AbortSignal.timeout(15000),
        });
        const data = await resp.json();
        if (data.ok) {
          const result = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
          const truncated = result.length > 3500 ? result.slice(0, 3500) + '...' : result;
          await sendMessage(chatId, `*${toolName}*\n\`\`\`json\n${truncated}\`\`\``, 'Markdown');
          if (VOICE_MODE) sendVoiceReply(chatId, `Tool ${toolName.replace('jarvis_', '')} execute avec succes.`);
        } else {
          await sendMessage(chatId, `Erreur: ${data.error || 'inconnue'}`);
        }
      } catch (e) {
        await sendMessage(chatId, `Tool ${toolName} timeout: ${e.message}`);
      }
      return true;
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
      await sendMessage(chatId, 'Detection gros mouvements...');
      try {
        const helperPath = path.join(__dirname, 'bot-helpers.py');
        const r = execSync(`python "${helperPath}" whales`, { timeout: 15000, encoding: 'utf-8', cwd });
        const rows = JSON.parse(r.trim());
        if (rows.length) {
          const lines = ['*Top mouvements detectes:*'];
          for (const w of rows) {
            lines.push(`  ${w.sym}: score ${w.avg.toFixed(0)} (best ${w.best}) | ${w.dir} | ${w.scans} scans`);
          }
          return sendMessage(chatId, lines.join('\n'), 'Markdown');
        }
        return sendMessage(chatId, 'Aucun mouvement majeur detecte');
      } catch (e) {
        return sendMessage(chatId, 'Erreur detection whales: ' + e.message.slice(0, 100));
      }
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
  return `Tu es JARVIS, assistant de Turbo. LANGUE: FRANCAIS OBLIGATOIRE. JAMAIS d'anglais.
Concis (2-5 phrases). Les messages viennent de transcription vocale (fautes normales, comprends l'intention).
Trading: MEXC Futures 10x, TP 0.4-1.5%, SL 0.25%.
Il est ${hour}h (${period}).`;
}

function queryNode(node, prompt) {
  const sysPromptFull = '/nothink\n' + buildSystemPrompt();
  // OL1 (1.7B) needs a minimal system prompt — no /nothink (Ollama ignores it)
  const sysPromptMini = 'Tu es JARVIS, assistant de Turbo. Francais, concis, 2-5 phrases.';
  const sysPrompt = node.isOllama ? sysPromptMini : sysPromptFull;
  return new Promise((resolve, reject) => {
    const start = Date.now();
    let body, headers;
    if (node.isOllama) {
      body = JSON.stringify({
        model: node.model,
        messages: [{ role: 'system', content: sysPrompt }, { role: 'user', content: prompt }],
        stream: false, think: false, options: { num_predict: 200 }
      });
      headers = { 'Content-Type': 'application/json' };
    } else {
      // LM Studio (OpenAI-compatible) — /nothink in system prompt, max_tokens 256 for speed
      body = JSON.stringify({
        model: node.model,
        messages: [{ role: 'system', content: sysPrompt }, { role: 'user', content: prompt }],
        temperature: 0.3, max_tokens: 150, stream: false
      });
      headers = { 'Content-Type': 'application/json' };
    }
    httpRequest(node.url, { method: 'POST', headers, timeout: node.timeout || 15000 }, body)
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
        if (!text || text.length < 2) return reject(new Error('empty response'));
        // Reject responses that regurgitate the system prompt examples
        if (text.includes('lis me mail') && text.includes('scan treding') && prompt.indexOf('mail') < 0) {
          return reject(new Error('prompt regurgitation'));
        }
        resolve({ text, node: node.id, model: node.model, latency: Date.now() - start });
      })
      .catch(reject);
  });
}

/** Query a single node and return text only (for /model fallback) */
async function queryNodeDirect(node, prompt) {
  const result = await queryNode(node, prompt);
  return result ? result.text : null;
}

async function clusterRace(prompt) {
  // TRUE PARALLEL RACE — all nodes at once, first good response wins
  return new Promise((resolve) => {
    let resolved = false;
    let done = 0;
    const total = CLUSTER_NODES.length;

    CLUSTER_NODES.forEach(node => {
      queryNode(node, prompt)
        .then(r => {
          done++;
          if (r && !resolved) {
            resolved = true;
            log(`  WINNER: [${r.node}] ${r.latency}ms — ${r.text.slice(0, 60)}...`);
            resolve(r);
          }
          if (done === total && !resolved) resolve(null);
        })
        .catch(e => {
          done++;
          log(`  [${node.id}] failed: ${e.message}`);
          if (done === total && !resolved) resolve(null);
        });
    });

    // Safety timeout 10s
    setTimeout(() => { if (!resolved) { resolved = true; resolve(null); } }, 10000);
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

  // 4. Transcribe — try WS backend first (Whisper already loaded in memory = fast)
  let text = '';
  try {
    const wavB64 = fs.readFileSync(tmpWav).toString('base64');
    const postData = JSON.stringify({ audio: wavB64, format: 'wav', language: 'fr' });
    const tmpJson = path.join(os.tmpdir(), `tg_whisper_${Date.now()}.json`);
    fs.writeFileSync(tmpJson, postData);
    const wsResult = execSync(
      `curl -s --max-time 15 -X POST http://127.0.0.1:9742/api/voice/transcribe_blob -H "Content-Type: application/json" -d @"${tmpJson}"`,
      { timeout: 20000, encoding: 'utf-8' }
    );
    try { fs.unlinkSync(tmpJson); } catch (_) {}
    const parsed = JSON.parse(wsResult);
    text = (parsed.text || '').trim();
    if (text) log(`  Whisper via WS (fast)`);
  } catch (e) {
    log(`  WS Whisper failed: ${(e.message || '').slice(0, 80)}`);
  }

  // Fallback: direct venv script (cold start ~20s)
  if (!text) {
    try {
      text = execSync(
        `"${VENV_PYTHON}" "F:/BUREAU/turbo/scripts/transcribe.py" "${tmpWav}" --language fr`,
        { timeout: 30000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
      ).trim();
      if (text) log(`  Whisper via script (fallback)`);
    } catch (_) {
      text = '[Transcription indisponible]';
    }
  }

  // Cleanup
  try { fs.unlinkSync(tmpOgg); } catch (_) {}
  try { fs.unlinkSync(tmpWav); } catch (_) {}

  return text || '[Audio vide]';
}

// ─── Voice: send response as Telegram voice message ──────────────────────────

async function sendVoiceReply(chatId, text) {
  try {
    const cleanText = text.replace(/[\r\n]+/g, ' ').replace(/"/g, '').replace(/'/g, '').slice(0, 500);
    if (!cleanText.trim()) return false;

    // Non-blocking: spawn TTS in background (don't block the event loop)
    const { spawn } = require('child_process');
    const child = spawn(VENV_PYTHON, [TTS_SCRIPT, '--speak', cleanText, '--telegram'], {
      cwd: path.join(__dirname, '..'),
      stdio: 'ignore',
      timeout: 25000,
    });
    child.on('close', (code) => {
      if (code === 0) {
        log(`  VOICE sent via DeniseNeural`);
        stats.messages_out++;
      } else {
        logErr(`  VOICE TTS exited with code ${code}`);
      }
    });
    child.on('error', (e) => logErr('TTS spawn error:', e.message));
    return true;
  } catch (e) {
    logErr('sendVoiceReply failed:', e.message.slice(0, 100));
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

  // Commande spéciale ?
  if (text.startsWith('/')) {
    const spaceIdx = text.indexOf(' ');
    const cmd = spaceIdx > 0 ? text.slice(0, spaceIdx).toLowerCase() : text.toLowerCase();
    const args = spaceIdx > 0 ? text.slice(spaceIdx + 1).trim() : '';
    const handled = await handleCommand(chatId, cmd, args, isAdmin);
    if (handled !== null) return;
  }

  // ── Direct to cluster — no intermediate routing for speed ──
  let reply = '';
  let model = '';
  const start = Date.now();

  // Minimal context — only last exchange to keep input tokens low
  const memMsgs = getMemoryMessages(chatId);
  let enrichedPrompt = text;
  if (memMsgs.length > 0) {
    const last2 = memMsgs.slice(-2);
    const ctx = last2.map(m => `${m.role}: ${m.content}`).join('\n');
    enrichedPrompt = `${ctx}\nuser: ${text}`;
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

  // Send text IMMEDIATELY, voice in parallel (don't block response)
  const textPromise = sendMessage(chatId, reply + attr, 'Markdown');

  // TTS only when user sent a vocal — text replies stay text-only for speed
  if (isVoice && reply.length < 1500) {
    sendVoiceReply(chatId, reply).catch(e => logErr('Voice:', e.message));
  }

  await textPromise;
}

// ─── Inline Keyboard Menu ────────────────────────────────────────────────────

async function sendMenuKeyboard(chatId) {
  const keyboard = {
    inline_keyboard: [
      // Row 1: Cluster
      [
        { text: '🟢 Cluster', callback_data: 'cmd_status' },
        { text: '📊 Health', callback_data: 'cmd_health' },
        { text: '🎮 GPU', callback_data: 'cmd_gpu' },
      ],
      // Row 2: Trading
      [
        { text: '📈 Marche', callback_data: 'cmd_market' },
        { text: '🎯 Scan', callback_data: 'cmd_scan' },
        { text: '🔥 Coins Chauds', callback_data: 'cmd_hot' },
      ],
      // Row 3: Signaux
      [
        { text: '💹 Signaux', callback_data: 'cmd_signals' },
        { text: '📉 Resultats', callback_data: 'cmd_perf' },
        { text: '🔬 Deep Scan', callback_data: 'cmd_deepscan' },
      ],
      // Row 4: Outils
      [
        { text: '🎲 Dominos', callback_data: 'cmd_dominos' },
        { text: '📖 Dict', callback_data: 'cmd_dict' },
        { text: '🔁 Loop', callback_data: 'cmd_loop' },
      ],
      // Row 5: Systeme
      [
        { text: '💾 Disque', callback_data: 'cmd_disk' },
        { text: TRADING_ALERTS ? '🔕 Alertes OFF' : '🔔 Alertes ON', callback_data: TRADING_ALERTS ? 'cmd_alertoff' : 'cmd_alerton' },
        { text: '❓ Aide', callback_data: 'cmd_help' },
      ],
    ]
  };
  await telegramAPI('sendMessage', {
    chat_id: chatId,
    text: `*JARVIS Dashboard*\nAlertes: ${TRADING_ALERTS ? '🟢 ON' : '🔴 OFF'}\nChoisissez une action:`,
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
    case 'cmd_status': return handleCommand(chatId, '/status', '', isAdmin);
    case 'cmd_health': return handleCommand(chatId, '/health', '', isAdmin);
    case 'cmd_help': return handleCommand(chatId, '/help', '', isAdmin);
    case 'cmd_realtime': return handleRealtimeStatus(chatId);
    case 'cmd_perf': return handlePerformance(chatId);
    case 'cmd_market': return handleMarketSummary(chatId);
    case 'cmd_hot': return handleHotCoins(chatId, 10);
    case 'cmd_loop': return handleLoopStatus(chatId);
    case 'cmd_gpu': return handleGpuStatus(chatId);
    case 'cmd_scan': return handleSniperScan(chatId, 50);
    case 'cmd_backtest': return handleBacktestResults(chatId);
    case 'cmd_menu': return sendMenuKeyboard(chatId);
    case 'cmd_deepscan': return handleDeepScan(chatId, 10);
    case 'cmd_signals': return handleOpenSignals(chatId);
    case 'cmd_dominos': return handleDominos(chatId);
    case 'cmd_dict': return handleDictSearch(chatId, '');
    case 'cmd_disk': return handleCommand(chatId, '/disk', '', isAdmin);
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
    const helperAlerts = path.join(__dirname, 'bot-helpers.py');
    const result = execSync(`python "${helperAlerts}" proactive-alerts`, { timeout: 10000, encoding: 'utf-8', cwd: path.join(__dirname, '..') });
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
      notifiedSignals.clear();
      arr.slice(-100).forEach(id => notifiedSignals.add(id));
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

  // Clear webhook + pending updates to prevent Conflict errors
  try {
    await telegramAPI('deleteWebhook', { drop_pending_updates: true });
    log('Webhook cleared + pending updates dropped');
  } catch (e) {
    log('deleteWebhook skipped: ' + e.message);
  }

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
    log('⚠️  Proxy non joignable — le bot démarrera quand même (fallback direct cluster)');
  }

  // Enregistre les commandes dans le menu Telegram
  try {
    await telegramAPI('setMyCommands', {
      commands: [
        // Les plus utilises en premier
        { command: 'menu', description: 'Ouvrir le dashboard (boutons)' },
        { command: 'ask', description: 'Poser une question au cluster IA' },
        { command: 'market', description: 'Prix BTC + tendance + top movers' },
        { command: 'scan', description: 'Scanner rapide top 50 coins' },
        { command: 'hot', description: 'Coins les plus chauds du moment' },
        { command: 'signals', description: 'Mes signaux ouverts' },
        { command: 'dict', description: 'Rechercher dans le dictionnaire vocal (11000+ entrees)' },
        { command: 'cmd', description: 'Lister les commandes par categorie' },
        { command: 'pipeline', description: 'Voir/lancer un pipeline d\'actions' },
        { command: 'domino', description: 'Lancer une automatisation (401 dispo)' },
        // Trading avance
        { command: 'deepscan', description: 'Scanner profond 800+ coins' },
        { command: 'perf', description: 'Resultats: combien de TP/SL touches' },
        { command: 'compare', description: 'Comparer 2 coins (ex: BTC SOL)' },
        { command: 'whales', description: 'Gros mouvements detectes' },
        { command: 'news', description: 'Actus crypto du jour' },
        { command: 'backtest', description: 'Resultats des backtests' },
        { command: 'alerton', description: 'Activer les alertes trading' },
        { command: 'alertoff', description: 'Couper les alertes trading' },
        // Cluster & Systeme
        { command: 'status', description: 'Quels noeuds IA sont en ligne' },
        { command: 'consensus', description: 'Question a tous les noeuds (vote)' },
        { command: 'model', description: 'Forcer un noeud precis (M1/OL1...)' },
        { command: 'gpu', description: 'Temperatures GPU' },
        { command: 'disk', description: 'Espace disque libre' },
        { command: 'ping', description: 'Le bot repond-il? (test rapide)' },
        { command: 'sniper', description: 'Le scanner tourne-t-il?' },
        { command: 'loop', description: 'Amelioration auto en cours?' },
        { command: 'scanstats', description: 'Statistiques du scanner' },
        { command: 'realtime', description: 'Scanner temps reel' },
        { command: 'stats', description: 'Chiffres du bot' },
        { command: 'post', description: 'LinkedIn: generer, publier, commenter' },
        { command: 'help', description: 'Liste de toutes les commandes' },
      ]
    });
    log('Commandes Telegram enregistrees (26 commandes)');
  } catch (e) {
    logErr('setMyCommands failed:', e.message);
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
