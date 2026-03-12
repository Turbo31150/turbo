"""
Knowledge Base Indexer V2.0 - FULL BUREAU + WEB DOCS
Indexe TOUT /home/turbo + documentation externe depuis internet
"""
import sqlite3
import os
import re
import json
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser

DB_PATH = r"/home/turbo\TRADING_V2_PRODUCTION\database\trading.db"

# ==========================================
# CATEGORIES ENRICHIES
# ==========================================
CATEGORIES = {
    "guides": {"desc": "Guides demarrage, tutoriels, quickstarts", "icon": "G",
        "patterns": ["GUIDE", "DEMARRAGE", "QUICKSTART", "START_HERE", "README", "QUICK_START", "UTILISATION", "HOWTO", "TUTORIAL"]},
    "scanners": {"desc": "Scanners MEXC, sniper, breakout", "icon": "S",
        "patterns": ["SCANNER", "SCAN_", "SNIPER", "AUTO_SCANNER", "BREAKOUT", "SCAN_MEXC"]},
    "orchestrateur": {"desc": "Meta-orchestrateur, coordination, domino, pipeline", "icon": "O",
        "patterns": ["META_ORCHESTRATEUR", "ORCHESTR", "DOMINO", "PIPELINE", "ROUTING"]},
    "sessions": {"desc": "Recaps sessions, status, changelog", "icon": "R",
        "patterns": ["SESSION", "RECAP", "RESUME_SESSION", "FICHIERS_CREES", "CHANGELOG"]},
    "systeme": {"desc": "Configuration systeme, deploiement, installation", "icon": "X",
        "patterns": ["SYSTEME", "DEPLOIEMENT", "INSTALLATION", "ACTIVATION", "HEALTH", "SETUP"]},
    "analyse": {"desc": "Analyses techniques, OHLCV, indicateurs", "icon": "A",
        "patterns": ["ANALYSE", "REALTIME", "RIVER", "OHLCV", "INDICATOR", "TECHNICAL"]},
    "consensus": {"desc": "Consensus multi-IA, alertes, telegram", "icon": "C",
        "patterns": ["CONSENSUS", "MULTI_IA", "ALERTES", "TELEGRAM", "VOTE"]},
    "navigation": {"desc": "Raccourcis, acces rapides, index", "icon": "N",
        "patterns": ["ACCES_RAPIDE", "RACCOURCIS", "INDEX", "RANGEMENT", "CLUSTER_INDEX"]},
    "configs": {"desc": "Fichiers configuration JSON, env, yaml", "icon": "F",
        "patterns": ["config", "cluster_map", "mcp-config", "api-keys", "settings", ".env", ".yaml", ".toml"]},
    "scripts_py": {"desc": "Scripts Python - trading, MCP, analysis", "icon": "P",
        "patterns": [".py"]},
    "scripts_ps": {"desc": "Scripts PowerShell - profil, lanceurs", "icon": "W",
        "patterns": [".ps1", ".bat", ".cmd"]},
    "ameliorations": {"desc": "Taches amelioration, plans, roadmap", "icon": "T",
        "patterns": ["TACHES", "AMELIORATION", "PROCHAINES_ETAPES", "TODO", "ROADMAP"]},
    "mcp_server": {"desc": "MCP server, outils, endpoints", "icon": "M",
        "patterns": ["mcp", "trading_mcp", "MCP_", "mcp_server"]},
    "voice_system": {"desc": "Voice OS, Whisper, TTS, VAD", "icon": "V",
        "patterns": ["voice", "whisper", "tts", "vad", "stt", "speech", "audio"]},
    "gpu_cluster": {"desc": "GPU config, LM Studio cluster, modeles", "icon": "U",
        "patterns": ["gpu", "lmstudio", "cluster", "model", "vram"]},
    "n8n_workflows": {"desc": "Workflows n8n, webhooks, automation", "icon": "8",
        "patterns": ["n8n", "workflow", "webhook"]},
    "market_data": {"desc": "Donnees marche, orderbook, shadow_data", "icon": "D",
        "patterns": ["shadow_data", "coinglass", "orderbook", "market", "kline", "ticker"]},
    "backup": {"desc": "Backups, archives, sauvegardes", "icon": "B",
        "patterns": ["backup", "archive", "sauvegarde", "BACKUP", "LMSTUDIO_BACKUP"]},
    "jarvis": {"desc": "JARVIS Agent - assistant IA autonome", "icon": "J",
        "patterns": ["jarvis", "JARVIS"]},
    "web_docs": {"desc": "Documentation externe fetched depuis internet", "icon": "E",
        "patterns": ["web_doc", "external", "api_doc"]},
    "trading_core": {"desc": "Core trading - strategies, signals, predictions", "icon": "T",
        "patterns": ["trading", "signal", "prediction", "strategy", "trade"]},
    "status": {"desc": "Status systeme, health checks, logs", "icon": "H",
        "patterns": ["STATUS", "HEALTH", "LOG", "MONITOR"]},
}

