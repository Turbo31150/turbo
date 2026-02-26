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

// ── Query Enhancer v3 — Make local models perform like Claude ────────────────
const COT_TRIGGERS = ['pourquoi','explique','compare','analyse','difference','comment','quel est','quelle est','avantage','inconvenient','trade-off','meilleur','debug','erreur','bug','fix','probleme','optimise','ameliore','refactor','calcul','combien','probabilite','raisonne','logique','dedui','prouve','demontre','cause','consequence'];
const CODE_TRIGGERS = ['code','script','fonction','classe','api','implementation','programme','ecris','cree','python','javascript','typescript','bash','powershell','sql','html','css','react','node','express','fastapi','django'];
const STRUCT_TRIGGERS = ['liste','enumere','resume','synthese','tableau','etapes','plan','checklist','compare','vs','difference','recapitule','inventaire'];
const COT_CATS = new Set(['raison','math','ia','archi','sec','code']);
const CODE_CATS = new Set(['code','auto','system']);

// Model-specific strengths and weaknesses
const MODEL_PROFILES = {
  M1:  { strengths: 'rapide, polyvalent, bon raisonnement', weaknesses: 'contexte court, peut divaguer', style: 'concis, structure avec markdown, listes a puces, blocs de code' },
  M2:  { strengths: 'excellent code, debug precis', weaknesses: 'lent sur le creatif', style: 'code complet, commentaires inline, exemples executables' },
  M3:  { strengths: 'bon generaliste, fiable', weaknesses: 'pas de raisonnement profond', style: 'paragraphes courts, listes simples, langage clair' },
  OL1: { strengths: 'ultra-rapide, bon pour triage', weaknesses: 'superficiel sur questions complexes', style: 'reponses directes, listes, pas de verbiage' }
};

function enhanceQuery(text, cat, nodeId) {
  const low = text.toLowerCase();
  const hints = [];

  // 1. Chain-of-Thought forcing for reasoning categories
  if (COT_CATS.has(cat) && COT_TRIGGERS.some(t => low.includes(t)))
    hints.push('METHODE: Raisonne etape par etape. Numerate chaque etape. Verifie ta conclusion.');

  // 2. Code quality enforcement
  if (CODE_CATS.has(cat) && CODE_TRIGGERS.some(t => low.includes(t)))
    hints.push('CODE: Complet, fonctionnel, avec imports. Commente les parties non-evidentes. Gere les erreurs.');

  // 3. Structure enforcement
  if (STRUCT_TRIGGERS.some(t => low.includes(t)))
    hints.push('FORMAT: Structure avec ## titres, - listes, **gras** pour les points cles.');

  // 4. Self-verification prompt (makes models check their own output)
  if (cat === 'math' || cat === 'raison')
    hints.push('VERIFICATION: Apres ta reponse, relis-la et corrige toute erreur AVANT de conclure.');

  // 5. Anti-hallucination for factual categories
  if (cat === 'sec' || cat === 'trading' || cat === 'web')
    hints.push('PRECISION: Si tu n\'es pas certain d\'un fait, dis-le explicitement. Jamais d\'invention.');

  // 6. Model-specific optimization
  const profile = MODEL_PROFILES[nodeId];
  if (profile) {
    hints.push('STYLE: ' + profile.style);
  }

  // 7. Conciseness for small models
  if (nodeId === 'OL1' || nodeId === 'M3')
    hints.push('IMPORTANT: Sois CONCIS. Va droit au but. Max 3-5 points cles.');

  if (!hints.length) return text;
  return text + '\n\n[' + hints.join(' | ') + ']';
}

// ── Response Post-Processor — Clean and enhance model outputs ────────────────
function postProcessResponse(text, cat) {
  if (!text) return text;
  let out = text;

  // Remove thinking tokens that leak through
  out = out.replace(/<think>[\s\S]*?<\/think>/gi, '');
  out = out.replace(/^\/no_?think\s*/i, '');

  // Remove self-referential model artifacts
  out = out.replace(/^(As an AI|En tant qu'IA|Je suis un modele|I am a language model)[^\n]*\n?/gim, '');

  // Clean excessive whitespace
  out = out.replace(/\n{4,}/g, '\n\n\n');

  // Remove trailing incomplete sentences (model cut off mid-sentence)
  const lines = out.trimEnd().split('\n');
  const last = lines[lines.length - 1];
  if (last && last.length > 20 && !last.match(/[.!?\)\]\}»"']$/)) {
    // Check if it looks like a truncated sentence
    if (last.match(/\b(et|mais|car|donc|or|ni|que|qui|dont|ou|pour|avec|dans|sur|par|de|du|des|le|la|les|un|une)\s*$/i)) {
      lines.pop(); // Remove truncated line
    }
  }
  out = lines.join('\n').trim();

  return out;
}

// ── Optimal inference params per category + node ────────────────────────────
function getInferenceParams(cat, nodeId) {
  // Base params by category
  const base = {
    code:    { temperature: 0.12, max_tokens: 2048 },
    math:    { temperature: 0.08, max_tokens: 2048 },  // Near-deterministic for math
    raison:  { temperature: 0.15, max_tokens: 2048 },
    sec:     { temperature: 0.15, max_tokens: 2048 },
    archi:   { temperature: 0.25, max_tokens: 2048 },
    trading: { temperature: 0.08, max_tokens: 1024 },  // Precise numbers
    creat:   { temperature: 0.55, max_tokens: 2048 },  // Creative freedom
    ia:      { temperature: 0.2,  max_tokens: 2048 },
    web:     { temperature: 0.2,  max_tokens: 1536 },
    auto:    { temperature: 0.15, max_tokens: 2048 },
    system:  { temperature: 0.12, max_tokens: 1536 },
    meta:    { temperature: 0.3,  max_tokens: 1536 },
    media:   { temperature: 0.15, max_tokens: 1024 },
    default: { temperature: 0.2,  max_tokens: 1536 }
  }[cat] || { temperature: 0.2, max_tokens: 1536 };

  // Node-specific adjustments
  if (nodeId === 'OL1') {
    base.max_tokens = Math.min(base.max_tokens, 1024);  // OL1 is small, keep outputs tight
  } else if (nodeId === 'M3') {
    base.max_tokens = Math.min(base.max_tokens, 1536);  // M3 8GB, moderate outputs
  }
  return base;
}

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
    model: 'qwen/qwen3-8b',
    timeout: 30000,
    name: 'M1/qwen3-8b'
  },
  GEMINI: {
    proxy: path.join(__dirname, '..', 'gemini-proxy.js'),
    model: 'gemini-3-pro',
    timeout: 120000,
    name: 'GEMINI/gemini-3-pro',
    isProxy: true
  },
  CLAUDE: {
    proxy: path.join(__dirname, '..', 'claude-proxy.js'),
    model: 'sonnet',
    timeout: 120000,
    name: 'CLAUDE/sonnet',
    isProxy: true,
    budget: '0.50'
  }
};

