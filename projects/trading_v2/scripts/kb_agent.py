"""
Knowledge Base Agent v2.0 - Bibliothecaire Autonome
Recherche ultra-rapide FTS5, gestion complete de la bibliotheque interne + externe
Usage:
    python kb_agent.py search "mexc scanner"           Recherche full-text (1-3ms)
    python kb_agent.py search "query" --limit 10       Limiter resultats
    python kb_agent.py chunks "query"                  Recherche granulaire
    python kb_agent.py list [category]                 Lister documents
    python kb_agent.py tags                            Tous les tags
    python kb_agent.py stats                           Statistiques globales
    python kb_agent.py info <doc_id>                   Detail document
    python kb_agent.py similar <doc_id>                Documents similaires
    python kb_agent.py reindex                         Re-indexation FULL (V2)
    python kb_agent.py add <file_path>                 Ajouter un fichier
    python kb_agent.py web <url> [--title "t"]         Fetch + indexer doc web
    python kb_agent.py export [--format json|csv]      Export
    python kb_agent.py cleanup                         Nettoyage
    python kb_agent.py serve [--port 8899]             API REST locale
    python kb_agent.py categories                      Liste categories
    python kb_agent.py top [n]                         Top N documents par taille
"""
import sqlite3
import sys
import os
import json
import re
import time
from datetime import datetime
from pathlib import Path

DB_PATH = r"F:\BUREAU\TRADING_V2_PRODUCTION\database\trading.db"


