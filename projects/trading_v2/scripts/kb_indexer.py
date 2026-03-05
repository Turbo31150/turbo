"""
Knowledge Base Indexer v1.0
Indexe tous les fichiers documentation, configs et scripts dans SQLite FTS5
"""
import sqlite3
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

DB_PATH = r"F:\BUREAU\TRADING_V2_PRODUCTION\database\trading.db"

# Categories avec mapping automatique
CATEGORIES = {
    "guides": {"desc": "Guides de demarrage, tutoriels, quickstarts", "icon": "📖",
        "patterns": ["GUIDE", "DEMARRAGE", "QUICKSTART", "START_HERE", "README", "QUICK_START", "UTILISATION"]},
    "scanners": {"desc": "Documentation scanners MEXC, sniper, breakout", "icon": "🔍",
        "patterns": ["SCANNER", "SCAN_", "SNIPER", "AUTO_SCANNER", "BREAKOUT"]},
    "orchestrateur": {"desc": "Meta-orchestrateur, coordination, domino", "icon": "🎯",
        "patterns": ["META_ORCHESTRATEUR", "ORCHESTR", "DOMINO", "PIPELINE"]},
    "sessions": {"desc": "Recaps de sessions, status, changelog", "icon": "📝",
        "patterns": ["SESSION", "RECAP", "RESUME_SESSION", "STATUS", "FICHIERS_CREES"]},
    "systeme": {"desc": "Configuration systeme, deploiement, installation", "icon": "⚙️",
        "patterns": ["SYSTEME", "CONFIG", "DEPLOIEMENT", "INSTALLATION", "ACTIVATION"]},
    "analyse": {"desc": "Analyses techniques, RIVER, realtime", "icon": "📊",
        "patterns": ["ANALYSE", "REALTIME", "RIVER"]},
    "consensus": {"desc": "Consensus multi-IA, alertes, telegram", "icon": "🤖",
        "patterns": ["CONSENSUS", "MULTI_IA", "ALERTES", "TELEGRAM"]},
    "navigation": {"desc": "Raccourcis, acces rapides, index", "icon": "🗂️",
        "patterns": ["ACCES_RAPIDE", "RACCOURCIS", "INDEX", "RANGEMENT"]},
    "configs": {"desc": "Fichiers de configuration JSON, env, etc.", "icon": "🔧",
        "patterns": ["config", "cluster_map", "pipeline", "mcp-config", "api-keys"]},
    "scripts": {"desc": "Scripts Python, PowerShell, batch", "icon": "💻",
        "patterns": ["script", ".py", ".ps1", ".bat", ".cmd"]},
    "ameliorations": {"desc": "Taches d'amelioration, plans, roadmap", "icon": "🚀",
        "patterns": ["TACHES", "AMELIORATION", "PROCHAINES_ETAPES"]},
}

# Dossiers a scanner
SCAN_DIRS = [
    (r"F:\BUREAU\DOCUMENTATION", "documentation"),
    (r"F:\BUREAU\TRADING_V2_PRODUCTION\config", "configs"),
    (r"F:\BUREAU\PROD_INTENSIVE_V1\config", "configs"),
    (r"F:\BUREAU\carV1\config", "configs"),
    (r"F:\BUREAU\SCRIPTS", "scripts"),
    (r"F:\BUREAU\SCRIPTS_LANCEURS", "scripts"),
]

# Extensions a indexer
INDEXABLE_EXTS = {".txt", ".md", ".json", ".py", ".ps1", ".bat", ".cmd", ".env", ".sql", ".cfg", ".yaml", ".yml", ".toml"}


def get_category(filename, source_tag):
    """Determine la categorie d'un fichier par pattern matching"""
    fname_upper = filename.upper()
    for cat_name, cat_info in CATEGORIES.items():
        for pattern in cat_info["patterns"]:
            if pattern.upper() in fname_upper:
                return cat_name
    # Fallback par source tag
    if source_tag in ("configs",):
        return "configs"
    if source_tag in ("scripts",):
        return "scripts"
    return "systeme"  # default