# ==========================================
# TOUS LES DOSSIERS A SCANNER
# ==========================================
SCAN_DIRS = [
    # Documentation
    (r"/home/turbo\DOCUMENTATION", "guides"),
    # Trading V2 Production
    (r"/home/turbo\TRADING_V2_PRODUCTION\config", "configs"),
    (r"/home/turbo\TRADING_V2_PRODUCTION\scripts", "scripts_py"),
    # Prod V1
    (r"/home/turbo\PROD_INTENSIVE_V1\config", "configs"),
    (r"/home/turbo\PROD_INTENSIVE_V1\scripts", "scripts_py"),
    # CarV1 - CORE
    (r"/home/turbo\carV1\config", "configs"),
    (r"/home/turbo\carV1\python_scripts", "mcp_server"),
    (r"/home/turbo\carV1\scripts", "scripts_py"),
    (r"/home/turbo\carV1\voice_system", "voice_system"),
    (r"/home/turbo\carV1\launchers", "scripts_ps"),
    (r"/home/turbo\carV1\app", "systeme"),
    (r"/home/turbo\carV1\app\services", "systeme"),
    (r"/home/turbo\carV1\docs", "guides"),
    (r"/home/turbo\carV1\database", "configs"),
    # Meta orchestrator
    (r"/home/turbo\carV1\meta_orchestrator", "orchestrateur"),
    # SYSTEMES_IA
    (r"/home/turbo\carV1\SYSTEMES_IA", "gpu_cluster"),
    # Trading cluster manager
    (r"/home/turbo\carV1\trading-cluster-manager", "n8n_workflows"),
    # Control center
    (r"/home/turbo\carV1\control-center", "orchestrateur"),
    # Shadow data (market)
    (r"/home/turbo\carV1\shadow_data", "market_data"),
    # Scripts user
    (r"/home/turbo\carV1\scripts_user", "scripts_py"),
    # Multi IA comm
    (r"/home/turbo\carV1\multi_ia_comm", "consensus"),
    # SCRIPTS bureau
    (r"/home/turbo\SCRIPTS", "scripts_ps"),
    (r"/home/turbo\SCRIPTS_LANCEURS", "scripts_ps"),
    # JARVIS
    (r"/home/turbo\JARVIS", "jarvis"),
    (r"/home/turbo\JARVIS\config", "jarvis"),
    # Backups
    (r"/home/turbo\carV1\backups", "backup"),
    (r"/home/turbo\LMSTUDIO_BACKUP", "backup"),
    (r"/home/turbo\LMSTUDIO_BACKUP\scripts", "backup"),
    # n8n workflows
    (r"/home/turbo\n8n_workflows_backup", "n8n_workflows"),
    # Extrait
    (r"/home/turbo\extrait\bureau-profilshell", "scripts_ps"),
    # Page Trading (frontend)
    (r"/home/turbo\Page-Trading", "trading_core"),
    # Marche
    (r"/home/turbo\carV1\marche", "trading_core"),
]