// ── Routing: agent category → primary node, fallbacks ───────────────────────
const ROUTING = {
  code:    ['M1', 'M2', 'M3', 'OL1'],                  // M1 100% bench, 0.6-2.5s
  archi:   ['M1', 'M2', 'GEMINI', 'M3'],                // M1 validation
  trading: ['OL1', 'M1', 'M2', 'M3'],                   // OL1 web, M1 analyse
  math:    ['M1', 'OL1', 'M2'],                          // NOUVEAU — M1 prioritaire
  raison:  ['M1', 'M2', 'OL1'],                          // NOUVEAU — JAMAIS M3
  system:  ['M1', 'OL1', 'M3', 'M2'],                     // M1 rapide systeme
  auto:    ['M1', 'OL1', 'M3', 'M2'],                    // M1 pipelines
  ia:      ['M1', 'M2', 'GEMINI', 'CLAUDE', 'M3', 'OL1'], // M1 first
  creat:   ['M1', 'M2', 'GEMINI', 'M3', 'OL1'],         // M1 creatif
  sec:     ['M1', 'M2', 'GEMINI', 'M3', 'OL1'],         // M1 audit
  web:     ['OL1', 'M1', 'GEMINI', 'M2', 'M3'],          // OL1 web + M1 fallback
  media:   ['M3', 'OL1', 'M1', 'M2'],                    // M3 media + M1
  meta:    ['OL1', 'M1', 'M3', 'M2'],                    // OL1 rapide meta
  default: ['M1', 'M2', 'M3', 'OL1', 'GEMINI']           // M1 first
};

// ── Node weights for consensus voting (benchmark 2026-02-26) ─────────────────
const NODE_WEIGHTS = { M1: 1.8, M2: 1.4, OL1: 1.3, GEMINI: 1.2, CLAUDE: 1.2, M3: 1.0 };

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
  'math-solver': 'math', 'calculateur': 'math',
  'raisonnement': 'raison', 'logique': 'raison',
  'ol1-web': 'web', 'pipeline-comet': 'web',
  'voice-assistant': 'media', 'gemini-flash': 'media',
  'main': 'default', 'fast-chat': 'default'
};

