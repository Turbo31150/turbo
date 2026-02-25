// JARVIS Canvas — Direct Cluster Proxy (no OpenClaw dependency)
// Replaces chat-proxy.js by calling LM Studio / Ollama / Gemini / Claude directly
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const AutolearnEngine = require('./autolearn');

const PORT = 18800;
const CANVAS_HTML = path.join(__dirname, 'index.html');

// ── Cluster nodes ───────────────────────────────────────────────────────────
const NODES = {
  M2: {
    url: 'http://192.168.1.26:1234/v1/chat/completions',
    auth: 'Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4',
    model: 'deepseek-coder-v2-lite-instruct',
    timeout: 60000,
    name: 'M2/deepseek'
  },
  M3: {
    url: 'http://192.168.1.113:1234/v1/chat/completions',
    auth: 'Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux',
    model: 'mistral-7b-instruct-v0.3',
    timeout: 60000,
    name: 'M3/mistral'
  },
  OL1: {
    url: 'http://127.0.0.1:11434/api/chat',
    model: 'qwen3:1.7b',
    timeout: 30000,
    name: 'OL1/qwen3',
    isOllama: true
  },
  M1: {
    url: 'http://10.5.0.2:1234/v1/chat/completions',
    auth: 'Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7',
    model: 'qwen/qwen3-30b-a3b-2507',
    timeout: 120000,
    name: 'M1/qwen3-30b'
  }
};

// ── Routing: agent category → primary node, fallbacks ───────────────────────
const ROUTING = {
  code:    ['M2', 'M3', 'OL1'],       // code, debug, review, devops
  archi:   ['M2', 'M3', 'OL1'],       // architecture, database, perf
  trading: ['OL1', 'M2', 'M3'],       // trading, market data
  system:  ['M3', 'M2', 'OL1'],       // windows, cluster, maintenance
  auto:    ['M3', 'OL1', 'M2'],       // pipelines, cron, workflows
  ia:      ['M2', 'M3', 'OL1'],       // consensus, reasoning, analysis
  creat:   ['M2', 'M3', 'OL1'],       // creative, docs, translation
  sec:     ['M2', 'M3', 'OL1'],       // security, audit
  web:     ['OL1', 'M2', 'M3'],       // search, browser
  media:   ['M3', 'OL1', 'M2'],       // voice, image
  meta:    ['OL1', 'M3', 'M2'],       // help, config
  default: ['M2', 'M3', 'OL1']        // fallback
};

// Agent → category mapping (mirrors canvas ROUTES)
const AGENT_CAT = {
  'coding': 'code', 'debug-detective': 'code', 'm2-review': 'code', 'devops-ci': 'code',
  'gemini-pro': 'archi', 'data-analyst': 'archi',
  'trading-scanner': 'trading', 'pipeline-trading': 'trading',
  'windows': 'system', 'pipeline-monitor': 'system', 'pipeline-maintenance': 'system',
  'pipeline-modes': 'auto', 'pipeline-routines': 'auto',
  'consensus-master': 'ia', 'claude-reasoning': 'ia', 'recherche-synthese': 'ia',
  'creative-brainstorm': 'creat', 'doc-writer': 'creat', 'translator': 'creat',
  'securite-audit': 'sec',
  'ol1-web': 'web', 'pipeline-comet': 'web',
  'voice-assistant': 'media', 'gemini-flash': 'media',
  'main': 'default', 'fast-chat': 'default'
};