# Extensions indexables
INDEXABLE_EXTS = {
    ".txt", ".md", ".json", ".py", ".ps1", ".bat", ".cmd", ".env",
    ".sql", ".cfg", ".yaml", ".yml", ".toml", ".js", ".html", ".css",
    ".sh", ".ini", ".xml", ".csv",
}

# Fichiers a ignorer (trop gros / binaires / node_modules)
IGNORE_PATTERNS = [
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "package-lock.json", "yarn.lock", ".pyc", ".pyo",
    "ACE-Step", "temp-repos",  # Skip ML et repos temporaires
]

# Taille max fichier (500KB - skip les gros JSON)
MAX_FILE_SIZE = 500_000

# ==========================================
# WEB DOCS EXTERNES
# ==========================================
WEB_DOCS = [
    {
        "url": "https://contract.mexc.com/api/v1/contract/detail",
        "title": "MEXC Futures API - Contract Details",
        "category": "web_docs",
        "tags": "mexc, api, futures, contract, external",
    },
    {
        "url": "https://mxcdevelop.github.io/apidocs/contract_v1_en/",
        "title": "MEXC Futures API Documentation v1",
        "category": "web_docs",
        "tags": "mexc, api, documentation, futures, external",
    },
    {
        "url": "https://lmstudio.ai/docs",
        "title": "LM Studio Documentation Officielle",
        "category": "web_docs",
        "tags": "lmstudio, documentation, api, models, external",
    },
    {
        "url": "https://docs.n8n.io/api/",
        "title": "n8n API Documentation",
        "category": "web_docs",
        "tags": "n8n, api, workflow, automation, external",
    },
    {
        "url": "https://docs.ccxt.com/",
        "title": "CCXT Library Documentation",
        "category": "web_docs",
        "tags": "ccxt, trading, exchange, api, python, external",
    },
    {
        "url": "https://python-telegram-bot.readthedocs.io/en/stable/",
        "title": "Python Telegram Bot Documentation",
        "category": "web_docs",
        "tags": "telegram, bot, python, api, external",
    },
    {
        "url": "https://docs.python.org/3/library/sqlite3.html",
        "title": "Python SQLite3 Documentation",
        "category": "web_docs",
        "tags": "sqlite, python, database, sql, external",
    },
    {
        "url": "https://rich.readthedocs.io/en/latest/",
        "title": "Rich Python Library - Terminal Formatting",
        "category": "web_docs",
        "tags": "rich, python, terminal, ui, external",
    },
    {
        "url": "https://modelcontextprotocol.io/docs",
        "title": "Model Context Protocol (MCP) Documentation",
        "category": "web_docs",
        "tags": "mcp, protocol, ai, tools, external",
    },
    {
        "url": "https://github.com/openai/whisper",
        "title": "OpenAI Whisper - Speech Recognition",
        "category": "web_docs",
        "tags": "whisper, stt, speech, openai, voice, external",
    },
]


# ==========================================
# HTML CLEANER
# ==========================================
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self.skip = False
        if tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'br', 'tr'):
            self.result.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data)

    def get_text(self):
        return ''.join(self.result)