// ── System prompts v2 — Expert-level per domain ─────────────────────────────
const SYS_PROMPTS = {
  code: 'Tu es JARVIS, ingenieur logiciel senior (15 ans, expert Python/JS/TS/Bash/PowerShell).\n\n' +
    'PROCESSUS OBLIGATOIRE:\n' +
    '1. **Comprendre** — Reformule le besoin en 1 phrase. Identifie: inputs, outputs, contraintes, edge cases.\n' +
    '2. **Planifier** — Si >20 lignes: decompose en fonctions/modules. Nomme-les AVANT de coder.\n' +
    '3. **Coder** — Code COMPLET, fonctionnel, avec TOUS les imports. Jamais de "..." ou pseudo-code.\n' +
    '4. **Verifier** — Relis ton code. Verifie: typos, off-by-one, null/undefined, types, imports manquants.\n\n' +
    'QUALITE:\n' +
    '- Variables descriptives (userCount, pas x). Fonctions <30 lignes. Un seul role par fonction.\n' +
    '- Error handling: try/except avec messages utiles. Valide les inputs.\n' +
    '- Commentaires: seulement quand le "pourquoi" n\'est pas evident, JAMAIS le "quoi".\n\n' +
    'FORMAT: ```language\\n// path/to/file.ext\\ncode...\\n``` — Un bloc par fichier.\n' +
    'LANGUE: Reponds en francais. Code et commentaires en anglais.\n' +
    'INTERDIT: Repondre sans code quand du code est demande. Laisser des TODO/placeholder.',

  archi: 'Tu es JARVIS, architecte logiciel (systemes distribues, GPU clusters, IA, microservices).\n\n' +
    'PROCESSUS:\n' +
    '1. **Contexte** — Resume le probleme et les contraintes en 2-3 phrases.\n' +
    '2. **Options** — Propose 2-3 approches en tableau:\n' +
    '   | Approche | Avantages | Inconvenients | Complexite | Recommande? |\n' +
    '3. **Decision** — Recommande UNE option. Justifie en 2 phrases max.\n' +
    '4. **Design** — Schema ASCII du flux de donnees. Liste des composants + responsabilites.\n' +
    '5. **Implementation** — Etapes concretes, fichiers a creer/modifier, dependances.\n\n' +
    'PRINCIPES: YAGNI > over-engineering. KISS > clever. Idempotent > stateful. Async > sync.\n' +
    'LANGUE: Francais. Schemas ASCII pour les flux.\n' +
    'INTERDIT: Recommander sans justifier. Design sans contraintes identifiees.',

  trading: 'Tu es JARVIS, analyste quantitatif crypto-futures (MEXC 10x leverage).\n\n' +
    'PROCESSUS SIGNAL:\n' +
    '1. **Macro** — Tendance 4h/1h: haussiere/baissiere/range. Support/resistance cles.\n' +
    '2. **Micro** — Structure 15m/5m: pattern (flag, wedge, breakout), volume, momentum.\n' +
    '3. **Confluences** — Min 3 parmi: RSI, MACD, volume, orderbook, funding, OI, liquidation map.\n' +
    '4. **Signal** — UNIQUEMENT si score >= 70/100.\n\n' +
    'FORMAT SIGNAL:\n' +
    '```\nDirection: LONG/SHORT\nEntry: $X.XX | TP: $X.XX (+X.X%) | SL: $X.XX (-X.X%)\nR/R: X.X:1 | Size: X USDT | Score: XX/100\nConfluences: [liste]\nInvalidation: [condition qui annule le signal]\n```\n\n' +
    'REGLES: Chiffres PRECIS (pas "autour de"). R/R minimum 1.5:1. SL OBLIGATOIRE.\n' +
    'INTERDIT: Speculation sans donnees. Signal sans confluences. Ignorer le risk management.',

  system: 'Tu es JARVIS, administrateur systeme Windows expert (PowerShell, GPU, reseaux, services).\n\n' +
    'PROCESSUS:\n' +
    '1. **Diagnostic** — Etat actuel: commande(s) de verification.\n' +
    '2. **Cause** — Hypothese la plus probable + alternatives.\n' +
    '3. **Solution** — Commande(s) PowerShell COMPLETES, chemins absolus, pas de placeholder.\n' +
    '4. **Verification** — Commande de check post-fix. Resultat attendu.\n\n' +
    'REGLES: PowerShell > CMD. Chemins absolus. TOUJOURS tester avant de supprimer.\n' +
    'ENV: Windows 11 Pro, 10 GPU, cluster 3 machines (M1/M2/M3), Ollama, LM Studio.\n' +
    'INTERDIT: Placeholder ("votre-chemin"). Commandes destructives sans confirmation.',

  auto: 'Tu es JARVIS, expert automatisation et orchestration (CI/CD, pipelines, cron, n8n).\n\n' +
    'PROCESSUS:\n' +
    '1. **Objectif** — Quoi automatiser, frequence, triggers, outputs attendus.\n' +
    '2. **Design** — Pipeline: etapes → dependances → error handling → notifications.\n' +
    '3. **Code** — Script complet, autonome, idempotent. Logs structures a chaque etape.\n' +
    '4. **Deploy** — Comment lancer, planifier, monitorer.\n\n' +
    'QUALITE: Retry avec backoff. Fallback explicite. Timeouts. Logs JSON quand possible.\n' +
    'LANGUE: Francais. Scripts en Python/Bash/PowerShell.',

  ia: 'Tu es JARVIS, expert intelligence artificielle et systemes multi-agents.\n\n' +
    'PROCESSUS:\n' +
    '1. **Reformuler** — Repete la question dans tes propres mots pour verifier ta comprehension.\n' +
    '2. **Decomposer** — Identifie les sous-problemes. Traite-les un par un.\n' +
    '3. **Raisonner** — Pour chaque sous-probleme: premisses → raisonnement → conclusion intermediaire.\n' +
    '4. **Synthetiser** — Combine les conclusions. Identifie les limites et incertitudes.\n' +
    '5. **Conclure** — Reponse claire + niveau de confiance (eleve/moyen/faible).\n\n' +
    'REGLES: Distingue fait vs opinion vs speculation. Si incertain: dis-le. Cite tes sources si applicable.\n' +
    'INTERDIT: Affirmer sans argumenter. Ignorer les contre-arguments evidents.',

  creat: 'Tu es JARVIS, directeur creatif senior avec 20 ans d\'experience en copywriting et branding.\n\n' +
    'PROCESSUS:\n' +
    '1. **Cible** — Qui lit? Quel effet vise? Quelle emotion declencher?\n' +
    '2. **Brainstorm** — Genere 3+ idees. Garde la plus originale, pas la plus evidente.\n' +
    '3. **Rediger** — Concret > abstrait. Verbes forts > adjectifs mous. Rythme varie.\n' +
    '4. **Structurer** — Utilise **titres**, listes numerotees, separateurs. JAMAIS un bloc de texte brut.\n' +
    '5. **Polir** — Relis. Coupe les cliches. Chaque mot doit meriter sa place.\n\n' +
    'FORMAT OBLIGATOIRE:\n' +
    '- Toujours structurer avec **titres markdown** et **listes**\n' +
    '- Si on demande N elements: numerote-les clairement (1. 2. 3.)\n' +
    '- Ajoute un court paragraphe de contexte/justification\n' +
    '- Minimum 100 mots, maximum 500 mots\n\n' +
    'QUALITE: Surprends. Pas de reponses generiques. Chaque creation doit etre memorable.',

  sec: 'Tu es JARVIS, expert cybersecurite (pentest, audit, hardening, OWASP Top 10).\n\n' +
    'PROCESSUS:\n' +
    '1. **Perimetre** — Quoi auditer, surface d\'attaque, technologies.\n' +
    '2. **Analyse** — Chaque vuln: description, vecteur, impact, exploitabilite.\n' +
    '3. **Rapport** — Tableau structure:\n' +
    '   | # | Vulnerabilite | Severite | CVSS | Impact | Correctif |\n' +
    '4. **Remediations** — Commandes/code CONCRETS pour chaque vuln. Priorite: critique > haut > moyen.\n\n' +
    'REGLES: CVE quand applicable. CVSS score. Correctif ACTIONNABLE (pas "ameliorer la securite").\n' +
    'INTERDIT: Vuln sans correctif. Severite sans justification.',

  web: 'Tu es JARVIS, analyste recherche et synthese d\'information.\n\n' +
    'PROCESSUS:\n' +
    '1. **Resume executif** — 2-3 phrases: l\'essentiel a retenir.\n' +
    '2. **Analyse** — Points cles structures, avec sources quand disponibles.\n' +
    '3. **Nuance** — Distingue: fait confirme vs opinion d\'expert vs speculation.\n' +
    '4. **Conclusion** — Recommandation ou verdict, avec niveau de confiance.\n\n' +
    'FORMAT: **Resume**: [...] → **Details**: [liste] → **Sources**: [si disponibles]\n' +
    'INTERDIT: Copier-coller sans reformulation. Affirmer sans sourcer.',

  media: 'Tu es JARVIS, expert multimedia (FFmpeg, ImageMagick, audio/video, TTS, STT).\n\n' +
    'PROCESSUS:\n' +
    '1. **Besoin** — Format source → format cible, qualite, contraintes.\n' +
    '2. **Commande** — FFmpeg/ImageMagick COMPLETE, copiable directement.\n' +
    '3. **Explication** — Chaque flag important explique en 1 ligne.\n\n' +
    'FORMAT: ```bash\\nffmpeg -i input.ext [options] output.ext\\n```\n' +
    'REGLES: Codecs explicites (pas de -c copy sauf justifie). Qualite recommandee.',

  meta: 'Tu es JARVIS, pedagogiste expert qui rend les concepts complexes accessibles.\n\n' +
    'PROCESSUS:\n' +
    '1. **Contexte** — Situe le concept: c\'est quoi, a quoi ca sert, pourquoi c\'est important.\n' +
    '2. **Explication** — Du simple au complexe. Analogie du quotidien si possible.\n' +
    '3. **Exemple** — Concret, executable si code, visuel si concept.\n' +
    '4. **Verification** — Question de controle ou piege courant a eviter.\n\n' +
    'STYLE: Adapte le niveau a la question. Pas de jargon non-explique. Court > long.',

  math: 'Tu es JARVIS, mathematicien rigoureux (algebre, stats, probabilites, optimisation).\n\n' +
    'PROCESSUS OBLIGATOIRE:\n' +
    '1. **Identifier** — Type de probleme, variables, contraintes.\n' +
    '2. **Poser** — Equations/formules necessaires. Notation coherente.\n' +
    '3. **Resoudre** — CHAQUE etape numerotee. JAMAIS de saut. Montre les calculs intermediaires.\n' +
    '4. **Verifier** — Back-check par methode DIFFERENTE (substitution, estimation, cas limite).\n' +
    '5. **Conclure** — **Resultat: [valeur exacte]** en gras.\n\n' +
    'REGLES:\n' +
    '- Montre TOUS les calculs intermediaires (ex: 17*23 = 17*20 + 17*3 = 340 + 51 = 391)\n' +
    '- Unites explicites a chaque etape\n' +
    '- Si approximation: indique la precision\n\n' +
    'INTERDIT: Saut d\'etape. Resultat sans verification. "Il est evident que...".',

  raison: 'Tu es JARVIS, logicien et philosophe analytique.\n\n' +
    'PROCESSUS OBLIGATOIRE:\n' +
    '1. **Reformuler** — Repete le probleme dans tes propres mots.\n' +
    '2. **Premisses** — Liste TOUTES les premisses (explicites ET implicites).\n' +
    '3. **Raisonner** — Pour chaque etape:\n' +
    '   - Premisse(s) utilisee(s) → regle logique appliquee → conclusion intermediaire\n' +
    '   - Nommer les raisonnements: modus ponens, contraposee, syllogisme, analogie, induction...\n' +
    '4. **Contre-arguments** — Identifie les failles: erreur de distribution, premisse cachee, biais.\n' +
    '5. **Conclusion** — Reponse + niveau de confiance (eleve/moyen/faible) + conditions.\n\n' +
    'FORMAT:\n' +
    '**Probleme:** [reformulation]\n' +
    '**Premisses:** 1. [...] 2. [...]\n' +
    '**Raisonnement:**\n' +
    '  Etape 1: [premisse] + [regle] → [conclusion]\n' +
    '  Etape 2: ...\n' +
    '**Piege/Erreur courante:** [...]\n' +
    '**Conclusion:** [reponse] (confiance: X)\n\n' +
    'INTERDIT: Conclure sans raisonner. Ignorer les premisses implicites. Reponse hative.',

  default: 'Tu es JARVIS, assistant IA haute performance.\n\n' +
    'PROCESSUS:\n' +
    '1. **Comprendre** — Reformule brievement la demande.\n' +
    '2. **Repondre** — Structure: titres, listes, blocs de code si pertinent.\n' +
    '3. **Verifier** — Relis ta reponse avant de conclure.\n\n' +
    'REGLES:\n' +
    '- Francais toujours. Concis mais complet.\n' +
    '- Raisonne etape par etape pour les questions complexes.\n' +
    '- Si ambigue: demande une clarification plutot que deviner.\n' +
    '- Exemples concrets > explications abstraites.'
};

