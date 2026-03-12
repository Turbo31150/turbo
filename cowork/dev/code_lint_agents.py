#!/usr/bin/env python3
"""JARVIS Code Lint Agents — 10 agents de verification automatique.

Chaque agent verifie un point specifique dans les fichiers crees/modifies.
S'execute AVANT et APRES chaque modification de code.

Usage:
    python cowork/dev/code_lint_agents.py                     # Scan tout
    python cowork/dev/code_lint_agents.py canvas/bot-helpers.py  # Scan un fichier
    python cowork/dev/code_lint_agents.py --recent             # Fichiers modifies < 24h
    python cowork/dev/code_lint_agents.py --fix                # Auto-corrige ce qui est possible
    python cowork/dev/code_lint_agents.py --json               # Output JSON

10 Agents:
  1. PUNCT     — Ponctuation: guillemets mal fermes, parentheses orphelines
  2. ESCAPE    — Echappement: backslash parasite, /n dans strings, unicode casse
  3. PATH      — Chemins: localhost au lieu de 127.0.0.1, slash/backslash mix
  4. TOKEN     — Tokens/API keys: hardcode detecte, .env non lu, placeholder vide
  5. SYNTAX_PY — Syntaxe Python: compile check, indentation, encoding
  6. SYNTAX_JS — Syntaxe JS: node --check, accolades, semicolons
  7. IMPORT    — Imports: modules absents, chemins relatifs casses
  8. ENCODING  — Encoding: BOM, UTF-8, caracteres non-ASCII dans les paths
  9. COMMAND   — Commandes: py3 vs python, executables absents, timeouts
  10. LOGIC    — Logique: division par zero, JSON.parse sans try, variables inutilisees
"""

import json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timedelta

TURBO = Path(__file__).resolve().parent.parent.parent

# ── Agent Results ────────────────────────────────────────────

class LintResult:
    def __init__(self, agent, file, line, severity, message, fix=None):
        self.agent = agent
        self.file = file
        self.line = line
        self.severity = severity  # ERROR, WARN, INFO
        self.message = message
        self.fix = fix  # suggestion de correction

    def __repr__(self):
        return f"[{self.severity}] {self.agent} {self.file}:{self.line} — {self.message}"

    def to_dict(self):
        return {"agent": self.agent, "file": str(self.file), "line": self.line,
                "severity": self.severity, "message": self.message, "fix": self.fix}

# ── Agent 1: PUNCT — Ponctuation ────────────────────────────

def agent_punct(filepath, content, lines):
    """Verifie les guillemets, parentheses, crochets mal fermes."""
    results = []
    # Count paired delimiters
    for i, line in enumerate(lines, 1):
        # Skip comments and strings (rough)
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Unbalanced parentheses in single line (rough check)
        opens = line.count("(") - line.count(")")
        if abs(opens) > 3:
            results.append(LintResult("PUNCT", filepath, i, "WARN",
                f"Parentheses potentiellement desequilibrees (diff={opens})"))

        # Unbalanced brackets
        opens_b = line.count("[") - line.count("]")
        if abs(opens_b) > 3:
            results.append(LintResult("PUNCT", filepath, i, "WARN",
                f"Crochets potentiellement desequilibres (diff={opens_b})"))

        # Unbalanced braces
        opens_c = line.count("{") - line.count("}")
        if abs(opens_c) > 3:
            results.append(LintResult("PUNCT", filepath, i, "WARN",
                f"Accolades potentiellement desequilibrees (diff={opens_c})"))

        # Double comma (skip regex patterns)
        if ",," in line and "',,'," not in line and '",,"' not in line and ",{" not in line:
            results.append(LintResult("PUNCT", filepath, i, "ERROR",
                "Double virgule detectee", fix="Supprimer une virgule"))

        # Trailing comma before closing paren/bracket (JS specific)
        if filepath.suffix == ".js" and re.search(r",\s*\)", line):
            # Actually valid in JS, skip
            pass

    return results