def html_to_text(html):
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ==========================================
# FONCTIONS CORE (reprises de V1 + ameliorees)
# ==========================================
def get_category(filename, source_tag):
    fname_upper = filename.upper()
    # Priority: source_tag specific matches first
    if source_tag in ("mcp_server",) and filename.endswith(".py"):
        return "mcp_server"
    if source_tag in ("voice_system",):
        return "voice_system"
    if source_tag in ("jarvis",):
        return "jarvis"
    if source_tag in ("market_data",):
        return "market_data"
    if source_tag in ("gpu_cluster",):
        return "gpu_cluster"
    if source_tag in ("n8n_workflows",):
        return "n8n_workflows"
    if source_tag in ("backup",):
        return "backup"
    if source_tag in ("web_docs",):
        return "web_docs"

    for cat_name, cat_info in CATEGORIES.items():
        for pattern in cat_info["patterns"]:
            if pattern.upper() in fname_upper:
                return cat_name

    # Fallback par extension
    ext = Path(filename).suffix.lower()
    if ext == ".py":
        return "scripts_py"
    if ext in (".ps1", ".bat", ".cmd"):
        return "scripts_ps"
    if ext in (".json", ".yaml", ".yml", ".toml", ".env", ".cfg", ".ini"):
        return "configs"
    if source_tag:
        return source_tag

    return "systeme"


def should_skip(filepath):
    for pattern in IGNORE_PATTERNS:
        if pattern in filepath:
            return True
    return False


def extract_keywords(content, title):
    title_words = re.findall(r'[A-Z][a-z]+|[A-Z]+|[a-z]+', title)
    tech_patterns = [
        r'(?:MEXC|LM Studio|Telegram|n8n|Pinecone|SQLite|Gemini|Claude|Perplexity|Whisper|CCXT)',
        r'(?:LONG|SHORT|BREAKOUT|REVERSAL|ANCRAGE|MARGE|CONSENSUS|NEUTRAL|WAIT)',
        r'(?:scanner|sniper|pipeline|webhook|workflow|API|MCP|endpoint)',
        r'(?:RSI|MACD|Chaikin|Bollinger|Fibonacci|EMA|ADX|OBV|ATR|VWAP)',
        r'(?:TP1|TP2|TP3|SL|PnL|ROI|leverage|margin|funding)',
        r'(?:GPU|CUDA|VRAM|CPU|RAM|ONNX|PyTorch)',
        r'(?:192\.168\.1\.\d+)',
        r'(?:JARVIS|DOMINO|ANCRAGE|SYMBIOSE)',
        r'(?:ThreadPoolExecutor|asyncio|RunspacePool|WebSocket)',
        r'(?:Rich|prompt_toolkit|FastAPI|Flask|uvicorn)',
    ]
    keywords = set(w.lower() for w in title_words if len(w) > 2)
    for pattern in tech_patterns:
        matches = re.findall(pattern, content[:50000], re.IGNORECASE)
        keywords.update(m.lower() for m in matches)
    return ", ".join(sorted(keywords)[:40])


def extract_summary(content, max_len=500):
    lines = content.split('\n')
    summary_lines = []
    char_count = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('---') or line.startswith('```'):
            continue
        if len(line) > 15:
            summary_lines.append(line)
            char_count += len(line)
            if char_count >= max_len:
                break
    return " ".join(summary_lines)[:max_len]


def extract_tags(content, filename):
    tags = set()
    tag_map = {
        "mexc": ["mexc", "futures", "contract.mexc"],
        "lmstudio": ["lm studio", "lmstudio", "192.168.1.85", "192.168.1.26", "192.168.1.113"],
        "telegram": ["telegram", "@turbo", "send_telegram"],
        "n8n": ["n8n", "workflow", "webhook"],
        "scanner": ["scanner", "scan_mexc", "breakout", "sniper"],
        "consensus": ["consensus", "multi-ia", "parallel_consensus", "multi_ia"],
        "marge": ["marge", "margin", "ancrage", "liquidation"],
        "gpu": ["gpu", "cuda", "vram", "rtx"],
        "trading": ["trading", "signal", "position", "leverage"],
        "gemini": ["gemini"],
        "python": [".py", "python", "pip", "import "],
        "powershell": [".ps1", "powershell", "pwsh", "function global:"],
        "mcp": ["mcp", "tool_", "model context protocol"],
        "voice": ["voice", "whisper", "tts", "stt", "vad", "speech"],
        "jarvis": ["jarvis"],
        "sqlite": ["sqlite", ".db", "CREATE TABLE", "INSERT INTO"],
        "api": ["api", "endpoint", "REST", "http://", "https://"],
        "ccxt": ["ccxt", "exchange"],
        "rich": ["rich", "console", "Panel", "Table"],
        "electron": ["electron", "ipcMain", "BrowserWindow"],
    }
    content_lower = content[:50000].lower()
    for tag, patterns in tag_map.items():
        for p in patterns:
            if p.lower() in content_lower or p.lower() in filename.lower():
                tags.add(tag)
                break
    return ", ".join(sorted(tags))