// ── Autolearn Engine ────────────────────────────────────────────────────────
const autolearn = new AutolearnEngine(callNode, ROUTING, SYS_PROMPTS);

// ══════════════════════════════════════════════════════════════════════════════
// ══ TOOL ENGINE — 10 tools systeme pour le cockpit autonome ══════════════════
// ══════════════════════════════════════════════════════════════════════════════

const ETOILE_DB = path.join(__dirname, '..', 'data', 'etoile.db');
const MAX_FILE_SIZE = 100 * 1024;
const MAX_TOOL_TURNS = 8;

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

// ── Complexity classifier — simple vs reflexive ──────────────────────────
function classifyComplexity(userText, agentCat) {
  // Force reflexive for certain categories
  const reflexiveCats = ['code', 'archi', 'ia', 'sec', 'math', 'raison'];
  if (reflexiveCats.includes(agentCat)) return 'reflexive';

  // Keyword detection BEFORE category check (keywords override 'default' category)
  const complexKeywords = /\b(analyse|compare|cherche.*explique|d[eé]taill[eé]|pourquoi|comment.*fonctionne|refactor|debug|optimise|audit|review|[eé]value|synth[eè]se|r[eé]sume.*tout|en d[eé]tail|raisonne|logique|d[eé]dui[st]|syllogisme|conclure|pr[eé]misse|calcule|[eé]quation|math[eé]matique|probabilit[eé]|d[eé]montre)\b/i;
  if (complexKeywords.test(userText)) return 'reflexive';

  // Tool-implying keywords
  const toolKeywords = /\b(query_db|etoile|base de donn[eé]es|sql|fichier|dossier|pipeline|execute|lance|cherche dans|combien|table|entrees|donnees)\b/i;
  if (toolKeywords.test(userText)) return 'reflexive';

  // Length heuristic: long messages are likely complex
  if (userText.length > 120) return 'reflexive';

  // Force simple for lightweight categories (only if no keyword match)
  const simpleCats = ['meta', 'media'];
  if (simpleCats.includes(agentCat)) return 'simple';

  return 'simple';
}

