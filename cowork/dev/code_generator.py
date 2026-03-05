#!/usr/bin/env python3
"""code_generator.py

Generateur de code Python assiste par le cluster IA JARVIS.

Utilise le modele M1 (qwen3-8b sur LM Studio) pour generer du code Python
a partir d'une description en langage naturel.  Valide le code genere avec
ast.parse, peut executer --help, et propose des templates predefinis.

Templates disponibles :
  - jarvis-script  : script CLI argparse + JSON output + sqlite
  - mcp-tool       : outil MCP avec handler et schema
  - api-endpoint   : endpoint FastAPI avec modele Pydantic

CLI :
  --generate DESC   : generer un script a partir d'une description
  --template TYPE   : generer a partir d'un template predefini
  --test FILE       : tester un fichier Python (--help + import)
  --validate FILE   : valider la syntaxe Python avec ast.parse

API M1 : curl http://127.0.0.1:1234/api/v1/chat (qwen3-8b, /nothink)
Extraction : output[] -> dernier element type=message -> .content

Sortie JSON exclusivement. Stdlib uniquement.
"""

import argparse
import ast
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Base de donnees dans dev/data/
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "codegen.db"

# M1 — LM Studio local (qwen3-8b)
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M1_MODEL = "qwen3-8b"
M1_TIMEOUT = 120  # secondes

# ---------------------------------------------------------------------------
# Templates predefinis (pattern COWORK_QUEUE)
# ---------------------------------------------------------------------------