def chunk_content(content, chunk_size=1000, overlap=100):
    chunks = []
    sections = re.split(r'\n(?=##?\s)', content)
    current_chunk = ""
    current_title = ""
    for section in sections:
        title_match = re.match(r'(#{1,3})\s+(.+)', section)
        if title_match:
            current_title = title_match.group(2).strip()
        if len(current_chunk) + len(section) > chunk_size and current_chunk:
            chunks.append((current_title, current_chunk.strip()))
            current_chunk = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
        current_chunk += section + "\n"
    if current_chunk.strip():
        chunks.append((current_title, current_chunk.strip()))
    if len(chunks) <= 1 and len(content) > chunk_size:
        chunks = []
        for i in range(0, len(content), chunk_size - overlap):
            chunk = content[i:i + chunk_size]
            chunks.append(("", chunk.strip()))
    return chunks


def index_file(conn, filepath, source_tag, category_map):
    path = Path(filepath)
    if path.suffix.lower() not in INDEXABLE_EXTS:
        return None
    if should_skip(str(filepath)):
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > MAX_FILE_SIZE or size < 10:
        return None
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None
    if len(content.strip()) < 10:
        return None

    title = path.stem.replace('_', ' ').replace('-', ' ').title()
    # Dedupe: ajouter le parent dir si titre trop generique
    if title.lower() in ("config", "settings", "index", "readme", "main", "utils", "api", "test"):
        title = f"{path.parent.name}/{title}"

    category = get_category(path.name, source_tag)
    cat_id = category_map.get(category, category_map.get("systeme", 1))
    keywords = extract_keywords(content, title)
    summary = extract_summary(content)
    tags = extract_tags(content, path.name)

    c = conn.cursor()
    c.execute("SELECT id FROM kb_documents WHERE source_path = ?", (str(filepath),))
    existing = c.fetchone()

    if existing:
        c.execute("""UPDATE kb_documents SET
            title=?, content=?, summary=?, category_id=?, file_type=?,
            file_size=?, tags=?, keywords=?, updated_at=CURRENT_TIMESTAMP, indexed_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (title, content, summary, cat_id, path.suffix, size, tags, keywords, existing[0]))
        doc_id = existing[0]
        c.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        action = "UPDATE"
    else:
        c.execute("""INSERT INTO kb_documents
            (title, content, summary, category_id, source_path, source_type, file_type, file_size, tags, keywords, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (title, content, summary, cat_id, str(filepath), 'file', path.suffix, size, tags, keywords))
        doc_id = c.lastrowid
        action = "INSERT"

    chunks = chunk_content(content)
    for i, (section_title, chunk_text) in enumerate(chunks):
        c.execute("""INSERT INTO kb_chunks (doc_id, chunk_text, chunk_index, chunk_size, section_title)
            VALUES (?, ?, ?, ?, ?)""", (doc_id, chunk_text, i, len(chunk_text), section_title))

    for tag_name in [t.strip() for t in tags.split(',') if t.strip()]:
        c.execute("INSERT OR IGNORE INTO kb_tags (name) VALUES (?)", (tag_name,))
        c.execute("SELECT id FROM kb_tags WHERE name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO kb_doc_tags (doc_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))

    return {"action": action, "doc_id": doc_id, "title": title, "category": category, "chunks": len(chunks), "size": size, "tags": tags}


def fetch_web_doc(url, title, timeout=15):
    """Fetch une page web et extrait le texte"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (KB-Agent/2.0; Trading-AI-System)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            encoding = resp.headers.get_content_charset() or 'utf-8'
            html = raw.decode(encoding, errors='replace')

        # Extraire le texte
        text = html_to_text(html)
        # Nettoyer
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{3,}', ' ', text)

        if len(text.strip()) < 50:
            return None

        # Limiter a 100KB de texte
        return text[:100_000]
    except Exception as e:
        print(f"    FETCH FAIL {url}: {e}")
        return None


def index_web_doc(conn, doc_info, category_map):
    """Indexe un document web dans la base"""
    url = doc_info["url"]
    title = doc_info["title"]
    category = doc_info.get("category", "web_docs")
    tags = doc_info.get("tags", "external")

    c = conn.cursor()
    # Check si deja indexe
    c.execute("SELECT id FROM kb_documents WHERE source_path = ?", (url,))
    existing = c.fetchone()

    content = fetch_web_doc(url, title)
    if not content:
        return None

    cat_id = category_map.get(category, category_map.get("web_docs", 1))
    keywords = extract_keywords(content, title)
    summary = extract_summary(content)

    if existing:
        c.execute("""UPDATE kb_documents SET
            title=?, content=?, summary=?, category_id=?, file_type=?,
            file_size=?, tags=?, keywords=?, updated_at=CURRENT_TIMESTAMP, indexed_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (title, content, summary, cat_id, '.html', len(content), tags, keywords, existing[0]))
        doc_id = existing[0]
        c.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        action = "UPDATE"
    else:
        c.execute("""INSERT INTO kb_documents
            (title, content, summary, category_id, source_path, source_type, file_type, file_size, tags, keywords, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (title, content, summary, cat_id, url, 'web', '.html', len(content), tags, keywords))
        doc_id = c.lastrowid
        action = "INSERT"

    chunks = chunk_content(content)
    for i, (section_title, chunk_text) in enumerate(chunks):
        c.execute("""INSERT INTO kb_chunks (doc_id, chunk_text, chunk_index, chunk_size, section_title)
            VALUES (?, ?, ?, ?, ?)""", (doc_id, chunk_text, i, len(chunk_text), section_title))

    for tag_name in [t.strip() for t in tags.split(',') if t.strip()]:
        c.execute("INSERT OR IGNORE INTO kb_tags (name) VALUES (?)", (tag_name,))
        c.execute("SELECT id FROM kb_tags WHERE name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO kb_doc_tags (doc_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))

    return {"action": action, "doc_id": doc_id, "title": title, "category": category, "chunks": len(chunks), "size": len(content)}


# ==========================================
# MAIN
# ==========================================
def main():
    start_time = time.time()
    print("=" * 70)
    print("  KNOWLEDGE BASE INDEXER V2.0 - FULL BUREAU + WEB DOCS")
    print(f"  DB: {DB_PATH}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Categories
    print("\n[1/4] Categories...")
    category_map = {}
    for cat_name, cat_info in CATEGORIES.items():
        c.execute("INSERT OR IGNORE INTO kb_categories (name, description, icon) VALUES (?, ?, ?)",
                  (cat_name, cat_info["desc"], cat_info["icon"]))
        c.execute("SELECT id FROM kb_categories WHERE name = ?", (cat_name,))
        row = c.fetchone()
        if row:
            category_map[cat_name] = row[0]
    conn.commit()
    print(f"  => {len(category_map)} categories")

    # 2. Indexation fichiers locaux
    print("\n[2/4] Indexation COMPLETE F:/BUREAU...")
    stats = {"total": 0, "inserted": 0, "updated": 0, "skipped": 0, "chunks": 0, "bytes": 0, "errors": 0}

    for scan_dir, source_tag in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue

        files = []
        for root, dirs, filenames in os.walk(scan_dir):
            # Skip certains sous-dossiers
            dirs[:] = [d for d in dirs if not should_skip(os.path.join(root, d))]
            for fname in filenames:
                fpath = os.path.join(root, fname)
                if not should_skip(fpath):
                    files.append(fpath)

        if not files:
            continue

        dir_inserted = 0
        dir_updated = 0
        for filepath in sorted(files):
            stats["total"] += 1
            try:
                result = index_file(conn, filepath, source_tag, category_map)
            except Exception as e:
                stats["errors"] += 1
                continue

            if result is None:
                stats["skipped"] += 1
                continue

            if result["action"] == "INSERT":
                stats["inserted"] += 1
                dir_inserted += 1
            else:
                stats["updated"] += 1
                dir_updated += 1
            stats["chunks"] += result["chunks"]
            stats["bytes"] += result["size"]

        total_dir = dir_inserted + dir_updated
        if total_dir > 0:
            print(f"  {scan_dir.replace('F:/BUREAU/', '')[:50]:50s} +{dir_inserted:3d} ~{dir_updated:3d} ({total_dir} docs)")

    conn.commit()

    # 3. Web docs externes
    print(f"\n[3/4] Fetching {len(WEB_DOCS)} docs web externes...")
    web_stats = {"fetched": 0, "failed": 0}

    for doc_info in WEB_DOCS:
        print(f"  Fetching: {doc_info['title'][:50]}...", end=" ", flush=True)
        try:
            result = index_web_doc(conn, doc_info, category_map)
            if result:
                web_stats["fetched"] += 1
                stats["chunks"] += result["chunks"]
                stats["bytes"] += result["size"]
                print(f"OK ({result['chunks']} chunks, {result['size']//1024}KB)")
            else:
                web_stats["failed"] += 1
                print("SKIP (empty)")
        except Exception as e:
            web_stats["failed"] += 1
            print(f"FAIL ({e})")

    conn.commit()

    # 4. Mise a jour compteurs
    print("\n[4/4] Compteurs et stats...")
    c.execute("""UPDATE kb_categories SET doc_count = (
        SELECT COUNT(*) FROM kb_documents WHERE category_id = kb_categories.id AND is_active = 1
    )""")
    c.execute("""UPDATE kb_tags SET doc_count = (
        SELECT COUNT(*) FROM kb_doc_tags WHERE tag_id = kb_tags.id
    )""")
    conn.commit()

    # Stats finales
    c.execute("SELECT COUNT(*) FROM kb_documents WHERE is_active = 1")
    total_docs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kb_chunks")
    total_chunks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kb_tags WHERE doc_count > 0")
    total_tags = c.fetchone()[0]
    c.execute("SELECT name, doc_count FROM kb_categories WHERE doc_count > 0 ORDER BY doc_count DESC")
    cats = c.fetchall()

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("  RESULTATS V2.0")
    print("=" * 70)
    print(f"  Documents indexes: {total_docs}")
    print(f"  Chunks crees:     {total_chunks}")
    print(f"  Tags uniques:     {total_tags}")
    print(f"  Taille totale:    {stats['bytes'] / 1024 / 1024:.1f} MB")
    print(f"  Fichiers scannes: {stats['total']}")
    print(f"  Inseres:          {stats['inserted']}")
    print(f"  Mis a jour:       {stats['updated']}")
    print(f"  Ignores:          {stats['skipped']}")
    print(f"  Erreurs:          {stats['errors']}")
    print(f"  Web docs fetched: {web_stats['fetched']}/{len(WEB_DOCS)}")
    print(f"  Duree:            {elapsed:.1f}s")

    print(f"\n  Categories:")
    for name, count in cats:
        bar = '#' * min(count, 40)
        print(f"    {name:20s} {count:4d} {bar}")

    conn.close()
    print(f"\n  Termine: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
