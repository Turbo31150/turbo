// JARVIS Canvas — Direct Cluster Proxy v2 (Cockpit Autonome)
// Chat conversationnel + Tool Engine + Boucle Agentique
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execFileSync, execSync, spawn } = require('child_process');
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

// ══════════════════════════════════════════════════════════════════════════════
// ══ TOOL ENGINE — 10 tools systeme pour le cockpit autonome ══════════════════
// ══════════════════════════════════════════════════════════════════════════════

const ETOILE_DB = path.join(__dirname, '..', 'etoile.db');
const MAX_FILE_SIZE = 100 * 1024;
const MAX_TOOL_TURNS = 15;

// ── Load etoile.db schemas at startup ──────────────────────────────────────
let ETOILE_SCHEMAS = '';
try {
  const schemaTables = execSync('sqlite3 "' + ETOILE_DB + '" ".tables"', {
    encoding: 'utf8', timeout: 3000, windowsHide: true
  }).trim().split(/\s+/).filter(Boolean);
  const schemaLines = [];
  for (const t of schemaTables) {
    const schema = execSync('sqlite3 "' + ETOILE_DB + '" ".schema ' + t + '"', {
      encoding: 'utf8', timeout: 3000, windowsHide: true
    }).trim();
    if (schema) schemaLines.push('-- Table: ' + t + '\n' + schema);
  }
  ETOILE_SCHEMAS = schemaLines.join('\n\n');
  console.log('[etoile] Schemas loaded: ' + schemaTables.length + ' tables (' + schemaTables.join(', ') + ')');
} catch (e) {
  console.warn('[etoile] Schema extraction failed:', e.message);
}

// ── Load etoile.db summary at startup ────────────────────────────────────────
let ETOILE_SUMMARY = '';
try {
  const countByType = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT entity_type, COUNT(*) FROM map GROUP BY entity_type ORDER BY COUNT(*) DESC;"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();
  const launchers = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT entity_name, role FROM map WHERE entity_type=\'launcher\';"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();
  const skills = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT entity_name, role FROM map WHERE entity_type=\'skill\' LIMIT 30;"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();
  const agents = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT name, model, status FROM agents;"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();
  const apiKeyCount = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT COUNT(*) FROM api_keys;"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();
  const memoryCount = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT COUNT(*) FROM memories;"', {
    timeout: 5000, encoding: 'utf8', windowsHide: true
  }).trim();

  ETOILE_SUMMARY = [
    '\n=== BASE DE DONNEES etoile.db ===',
    'Contenu: ' + countByType.split('\n').map(l => { const p = l.split('|'); return p[1] + ' ' + p[0]; }).join(', '),
    apiKeyCount + ' cles API, ' + memoryCount + ' memories',
    '',
    'LAUNCHERS (executables via pipeline tool):',
    launchers.split('\n').map(l => { const p = l.split('|'); return '- ' + p[0] + ': ' + (p[1] || ''); }).join('\n'),
    '',
    'SKILLS (modes et routines):',
    skills.split('\n').map(l => { const p = l.split('|'); return '- ' + p[0] + ': ' + (p[1] || ''); }).join('\n'),
    '',
    'AGENTS IA:',
    agents.split('\n').map(l => { const p = l.split('|'); return '- ' + p[0] + ' (' + (p[1] || '?') + ') — ' + (p[2] || '?'); }).join('\n'),
    '',
    'Pour explorer etoile.db: utilise query_db avec SQL (tables: map, agents, api_keys, memories, metrics, sessions)',
    'Pour lancer un launcher/script: utilise pipeline avec le nom exact',
    '',
    '=== DB SCHEMAS (etoile.db) ===',
    ETOILE_SCHEMAS,
    'IMPORTANT: Utilise UNIQUEMENT les colonnes listees ci-dessus pour query_db. Ne devine JAMAIS les noms de colonnes.'
  ].join('\n');
  console.log('[etoile] Loaded summary: ' + countByType.split('\n').length + ' types, ' + launchers.split('\n').length + ' launchers');
} catch (e) {
  console.error('[etoile] Failed to load summary:', e.message);
  ETOILE_SUMMARY = '\n[etoile.db non disponible — utilise query_db pour explorer]';
}