TEMPLATES = {
    "jarvis-script": {
        "name": "Script JARVIS CLI",
        "description": "Script Python CLI avec argparse, sortie JSON et stockage SQLite",
        "code": textwrap.dedent('''\
            #!/usr/bin/env python3
            """__NAME__.py

            __DESCRIPTION__

            CLI :
              --run ARG     : executer la tache principale
              --status      : afficher le statut actuel
              --history     : afficher l'historique

            Sortie JSON. Stdlib uniquement.
            """

            import argparse
            import json
            import sqlite3
            import sys
            from datetime import datetime
            from pathlib import Path

            # Configuration
            DB_PATH = Path(__file__).parent / "data" / "__NAME__.db"


            def _get_conn() -> sqlite3.Connection:
                """Retourne une connexion SQLite initialisee."""
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS entries (
                        id   INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts   TEXT NOT NULL,
                        data TEXT NOT NULL
                    )
                """)
                conn.commit()
                return conn


            def cmd_run(arg: str):
                """Executer la tache principale."""
                conn = _get_conn()
                ts = datetime.utcnow().isoformat()
                conn.execute("INSERT INTO entries (ts, data) VALUES (?, ?)", (ts, arg))
                conn.commit()
                conn.close()
                result = {"status": "ok", "timestamp": ts, "input": arg}
                print(json.dumps(result, ensure_ascii=False, indent=2))


            def cmd_status():
                """Afficher le statut actuel."""
                conn = _get_conn()
                cur = conn.execute("SELECT COUNT(*) as total FROM entries")
                total = cur.fetchone()["total"]
                conn.close()
                result = {"status": "ok", "total_entries": total}
                print(json.dumps(result, ensure_ascii=False, indent=2))


            def cmd_history():
                """Afficher l'historique."""
                conn = _get_conn()
                cur = conn.execute("SELECT * FROM entries ORDER BY id DESC LIMIT 20")
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                result = {"status": "ok", "total": len(rows), "entries": rows}
                print(json.dumps(result, ensure_ascii=False, indent=2))


            def main():
                parser = argparse.ArgumentParser(description="__DESCRIPTION__")
                group = parser.add_mutually_exclusive_group(required=True)
                group.add_argument("--run", type=str, metavar="ARG", help="Executer la tache")
                group.add_argument("--status", action="store_true", help="Statut actuel")
                group.add_argument("--history", action="store_true", help="Historique")
                args = parser.parse_args()

                if args.run:
                    cmd_run(args.run)
                elif args.status:
                    cmd_status()
                elif args.history:
                    cmd_history()


            if __name__ == "__main__":
                main()
        '''),
    },
    "mcp-tool": {
        "name": "Outil MCP",
        "description": "Outil MCP avec handler, schema JSON et integration JARVIS",
        "code": textwrap.dedent('''\
            #!/usr/bin/env python3
            """mcp___NAME__.py

            Outil MCP : __DESCRIPTION__

            Schema d'entree : {"input": "string"}
            Schema de sortie : {"status": "string", "result": "any"}
            """

            import argparse
            import json
            import sys
            from datetime import datetime

            # Schema de l'outil MCP
            TOOL_SCHEMA = {
                "name": "__NAME__",
                "description": "__DESCRIPTION__",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Parametre d'entree"}
                    },
                    "required": ["input"],
                },
            }


            def handle(params: dict) -> dict:
                """Handler principal de l'outil MCP."""
                input_val = params.get("input", "")
                # --- Logique metier a implementer ---
                result = {
                    "status": "ok",
                    "tool": "__NAME__",
                    "timestamp": datetime.utcnow().isoformat(),
                    "input": input_val,
                    "result": f"Traitement de : {input_val}",
                }
                return result


            def main():
                parser = argparse.ArgumentParser(description="Outil MCP : __DESCRIPTION__")
                group = parser.add_mutually_exclusive_group(required=True)
                group.add_argument("--run", type=str, metavar="INPUT", help="Executer l'outil")
                group.add_argument("--schema", action="store_true", help="Afficher le schema MCP")
                args = parser.parse_args()

                if args.schema:
                    print(json.dumps(TOOL_SCHEMA, ensure_ascii=False, indent=2))
                elif args.run:
                    result = handle({"input": args.run})
                    print(json.dumps(result, ensure_ascii=False, indent=2))


            if __name__ == "__main__":
                main()
        '''),
    },
    "api-endpoint": {
        "name": "Endpoint API",
        "description": "Endpoint HTTP avec serveur integre, modele de donnees et stockage SQLite",
        "code": textwrap.dedent('''\
            #!/usr/bin/env python3
            """api___NAME__.py

            Endpoint API : __DESCRIPTION__

            Routes :
              GET  /status    : statut du service
              POST /process   : traiter une requete
              GET  /history   : historique des requetes

            Utilise http.server (stdlib). Port 8900.
            """

            import argparse
            import json
            import sqlite3
            import sys
            from datetime import datetime
            from http.server import HTTPServer, BaseHTTPRequestHandler
            from pathlib import Path
            from urllib.parse import urlparse

            DB_PATH = Path(__file__).parent / "data" / "api___NAME__.db"
            PORT = 8900


            def _get_conn() -> sqlite3.Connection:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id   INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts   TEXT NOT NULL,
                        path TEXT NOT NULL,
                        body TEXT
                    )
                """)
                conn.commit()
                return conn


            class Handler(BaseHTTPRequestHandler):
                def _json_response(self, data: dict, code: int = 200):
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())

                def do_GET(self):
                    path = urlparse(self.path).path
                    if path == "/status":
                        self._json_response({"status": "ok", "service": "__NAME__"})
                    elif path == "/history":
                        conn = _get_conn()
                        rows = [dict(r) for r in conn.execute(
                            "SELECT * FROM requests ORDER BY id DESC LIMIT 20"
                        ).fetchall()]
                        conn.close()
                        self._json_response({"status": "ok", "entries": rows})
                    else:
                        self._json_response({"error": "Not found"}, 404)

                def do_POST(self):
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length).decode() if length else ""
                    conn = _get_conn()
                    conn.execute(
                        "INSERT INTO requests (ts, path, body) VALUES (?, ?, ?)",
                        (datetime.utcnow().isoformat(), self.path, body),
                    )
                    conn.commit()
                    conn.close()
                    self._json_response({"status": "ok", "received": body})

                def log_message(self, fmt, *args):
                    pass  # Silencieux


            def main():
                parser = argparse.ArgumentParser(description="API : __DESCRIPTION__")
                group = parser.add_mutually_exclusive_group(required=True)
                group.add_argument("--serve", action="store_true",
                                   help=f"Demarrer le serveur sur le port {PORT}")
                group.add_argument("--schema", action="store_true",
                                   help="Afficher le schema de l'API")
                args = parser.parse_args()

                if args.schema:
                    schema = {
                        "service": "__NAME__",
                        "port": PORT,
                        "routes": [
                            {"method": "GET", "path": "/status"},
                            {"method": "POST", "path": "/process"},
                            {"method": "GET", "path": "/history"},
                        ],
                    }
                    print(json.dumps(schema, ensure_ascii=False, indent=2))
                else:
                    print(f"Serveur __NAME__ demarre sur le port {PORT}...")
                    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


            if __name__ == "__main__":
                main()
        '''),
    },
}