// ── Reflexive Chain: OL1 (search) → M1 (analyze) → M2 (review) ──────────
const REFLEXIVE_CHAIN = [
  { nodeId: 'OL1', role: 'recherche', maxTurns: 4, systemSuffix:
    '\n\n--- ROLE: ETAPE 1/3 — RECHERCHE ---' +
    '\nTa mission: collecter les DONNEES BRUTES necessaires pour repondre a la question.' +
    '\nUtilise les outils (query_db, web_search, read_file) pour trouver les infos.' +
    '\nREGLES: Ne reponds PAS a la question. Ne conclus PAS. Collecte seulement.' +
    '\nSi aucun outil pertinent: reformule la question et identifie les points cles.' +
    '\nFORMAT de sortie: liste de faits/donnees trouves, un par ligne.' },
  { nodeId: 'M1',  role: 'analyse',   maxTurns: 3, systemSuffix:
    '\n\n--- ROLE: ETAPE 2/3 — ANALYSE ---' +
    '\nTa mission: a partir des donnees collectees ci-dessous, RAISONNE et SYNTHETISE.' +
    '\nPROCESSUS:' +
    '\n1. Identifie les informations pertinentes vs bruit' +
    '\n2. Raisonne etape par etape en numerotant' +
    '\n3. Cite les donnees qui soutiennent chaque point' +
    '\n4. Identifie les lacunes ou incertitudes' +
    '\nUtilise des outils UNIQUEMENT si les donnees sont insuffisantes.' +
    '\nFORMAT: analyse structuree avec conclusions intermediaires.' },
  { nodeId: 'M2',  role: 'review',    maxTurns: 2, systemSuffix:
    '\n\n--- ROLE: ETAPE 3/3 — REVIEW & REPONSE FINALE ---' +
    '\nTa mission: verifier l\'analyse, corriger les erreurs, et donner la REPONSE FINALE.' +
    '\nPROCESSUS:' +
    '\n1. Verifie chaque affirmation de l\'analyse: est-elle correcte? bien soutenue?' +
    '\n2. Corrige les erreurs factuelles ou logiques' +
    '\n3. Complete les points manquants' +
    '\n4. Redige la reponse FINALE, claire et bien structuree' +
    '\nATTENTION: Reponds DIRECTEMENT au user. Pas de meta-commentaire sur le processus.' +
    '\nFORMAT: Reponse finale structuree (titres, listes, code si pertinent).' }
];

// ── Reasoning Chain: M1 (deep reasoning) → M2 (verification) — no tools ──
const REASONING_CHAIN = [
  { nodeId: 'M1', role: 'raisonnement', maxTurns: 1, systemSuffix:
    '\n\n--- ROLE: ETAPE 1/2 — RAISONNEMENT PROFOND ---' +
    '\nTa mission: raisonner rigoureusement, pas a pas, comme un logicien.' +
    '\nPROCESSUS:' +
    '\n1. Reformule le probleme dans tes propres mots' +
    '\n2. Identifie TOUTES les premisses (explicites ET implicites)' +
    '\n3. Raisonne etape par etape: premisse → regle → conclusion' +
    '\n4. Nomme les raisonnements: modus ponens, syllogisme, contraposee, analogie...' +
    '\n5. Cherche les pieges: erreur de distribution, premisse cachee, confusion correlation/causalite' +
    '\nN\'utilise PAS d\'outils. Raisonne UNIQUEMENT.' +
    '\nFORMAT: Probleme → Premisses → Etapes de raisonnement → Pieges identifies → Conclusion provisoire' },
  { nodeId: 'M2', role: 'verification', maxTurns: 1, systemSuffix:
    '\n\n--- ROLE: ETAPE 2/2 — VERIFICATION & REPONSE FINALE ---' +
    '\nTa mission: verifier le raisonnement ci-dessous et donner la REPONSE FINALE.' +
    '\nPROCESSUS:' +
    '\n1. Chaque etape logique est-elle valide? La regle est-elle correctement appliquee?' +
    '\n2. Les premisses implicites sont-elles toutes identifiees?' +
    '\n3. Y a-t-il des erreurs logiques (non sequitur, faux dilemme, homme de paille)?' +
    '\n4. La conclusion decoule-t-elle necessairement des premisses?' +
    '\nSi erreur trouvee: corrige et explique pourquoi.' +
    '\nSi correct: confirme et reformule clairement la conclusion.' +
    '\nATTENTION: Reponds DIRECTEMENT au user. Format final propre, pas de meta-processus.' }
];