// ── Safety Gate ─────────────────────────────────────────────────────────────
const DANGEROUS_EXEC = /\b(rm\s+-rf|del\s+\/[sfq]|rmdir\s+\/s|format\s|fdisk|drop\s+table|truncate\s|push\s+--force|reset\s+--hard|shutdown|restart-computer)\b/i;
const DANGEROUS_WRITE = /\.(env|credentials|pem|key|p12)$|system32|\\windows\\/i;
const DANGEROUS_SQL = /\b(DELETE|DROP|TRUNCATE|ALTER|UPDATE)\b/i;

const pendingConfirms = new Map();

function isDangerous(toolName, args) {
  if (toolName === 'delete') return { dangerous: true, reason: 'Suppression de: ' + (args.path || '') };
  if (toolName === 'exec' && DANGEROUS_EXEC.test(args.cmd || ''))
    return { dangerous: true, reason: 'Commande dangereuse: ' + (args.cmd || '') };
  if (toolName === 'write_file' && DANGEROUS_WRITE.test(args.path || ''))
    return { dangerous: true, reason: 'Ecriture sur fichier sensible: ' + (args.path || '') };
  if (toolName === 'query_db' && DANGEROUS_SQL.test(args.sql || ''))
    return { dangerous: true, reason: 'SQL destructif: ' + (args.sql || '') };
  return { dangerous: false };
}