// ── System prompts by category ──────────────────────────────────────────────
const SYS_PROMPTS = {
  code:    'Tu es JARVIS, assistant IA expert en code. Reponds en francais. Sois concis et direct. Donne du code quand c\'est pertinent.',
  archi:   'Tu es JARVIS, architecte logiciel senior. Reponds en francais. Analyse les trade-offs et propose des solutions pragmatiques.',
  trading: 'Tu es JARVIS, analyste trading crypto. Reponds en francais. Analyse technique, signaux, gestion du risque. Sois factuel.',
  system:  'Tu es JARVIS, expert systeme Windows et administration cluster. Reponds en francais. Commandes PowerShell quand utile.',
  auto:    'Tu es JARVIS, expert automatisation et pipelines. Reponds en francais. Configure, deploie, automatise.',
  ia:      'Tu es JARVIS, assistant IA polyvalent. Reponds en francais. Raisonne etape par etape quand necessaire.',
  creat:   'Tu es JARVIS, assistant creatif et redacteur. Reponds en francais. Sois original et structure.',
  sec:     'Tu es JARVIS, expert cybersecurite. Reponds en francais. Identifie les vulnerabilites, propose des correctifs.',
  web:     'Tu es JARVIS, assistant recherche web. Reponds en francais. Synthese claire des informations.',
  media:   'Tu es JARVIS, assistant multimedia. Reponds en francais.',
  meta:    'Tu es JARVIS, assistant IA polyvalent. Reponds en francais. Aide, explique, guide.',
  default: 'Tu es JARVIS, assistant IA polyvalent. Reponds en francais. Sois concis et utile.'
};

// ── Autolearn Engine ────────────────────────────────────────────────────────
const autolearn = new AutolearnEngine(callNode, ROUTING, SYS_PROMPTS);