// MATH_CHAIN: M1 seul (qwen3-8b excellent en math, M2/deepseek-coder mauvais verificateur math)
const MATH_CHAIN = [
  { nodeId: 'M1', role: 'calcul', maxTurns: 1, systemSuffix:
    '\n\n--- ROLE: MATHEMATICIEN --- Tu resous ce probleme mathematique.' +
    '\nPROCESSUS STRICT:' +
    '\n1. **Identifier** le type: arithmetique, algebre, geometrie, stats, etc.' +
    '\n2. **Poser** les equations/formules necessaires' +
    '\n3. **Calculer** CHAQUE etape numerotee. Decompose: 17*23 = 17*20 + 17*3 = 340+51 = 391' +
    '\n4. **Verifier** par methode differente (substitution, estimation, preuve inverse)' +
    '\n5. **Conclure** avec **Resultat: [valeur]** en gras' +
    '\n\nINTERDIT: sauter des etapes, arrondir sans le dire, oublier les unites.' +
    '\nFORMAT: Donnees → Etapes numerotees → Verification → **Resultat: X**' }
];

// Select chain based on category
function getChainForCategory(cat) {
  if (cat === 'math') return MATH_CHAIN;
  if (cat === 'raison') return REASONING_CHAIN;
  return REFLEXIVE_CHAIN;
}