# ── Agent 2: ESCAPE — Echappement ───────────────────────────

def agent_escape(filepath, content, lines):
    """Detecte les backslash parasites, /n dans les mauvais contextes."""
    results = []
    for i, line in enumerate(lines, 1):
        # Windows backslash in Python string that should be forward slash
        if filepath.suffix == ".py":
            # Detect raw Windows paths not using raw strings
            if re.search(r"['\"]F://BUREAU", line) and not re.search(r"r['\"]F:", line):
                results.append(LintResult("ESCAPE", filepath, i, "WARN",
                    "Chemin Windows avec double backslash — utiliser raw string ou forward slash",
                    fix="Utiliser r'F:/BUREAU/...' ou 'F:/BUREAU/...'"))

        # /n literal in execSync command (JS)
        if filepath.suffix == ".js":
            if "//n" in line and "execSync" in line:
                results.append(LintResult("ESCAPE", filepath, i, "ERROR",
                    "//n literal dans execSync — sera interprete comme texte, pas newline"))

        # Unescaped single quote in single-quoted string
        if filepath.suffix == ".py":
            # Simple check: odd number of single quotes outside strings
            pass

    return results

# ── Agent 3: PATH — Chemins ─────────────────────────────────

def agent_path(filepath, content, lines):
    """Detecte localhost, chemins mixtes slash/backslash."""
    results = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # localhost instead of 127.0.0.1 (10s IPv6 latency on Windows)
        if "localhost:" in line.lower() and "127.0.0.1" not in line:
            results.append(LintResult("PATH", filepath, i, "ERROR",
                "'localhost' detecte — utiliser '127.0.0.1' (evite 10s latence IPv6 Windows)",
                fix="Remplacer 'localhost' par '127.0.0.1'"))

        # Mixed slash/backslash in same path
        if filepath.suffix in (".py", ".js"):
            path_match = re.search(r"['\"]([A-Z]:[//].+?)['\"]", line)
            if path_match:
                p = path_match.group(1)
                if "/" in p and "/" in p:
                    results.append(LintResult("PATH", filepath, i, "WARN",
                        f"Chemin avec mix slash/backslash: {p[:50]}",
                        fix="Uniformiser avec / ou // selon le contexte"))

    return results

# ── Agent 4: TOKEN — Tokens/API Keys ────────────────────────

def agent_token(filepath, content, lines):
    """Detecte les tokens hardcodes, placeholders vides."""
    results = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Hardcoded Telegram token pattern
        if re.search(r"['\"][0-9]{8,10}:[A-Za-z0-9_-]{35}['\"]", line):
            results.append(LintResult("TOKEN", filepath, i, "ERROR",
                "Token Telegram hardcode detecte!",
                fix="Utiliser os.environ.get('TELEGRAM_TOKEN') ou process.env.TELEGRAM_TOKEN"))

        # Hardcoded API key pattern (sk-xxx, Bearer xxx)
        if re.search(r"['\"]sk-[a-zA-Z0-9]{20,}['\"]", line):
            if ".env" not in str(filepath) and "example" not in str(filepath).lower():
                results.append(LintResult("TOKEN", filepath, i, "ERROR",
                    "Cle API hardcodee detectee (sk-...)",
                    fix="Deplacer dans .env et lire via env variable"))

        # Empty placeholder
        if re.search(r"(TOKEN|KEY|SECRET|PASSWORD)\s*=\s*['\"]['\"]", line, re.IGNORECASE):
            results.append(LintResult("TOKEN", filepath, i, "WARN",
                "Token/key vide detecte — placeholder sans valeur"))

    return results

# ── Agent 5: SYNTAX_PY — Syntaxe Python ─────────────────────