// ── HTTP helper ─────────────────────────────────────────────────────────────
function httpRequest(urlStr, body, headers, timeout) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const mod = url.protocol === 'https:' ? https : http;
    const opts = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      timeout,
      headers: { 'Content-Type': 'application/json', ...headers }
    };
    const data = JSON.stringify(body);
    opts.headers['Content-Length'] = Buffer.byteLength(data);

    const req = mod.request(opts, res => {
      let buf = '';
      res.on('data', c => buf += c);
      res.on('end', () => {
        if (res.statusCode >= 400) reject(new Error(`HTTP ${res.statusCode}: ${buf.slice(0, 200)}`));
        else { try { resolve(JSON.parse(buf)); } catch (e) { resolve(buf); } }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(data);
    req.end();
  });
}

// ── Call a single node ──────────────────────────────────────────────────────
async function callNode(nodeId, messages) {
  const node = NODES[nodeId];
  if (!node) throw new Error('Unknown node: ' + nodeId);

  const headers = {};
  if (node.auth) headers['Authorization'] = node.auth;

  if (node.isOllama) {
    // Ollama API format
    const body = {
      model: node.model,
      messages,
      stream: false,
      think: false
    };
    const res = await httpRequest(node.url, body, headers, node.timeout);
    const text = res.message?.content || '';
    return { text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: 'ollama' };
  } else {
    // OpenAI-compatible (LM Studio)
    const body = {
      model: node.model,
      messages,
      temperature: 0.3,
      max_tokens: 4096,
      stream: false
    };
    const res = await httpRequest(node.url, body, headers, node.timeout);
    const text = res.choices?.[0]?.message?.content || '';
    return { text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: 'lm-studio' };
  }
}

// ── Route and call with fallback ────────────────────────────────────────────
async function routeAndCall(agentId, userText) {
  const cat = AGENT_CAT[agentId] || 'default';
  const chain = ROUTING[cat] || ROUTING.default;
  let sysProm = SYS_PROMPTS[cat] || SYS_PROMPTS.default;

  // Autolearn: inject memory context into system prompt
  const ctxInjection = autolearn.getContextInjection(cat);
  if (ctxInjection) sysProm = sysProm + '\n' + ctxInjection;

  const messages = [
    { role: 'system', content: sysProm },
    { role: 'user', content: userText }
  ];

  const errors = [];
  for (const nodeId of chain) {
    try {
      console.log(`[chat] ${agentId} (${cat}) -> ${nodeId}/${NODES[nodeId].model}`);
      const t0 = Date.now();
      const result = await callNode(nodeId, messages);
      const latencyMs = Date.now() - t0;
      console.log(`[chat] OK from ${nodeId} (${result.text.length} chars, ${latencyMs}ms)`);

      // Autolearn: record + background quality scoring
      const entry = {
        agent: agentId, category: cat, userText, responseText: result.text,
        nodeId, latencyMs, ts: new Date().toISOString()
      };
      autolearn.scoreResponse(entry).then(q => {
        entry.quality = q;
        autolearn.recordConversation(entry);
      }).catch(() => {
        entry.quality = 5;
        autolearn.recordConversation(entry);
      });

      return result;
    } catch (e) {
      console.log(`[chat] ${nodeId} FAILED: ${e.message}`);
      errors.push(`${nodeId}: ${e.message}`);

      // Autolearn: record failure
      autolearn.recordConversation({
        agent: agentId, category: cat, userText, responseText: '',
        nodeId, latencyMs: 0, ts: new Date().toISOString(), error: true
      });
    }
  }
  throw new Error('All nodes failed: ' + errors.join(' | '));
}

// ── Health check: ping all nodes ────────────────────────────────────────────
async function healthCheck() {
  const checks = [
    { name: 'OL1', url: 'http://127.0.0.1:11434/api/tags' },
    { name: 'M2', url: 'http://192.168.1.26:1234/v1/models', headers: { Authorization: NODES.M2.auth } },
    { name: 'M3', url: 'http://192.168.1.113:1234/v1/models', headers: { Authorization: NODES.M3.auth } },
    { name: 'M1', url: 'http://10.5.0.2:1234/v1/models', headers: { Authorization: NODES.M1.auth } }
  ];

  const results = await Promise.all(checks.map(n => {
    return new Promise(resolve => {
      const start = Date.now();
      const url = new URL(n.url);
      const opts = { hostname: url.hostname, port: url.port, path: url.pathname, method: 'GET', timeout: 4000, headers: n.headers || {} };
      const r = http.request(opts, res => {
        let d = '';
        res.on('data', c => d += c);
        res.on('end', () => resolve({ name: n.name, ok: res.statusCode === 200, latency: Date.now() - start }));
      });
      r.on('error', () => resolve({ name: n.name, ok: false, latency: 0 }));
      r.on('timeout', () => { r.destroy(); resolve({ name: n.name, ok: false, latency: 0 }); });
      r.end();
    });
  }));

  return { ok: results.some(r => r.ok), proxy: 'direct-proxy', port: PORT, nodes: results };
}

// ── HTTP Server ─────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.method === 'POST' && req.url === '/chat') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const { agent, text } = JSON.parse(body);
        const agentId = agent || 'main';
        const result = await routeAndCall(agentId, text);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, data: result }));
      } catch (e) {
        console.error('[chat] Error:', e.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
  } else if (req.method === 'GET' && req.url === '/health') {
    try {
      const h = await healthCheck();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(h));
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, proxy: 'direct-proxy', error: e.message }));
    }
  } else if (req.method === 'GET' && req.url === '/cluster') {
    try {
      const h = await healthCheck();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, nodes: h.nodes }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
  } else if (req.method === 'GET' && req.url === '/autolearn/status') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getStatus()));
  } else if (req.method === 'GET' && req.url === '/autolearn/memory') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getMemory()));
  } else if (req.method === 'GET' && req.url === '/autolearn/scores') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getScores()));
  } else if (req.method === 'GET' && req.url === '/autolearn/history') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getHistory()));
  } else if (req.method === 'POST' && req.url === '/autolearn/trigger') {
    try {
      const result = await autolearn.triggerReview();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
  } else if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
    // Serve canvas HTML
    try {
      const html = fs.readFileSync(CANVAS_HTML, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch (e) {
      res.writeHead(500);
      res.end('Cannot read index.html: ' + e.message);
    }
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`JARVIS Direct Proxy on http://127.0.0.1:${PORT}`);
  console.log('Nodes: M2(deepseek), M3(mistral), OL1(qwen3), M1(qwen3-30b)');
  console.log('Zero OpenClaw dependency');
  autolearn.start();
  console.log('Autolearn engine started — 3 pillars active');
});