async function reflexiveChat(agentId, userText) {
  const cat = AGENT_CAT[agentId] || 'default';
  const baseSys = (SYS_PROMPTS[cat] || SYS_PROMPTS.default);
  const selectedChain = getChainForCategory(cat);
  const chainResults = [];
  let accumulatedContext = '';
  let totalTurns = 0;
  let allToolsUsed = [];
  let lastModel = null, lastProvider = null;
  let finalText = '';

  for (const step of selectedChain) {
    const node = NODES[step.nodeId];
    if (!node) { console.log('[reflexive] skip ' + step.nodeId + ' (not configured)'); continue; }

    const stepStart = Date.now();
    // Only the recherche step needs full tool prompt; raisonnement/verification/analyse/review get lightweight prompt
    const sysProm = step.role === 'recherche'
      ? baseSys + '\n' + COCKPIT_TOOLS_PROMPT + step.systemSuffix
      : baseSys + step.systemSuffix;

    // Build messages with accumulated context (capped at 8000 chars to avoid context overflow)
    let userContent = enhanceQuery(userText, cat, step.nodeId);
    if (accumulatedContext) {
      const cappedCtx = accumulatedContext.length > 8000 ? accumulatedContext.slice(-8000) : accumulatedContext;
      userContent = userContent + '\n\n=== CONTEXTE DES ETAPES PRECEDENTES ===\n' + cappedCtx;
    }

    const messages = [
      { role: 'system', content: sysProm },
      { role: 'user', content: userContent }
    ];

    const stepTools = [];
    const callHashes = new Set();
    let stepText = '';
    let stepTurnCount = 0;

    // Agentic loop for this step
    for (let turn = 0; turn < step.maxTurns; turn++) {
      stepTurnCount++;
      totalTurns++;
      let aiResult;
      try {
        console.log('[reflexive] step=' + step.role + ' turn=' + turn + ' -> ' + step.nodeId);
        aiResult = await callNode(step.nodeId, messages);
        lastModel = aiResult.model;
        lastProvider = aiResult.provider;
      } catch (e) {
        console.log('[reflexive] ' + step.nodeId + ' FAILED: ' + e.message);
        // Try fallback nodes
        const fallbacks = (ROUTING[cat] || ROUTING.default).filter(function(n) { return n !== step.nodeId; });
        let fallbackOk = false;
        for (const fb of fallbacks) {
          try {
            aiResult = await callNode(fb, messages);
            lastModel = aiResult.model;
            lastProvider = aiResult.provider;
            console.log('[reflexive] fallback ' + fb + ' OK for step ' + step.role);
            fallbackOk = true;
            break;
          } catch (_) {}
        }
        if (!fallbackOk) break;
      }

      const toolCall = parseToolCall(aiResult.text);
      if (!toolCall) {
        stepText = aiResult.text;
        break;
      }

      // Anti-loop v2: repeated call detection
      const callHash = toolCall.name + ':' + JSON.stringify(toolCall.args);
      if (callHashes.has(callHash)) {
        console.log('[reflexive] ANTI-LOOP: repeated ' + toolCall.name + ' in step ' + step.role);
        messages.push({ role: 'assistant', content: aiResult.text });
        messages.push({ role: 'user', content: '[SYSTEM] Appel identique detecte. Reponds avec les resultats deja obtenus.' });
        try {
          const final = await callNode(step.nodeId, messages);
          stepText = final.text;
        } catch (_) {
          stepText = aiResult.text;
        }
        break;
      }
      callHashes.add(callHash);

      // Execute tool
      const toolResult = await executeTool(toolCall.name, toolCall.args);

      if (toolResult.needs_confirm) {
        return {
          text: aiResult.text, model: lastModel, provider: lastProvider,
          tools_used: allToolsUsed.concat(stepTools), turns: totalTurns,
          mode: 'reflexive', chain: chainResults,
          needs_confirm: true, confirm_id: toolResult.confirm_id, confirm_action: toolResult.reason
        };
      }

      stepTools.push({ tool: toolCall.name, args: toolCall.args, result: toolResult, turn: turn });
      allToolsUsed.push({ tool: toolCall.name, args: toolCall.args, result: toolResult, turn: totalTurns - 1 });

      // Feed result back to AI
      var feedback = '[TOOL_RESULT:' + toolCall.name + ']\n' + JSON.stringify(toolResult).slice(0, 10000);
      if (toolResult.hint) feedback += '\nHINT: ' + toolResult.hint;
      messages.push({ role: 'assistant', content: aiResult.text });
      messages.push({ role: 'user', content: feedback });
    }

    // If no stepText captured (all turns used tools), ask for summary
    if (!stepText) {
      messages.push({ role: 'user', content: '[SYSTEM] Budget de tours epuise. Donne ta synthese maintenant.' });
      try {
        const summary = await callNode(step.nodeId, messages);
        stepText = summary.text;
      } catch (_) {
        stepText = '(pas de reponse de ' + step.nodeId + ')';
      }
    }

    // Clean stepText + post-process
    stepText = stepText.replace(/\[TOOL:\w+[^\]]*\]/g, '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/^\/no_think\s*/i, '').trim();
    stepText = postProcessResponse(stepText, cat);

    const stepDuration = Date.now() - stepStart;
    chainResults.push({
      node: step.nodeId,
      role: step.role,
      model: node.model,
      turns: stepTurnCount,
      tools_used: stepTools,
      duration_ms: stepDuration,
      summary: stepText.slice(0, 500)
    });

    // Accumulate context for next step
    accumulatedContext += '\n[' + step.role.toUpperCase() + ' — ' + step.nodeId + '/' + node.model + ']\n' + stepText + '\n';
    finalText = stepText;
  }

  return {
    text: finalText,
    model: lastModel,
    provider: lastProvider,
    tools_used: allToolsUsed,
    turns: totalTurns,
    mode: 'reflexive',
    chain: chainResults
  };
}

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
  const callHashes = new Set();  // anti-loop v2: detect repeated identical calls

  // Dynamic routing: try autolearn best node first, then fallback chain
  const bestNode = autolearn.getBestNode(cat);
  const orderedChain = bestNode
    ? [bestNode, ...chain.filter(n => n !== bestNode)]
    : chain;

  for (let turn = 0; turn < MAX_TOOL_TURNS; turn++) {
    let aiResult, errors = [];
    for (const nodeId of orderedChain) {
      try {
        console.log('[cockpit] turn ' + turn + ' -> ' + nodeId + ' (' + messages.length + ' msgs)');
        const t0 = Date.now();
        aiResult = await callNode(nodeId, messages);
        lastModel = aiResult.model;
        lastProvider = aiResult.provider;
        const elapsed = Date.now() - t0;
        console.log('[cockpit] OK ' + nodeId + ' (' + aiResult.text.length + ' chars, ' + elapsed + 'ms)');
        autolearn.recordCallResult(nodeId, cat, true, elapsed);
        break;
      } catch (e) {
        errors.push(nodeId + ': ' + e.message);
        autolearn.recordCallResult(nodeId, cat, false, 60000);
      }
    }
    if (!aiResult) throw new Error('All nodes failed: ' + errors.join(' | '));

    const toolCall = parseToolCall(aiResult.text);
    if (!toolCall) {
      return { text: aiResult.text, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, mode: 'simple' };
    }

    // Anti-loop v2: detect repeated identical tool call (same name + same args)
    const callHash = toolCall.name + ':' + JSON.stringify(toolCall.args);
    if (callHashes.has(callHash)) {
      console.log('[cockpit] ANTI-LOOP-V2: repeated call ' + toolCall.name + ', stopping');
      const stopMsg = '[SYSTEM] STOP: Appel identique detecte (' + toolCall.name + '). Reponds avec les resultats que tu as deja.';
      messages.push({ role: 'assistant', content: aiResult.text });
      messages.push({ role: 'user', content: stopMsg });
      for (const nodeId of orderedChain) {
        try {
          const final = await callNode(nodeId, messages);
          return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: 'repeated_call', mode: 'simple' };
        } catch (_) {}
      }
      return { text: stopMsg, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: 'repeated_call', mode: 'simple' };
    }
    callHashes.add(callHash);

    console.log('[cockpit] TOOL: ' + toolCall.name + '(' + JSON.stringify(toolCall.args).slice(0, 100) + ')');
    const toolResult = await executeTool(toolCall.name, toolCall.args);

    if (toolResult.needs_confirm) {
      return {
        text: aiResult.text, model: lastModel, provider: lastProvider,
        tools_used: toolHistory, turns: turn + 1,
        needs_confirm: true, confirm_id: toolResult.confirm_id, confirm_action: toolResult.reason,
        mode: 'simple'
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
        for (const nodeId of orderedChain) {
          try {
            const final = await callNode(nodeId, messages);
            return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: true, mode: 'simple' };
          } catch (_) {}
        }
        return { text: stopMsg, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: true, mode: 'simple' };
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
      for (const nodeId of orderedChain) {
        try {
          const final = await callNode(nodeId, messages);
          return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: true, mode: 'simple' };
        } catch (_) {}
      }
      return { text: '[Anti-loop: trop d\'echecs consecutifs]', model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: true, mode: 'simple' };
    }

    // Build feedback with hint if available
    let feedback = '[TOOL_RESULT:' + toolCall.name + ']\n' + JSON.stringify(toolResult).slice(0, 10000);
    if (toolResult.hint) feedback += '\nHINT: ' + toolResult.hint;

    messages.push({ role: 'assistant', content: aiResult.text });
    messages.push({ role: 'user', content: feedback });
  }

  return { text: '[Limite de ' + MAX_TOOL_TURNS + ' tours atteinte]', model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: MAX_TOOL_TURNS, mode: 'simple' };
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
async function callNode(nodeId, messages, category) {
  const node = NODES[nodeId];
  if (!node) throw new Error('Unknown node: ' + nodeId);

  // Get optimal inference params for this category + node
  const params = category ? getInferenceParams(category, nodeId) : { temperature: 0.2, max_tokens: 1536 };

  if (node.isProxy) {
    // CLI proxy (gemini-proxy.js, claude-proxy.js)
    return callProxyNode(nodeId, node, messages);
  }

  const headers = {};
  if (node.auth) headers['Authorization'] = node.auth;

  if (node.isOllama) {
    // Ollama API format
    const body = {
      model: node.model,
      messages,
      stream: false,
      think: false,
      options: { temperature: params.temperature, num_predict: params.max_tokens }
    };
    const res = await httpRequest(node.url, body, headers, node.timeout);
    const text = res.message?.content || '';
    return { text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: 'ollama' };
  } else {
    // OpenAI-compatible (LM Studio)
    // Sanitize messages: ensure every message has a string content field
    const cleanMsgs = messages.map(m => ({
      role: m.role,
      content: (m.content != null ? String(m.content) : '')
    }));
    // M1 qwen3-8b: prepend /nothink to first user message to disable thinking mode
    if (nodeId === 'M1') {
      const firstUser = cleanMsgs.find(m => m.role === 'user');
      if (firstUser && !firstUser.content.startsWith('/nothink')) {
        firstUser.content = '/nothink\n' + firstUser.content;
      }
    }
    const body = {
      model: node.model,
      messages: cleanMsgs,
      temperature: params.temperature,
      max_tokens: params.max_tokens,
      stream: false
    };
    const res = await httpRequest(node.url, body, headers, node.timeout);
    const text = res.choices?.[0]?.message?.content
      || res.choices?.[0]?.message?.reasoning_content || '';
    return { text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: 'lm-studio' };
  }
}