// ── Tool implementations ────────────────────────────────────────────────────
// NOTE: exec uses shell=true intentionally — this is the cockpit's purpose.
// The Safety Gate above filters dangerous patterns before execution.
const TOOLS = {
  exec(args) {
    const cmd = args.cmd || args.command || '';
    if (!cmd) return { error: 'Pas de commande specifiee' };
    try {
      const output = execSync(cmd, {
        timeout: 60000, maxBuffer: 1024 * 1024,
        cwd: args.cwd || 'C:\\Users\\franc',
        encoding: 'utf8', shell: true, windowsHide: true
      });
      return { ok: true, output: output.slice(0, 50000), cmd };
    } catch (e) {
      return { ok: false, error: (e.stderr || e.message || '').slice(0, 5000), exit_code: e.status, cmd };
    }
  },

  read_file(args) {
    const p = args.path;
    if (!p) return { error: 'Pas de chemin specifie' };
    try {
      const stat = fs.statSync(p);
      if (stat.size > MAX_FILE_SIZE) return { error: 'Fichier trop gros: ' + (stat.size/1024).toFixed(0) + 'KB (max 100KB)' };
      return { ok: true, path: p, content: fs.readFileSync(p, 'utf8'), size: stat.size };
    } catch (e) {
      return { ok: false, error: e.message, path: p };
    }
  },

  write_file(args) {
    const p = args.path;
    const content = args.content;
    if (!p || content === undefined) return { error: 'path et content requis' };
    try {
      const dir = path.dirname(p);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(p, content, 'utf8');
      return { ok: true, path: p, size: Buffer.byteLength(content, 'utf8') };
    } catch (e) {
      return { ok: false, error: e.message, path: p };
    }
  },

  edit_file(args) {
    const p = args.path;
    const old_str = args.old || args.old_string;
    const new_str = args.new || args.new_string;
    if (!p || !old_str || new_str === undefined) return { error: 'path, old et new requis' };
    try {
      let content = fs.readFileSync(p, 'utf8');
      if (!content.includes(old_str)) return { ok: false, error: 'Texte a remplacer non trouve' };
      content = content.replace(old_str, new_str);
      fs.writeFileSync(p, content, 'utf8');
      return { ok: true, path: p, replaced: true };
    } catch (e) {
      return { ok: false, error: e.message, path: p };
    }
  },

  list_dir(args) {
    const p = args.path || '.';
    try {
      const entries = fs.readdirSync(p, { withFileTypes: true });
      const items = entries.slice(0, 200).map(e => {
        let size = null;
        if (e.isFile()) { try { size = fs.statSync(path.join(p, e.name)).size; } catch(_) {} }
        return { name: e.name, type: e.isDirectory() ? 'dir' : 'file', size };
      });
      return { ok: true, path: p, count: items.length, items };
    } catch (e) {
      return { ok: false, error: e.message, path: p };
    }
  },

  mkdir(args) {
    const p = args.path;
    if (!p) return { error: 'Pas de chemin specifie' };
    try {
      fs.mkdirSync(p, { recursive: true });
      return { ok: true, path: p, created: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  },

  delete(args) {
    const p = args.path;
    if (!p) return { error: 'Pas de chemin specifie' };
    try {
      const stat = fs.statSync(p);
      if (stat.isDirectory()) fs.rmSync(p, { recursive: true, force: true });
      else fs.unlinkSync(p);
      return { ok: true, path: p, deleted: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  },

  query_db(args) {
    const sql = args.sql;
    const db = args.db || ETOILE_DB;
    if (!sql) return { error: 'Pas de requete SQL' };
    try {
      const safeSql = sql.replace(/"/g, '\\"');
      const output = execSync('sqlite3 -json "' + db + '" "' + safeSql + '"', {
        timeout: 10000, encoding: 'utf8', windowsHide: true
      });
      try { return { ok: true, results: JSON.parse(output), db: path.basename(db) }; }
      catch (_) { return { ok: true, output: output.trim(), db: path.basename(db) }; }
    } catch (e) {
      let hint = '';
      try {
        const tbls = execSync('sqlite3 "' + ETOILE_DB + '" ".tables"', { encoding: 'utf8', timeout: 2000, windowsHide: true }).trim();
        hint = 'Tables disponibles: ' + tbls + '. Verifie les noms de colonnes dans le schema injecte.';
      } catch (_) {}
      return { ok: false, error: (e.stderr || e.message || '').slice(0, 2000), hint };
    }
  },

  pipeline(args) {
    const name = args.name;
    if (!name) return { error: 'Nom du pipeline requis' };
    try {
      const safeName = name.replace(/'/g, "''");
      // Look up in etoile.db map by entity_name (launchers, scripts, skills)
      const row = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT entity_type, entity_name, role, metadata FROM map WHERE entity_name=\'' + safeName + '\' LIMIT 1;"', {
        timeout: 5000, encoding: 'utf8', windowsHide: true
      }).trim();
      if (!row) {
        // Try fuzzy match
        const fuzzy = execSync('sqlite3 "' + ETOILE_DB + '" "SELECT entity_name, entity_type, role FROM map WHERE entity_name LIKE \'%' + safeName + '%\' LIMIT 5;"', {
          timeout: 5000, encoding: 'utf8', windowsHide: true
        }).trim();
        if (fuzzy) return { ok: false, error: "'" + name + "' non trouve. Suggestions:\n" + fuzzy, pipeline: name };
        return { ok: false, error: "Pipeline '" + name + "' non trouve dans etoile.db", pipeline: name };
      }
      const parts = row.split('|');
      const entityType = parts[0];
      const entityName = parts[1];
      const role = parts[2] || '';
      let meta = {};
      try { meta = JSON.parse(parts[3] || '{}'); } catch (_) {}

      // Launchers: .bat files in launchers/ — launched detached (non-blocking)
      if (entityType === 'launcher') {
        const batPath = 'F:\\BUREAU\\turbo\\launchers\\' + entityName + '.bat';
        const exists = fs.existsSync(batPath);
        if (!exists) return { ok: false, pipeline: entityName, type: entityType, role, error: 'Launcher bat non trouve: ' + batPath };
        const child = spawn('cmd', ['/c', batPath], {
          detached: true, stdio: 'ignore', windowsHide: true, cwd: 'F:\\BUREAU\\turbo'
        });
        child.unref();
        return { ok: true, pipeline: entityName, type: entityType, role, command: batPath, output: 'Launcher ' + entityName + ' demarre (PID ' + child.pid + '). Processus detache.' };
      }

      // Scripts: .py in scripts/ or root
      if (entityType === 'script') {
        let scriptPath = 'F:\\BUREAU\\turbo\\scripts\\' + entityName + (entityName.includes('.') ? '' : '.py');
        if (!fs.existsSync(scriptPath)) scriptPath = 'F:\\BUREAU\\turbo\\' + entityName + (entityName.includes('.') ? '' : '.py');
        if (!fs.existsSync(scriptPath)) return { ok: false, pipeline: entityName, type: entityType, role, error: 'Script non trouve: ' + entityName };
        const isJs = scriptPath.endsWith('.js');
        const cmd = isJs ? 'node "' + scriptPath + '"' : 'uv run python "' + scriptPath + '"';
        try {
          const output = execSync(cmd, { timeout: 120000, encoding: 'utf8', windowsHide: true, cwd: 'F:\\BUREAU\\turbo' });
          return { ok: true, pipeline: entityName, type: entityType, role, command: cmd, output: output.slice(0, 20000) };
        } catch (e) {
          return { ok: true, pipeline: entityName, type: entityType, role, command: cmd, output: (e.stdout || '').slice(0, 5000), error: (e.stderr || '').slice(0, 2000) };
        }
      }

      // Other types: return info only
      return { ok: true, pipeline: entityName, type: entityType, role, metadata: meta, info: 'Type ' + entityType + ' — non executable directement. Utilise exec ou query_db.' };
    } catch (e) {
      return { ok: false, error: (e.stderr || e.message || '').slice(0, 2000), pipeline: name };
    }
  }
};

// ── Execute tool (async for web_search) ─────────────────────────────────────
async function executeTool(toolName, args) {
  const safety = isDangerous(toolName, args);
  if (safety.dangerous) {
    const id = 'confirm_' + Date.now();
    pendingConfirms.set(id, { tool: toolName, args });
    setTimeout(() => pendingConfirms.delete(id), 60000);
    return { needs_confirm: true, confirm_id: id, tool: toolName, reason: safety.reason };
  }

  if (toolName === 'web_search') {
    try {
      const query = args.query;
      const messages = [
        { role: 'system', content: 'Reponds en francais. Recherche web et synthese factuelle.' },
        { role: 'user', content: query }
      ];
      const body = { model: 'minimax-m2.5:cloud', messages, stream: false, think: false };
      const res = await httpRequest('http://127.0.0.1:11434/api/chat', body, {}, 30000);
      const text = (res.message?.content || '').replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
      return { ok: true, query, results: text };
    } catch (e) {
      return { ok: false, error: e.message, query: args.query };
    }
  }

  const fn = TOOLS[toolName];
  if (!fn) return { error: 'Tool inconnu: ' + toolName };
  return fn(args);
}

// ── Parse tool calls from AI response ───────────────────────────────────────
// Supports multiple formats:
//   [TOOL:name:args]  [TOOL:name(args)]  [TOOL:name:{json}]
const TOOL_PATTERNS = [
  /\[TOOL:(\w+):\{([\s\S]*?)\}\]/,           // [TOOL:name:{json}]
  /\[TOOL:(\w+):([^\]]+)\]/,                  // [TOOL:name:simple_arg]
  /\[TOOL:(\w+)\(([^)]*)\)\]/,               // [TOOL:name(arg)]
  /\[TOOL:(\w+)\(\{([\s\S]*?)\}\)\]/,        // [TOOL:name({json})]
];

function parseToolCall(text) {
  for (const regex of TOOL_PATTERNS) {
    const m = text.match(regex);
    if (m) {
      const name = m[1];
      let argsStr = m[2].trim();
      // Try JSON parse first
      try {
        if (!argsStr.startsWith('{')) argsStr = '{' + argsStr + '}';
        return { name, args: JSON.parse(argsStr) };
      } catch (_) {
        // Fallback: treat as primary argument
        const raw = m[2].trim();
        if (name === 'exec') return { name, args: { cmd: raw } };
        if (name === 'read_file' || name === 'list_dir' || name === 'mkdir' || name === 'delete')
          return { name, args: { path: raw } };
        if (name === 'query_db') return { name, args: { sql: raw } };
        if (name === 'pipeline') return { name, args: { name: raw } };
        if (name === 'web_search') return { name, args: { query: raw } };
        return { name, args: { value: raw } };
      }
    }
  }
  return null;
}

// ── Agent system prompt with tools ──────────────────────────────────────────
const COCKPIT_TOOLS_PROMPT = [
  '',
  '=== OUTILS SYSTEME (OBLIGATOIRE) ===',
  'Tu as acces au systeme Windows. Pour TOUTE action (lire fichier, lister dossier, executer commande, etc.),',
  'tu DOIS utiliser un outil. NE REPONDS JAMAIS de memoire. Utilise TOUJOURS un outil.',
  '',
  'FORMAT EXACT (une seule ligne, debut de ta reponse):',
  '[TOOL:nom:argument]',
  '',
  'Exemples:',
  '[TOOL:list_dir:C:\\Users\\franc\\Desktop]',
  '[TOOL:exec:dir C:\\Users\\franc\\Desktop]',
  '[TOOL:read_file:F:\\BUREAU\\turbo\\README.md]',
  '[TOOL:write_file:{"path":"C:\\Users\\franc\\Desktop\\test.txt","content":"hello"}]',
  '[TOOL:edit_file:{"path":"fichier.py","old":"ancien","new":"nouveau"}]',
  '[TOOL:mkdir:C:\\Users\\franc\\Desktop\\MonDossier]',
  '[TOOL:delete:C:\\Users\\franc\\Desktop\\test.txt]',
  '[TOOL:query_db:SELECT * FROM map LIMIT 5]',
  '[TOOL:pipeline:trading-scan]',
  '[TOOL:web_search:bitcoin prix aujourd hui]',
  '',
  'REGLES:',
  '- UN SEUL [TOOL:...] par message, TOUJOURS en premiere ligne',
  '- Attends le resultat avant de continuer',
  '- NE FABRIQUE JAMAIS de donnees. Si on demande des fichiers, utilise list_dir ou exec.',
  '- Quand tu as le resultat et que tu as fini, reponds normalement SANS [TOOL:]',
  '- Contexte: Windows 11, user franc, C:\\ et F:\\, JARVIS: F:\\BUREAU\\turbo, Bureau: C:\\Users\\franc\\Desktop',
  ETOILE_SUMMARY
].join('\n');

// ── Agentic loop ────────────────────────────────────────────────────────────
async function agenticChat(agentId, userText) {
  const cat = AGENT_CAT[agentId] || 'default';
  const chain = ROUTING[cat] || ROUTING.default;
  let sysProm = (SYS_PROMPTS[cat] || SYS_PROMPTS.default) + '\n' + COCKPIT_TOOLS_PROMPT;

  const ctxInjection = autolearn.getContextInjection(cat);
  if (ctxInjection) sysProm += '\n' + ctxInjection;

  const messages = [
    { role: 'system', content: sysProm },
    { role: 'user', content: userText }
  ];

  const toolHistory = [];
  let lastModel = null, lastProvider = null;
  const toolFailCount = {};  // anti-loop: { "tool_name": fail_count }
  const MAX_SAME_FAIL = 3;
  let noProgressCount = 0;

  for (let turn = 0; turn < MAX_TOOL_TURNS; turn++) {
    let aiResult, errors = [];
    for (const nodeId of chain) {
      try {
        console.log('[cockpit] turn ' + turn + ' -> ' + nodeId + ' (' + messages.length + ' msgs)');
        const t0 = Date.now();
        aiResult = await callNode(nodeId, messages);
        lastModel = aiResult.model;
        lastProvider = aiResult.provider;
        console.log('[cockpit] OK ' + nodeId + ' (' + aiResult.text.length + ' chars, ' + (Date.now()-t0) + 'ms)');
        break;
      } catch (e) {
        errors.push(nodeId + ': ' + e.message);
      }
    }
    if (!aiResult) throw new Error('All nodes failed: ' + errors.join(' | '));

    const toolCall = parseToolCall(aiResult.text);
    if (!toolCall) {
      return { text: aiResult.text, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1 };
    }

    console.log('[cockpit] TOOL: ' + toolCall.name + '(' + JSON.stringify(toolCall.args).slice(0, 100) + ')');
    const toolResult = await executeTool(toolCall.name, toolCall.args);

    if (toolResult.needs_confirm) {
      return {
        text: aiResult.text, model: lastModel, provider: lastProvider,
        tools_used: toolHistory, turns: turn + 1,
        needs_confirm: true, confirm_id: toolResult.confirm_id, confirm_action: toolResult.reason
      };
    }

    toolHistory.push({ tool: toolCall.name, args: toolCall.args, result: toolResult, turn });

    // Anti-loop: track failures per tool
    if (!toolResult.ok && toolResult.error) {
      toolFailCount[toolCall.name] = (toolFailCount[toolCall.name] || 0) + 1;
      if (toolFailCount[toolCall.name] >= MAX_SAME_FAIL) {
        console.log('[cockpit] ANTI-LOOP: ' + toolCall.name + ' failed ' + MAX_SAME_FAIL + 'x, stopping');
        const stopMsg = '[SYSTEM] STOP: ' + toolCall.name + ' a echoue ' + MAX_SAME_FAIL + ' fois. Ne retente PAS cet outil. Reponds avec ce que tu sais.';
        messages.push({ role: 'assistant', content: aiResult.text });
        messages.push({ role: 'user', content: stopMsg });
        // One last AI turn to wrap up
        for (const nodeId of chain) {
          try {
            const final = await callNode(nodeId, messages);
            return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: true };
          } catch (_) {}
        }
        return { text: stopMsg, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: true };
      }
    } else {
      toolFailCount[toolCall.name] = 0; // reset on success
    }

    // Anti-loop: no progress detection (all tools in this turn failed)
    if (!toolResult.ok && toolResult.error) {
      noProgressCount++;
    } else {
      noProgressCount = 0;
    }
    if (noProgressCount >= 4) {
      console.log('[cockpit] ANTI-LOOP: ' + noProgressCount + ' consecutive failures, forcing stop');
      messages.push({ role: 'assistant', content: aiResult.text });
      messages.push({ role: 'user', content: '[SYSTEM] ' + noProgressCount + ' echecs consecutifs. Reponds maintenant avec ce que tu sais.' });
      for (const nodeId of chain) {
        try {
          const final = await callNode(nodeId, messages);
          return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: true };
        } catch (_) {}
      }
      return { text: '[Anti-loop: trop d\'echecs consecutifs]', model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: true };
    }

    // Build feedback with hint if available
    let feedback = '[TOOL_RESULT:' + toolCall.name + ']\n' + JSON.stringify(toolResult).slice(0, 10000);
    if (toolResult.hint) feedback += '\nHINT: ' + toolResult.hint;

    messages.push({ role: 'assistant', content: aiResult.text });
    messages.push({ role: 'user', content: feedback });
  }

  return { text: '[Limite de ' + MAX_TOOL_TURNS + ' tours atteinte]', model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: MAX_TOOL_TURNS };
}

// ══════════════════════════════════════════════════════════════════════════════

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
        const result = await agenticChat(agentId, text);

        // Autolearn: record the final result
        const entry = {
          agent: agentId, category: AGENT_CAT[agentId] || 'default',
          userText: text, responseText: result.text,
          nodeId: 'cockpit', latencyMs: 0, ts: new Date().toISOString()
        };
        autolearn.recordConversation(entry);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, data: result }));
      } catch (e) {
        console.error('[cockpit] Error:', e.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
  } else if (req.method === 'POST' && req.url === '/tool') {
    // Direct tool execution endpoint
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const { name, args } = JSON.parse(body);
        const result = await executeTool(name, args || {});
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, data: result }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
  } else if (req.method === 'POST' && req.url === '/confirm') {
    // Confirm a dangerous action
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const { confirm_id, approved } = JSON.parse(body);
        const pending = pendingConfirms.get(confirm_id);
        if (!pending) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: 'Action expiree ou introuvable' }));
          return;
        }
        pendingConfirms.delete(confirm_id);
        if (!approved) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, cancelled: true }));
          return;
        }
        // Execute the confirmed action (bypass safety gate)
        const fn = TOOLS[pending.tool];
        const result = fn ? fn(pending.args) : { error: 'Tool inconnu' };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, data: result }));
      } catch (e) {
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

const BIND = process.env.JARVIS_BIND || '0.0.0.0';
server.listen(PORT, BIND, () => {
  console.log(`JARVIS Direct Proxy on http://${BIND}:${PORT}`);
  console.log('Nodes: M2(deepseek), M3(mistral), OL1(qwen3), M1(qwen3-30b)');
  console.log('Zero OpenClaw dependency');
  autolearn.start();
  console.log('Autolearn engine started — 3 pillars active');
});