def extract_keywords(content, title):
    """Extrait les mots-cles importants du contenu"""
    # Mots-cles du titre
    title_words = re.findall(r'[A-Z][a-z]+|[A-Z]+|[a-z]+', title)

    # Mots-cles techniques du contenu
    tech_patterns = [
        r'(?:MEXC|LM Studio|Telegram|n8n|Pinecone|SQLite|Gemini|Claude|Perplexity)',
        r'(?:LONG|SHORT|BREAKOUT|REVERSAL|ANCRAGE|MARGE|CONSENSUS)',
        r'(?:scanner|sniper|pipeline|webhook|workflow|API)',
        r'(?:RSI|MACD|Chaikin|Bollinger|Fibonacci|EMA)',
        r'(?:TP1|TP2|TP3|SL|PnL|ROI|leverage)',
        r'(?:GPU|CUDA|VRAM|CPU|RAM)',
        r'(?:192\.168\.1\.\d+)',
    ]

    keywords = set(w.lower() for w in title_words if len(w) > 2)
    for pattern in tech_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        keywords.update(m.lower() for m in matches)

    return ", ".join(sorted(keywords)[:30])


def extract_summary(content, max_len=500):
    """Extrait un resume du contenu (premiers paragraphes significatifs)"""
    lines = content.split('\n')
    summary_lines = []
    char_count = 0

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('---') or line.startswith('```'):
            continue
        if len(line) > 20:  # Lignes significatives seulement
            summary_lines.append(line)
            char_count += len(line)
            if char_count >= max_len:
                break

    return " ".join(summary_lines)[:max_len]


def extract_tags(content, filename):
    """Extrait les tags du contenu"""
    tags = set()

    # Tags par contenu
    tag_map = {
        "mexc": ["mexc", "futures", "contract"],
        "lmstudio": ["lm studio", "lmstudio", "192.168"],
        "telegram": ["telegram", "@turbo"],
        "n8n": ["n8n", "workflow"],
        "scanner": ["scanner", "scan", "breakout"],
        "consensus": ["consensus", "multi-ia", "parallel"],
        "marge": ["marge", "margin", "ancrage"],
        "gpu": ["gpu", "cuda", "vram"],
        "trading": ["trading", "signal", "position"],
        "gemini": ["gemini"],
        "python": [".py", "python", "pip"],
        "powershell": [".ps1", "powershell", "pwsh"],
    }

    content_lower = content.lower()
    for tag, patterns in tag_map.items():
        for p in patterns:
            if p in content_lower:
                tags.add(tag)
                break

    return ", ".join(sorted(tags))


def chunk_content(content, chunk_size=1000, overlap=100):
    """Decoupe le contenu en chunks pour recherche granulaire"""
    chunks = []

    # Essayer de decouper par sections (##)
    sections = re.split(r'\n(?=##?\s)', content)

    current_chunk = ""
    current_title = ""

    for section in sections:
        # Extraire le titre de section
        title_match = re.match(r'(#{1,3})\s+(.+)', section)
        if title_match:
            current_title = title_match.group(2).strip()

        if len(current_chunk) + len(section) > chunk_size and current_chunk:
            chunks.append((current_title, current_chunk.strip()))
            # Overlap
            current_chunk = current_chunk[-overlap:] if len(current_chunk) > overlap else ""

        current_chunk += section + "\n"

    if current_chunk.strip():
        chunks.append((current_title, current_chunk.strip()))

    # Si pas de sections, decouper par taille
    if len(chunks) <= 1 and len(content) > chunk_size:
        chunks = []
        for i in range(0, len(content), chunk_size - overlap):
            chunk = content[i:i + chunk_size]
            chunks.append(("", chunk.strip()))

    return chunks