# ---------------------------------------------------------------------------
# Base de donnees SQLite
# ---------------------------------------------------------------------------

def _ensure_db_dir():
    """Cree le repertoire data/ s'il n'existe pas."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """Retourne une connexion SQLite initialisee."""
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """Cree les tables si elles n'existent pas encore."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS generations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ts           TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            template     TEXT,
            code         TEXT    NOT NULL,
            valid        INTEGER NOT NULL DEFAULT 0,
            model        TEXT    NOT NULL DEFAULT 'qwen3-8b',
            tokens       INTEGER DEFAULT 0,
            latency_ms   INTEGER DEFAULT 0,
            error        TEXT
        )
    """)
    conn.commit()

# ---------------------------------------------------------------------------
# Appel au cluster IA (M1 via LM Studio Responses API)
# ---------------------------------------------------------------------------

def _call_m1(prompt: str) -> dict:
    """Appelle M1 (qwen3-8b) et retourne le contenu genere.

    Utilise l'API Responses (/api/v1/chat) de LM Studio.
    Le prefixe /nothink est obligatoire pour eviter le thinking cache Qwen3.
    Extraction : dernier element type=message dans output[].
    """
    payload = json.dumps({
        "model": M1_MODEL,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": 8192,
        "stream": False,
        "store": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        M1_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=M1_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"M1 inaccessible : {e}",
            "content": "",
            "latency_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erreur appel M1 : {e}",
            "content": "",
            "latency_ms": int((time.time() - start) * 1000),
        }

    latency_ms = int((time.time() - start) * 1000)

    # Extraire le contenu : dernier element type=message dans output[]
    content = ""
    output_list = data.get("output", [])
    for item in reversed(output_list):
        if isinstance(item, dict) and item.get("type") == "message":
            # Le contenu est dans .content (peut etre une liste ou une string)
            raw_content = item.get("content", "")
            if isinstance(raw_content, list):
                # Prendre le texte de chaque element
                parts = []
                for part in raw_content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", str(part)))
                    else:
                        parts.append(str(part))
                content = "".join(parts)
            else:
                content = str(raw_content)
            break

    # Fallback : si output est une string directe
    if not content and isinstance(output_list, str):
        content = output_list

    return {
        "success": True,
        "content": content,
        "latency_ms": latency_ms,
        "model": data.get("model", M1_MODEL),
    }


def _extract_python_code(raw: str) -> str:
    """Extrait le code Python d'une reponse qui peut contenir du markdown.

    Cherche un bloc ```python ... ``` ou ``` ... ```.
    Si aucun bloc n'est trouve, retourne le texte brut.
    """
    # Chercher un bloc ```python
    lines = raw.split("\n")
    in_block = False
    block_lines = []
    found_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```python") and not in_block:
            in_block = True
            found_block = True
            continue
        elif stripped.startswith("```") and not in_block and not found_block:
            in_block = True
            found_block = True
            continue
        elif stripped == "```" and in_block:
            in_block = False
            continue
        if in_block:
            block_lines.append(line)

    if block_lines:
        return "\n".join(block_lines)

    # Pas de bloc markdown → retourner le texte brut
    return raw.strip()

# ---------------------------------------------------------------------------
# Validation et test
# ---------------------------------------------------------------------------

def _validate_syntax(code: str) -> dict:
    """Valide la syntaxe Python avec ast.parse."""
    try:
        ast.parse(code)
        return {"valid": True, "error": None}
    except SyntaxError as e:
        return {
            "valid": False,
            "error": f"SyntaxError ligne {e.lineno}: {e.msg}",
        }


def _test_file(filepath: str) -> dict:
    """Teste un fichier Python en executant --help et en verifiant l'import."""
    path = Path(filepath)
    if not path.exists():
        return {"success": False, "error": f"Fichier introuvable : {filepath}"}
    if not path.suffix == ".py":
        return {"success": False, "error": "Le fichier doit etre un .py"}

    results = {"file": str(path.resolve()), "tests": []}

    # Test 1 : validation syntaxique
    code = path.read_text(encoding="utf-8")
    syntax = _validate_syntax(code)
    results["tests"].append({
        "name": "syntax_check",
        "passed": syntax["valid"],
        "detail": syntax["error"] or "Syntaxe valide",
    })

    # Test 2 : execution --help
    try:
        proc = subprocess.run(
            [sys.executable, str(path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        help_ok = proc.returncode == 0
        results["tests"].append({
            "name": "help_check",
            "passed": help_ok,
            "detail": proc.stdout[:500] if help_ok else proc.stderr[:500],
        })
    except subprocess.TimeoutExpired:
        results["tests"].append({
            "name": "help_check",
            "passed": False,
            "detail": "Timeout apres 10s",
        })
    except Exception as e:
        results["tests"].append({
            "name": "help_check",
            "passed": False,
            "detail": str(e),
        })

    # Test 3 : import du module (compilation)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", f"import py_compile; py_compile.compile('{path}', doraise=True)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        compile_ok = proc.returncode == 0
        results["tests"].append({
            "name": "compile_check",
            "passed": compile_ok,
            "detail": "Compilation OK" if compile_ok else proc.stderr[:500],
        })
    except Exception as e:
        results["tests"].append({
            "name": "compile_check",
            "passed": False,
            "detail": str(e),
        })

    results["success"] = all(t["passed"] for t in results["tests"])
    return results

# ---------------------------------------------------------------------------
# Commandes CLI
# ---------------------------------------------------------------------------

def cmd_generate(description: str):
    """Genere un script Python a partir d'une description en langage naturel."""
    # Construire le prompt pour M1
    prompt = (
        "Tu es un expert Python. Genere un script Python complet et fonctionnel "
        "a partir de la description suivante. Le script DOIT utiliser :\n"
        "- argparse pour le CLI\n"
        "- json pour la sortie (print JSON)\n"
        "- sqlite3 pour le stockage (dans un fichier .db)\n"
        "- Uniquement la stdlib Python\n"
        "- Commentaires en francais\n\n"
        "IMPORTANT : retourne UNIQUEMENT le code Python, dans un bloc ```python```.\n"
        "Pas d'explications avant ou apres le code.\n\n"
        f"Description : {description}"
    )

    # Appeler M1
    m1_result = _call_m1(prompt)

    if not m1_result["success"]:
        result = {
            "status": "error",
            "message": m1_result["error"],
            "latency_ms": m1_result["latency_ms"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Extraire le code Python de la reponse
    raw_content = m1_result["content"]
    code = _extract_python_code(raw_content)

    # Valider la syntaxe
    syntax = _validate_syntax(code)

    # Enregistrer en base
    conn = _get_conn()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO generations (ts, description, code, valid, model, latency_ms, error)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ts, description, code, 1 if syntax["valid"] else 0,
         m1_result.get("model", M1_MODEL), m1_result["latency_ms"],
         syntax["error"]),
    )
    gen_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = {
        "status": "ok",
        "generation_id": gen_id,
        "timestamp": ts,
        "description": description,
        "model": m1_result.get("model", M1_MODEL),
        "latency_ms": m1_result["latency_ms"],
        "syntax_valid": syntax["valid"],
        "syntax_error": syntax["error"],
        "code": code,
        "lines": len(code.splitlines()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_template(template_type: str):
    """Genere du code a partir d'un template predefini."""
    if template_type not in TEMPLATES:
        result = {
            "status": "error",
            "message": f"Template inconnu : '{template_type}'",
            "available": list(TEMPLATES.keys()),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    tpl = TEMPLATES[template_type]
    code = tpl["code"]

    # Valider la syntaxe du template
    syntax = _validate_syntax(code)

    # Enregistrer en base
    conn = _get_conn()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO generations (ts, description, template, code, valid, model, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ts, tpl["description"], template_type, code,
         1 if syntax["valid"] else 0, "template", 0),
    )
    gen_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = {
        "status": "ok",
        "generation_id": gen_id,
        "timestamp": ts,
        "template": template_type,
        "template_name": tpl["name"],
        "description": tpl["description"],
        "syntax_valid": syntax["valid"],
        "code": code,
        "lines": len(code.splitlines()),
        "placeholders": ["__NAME__", "__DESCRIPTION__"],
        "instructions": "Remplacer __NAME__ et __DESCRIPTION__ par les valeurs souhaitees.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_test(filepath: str):
    """Teste un fichier Python (syntaxe, --help, compilation)."""
    results = _test_file(filepath)
    print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_validate(filepath: str):
    """Valide la syntaxe d'un fichier Python avec ast.parse."""
    path = Path(filepath)
    if not path.exists():
        result = {"status": "error", "message": f"Fichier introuvable : {filepath}"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    code = path.read_text(encoding="utf-8")
    syntax = _validate_syntax(code)

    result = {
        "status": "ok" if syntax["valid"] else "error",
        "file": str(path.resolve()),
        "valid": syntax["valid"],
        "error": syntax["error"],
        "lines": len(code.splitlines()),
        "size_bytes": len(code.encode("utf-8")),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generateur de code Python JARVIS — utilise le cluster IA (M1/qwen3-8b) pour generer, valider et tester du code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemples :
  python code_generator.py --generate "Script qui surveille l'espace disque et alerte si < 10GB"
  python code_generator.py --template jarvis-script
  python code_generator.py --template mcp-tool
  python code_generator.py --template api-endpoint
  python code_generator.py --validate mon_script.py
  python code_generator.py --test mon_script.py

Templates disponibles : jarvis-script, mcp-tool, api-endpoint
""",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", type=str, metavar="DESCRIPTION",
                       help="Generer un script a partir d'une description en langage naturel")
    group.add_argument("--template", type=str, metavar="TYPE",
                       choices=list(TEMPLATES.keys()),
                       help="Generer a partir d'un template (jarvis-script, mcp-tool, api-endpoint)")
    group.add_argument("--test", type=str, metavar="FILE",
                       help="Tester un fichier Python (syntaxe + --help + compilation)")
    group.add_argument("--validate", type=str, metavar="FILE",
                       help="Valider la syntaxe Python avec ast.parse")

    args = parser.parse_args()

    if args.generate:
        cmd_generate(args.generate)
    elif args.template:
        cmd_template(args.template)
    elif args.test:
        cmd_test(args.test)
    elif args.validate:
        cmd_validate(args.validate)


if __name__ == "__main__":
    main()
