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
const TTS_SCRIPT = 'C:/Users/franc/.openclaw/workspace/dev/win_tts.py';
const VOICE_MODE = true; // Toujours répondre en vocal
const CLUSTER_RACE = true; // Utiliser tout le cluster en parallèle

// ─── Cluster nodes (direct, sans passer par le proxy) ─────────────────────────
const CLUSTER_NODES = [
  { id: 'gpt-oss', url: 'http://127.0.0.1:11434/api/chat', model: 'gpt-oss:120b-cloud', isOllama: true, weight: 1.9 },
  { id: 'M1', url: 'http://127.0.0.1:1234/v1/chat/completions', model: 'qwen3-8b', weight: 1.8 },
  { id: 'devstral', url: 'http://127.0.0.1:11434/api/chat', model: 'devstral-2:123b-cloud', isOllama: true, weight: 1.5 },
  { id: 'M2', url: 'http://192.168.1.26:1234/v1/chat/completions', model: 'deepseek-coder-v2-lite-instruct', weight: 1.4 },
  { id: 'OL1', url: 'http://127.0.0.1:11434/api/chat', model: 'qwen3:1.7b', isOllama: true, weight: 1.3 },
];

if (!TOKEN) { console.error('[FATAL] TELEGRAM_TOKEN manquant dans .env'); process.exit(1); }
if (!CHAT_ID) { console.error('[FATAL] TELEGRAM_CHAT manquant dans .env'); process.exit(1); }

// ─── State ────────────────────────────────────────────────────────────────────

let offset = 0;
let running = true;
let stats = { started: new Date().toISOString(), messages_in: 0, messages_out: 0, errors: 0 };
let messageHistory = []; // derniers messages reçus (max 50)

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

/** POST vers canvas proxy /chat */
async function proxyChat(text, agentId = 'telegram') {
  const body = JSON.stringify({ agent: agentId, text });
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

async function handleCommand(chatId, cmd, args) {
  switch (cmd) {
    case '/start':
    case '/help':
      return sendMessage(chatId, [
        '🤖 *JARVIS Telegram Bot*',
        '',
        'Commandes:',
        '`/status` — Health check cluster',
        '`/health` — État détaillé des nœuds',
        '`/consensus <question>` — Vote pondéré multi-nœuds',
        '`/model <id> <question>` — Forcer un nœud (M1/M2/OL1...)',
        '`/stats` — Statistiques du bot',
        '`/help` — Cette aide',
        '',
        'Texte libre → dispatch automatique via routing intelligent.',
      ].join('\n'), 'Markdown');

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
        '📈 *Bot Stats*',
        `Démarré: ${stats.started}`,
        `Messages reçus: ${stats.messages_in}`,
        `Messages envoyés: ${stats.messages_out}`,
        `Erreurs: ${stats.errors}`,
      ].join('\n'), 'Markdown');

    default:
      return null; // pas une commande reconnue
  }
}

// ─── Cluster Race — Query all nodes in parallel, first good response wins ─────

function queryNode(node, prompt) {
  const sysPrompt = 'Tu es JARVIS, assistant IA. Reponds en francais, concis et utile. Max 300 mots.';
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
  const { execSync } = require('child_process');
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

async function sendVoiceReply(chatId, text) {
  try {
    const { execSync } = require('child_process');
    const result = execSync(
      `python "${TTS_SCRIPT}" --speak "${text.replace(/"/g, '\\"').slice(0, 2000)}" --telegram`,
      { timeout: 30000, encoding: 'utf-8', cwd: path.dirname(TTS_SCRIPT), stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const data = JSON.parse(result.trim());
    if (data.ok) {
      log(`  VOICE sent: ${data.duration}s OGG via DeniseNeural`);
      stats.messages_out++;
      return true;
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

  // Sécurité : ne répondre qu'au chat autorisé
  if (String(chatId) !== String(CHAT_ID)) {
    log(`Message ignoré de chat non autorisé: ${chatId} (${from})`);
    return;
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
  messageHistory.push({ from, text, ts: new Date().toISOString(), voice: isVoice });
  if (messageHistory.length > 50) messageHistory.shift();

  log(`[${from}] ${text.slice(0, 80)}${text.length > 80 ? '...' : ''}`);

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
    const handled = await handleCommand(chatId, cmd, args);
    if (handled !== null) return;
  }

  // ── Dispatch: cluster race (all nodes parallel) ou proxy fallback ──
  let reply = '';
  let model = '';
  const start = Date.now();

  if (CLUSTER_RACE) {
    log(`  CLUSTER RACE: dispatching to ${CLUSTER_NODES.length} nodes...`);
    const result = await clusterRace(text);
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

  // ── Send response: voice (preferred) + text fallback ──
  if (VOICE_MODE) {
    // Send voice reply via TTS
    const voiceSent = await sendVoiceReply(chatId, reply);
    // Also send text with attribution (for reading)
    const attr = model ? `\n\n_[${model}] ${totalMs}ms_` : '';
    await sendMessage(chatId, reply + attr, 'Markdown');
  } else {
    const attr = model ? `\n\n_[${model}] ${totalMs}ms_` : '';
    await sendMessage(chatId, reply + attr, 'Markdown');
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
        allowed_updates: ['message'],
      });

      for (const update of updates) {
        offset = update.update_id + 1;
        if (update.message) {
          // Process sans bloquer le polling (fire and forget avec catch)
          processMessage(update.message).catch(e => logErr('processMessage:', e.message));
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

  // Notifie l'utilisateur
  await sendMessage(CHAT_ID, '🤖 JARVIS Telegram Bot démarré. Envoyez /help pour les commandes.');

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