def index_file(conn, filepath, source_tag, category_map):
    """Indexe un fichier dans la base"""
    path = Path(filepath)

    if path.suffix.lower() not in INDEXABLE_EXTS:
        return None

    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"  SKIP {path.name}: {e}")
        return None

    if len(content.strip()) < 10:
        return None

    title = path.stem.replace('_', ' ').replace('-', ' ').title()
    category = get_category(path.name, source_tag)
    cat_id = category_map.get(category, 1)
    keywords = extract_keywords(content, title)
    summary = extract_summary(content)
    tags = extract_tags(content, path.name)

    c = conn.cursor()

    # Verifier si deja indexe (par source_path)
    c.execute("SELECT id FROM kb_documents WHERE source_path = ?", (str(filepath),))
    existing = c.fetchone()

    if existing:
        # Update
        c.execute("""UPDATE kb_documents SET
            title=?, content=?, summary=?, category_id=?, file_type=?,
            file_size=?, tags=?, keywords=?, updated_at=CURRENT_TIMESTAMP, indexed_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (title, content, summary, cat_id, path.suffix, path.stat().st_size, tags, keywords, existing[0]))
        doc_id = existing[0]
        # Supprimer anciens chunks
        c.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        action = "UPDATE"
    else:
        # Insert
        c.execute("""INSERT INTO kb_documents
            (title, content, summary, category_id, source_path, source_type, file_type, file_size, tags, keywords, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (title, content, summary, cat_id, str(filepath), 'file', path.suffix, path.stat().st_size, tags, keywords))
        doc_id = c.lastrowid
        action = "INSERT"

    # Chunks
    chunks = chunk_content(content)
    for i, (section_title, chunk_text) in enumerate(chunks):
        c.execute("""INSERT INTO kb_chunks (doc_id, chunk_text, chunk_index, chunk_size, section_title)
            VALUES (?, ?, ?, ?, ?)""", (doc_id, chunk_text, i, len(chunk_text), section_title))

    # Tags (many-to-many)
    for tag_name in [t.strip() for t in tags.split(',') if t.strip()]:
        c.execute("INSERT OR IGNORE INTO kb_tags (name) VALUES (?)", (tag_name,))
        c.execute("SELECT id FROM kb_tags WHERE name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO kb_doc_tags (doc_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))

    return {
        "action": action,
        "doc_id": doc_id,
        "title": title,
        "category": category,
        "chunks": len(chunks),
        "size": path.stat().st_size,
        "tags": tags
    }


def main():
    print("=" * 60)
    print("KNOWLEDGE BASE INDEXER v1.0")
    print(f"DB: {DB_PATH}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Inserer categories
    print("\n[1/3] Categories...")
    category_map = {}
    for cat_name, cat_info in CATEGORIES.items():
        c.execute("INSERT OR IGNORE INTO kb_categories (name, description, icon) VALUES (?, ?, ?)",
                  (cat_name, cat_info["desc"], cat_info["icon"]))
        c.execute("SELECT id FROM kb_categories WHERE name = ?", (cat_name,))
        category_map[cat_name] = c.fetchone()[0]
        print(f"  {cat_info['icon']} {cat_name}: {cat_info['desc']}")
    conn.commit()
    print(f"  => {len(category_map)} categories")

    # 2. Scanner et indexer
    print("\n[2/3] Indexation des fichiers...")
    stats = {"total": 0, "inserted": 0, "updated": 0, "skipped": 0, "chunks": 0, "bytes": 0}

    for scan_dir, source_tag in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            print(f"  SKIP {scan_dir} (n'existe pas)")
            continue

        print(f"\n  📂 {scan_dir}")
        files = []
        for root, dirs, filenames in os.walk(scan_dir):
            for fname in filenames:
                files.append(os.path.join(root, fname))

        for filepath in sorted(files):
            result = index_file(conn, filepath, source_tag, category_map)
            stats["total"] += 1

            if result is None:
                stats["skipped"] += 1
                continue

            if result["action"] == "INSERT":
                stats["inserted"] += 1
            else:
                stats["updated"] += 1
            stats["chunks"] += result["chunks"]
            stats["bytes"] += result["size"]

            print(f"    {result['action']:6s} #{result['doc_id']:3d} | {result['title'][:40]:40s} | {result['category']:15s} | {result['chunks']:2d} chunks | {result['tags'][:30]}")

    conn.commit()

    # 3. Mettre a jour les compteurs
    print("\n[3/3] Mise a jour compteurs...")
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
    c.execute("SELECT COUNT(*) FROM kb_tags")
    total_tags = c.fetchone()[0]
    c.execute("SELECT name, doc_count FROM kb_categories WHERE doc_count > 0 ORDER BY doc_count DESC")
    cats = c.fetchall()

    print("\n" + "=" * 60)
    print("RESULTATS")
    print("=" * 60)
    print(f"  Documents indexes: {total_docs}")
    print(f"  Chunks crees:     {total_chunks}")
    print(f"  Tags uniques:     {total_tags}")
    print(f"  Taille totale:    {stats['bytes'] / 1024:.1f} KB")
    print(f"  Inseres:          {stats['inserted']}")
    print(f"  Mis a jour:       {stats['updated']}")
    print(f"  Ignores:          {stats['skipped']}")
    print(f"\n  Categories:")
    for name, count in cats:
        print(f"    {name}: {count} docs")

    conn.close()
    print(f"\nTermine: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