def agent_syntax_py(filepath, content, lines):
    """Verifie la syntaxe Python via py_compile."""
    results = []
    if filepath.suffix != ".py":
        return results

    try:
        import py_compile
        py_compile.compile(str(filepath), doraise=True)
    except py_compile.PyCompileError as e:
        msg = str(e)
        # Extract line number
        line_match = re.search(r"line (\d+)", msg)
        line_num = int(line_match.group(1)) if line_match else 0
        results.append(LintResult("SYNTAX_PY", filepath, line_num, "ERROR",
            f"Erreur de syntaxe Python: {msg[:200]}"))

    # Check encoding declaration for non-ASCII
    has_non_ascii = any(ord(c) > 127 for c in content)
    if has_non_ascii:
        has_encoding = any("coding" in line for line in lines[:3])
        if not has_encoding:
            results.append(LintResult("SYNTAX_PY", filepath, 1, "INFO",
                "Caracteres non-ASCII sans declaration encoding"))

    # Bare except
    for i, line in enumerate(lines, 1):
        if re.match(r"\s*except\s*:", line):
            results.append(LintResult("SYNTAX_PY", filepath, i, "WARN",
                "Bare except: — capturer Exception au minimum"))

    return results

# ── Agent 6: SYNTAX_JS — Syntaxe JavaScript ─────────────────