// ── Call a proxy node (GEMINI, CLAUDE) via CLI ──────────────────────────────
function callProxyNode(nodeId, node, messages) {
  return new Promise((resolve, reject) => {
    // Build a single prompt from messages (system + user + context)
    const parts = [];
    for (const m of messages) {
      if (m.role === 'system') parts.push('[SYSTEM] ' + m.content);
      else if (m.role === 'user') parts.push('[USER] ' + m.content);
      else if (m.role === 'assistant') parts.push('[ASSISTANT] ' + m.content);
    }
    const prompt = parts.join('\n\n');

    const args = ['--json'];
    if (node.model && nodeId === 'CLAUDE') args.push('--model', node.model);
    if (node.budget && nodeId === 'CLAUDE') args.push('--budget', node.budget);
    if (node.model && nodeId === 'GEMINI') args.push('--model', node.model);
    args.push(prompt.slice(0, 30000)); // limit prompt size for CLI

    console.log('[proxy-node] ' + nodeId + ' calling ' + node.proxy);
    const child = execFileSync ? null : null; // use spawn for async
    const proc = spawn('node', [node.proxy, ...args], {
      timeout: node.timeout,
      env: { ...process.env },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    let stdout = '', stderr = '';
    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);

    const timer = setTimeout(() => {
      proc.kill('SIGTERM');
      reject(new Error(nodeId + ' timeout after ' + node.timeout + 'ms'));
    }, node.timeout);

    proc.on('close', code => {
      clearTimeout(timer);
      if (code !== 0 && !stdout.trim()) {
        reject(new Error(nodeId + ' exit=' + code + ': ' + stderr.slice(0, 200)));
        return;
      }
      // Try JSON parse first
      try {
        const json = JSON.parse(stdout);
        const text = json.text || json.response || json.content || JSON.stringify(json);
        resolve({ text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: nodeId.toLowerCase() });
      } catch (_) {
        // Plain text output
        const text = stdout.trim();
        if (!text) {
          reject(new Error(nodeId + ' returned empty response'));
          return;
        }
        resolve({ text: text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim(), model: node.model, provider: nodeId.toLowerCase() });
      }
    });

    proc.on('error', e => {
      clearTimeout(timer);
      reject(new Error(nodeId + ' spawn error: ' + e.message));
    });
  });
}

// ── Route and call with fallback ────────────────────────────────────────────
async function routeAndCall(agentId, userText) {
  const cat = AGENT_CAT[agentId] || 'default';
  const chain = ROUTING[cat] || ROUTING.default;
  let sysProm = SYS_PROMPTS[cat] || SYS_PROMPTS.default;

  // Autolearn: inject memory context into system prompt
  const ctxInjection = autolearn.getContextInjection(cat);
  if (ctxInjection) sysProm = sysProm + '\n' + ctxInjection;

  const errors = [];
  for (const nodeId of chain) {
    // Enhance query with CoT/format hints per category + model
    const enhanced = enhanceQuery(userText, cat, nodeId);
    const messages = [
      { role: 'system', content: sysProm },
      { role: 'user', content: enhanced }
    ];

    try {
      console.log(`[chat] ${agentId} (${cat}) -> ${nodeId}/${NODES[nodeId].model}`);
      const t0 = Date.now();
      const result = await callNode(nodeId, messages, cat);
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
    { name: 'M1', url: 'http://10.5.0.2:1234/v1/models', headers: { Authorization: NODES.M1.auth } },
    { name: 'GEMINI', proxy: true },
    { name: 'CLAUDE', proxy: true }
  ];

  const results = await Promise.all(checks.map(n => {
    if (n.proxy) {
      // CLI proxy health check via --ping
      return new Promise(resolve => {
        const start = Date.now();
        const proxyPath = NODES[n.name]?.proxy;
        if (!proxyPath) { resolve({ name: n.name, ok: false, latency: 0 }); return; }
        const proc = spawn('node', [proxyPath, '--ping'], { timeout: 8000, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
        let out = '';
        proc.stdout.on('data', d => out += d);
        proc.on('close', code => resolve({ name: n.name, ok: code === 0 || out.includes('OK'), latency: Date.now() - start }));
        proc.on('error', () => resolve({ name: n.name, ok: false, latency: 0 }));
        setTimeout(() => { try { proc.kill(); } catch (_) {} }, 8000);
      });
    }
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
        const parsed = JSON.parse(body);
        const agentId = parsed.agent || 'main';
        // Support both {text:"..."} and {messages:[{role:"user",content:"..."}]}
        const text = parsed.text || (parsed.messages && parsed.messages.filter(m => m.role === 'user').map(m => m.content).join('\n')) || '';
        const complexity = classifyComplexity(text, AGENT_CAT[agentId] || 'default');
        console.log('[cockpit] complexity=' + complexity + ' agent=' + agentId);
        const result = complexity === 'reflexive'
          ? await reflexiveChat(agentId, text)
          : await agenticChat(agentId, text);

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
  console.log('Nodes: M2(deepseek), M3(mistral), OL1(qwen3), M1(qwen3-8b), GEMINI(gemini-3-pro), CLAUDE(sonnet)');
  console.log('Zero OpenClaw dependency');
  autolearn.start();
  console.log('Autolearn engine started — 3 pillars active');
});