class KnowledgeBase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA cache_size=-8000")  # 8MB cache

    def close(self):
        self.conn.close()

    # ============ SEARCH ============
    def search(self, query, limit=10, category=None, tag=None):
        """Recherche FTS5 ultra-rapide avec ranking BM25"""
        start = time.time()

        # Preparer la query FTS5 (echapper caracteres speciaux, entourer de guillemets)
        words = []
        for w in query.split():
            # Enlever caracteres non-alphanumeriques problematiques pour FTS5
            clean = re.sub(r'[^\w]', '', w)
            if clean:
                words.append(f'"{clean}"')
        fts_query = " OR ".join(words) if words else f'"{query}"'

        sql = """
            SELECT d.id, d.title, d.source_path, d.file_type, d.file_size,
                   d.tags, d.keywords, c.name as category, c.icon,
                   snippet(kb_search_fts, 1, '>>>', '<<<', '...', 40) as snippet,
                   rank
            FROM kb_search_fts fts
            JOIN kb_documents d ON d.id = fts.rowid
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE kb_search_fts MATCH ?
              AND d.is_active = 1
        """
        params = [fts_query]

        if category:
            sql += " AND c.name = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        results = self.conn.execute(sql, params).fetchall()
        duration = (time.time() - start) * 1000

        # Log la recherche
        self.conn.execute(
            "INSERT INTO kb_search_log (query, results_count, search_type, duration_ms) VALUES (?,?,?,?)",
            (query, len(results), 'fts5', int(duration))
        )
        self.conn.commit()

        return results, duration

    def search_chunks(self, query, limit=20):
        """Recherche dans les chunks (granulaire)"""
        start = time.time()
        words = query.split()
        conditions = " AND ".join(["chunk_text LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]

        sql = f"""
            SELECT ch.id, ch.chunk_text, ch.section_title, ch.chunk_index,
                   d.id as doc_id, d.title, c.name as category
            FROM kb_chunks ch
            JOIN kb_documents d ON d.id = ch.doc_id
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE {conditions}
            ORDER BY d.priority DESC, ch.chunk_index
            LIMIT ?
        """
        params.append(limit)
        results = self.conn.execute(sql, params).fetchall()
        duration = (time.time() - start) * 1000
        return results, duration

    # ============ LIST ============
    def list_docs(self, category=None, limit=50):
        """Liste les documents par categorie"""
        sql = """
            SELECT d.id, d.title, d.source_path, d.file_type, d.file_size,
                   d.tags, c.name as category, c.icon, d.created_at
            FROM kb_documents d
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE d.is_active = 1
        """
        params = []
        if category:
            sql += " AND c.name = ?"
            params.append(category)
        sql += " ORDER BY c.name, d.title LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def list_categories(self):
        """Liste les categories avec compteurs"""
        return self.conn.execute(
            "SELECT id, name, description, icon, doc_count FROM kb_categories ORDER BY doc_count DESC"
        ).fetchall()

    def list_tags(self):
        """Liste tous les tags avec compteurs"""
        return self.conn.execute(
            "SELECT name, doc_count FROM kb_tags WHERE doc_count > 0 ORDER BY doc_count DESC"
        ).fetchall()

    # ============ INFO ============
    def get_doc(self, doc_id):
        """Detail complet d'un document"""
        doc = self.conn.execute("""
            SELECT d.*, c.name as category, c.icon
            FROM kb_documents d
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE d.id = ?
        """, (doc_id,)).fetchone()

        chunks = self.conn.execute(
            "SELECT * FROM kb_chunks WHERE doc_id = ? ORDER BY chunk_index", (doc_id,)
        ).fetchall()

        return doc, chunks

    def find_similar(self, doc_id, limit=5):
        """Trouve des documents similaires (par tags/keywords communs)"""
        doc = self.conn.execute("SELECT tags, keywords FROM kb_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            return []

        words = set()
        for field in [doc['tags'], doc['keywords']]:
            if field:
                words.update(w.strip() for w in field.split(',') if w.strip())

        if not words:
            return []

        # Chercher des docs avec des tags/keywords en commun
        word_list = list(words)[:10]
        conditions = " OR ".join(["tags LIKE ? OR keywords LIKE ?" for _ in word_list])
        params = []
        for w in word_list:
            params.extend([f"%{w}%", f"%{w}%"])

        sql = f"""
            SELECT d.id, d.title, d.tags, d.keywords, c.name as category, c.icon
            FROM kb_documents d
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE d.id != ? AND d.is_active = 1 AND ({conditions})
            LIMIT ?
        """
        return self.conn.execute(sql, [doc_id] + params + [limit]).fetchall()

    # ============ STATS ============
    def stats(self):
        """Statistiques globales"""
        s = {}
        s['total_docs'] = self.conn.execute("SELECT COUNT(*) FROM kb_documents WHERE is_active=1").fetchone()[0]
        s['total_chunks'] = self.conn.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
        s['total_tags'] = self.conn.execute("SELECT COUNT(*) FROM kb_tags WHERE doc_count>0").fetchone()[0]
        s['total_size'] = self.conn.execute("SELECT COALESCE(SUM(file_size),0) FROM kb_documents WHERE is_active=1").fetchone()[0]
        s['total_searches'] = self.conn.execute("SELECT COUNT(*) FROM kb_search_log").fetchone()[0]
        s['avg_search_ms'] = self.conn.execute("SELECT COALESCE(AVG(duration_ms),0) FROM kb_search_log").fetchone()[0]
        s['categories'] = self.conn.execute(
            "SELECT name, icon, doc_count FROM kb_categories WHERE doc_count>0 ORDER BY doc_count DESC"
        ).fetchall()
        s['top_tags'] = self.conn.execute(
            "SELECT name, doc_count FROM kb_tags WHERE doc_count>0 ORDER BY doc_count DESC LIMIT 15"
        ).fetchall()
        s['recent_searches'] = self.conn.execute(
            "SELECT query, results_count, duration_ms, created_at FROM kb_search_log ORDER BY id DESC LIMIT 5"
        ).fetchall()
        s['pinecone_synced'] = self.conn.execute(
            "SELECT COUNT(*) FROM kb_documents WHERE pinecone_synced=1"
        ).fetchone()[0]
        return s

    # ============ ADD ============
    def add_file(self, filepath, category=None, tags=None):
        """Ajoute un fichier a la base"""
        from kb_indexer import index_file, CATEGORIES
        category_map = {}
        for row in self.conn.execute("SELECT id, name FROM kb_categories").fetchall():
            category_map[row['name']] = row['id']

        result = index_file(self.conn, filepath, category or "systeme", category_map)
        self.conn.commit()
        return result

    def add_text(self, title, content, category="systeme", tags=""):
        """Ajoute du texte directement"""
        cat = self.conn.execute("SELECT id FROM kb_categories WHERE name=?", (category,)).fetchone()
        cat_id = cat['id'] if cat else 1

        self.conn.execute("""INSERT INTO kb_documents
            (title, content, summary, category_id, source_type, tags, indexed_at)
            VALUES (?, ?, ?, ?, 'manual', ?, CURRENT_TIMESTAMP)""",
            (title, content, content[:500], cat_id, tags))
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ============ EXPORT ============
    def export_json(self, category=None):
        """Exporte en JSON"""
        docs = self.list_docs(category=category, limit=9999)
        result = []
        for d in docs:
            result.append({
                "id": d['id'], "title": d['title'],
                "category": d['category'], "tags": d['tags'],
                "source": d['source_path'], "size": d['file_size']
            })
        return json.dumps(result, indent=2, ensure_ascii=False)

    def export_csv(self, category=None):
        """Exporte en CSV"""
        docs = self.list_docs(category=category, limit=9999)
        lines = ["id,title,category,tags,source,size"]
        for d in docs:
            lines.append(f'{d["id"]},"{d["title"]}",{d["category"]},"{d["tags"]}","{d["source_path"]}",{d["file_size"]}')
        return "\n".join(lines)

    # ============ CLEANUP ============
    def cleanup(self):
        """Nettoie doublons et docs vides"""
        deleted = 0
        # Docs vides
        c = self.conn.execute("DELETE FROM kb_documents WHERE LENGTH(TRIM(content)) < 10")
        deleted += c.rowcount
        # Chunks orphelins
        c = self.conn.execute("DELETE FROM kb_chunks WHERE doc_id NOT IN (SELECT id FROM kb_documents)")
        orphan_chunks = c.rowcount
        # Tags inutilises
        c = self.conn.execute("DELETE FROM kb_tags WHERE doc_count = 0")
        empty_tags = c.rowcount
        self.conn.commit()
        return {"docs_deleted": deleted, "orphan_chunks": orphan_chunks, "empty_tags": empty_tags}


# ============ CLI ============
def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    kb = KnowledgeBase()
    cmd = sys.argv[1].lower()

    try:
        if cmd == "search":
            query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            if not query:
                print("Usage: kb_agent.py search <query>")
                return

            limit = 10
            category = None
            if "--limit" in sys.argv:
                idx = sys.argv.index("--limit")
                limit = int(sys.argv[idx + 1])
            if "--category" in sys.argv:
                idx = sys.argv.index("--category")
                category = sys.argv[idx + 1]

            # Nettoyer la query des flags
            clean_query = re.sub(r'--\w+\s+\S+', '', query).strip()

            results, duration = kb.search(clean_query, limit=limit, category=category)
            print_header(f"RECHERCHE: '{clean_query}' ({len(results)} resultats, {duration:.1f}ms)")

            for r in results:
                icon = r['icon'] or ''
                print(f"\n  [{r['id']:3d}] {icon} {r['title']}")
                print(f"        Cat: {r['category']} | Tags: {r['tags'][:50]}")
                if r['snippet']:
                    snippet = r['snippet'].replace('\n', ' ')[:120]
                    print(f"        >>> {snippet}")
                if r['source_path']:
                    print(f"        Src: {r['source_path']}")

        elif cmd == "chunks":
            query = " ".join(sys.argv[2:])
            results, duration = kb.search_chunks(query)
            print_header(f"CHUNKS: '{query}' ({len(results)} resultats, {duration:.1f}ms)")
            for r in results:
                text = r['chunk_text'][:200].replace('\n', ' ')
                print(f"\n  Doc#{r['doc_id']} [{r['title']}] chunk#{r['chunk_index']}")
                print(f"  Section: {r['section_title']}")
                print(f"  {text}...")

        elif cmd == "list":
            category = sys.argv[2] if len(sys.argv) > 2 else None
            docs = kb.list_docs(category=category)
            title = f"DOCUMENTS: {category}" if category else "TOUS LES DOCUMENTS"
            print_header(f"{title} ({len(docs)})")
            current_cat = ""
            for d in docs:
                if d['category'] != current_cat:
                    current_cat = d['category']
                    icon = d['icon'] or ''
                    print(f"\n  {icon} {current_cat.upper()}")
                    print(f"  {'-' * 40}")
                print(f"    [{d['id']:3d}] {d['title'][:45]:45s} {d['file_type'] or '':5s} {d['file_size']:>7d}B")

        elif cmd == "tags":
            tags = kb.list_tags()
            print_header(f"TAGS ({len(tags)})")
            for t in tags:
                bar = '#' * min(t['doc_count'], 40)
                print(f"  {t['name']:20s} {t['doc_count']:3d} {bar}")

        elif cmd == "stats":
            s = kb.stats()
            print_header("STATISTIQUES KNOWLEDGE BASE")
            print(f"  Documents:      {s['total_docs']}")
            print(f"  Chunks:         {s['total_chunks']}")
            print(f"  Tags uniques:   {s['total_tags']}")
            print(f"  Taille totale:  {s['total_size'] / 1024:.1f} KB")
            print(f"  Recherches:     {s['total_searches']}")
            print(f"  Latence moy:    {s['avg_search_ms']:.1f} ms")
            print(f"  Pinecone sync:  {s['pinecone_synced']}/{s['total_docs']}")

            print(f"\n  Categories:")
            for c in s['categories']:
                print(f"    {c['icon']} {c['name']:20s} {c['doc_count']:3d} docs")

            print(f"\n  Top Tags:")
            for t in s['top_tags']:
                print(f"    {t['name']:20s} {t['doc_count']:3d} docs")

            if s['recent_searches']:
                print(f"\n  Dernieres recherches:")
                for r in s['recent_searches']:
                    print(f"    '{r['query'][:30]}' -> {r['results_count']} res ({r['duration_ms']}ms) {r['created_at']}")

        elif cmd == "info":
            doc_id = int(sys.argv[2])
            doc, chunks = kb.get_doc(doc_id)
            if not doc:
                print(f"Document #{doc_id} non trouve")
                return
            print_header(f"DOCUMENT #{doc_id}")
            print(f"  Titre:     {doc['title']}")
            print(f"  Categorie: {doc['icon']} {doc['category']}")
            print(f"  Source:    {doc['source_path']}")
            print(f"  Type:      {doc['file_type']} ({doc['file_size']} bytes)")
            print(f"  Tags:      {doc['tags']}")
            print(f"  Keywords:  {doc['keywords'][:100]}")
            print(f"  Indexe:    {doc['indexed_at']}")
            print(f"  Chunks:    {len(chunks)}")
            print(f"\n  Resume:")
            print(f"  {doc['summary'][:300]}")

        elif cmd == "similar":
            doc_id = int(sys.argv[2])
            results = kb.find_similar(doc_id)
            print_header(f"SIMILAIRES A #{doc_id}")
            for r in results:
                print(f"  [{r['id']:3d}] {r['icon']} {r['title']} ({r['category']})")

        elif cmd == "add":
            filepath = sys.argv[2]
            if os.path.isfile(filepath):
                result = kb.add_file(filepath)
                if result:
                    print(f"OK - Doc #{result['doc_id']} ajoute ({result['chunks']} chunks)")
                else:
                    print("Echec de l'ajout")
            else:
                print(f"Fichier non trouve: {filepath}")

        elif cmd == "export":
            fmt = "json"
            category = None
            if "--format" in sys.argv:
                idx = sys.argv.index("--format")
                fmt = sys.argv[idx + 1]
            if "--category" in sys.argv:
                idx = sys.argv.index("--category")
                category = sys.argv[idx + 1]

            if fmt == "csv":
                print(kb.export_csv(category))
            else:
                print(kb.export_json(category))

        elif cmd == "cleanup":
            result = kb.cleanup()
            print_header("CLEANUP")
            print(f"  Docs supprimes:   {result['docs_deleted']}")
            print(f"  Chunks orphelins: {result['orphan_chunks']}")
            print(f"  Tags vides:       {result['empty_tags']}")

        elif cmd == "reindex":
            print("Relancement de l'indexeur V2 complet...")
            os.system(f'python -X utf8 "{os.path.join(os.path.dirname(__file__), "kb_indexer_v2.py")}"')

        elif cmd == "web":
            if len(sys.argv) < 3:
                print("Usage: kb_agent.py web <url> [--title 'titre']")
                return
            url = sys.argv[2]
            title = url
            if "--title" in sys.argv:
                idx = sys.argv.index("--title")
                title = sys.argv[idx + 1]

            print(f"Fetching: {url}...")
            from kb_indexer_v2 import fetch_web_doc, index_web_doc
            cat_map = {}
            for row in kb.conn.execute("SELECT id, name FROM kb_categories").fetchall():
                cat_map[row['name']] = row['id']
            doc_info = {"url": url, "title": title, "category": "web_docs", "tags": "external, web"}
            result = index_web_doc(kb.conn, doc_info, cat_map)
            if result:
                print(f"OK - Doc #{result['doc_id']} ({result['chunks']} chunks, {result['size']//1024}KB)")
            else:
                print("ECHEC - page vide ou inaccessible")

        elif cmd == "categories":
            cats = kb.list_categories()
            print_header(f"CATEGORIES ({len(cats)})")
            for c in cats:
                print(f"  {c['icon']:3s} {c['name']:20s} {c['doc_count']:4d} docs | {c['description']}")

        elif cmd == "top":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            results = kb.conn.execute("""
                SELECT d.id, d.title, d.file_size, d.file_type, c.name as category, d.tags
                FROM kb_documents d LEFT JOIN kb_categories c ON c.id = d.category_id
                WHERE d.is_active = 1
                ORDER BY d.file_size DESC LIMIT ?
            """, (n,)).fetchall()
            print_header(f"TOP {n} DOCUMENTS PAR TAILLE")
            for r in results:
                print(f"  [{r['id']:4d}] {r['title'][:40]:40s} {r['file_size']:>8d}B {r['file_type'] or '':5s} {r['category']}")

        elif cmd == "serve":
            port = 8899
            if "--port" in sys.argv:
                idx = sys.argv.index("--port")
                port = int(sys.argv[idx + 1])
            start_api_server(kb, port)

        else:
            print(f"Commande inconnue: {cmd}")
            print(__doc__)

    finally:
        kb.close()


def start_api_server(kb, port=8899):
    """API REST locale pour integration avec d'autres outils"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class KBHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/search":
                q = params.get("q", [""])[0]
                limit = int(params.get("limit", ["10"])[0])
                cat = params.get("category", [None])[0]
                results, duration = kb.search(q, limit=limit, category=cat)
                data = {
                    "query": q, "count": len(results), "duration_ms": round(duration, 1),
                    "results": [dict(r) for r in results]
                }
            elif parsed.path == "/stats":
                data = {}
                s = kb.stats()
                data['total_docs'] = s['total_docs']
                data['total_chunks'] = s['total_chunks']
                data['total_tags'] = s['total_tags']
                data['categories'] = [{"name": c['name'], "count": c['doc_count']} for c in s['categories']]
            elif parsed.path == "/doc":
                doc_id = int(params.get("id", ["0"])[0])
                doc, chunks = kb.get_doc(doc_id)
                data = dict(doc) if doc else {"error": "not found"}
            elif parsed.path == "/tags":
                tags = kb.list_tags()
                data = [{"name": t['name'], "count": t['doc_count']} for t in tags]
            else:
                data = {"endpoints": ["/search?q=", "/stats", "/doc?id=", "/tags"]}

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

        def log_message(self, format, *args):
            pass  # Silencieux

    server = HTTPServer(("127.0.0.1", port), KBHandler)
    print(f"KB Agent API running on http://localhost:{port}")
    print(f"  /search?q=mexc&limit=5")
    print(f"  /stats")
    print(f"  /doc?id=1")
    print(f"  /tags")
    print(f"  Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