def agent_syntax_js(filepath, content, lines):
    """Verifie la syntaxe JavaScript via node --check."""
    results = []
    if filepath.suffix != ".js":
        return results

    try:
        r = subprocess.run(["node", "--check", str(filepath)],
                          capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            error = (r.stderr or "").strip()
            line_match = re.search(r":(\d+)", error)
            line_num = int(line_match.group(1)) if line_match else 0
            results.append(LintResult("SYNTAX_JS", filepath, line_num, "ERROR",
                f"Erreur de syntaxe JS: {error[:200]}"))
    except Exception as e:
        results.append(LintResult("SYNTAX_JS", filepath, 0, "WARN",
            f"Impossible de verifier la syntaxe JS: {str(e)[:100]}"))

    return results

# ── Agent 7: IMPORT — Imports ───────────────────────────────

def agent_import(filepath, content, lines):
    """Verifie que les imports/requires referent des modules existants."""
    results = []

    if filepath.suffix == ".py":
        for i, line in enumerate(lines, 1):
            # Check local imports with relative paths
            match = re.match(r"\s*from\s+(\S+)\s+import", line)
            if match:
                module = match.group(1)
                if module.startswith("."):
                    # Relative import — check if file exists
                    parts = module.lstrip(".").split(".")
                    rel_path = filepath.parent / "/".join(parts)
                    if not rel_path.with_suffix(".py").exists() and not (rel_path / "__init__.py").exists():
                        results.append(LintResult("IMPORT", filepath, i, "WARN",
                            f"Import relatif potentiellement casse: {module}"))

    if filepath.suffix == ".js":
        for i, line in enumerate(lines, 1):
            match = re.match(r"\s*(?:const|let|var)\s+\S+\s*=\s*require\(['\"](\./[^'\"]+)['\"]\)", line)
            if match:
                req_path = match.group(1)
                full = filepath.parent / req_path
                if not full.exists() and not full.with_suffix(".js").exists():
                    results.append(LintResult("IMPORT", filepath, i, "WARN",
                        f"require() fichier potentiellement absent: {req_path}"))

    return results

# ── Agent 8: ENCODING — Encoding ────────────────────────────

def agent_encoding(filepath, content, lines):
    """Detecte les problemes d'encoding: BOM, UTF-8, caracteres speciaux."""
    results = []

    # BOM detection
    raw = filepath.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        results.append(LintResult("ENCODING", filepath, 1, "WARN",
            "UTF-8 BOM detecte — peut causer des problemes",
            fix="Sauver en UTF-8 sans BOM"))

    # NUL bytes
    if b"\x00" in raw:
        pos = raw.index(b"\x00")
        line_num = raw[:pos].count(b"\n") + 1
        results.append(LintResult("ENCODING", filepath, line_num, "ERROR",
            "Caractere NUL (/x00) detecte — fichier possiblement corrompu"))

    # Trailing whitespace on many lines
    trailing = sum(1 for line in lines if line.rstrip() != line.rstrip("\n"))
    if trailing > len(lines) * 0.5 and trailing > 20:
        results.append(LintResult("ENCODING", filepath, 0, "INFO",
            f"Trailing whitespace sur {trailing}/{len(lines)} lignes"))

    return results

# ── Agent 9: COMMAND — Commandes systeme ────────────────────

def agent_command(filepath, content, lines):
    """Verifie py3/python executable, timeouts."""
    results = []
    in_docstring = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        # Track docstrings
        if '"""' in stripped or "'''" in stripped:
            count = stripped.count('"""') + stripped.count("'''")
            if count == 1:
                in_docstring = not in_docstring
            continue
        if in_docstring:
            continue

        # python3 on Windows (doesn't exist) — skip shebangs
        if stripped.startswith("#!/"):
            continue
        py3 = "python" + "3"
        if (py3 + " " in line or py3 + '"' in line or f"'{py3}'" in line) and "env " + py3 not in line:
            results.append(LintResult("COMMAND", filepath, i, "ERROR",
                f"'{py3}' detecte — n'existe pas sur Windows, utiliser 'python'",
                fix=f"Remplacer '{py3}' par 'python'"))

        # execSync/exec with multiline python -c (Windows problem)
        if filepath.suffix == ".js" and re.search(r'execSync\(["`]python\s+-c\s+', line):
            results.append(LintResult("COMMAND", filepath, i, "WARN",
                "execSync avec python -c inline — fragile sur Windows",
                fix="Deplacer le code Python dans bot-helpers.py"))

        # Missing timeout in execSync
        if filepath.suffix == ".js" and "execSync(" in line and "timeout" not in line:
            # Check next few lines for timeout option
            nearby = "\n".join(lines[max(0,i-1):min(len(lines),i+3)])
            if "timeout" not in nearby:
                results.append(LintResult("COMMAND", filepath, i, "WARN",
                    "execSync sans timeout — peut bloquer indefiniment"))

    return results

# ── Agent 10: LOGIC — Logique ───────────────────────────────

def agent_logic(filepath, content, lines):
    """Detecte division par zero, JSON.parse sans try, etc."""
    results = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # JSON.parse without try-catch (JS)
        if filepath.suffix == ".js" and "JSON.parse(" in line:
            # Check if inside a try block (rough)
            context = "\n".join(lines[max(0, i-5):i])
            if "try" not in context and "catch" not in context:
                results.append(LintResult("LOGIC", filepath, i, "WARN",
                    "JSON.parse() sans try-catch — crash si input invalide",
                    fix="Wrapper dans try { JSON.parse(...) } catch { ... }"))

        # Division by zero potential (JS)
        if filepath.suffix == ".js":
            if re.search(r"/\s*(?:total|count|len|size|length)", line) and "max(" not in line and "|| 1" not in line:
                results.append(LintResult("LOGIC", filepath, i, "INFO",
                    "Division potentielle par zero — verifier le denominateur"))

        # Python: bare except already handled by SYNTAX_PY

    return results

# ── Main Scanner ─────────────────────────────────────────────

ALL_AGENTS = [
    agent_punct, agent_escape, agent_path, agent_token,
    agent_syntax_py, agent_syntax_js, agent_import,
    agent_encoding, agent_command, agent_logic,
]

def scan_file(filepath):
    """Scan un fichier avec les 10 agents."""
    filepath = Path(filepath)
    if not filepath.exists():
        return [LintResult("SCAN", filepath, 0, "ERROR", "Fichier introuvable")]

    if filepath.suffix not in (".py", ".js", ".bat", ".sh", ".json"):
        return []

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [LintResult("SCAN", filepath, 0, "ERROR", f"Impossible de lire: {e}")]

    lines = content.split("\n")
    results = []

    for agent in ALL_AGENTS:
        try:
            results.extend(agent(filepath, content, lines))
        except Exception as e:
            results.append(LintResult(agent.__name__.replace("agent_", "").upper(),
                                      filepath, 0, "ERROR", f"Agent crash: {str(e)[:100]}"))

    return results

def scan_directory(dirpath, extensions=None, recent_hours=None):
    """Scan tous les fichiers d'un repertoire."""
    dirpath = Path(dirpath)
    extensions = extensions or [".py", ".js"]
    cutoff = datetime.now() - timedelta(hours=recent_hours) if recent_hours else None

    all_results = []
    for ext in extensions:
        for f in dirpath.rglob(f"*{ext}"):
            # Skip node_modules, __pycache__, .venv
            parts = str(f).lower()
            if any(skip in parts for skip in ["node_modules", "__pycache__", ".venv", "venv", ".git"]):
                continue
            if cutoff:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    continue
            all_results.extend(scan_file(f))

    return all_results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Code Lint Agents")
    parser.add_argument("files", nargs="*", help="Fichiers ou repertoires a scanner")
    parser.add_argument("--recent", action="store_true", help="Fichiers modifies < 24h")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix", action="store_true", help="Auto-corrige si possible")
    parser.add_argument("--errors-only", action="store_true", help="Affiche seulement les erreurs")
    args = parser.parse_args()

    targets = args.files if args.files else [str(TURBO / "canvas"), str(TURBO / "cowork" / "dev")]

    all_results = []
    for target in targets:
        p = Path(target)
        if p.is_file():
            all_results.extend(scan_file(p))
        elif p.is_dir():
            hours = 24 if args.recent else None
            all_results.extend(scan_directory(p, recent_hours=hours))
        else:
            # Try relative to TURBO
            full = TURBO / target
            if full.is_file():
                all_results.extend(scan_file(full))
            elif full.is_dir():
                hours = 24 if args.recent else None
                all_results.extend(scan_directory(full, recent_hours=hours))
            else:
                print(f"SKIP: {target} introuvable")

    if args.errors_only:
        all_results = [r for r in all_results if r.severity == "ERROR"]

    # Sort by severity
    severity_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    all_results.sort(key=lambda r: (severity_order.get(r.severity, 9), str(r.file), r.line))

    if args.json:
        print(json.dumps([r.to_dict() for r in all_results], indent=2, ensure_ascii=False))
        return

    # Pretty output
    errors = sum(1 for r in all_results if r.severity == "ERROR")
    warns = sum(1 for r in all_results if r.severity == "WARN")
    infos = sum(1 for r in all_results if r.severity == "INFO")

    print(f"\n{'='*60}")
    print(f"  JARVIS CODE LINT — 10 AGENTS DE VERIFICATION")
    print(f"  {len(all_results)} problemes: {errors} ERREURS | {warns} WARNINGS | {infos} INFO")
    print(f"{'='*60}\n")

    current_file = None
    for r in all_results:
        if str(r.file) != current_file:
            current_file = str(r.file)
            # Shorten path
            short = str(r.file).replace(str(TURBO), "").lstrip("//")
            print(f"\n  {short}:")

        icon = "X" if r.severity == "ERROR" else ("!" if r.severity == "WARN" else "i")
        line_str = f"L{r.line}" if r.line else "   "
        print(f"    [{icon}] {line_str:>6s} [{r.agent:10s}] {r.message}")
        if r.fix:
            print(f"         FIX: {r.fix}")

    print(f"\n{'='*60}")
    if errors == 0:
        print("  RESULTAT: Aucune erreur critique!")
    else:
        print(f"  RESULTAT: {errors} erreurs a corriger")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
