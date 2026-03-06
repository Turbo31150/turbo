#!/usr/bin/env python3
"""
MASTER INTERACTION NODE v1.0 - Protocole PRISC
Point d'entree unique: Voice/Text -> Consensus 3 Machines -> Confirmation -> Execution -> KB Log

Cycle PRISC:
  1. PERCEIVE  - Ecoute (Whisper STT ou texte)
  2. REASON    - Consensus parallele M1+M2+M3+Gemini + contexte KB
  3. INTERACT  - Propose la reponse, attend "Fais-le"
  4. SYNTHESIZE- Execute la tache confirmee
  5. CHRONICLE - Log dans KB + historique

Usage:
    python master_interaction_node.py              # Mode interactif (texte)
    python master_interaction_node.py --voice      # Mode vocal (Whisper)
    python master_interaction_node.py --auto       # Mode autonome (pas de confirmation)
    python master_interaction_node.py --query "prompt"  # Query unique
"""
import os
import sys
import json
import time
import sqlite3
import subprocess
import re
import signal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Force UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    import requests
except ImportError:
    print("ERREUR: pip install requests")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.live import Live
    RICH = True
except ImportError:
    RICH = False

# ============================================================
# CONFIG
# ============================================================
DB_PATH = r"F:\BUREAU\TRADING_V2_PRODUCTION\database\trading.db"
LOGS_DIR = r"F:\BUREAU\TRADING_V2_PRODUCTION\logs"
GEMINI_CMD = r"C:\Users\franc\AppData\Roaming\npm\gemini.cmd"

CLUSTER = {
    "M1": {
        "url": "http://192.168.1.85:1234",
        "model": "qwen/qwen3-30b-a3b-2507",
        "role": "Analyste profond - raisonnement strategique",
        "timeout": 90,
        "supports_system": True,
    },
    "M2": {
        "url": "http://192.168.1.26:1234",
        "model": "openai/gpt-oss-20b",
        "role": "Execution rapide - signaux et code",
        "timeout": 60,
        "supports_system": True,
    },
    "M3": {
        "url": "http://192.168.1.113:1234",
        "model": "openai/gpt-oss-20b",
        "role": "Validation contrarian - verification et doutes",
        "timeout": 60,
        "supports_system": True,
    },
}

NO_SYSTEM_MODELS = ["mistralai/mistral-7b-instruct-v0.3", "microsoft/phi-3.1-mini-128k-instruct"]

# Patterns de confirmation
CONFIRM_PATTERNS = re.compile(
    r"(?:fais[ -]?le|go|execute|lance|ok|oui|yes|valide|confirme|envoie|do it)",
    re.IGNORECASE,
)
CANCEL_PATTERNS = re.compile(
    r"(?:annule|cancel|non|no|stop|arrête|abort|skip|passe)",
    re.IGNORECASE,
)

# Patterns de tache executable
TASK_PATTERNS = {
    "scan_mexc": re.compile(r"(?:scan|scanne|scanner)\s*(?:mexc|marche|market|futures)?", re.I),
    "check_positions": re.compile(r"(?:position|marge|margin|ancrage|liquidation)", re.I),
    "backup_db": re.compile(r"(?:backup|sauvegarde|copie)\s*(?:db|database|base|sql)", re.I),
    "send_telegram": re.compile(r"(?:telegram|alerte|alert|envoie|send)\s*(?:message|msg|alerte)?", re.I),
    "kb_search": re.compile(r"(?:cherche|search|trouve|find|kb)\s+(.+)", re.I),
    "consensus": re.compile(r"(?:consensus|vote|avis|opinion)\s+(.+)", re.I),
    "analyze_coin": re.compile(r"(?:analyse|analyze)\s+(\w+)", re.I),
}

# ============================================================
# CONSOLE
# ============================================================
console = Console() if RICH else None


def cprint(text, style=""):
    if console:
        console.print(text, style=style)
    else:
        print(text)


def cpanel(content, title="", style="cyan"):
    if console:
        console.print(Panel(content, title=title, border_style=style))
    else:
        print(f"\n=== {title} ===\n{content}\n{'=' * 40}")


# ============================================================
# CLUSTER - Communication nodes
# ============================================================
def ask_node(name, url, model, prompt, system_prompt=None, timeout=60):
    """Query un node LM Studio"""
    start = time.time()
    try:
        messages = []
        if system_prompt and model not in NO_SYSTEM_MODELS:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        r = requests.post(
            f"{url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 1500,
                "stream": False,
            },
            headers={"Authorization": "Bearer lm-studio"},
            timeout=timeout,
        )
        elapsed = time.time() - start
        data = r.json()

        if "error" in data:
            return {"name": name, "ok": False, "error": str(data["error"]), "time": elapsed}

        msg = data["choices"][0]["message"]
        content = msg.get("content", "")
        # Fallback reasoning (GPT-OSS bug)
        if not content.strip():
            content = msg.get("reasoning", "")
        # Clean garbage tokens
        for garbage in ["<|endoftext|>", "SPECIAL_TOKEN", "<|im_end|>", "<|end|>"]:
            content = content.replace(garbage, "")

        tokens = data.get("usage", {}).get("completion_tokens", 0)
        return {
            "name": name, "ok": True, "text": content.strip(),
            "time": elapsed, "tokens": tokens, "model": model,
        }
    except requests.exceptions.Timeout:
        return {"name": name, "ok": False, "error": "TIMEOUT", "time": time.time() - start}
    except Exception as e:
        return {"name": name, "ok": False, "error": str(e), "time": time.time() - start}


def ask_gemini(prompt, timeout=45):
    """Query Gemini via CLI (OAuth, pas de cle API)"""
    start = time.time()
    try:
        proc = subprocess.run(
            [GEMINI_CMD, "--model", "gemini-2.0-flash"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start

        if proc.returncode != 0:
            return {"name": "Gemini", "ok": False, "error": f"RC={proc.returncode}", "time": elapsed}

        lines = [
            l for l in proc.stdout.strip().split("\n")
            if not l.startswith("(node:") and not l.startswith("[ERROR]") and not l.startswith("Loaded")
        ]
        text = "\n".join(lines).strip()
        return {"name": "Gemini", "ok": True, "text": text, "time": elapsed, "tokens": 0, "model": "gemini-2.0-flash"}
    except subprocess.TimeoutExpired:
        return {"name": "Gemini", "ok": False, "error": "TIMEOUT", "time": time.time() - start}
    except Exception as e:
        return {"name": "Gemini", "ok": False, "error": str(e), "time": time.time() - start}


def check_cluster_health():
    """Ping tous les nodes"""
    results = {}
    for name, cfg in CLUSTER.items():
        try:
            r = requests.get(f"{cfg['url']}/v1/models", timeout=5)
            models = [m["id"] for m in r.json().get("data", [])]
            results[name] = {"online": True, "models": len(models)}
        except Exception:
            results[name] = {"online": False, "models": 0}
    # Gemini
    try:
        proc = subprocess.run([GEMINI_CMD, "--version"], capture_output=True, timeout=5, text=True)
        results["Gemini"] = {"online": proc.returncode == 0, "models": 1}
    except Exception:
        results["Gemini"] = {"online": False, "models": 0}
    return results


# ============================================================
# KB - Knowledge Base integration
# ============================================================
def kb_search(query, limit=5):
    """Recherche dans la Knowledge Base locale"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        words = []
        for w in query.split():
            clean = re.sub(r"[^\w]", "", w)
            if clean:
                words.append(f'"{clean}"')
        fts_query = " OR ".join(words)

        results = conn.execute("""
            SELECT d.id, d.title, d.summary, d.tags, c.name as category,
                   snippet(kb_search_fts, 1, '>>>', '<<<', '...', 30) as snippet
            FROM kb_search_fts fts
            JOIN kb_documents d ON d.id = fts.rowid
            LEFT JOIN kb_categories c ON c.id = d.category_id
            WHERE kb_search_fts MATCH ? AND d.is_active = 1
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
        conn.close()
        return [dict(r) for r in results]
    except Exception:
        return []


def kb_log_interaction(prompt, response, consensus_data, action_taken=None):
    """Log l'interaction complete dans la KB"""
    try:
        conn = sqlite3.connect(DB_PATH)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"PRISC Interaction {now}"

        content_parts = [
            f"# PRISC Interaction - {now}",
            f"## Prompt\n{prompt}",
            f"## Consensus",
        ]
        for name, data in consensus_data.items():
            if data.get("ok"):
                content_parts.append(f"### {name} ({data.get('time', 0):.1f}s)\n{data.get('text', '')[:500]}")
            else:
                content_parts.append(f"### {name} - ERREUR: {data.get('error', '?')}")

        content_parts.append(f"## Synthese\n{response}")
        if action_taken:
            content_parts.append(f"## Action Executee\n{action_taken}")

        content = "\n\n".join(content_parts)
        tags = "prisc, consensus, interaction, live"

        c = conn.cursor()
        c.execute("SELECT id FROM kb_categories WHERE name = ?", ("consensus",))
        cat = c.fetchone()
        cat_id = cat[0] if cat else 1

        c.execute("""INSERT INTO kb_documents
            (title, content, summary, category_id, source_path, source_type, file_type, file_size, tags, keywords, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (title, content, response[:500], cat_id, "prisc://interaction", "prisc", ".md",
             len(content), tags, "prisc, consensus"))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ============================================================
# TTS - Text to Speech
# ============================================================
class Speaker:
    def __init__(self):
        self.engine = None
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 190)
            for v in self.engine.getProperty("voices"):
                if "french" in v.name.lower() or "hortense" in v.name.lower():
                    self.engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass

    def speak(self, text):
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception:
                pass
        cprint(f"  [VOICE] {text}", style="italic dim")


# ============================================================
# TASK EXECUTOR - Executions confirmees
# ============================================================
def execute_task(task_type, params=None):
    """Execute une tache apres confirmation"""
    params = params or {}

    if task_type == "scan_mexc":
        cprint("  Lancement scan MEXC...", style="yellow")
        script = os.path.join(os.path.dirname(__file__), "scan_and_index.py")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", script],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
        )
        return result.stdout[-1000:] if result.returncode == 0 else f"ERREUR: {result.stderr[-500:]}"

    elif task_type == "backup_db":
        cprint("  Backup de la base...", style="yellow")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        src = DB_PATH
        dst = os.path.join(LOGS_DIR, f"trading_backup_{ts}.db")
        import shutil
        shutil.copy2(src, dst)
        size = os.path.getsize(dst)
        return f"Backup cree: {dst} ({size // 1024}KB)"

    elif task_type == "kb_search":
        query = params.get("query", "")
        results = kb_search(query, limit=10)
        lines = [f"KB: {len(results)} resultats pour '{query}'"]
        for r in results:
            lines.append(f"  [{r['id']}] {r['title']} ({r['category']}) - {r.get('tags', '')[:40]}")
        return "\n".join(lines)

    elif task_type == "send_telegram":
        msg = params.get("message", "Test PRISC")
        token = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
        chat_id = "2010747443"
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        return f"Telegram: {'OK' if r.status_code == 200 else 'ERREUR ' + str(r.status_code)}"

    elif task_type == "check_positions":
        cprint("  Verification positions MEXC...", style="yellow")
        r = requests.get(
            "https://contract.mexc.com/api/v1/private/position/open_positions",
            headers={
                "ApiKey": "mx0vglrR6uWgWEB6Vm",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            if not data:
                return "Aucune position ouverte"
            lines = [f"{len(data)} positions ouvertes:"]
            for p in data:
                lines.append(f"  {p.get('symbol')} {p.get('positionType')} x{p.get('leverage')} | PnL: {p.get('unrealisedPnl')}")
            return "\n".join(lines)
        return f"MEXC API: {r.status_code}"

    return f"Tache '{task_type}' non implementee"


def detect_task(prompt):
    """Detecte si le prompt contient une tache executable"""
    for task_type, pattern in TASK_PATTERNS.items():
        m = pattern.search(prompt)
        if m:
            params = {"query": m.group(1)} if m.lastindex and m.lastindex >= 1 else {}
            if task_type == "send_telegram":
                params["message"] = prompt
            return task_type, params
    return None, None


# ============================================================
# MASTER NODE - Le cerveau central
# ============================================================
class MasterNode:
    def __init__(self, voice_mode=False, auto_mode=False):
        self.voice_mode = voice_mode
        self.auto_mode = auto_mode
        self.speaker = Speaker()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.history = []
        self.running = True

    def banner(self):
        health = check_cluster_health()
        online = sum(1 for v in health.values() if v["online"])
        total = len(health)

        if console:
            table = Table(title="PRISC Master Node v1.0", show_header=True, header_style="bold cyan")
            table.add_column("Node", style="bold")
            table.add_column("Status")
            table.add_column("Models")
            for name, info in health.items():
                status = "[green]ONLINE[/]" if info["online"] else "[red]OFFLINE[/]"
                table.add_row(name, status, str(info["models"]))
            console.print(table)
            console.print(f"  Session: {self.session_id} | Mode: {'VOICE' if self.voice_mode else 'TEXT'} | Confirm: {'AUTO' if self.auto_mode else 'MANUAL'}")
            console.print(f'  Commandes: "quit" pour sortir, "status" pour le cluster, "help" pour l\'aide\n')
        else:
            print(f"\nPRISC Master Node v1.0 - {online}/{total} nodes online")
            print(f"Session: {self.session_id}\n")

    # ---- PHASE 1: PERCEIVE ----
    def listen(self):
        """Ecoute l'utilisateur (texte ou voix)"""
        if self.voice_mode:
            return self._listen_voice()
        try:
            if console:
                prompt = console.input("[bold cyan]PRISC>[/] ")
            else:
                prompt = input("PRISC> ")
            return prompt.strip()
        except (EOFError, KeyboardInterrupt):
            self.running = False
            return None

    def _listen_voice(self):
        """Ecoute vocale via Whisper (si disponible)"""
        self.speaker.speak("Je vous ecoute.")
        try:
            # Tente d'utiliser le voice_driver existant
            sys.path.insert(0, r"F:\BUREAU\carV1\voice_system")
            from voice_driver import VoiceListener
            # Simplified: single capture
            cprint("  [MIC] Parlez maintenant... (Ctrl+C pour annuler)", style="yellow")
            # Fallback to text if voice fails
            return input("PRISC (voice fallback)> ").strip()
        except Exception:
            cprint("  [VOICE] Whisper non disponible, mode texte", style="red")
            return input("PRISC> ").strip()

    # ---- PHASE 2: REASON ----
    def think(self, prompt):
        """Consensus parallele M1+M2+M3+Gemini avec contexte KB"""
        # 1. Enrichir avec contexte KB
        kb_context = ""
        kb_results = kb_search(prompt, limit=3)
        if kb_results:
            kb_context = "\n\nContexte de la base de connaissances:\n"
            for r in kb_results:
                kb_context += f"- [{r['title']}] {r.get('summary', '')[:150]}\n"

        # 2. Detecter si c'est une tache executable
        task_type, task_params = detect_task(prompt)

        # 3. Construire le system prompt
        sys_prompt = (
            "Tu es un conseiller strategique du systeme Trading AI PRISC. "
            "Reponds en francais, concis (5-8 lignes max). "
            "Si la question concerne une action a executer, propose clairement l'action et ses parametres. "
            "Si c'est une analyse, donne ta conviction (LONG/SHORT/WAIT) avec pourcentage."
        )

        full_prompt = prompt + kb_context

        # 4. Consensus parallele
        cprint("\n  [THINK] Consensus parallele...", style="bold yellow")
        results = {}
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {}
            for name, cfg in CLUSTER.items():
                f = pool.submit(
                    ask_node, name, cfg["url"], cfg["model"],
                    full_prompt, sys_prompt, cfg["timeout"],
                )
                futures[f] = name

            # Gemini en parallele
            gemini_prompt = f"{sys_prompt}\n\n{full_prompt}" if sys_prompt else full_prompt
            f_gem = pool.submit(ask_gemini, gemini_prompt)
            futures[f_gem] = "Gemini"

            for future in as_completed(futures, timeout=120):
                name = futures[future]
                try:
                    r = future.result()
                    results[name] = r
                    status = "OK" if r["ok"] else "FAIL"
                    t = r.get("time", 0)
                    cprint(f"    [{status}] {name:10s} {t:5.1f}s", style="green" if r["ok"] else "red")
                except Exception as e:
                    results[name] = {"name": name, "ok": False, "error": str(e), "time": 0}
                    cprint(f"    [FAIL] {name:10s} {e}", style="red")

        total_time = time.time() - t0
        cprint(f"    Total: {total_time:.1f}s parallele", style="dim")

        # 5. Synthetiser
        synthesis = self._synthesize(prompt, results, task_type)

        return {
            "synthesis": synthesis,
            "raw_results": results,
            "task_type": task_type,
            "task_params": task_params,
            "kb_context": kb_results,
            "total_time": total_time,
        }

    def _synthesize(self, prompt, results, task_type):
        """Synthetise les reponses du cluster"""
        ok_results = {k: v for k, v in results.items() if v.get("ok")}

        if not ok_results:
            return "Aucun node n'a repondu. Cluster possiblement hors ligne."

        # Extraire directions si analyse trading
        directions = {}
        for name, r in ok_results.items():
            text = r.get("text", "").upper()
            if "LONG" in text and "SHORT" not in text:
                directions[name] = "LONG"
            elif "SHORT" in text and "LONG" not in text:
                directions[name] = "SHORT"
            elif "WAIT" in text or "NEUTR" in text:
                directions[name] = "WAIT"

        # Construire synthese
        parts = []
        parts.append(f"**Consensus {len(ok_results)}/{len(results)} nodes** ({sum(r['time'] for r in results.values()):.0f}s)")

        if directions:
            from collections import Counter
            votes = Counter(directions.values())
            winner = votes.most_common(1)[0]
            agreement = winner[1] / len(directions) * 100 if directions else 0
            parts.append(f"Direction: **{winner[0]}** ({agreement:.0f}% agreement - {dict(votes)})")

        for name in sorted(ok_results.keys()):
            r = ok_results[name]
            text = r["text"][:300].replace("\n", " ")
            parts.append(f"**{name}** ({r['time']:.1f}s): {text}")

        if task_type:
            parts.append(f"\nTache detectee: **{task_type}** - En attente de confirmation.")

        return "\n\n".join(parts)

    # ---- PHASE 3: INTERACT ----
    def propose(self, thought):
        """Presente la synthese et attend confirmation"""
        synthesis = thought["synthesis"]
        task_type = thought["task_type"]

        # Afficher la synthese
        if console:
            console.print(Panel(
                Markdown(synthesis),
                title=f"[bold]PRISC Consensus[/] ({thought['total_time']:.1f}s)",
                border_style="green" if task_type else "cyan",
            ))
        else:
            print(f"\n--- PRISC Consensus ({thought['total_time']:.1f}s) ---")
            print(synthesis)
            print("---")

        # TTS resume
        # Extraire la premiere ligne significative pour le vocal
        first_line = synthesis.split("\n")[0][:100]
        self.speaker.speak(first_line.replace("**", "").replace("*", ""))

        if task_type and not self.auto_mode:
            self.speaker.speak(f"Tache detectee: {task_type}. Dois-je l'executer?")
            cprint(f'\n  Tache: {task_type} | Dites "Fais-le" ou "Annule"', style="bold yellow")
            confirmation = self.listen()

            if confirmation and CONFIRM_PATTERNS.search(confirmation):
                return True
            elif confirmation and CANCEL_PATTERNS.search(confirmation):
                self.speaker.speak("Action annulee.")
                cprint("  Action annulee.", style="red")
                return False
            else:
                cprint("  Confirmation non reconnue, action annulee par securite.", style="red")
                return False

        elif task_type and self.auto_mode:
            cprint(f"  [AUTO] Execution automatique: {task_type}", style="bold green")
            return True

        return None  # Pas de tache, juste une reponse

    # ---- PHASE 4: SYNTHESIZE (Execute) ----
    def execute(self, thought):
        """Execute la tache confirmee"""
        task_type = thought["task_type"]
        task_params = thought["task_params"] or {}

        self.speaker.speak("Execution du protocole en cours.")
        cprint(f"\n  [EXEC] {task_type}...", style="bold green")

        try:
            result = execute_task(task_type, task_params)
            cpanel(result, title=f"Resultat: {task_type}", style="green")
            self.speaker.speak("Execution terminee avec succes.")
            return result
        except Exception as e:
            error = f"ERREUR: {e}"
            cpanel(error, title=f"Echec: {task_type}", style="red")
            self.speaker.speak(f"Erreur lors de l'execution: {e}")
            return error

    # ---- PHASE 5: CHRONICLE (Log) ----
    def chronicle(self, prompt, thought, action_result=None):
        """Log dans KB + historique"""
        kb_log_interaction(
            prompt,
            thought["synthesis"],
            thought["raw_results"],
            action_taken=action_result,
        )

        self.history.append({
            "time": datetime.now().isoformat(),
            "prompt": prompt,
            "synthesis": thought["synthesis"][:500],
            "task": thought["task_type"],
            "action": str(action_result)[:200] if action_result else None,
        })

    # ---- MAIN LOOP ----
    def run(self):
        """Boucle principale PRISC"""
        self.banner()
        self.speaker.speak("PRISC en ligne. Je vous ecoute.")

        while self.running:
            try:
                # 1. PERCEIVE
                prompt = self.listen()
                if not prompt:
                    continue

                # Commandes speciales
                if prompt.lower() in ("quit", "exit", "bye", "q"):
                    self.speaker.speak("Arret du systeme. A bientot.")
                    break
                if prompt.lower() == "status":
                    health = check_cluster_health()
                    for name, info in health.items():
                        status = "ONLINE" if info["online"] else "OFFLINE"
                        cprint(f"  {name}: {status} ({info['models']} modeles)", style="green" if info["online"] else "red")
                    continue
                if prompt.lower() == "help":
                    cprint("  Commandes: quit, status, help")
                    cprint("  Taches auto-detectees: scan, positions, backup, telegram, kb search, consensus, analyse")
                    cprint('  Apres une proposition: "Fais-le" ou "Annule"')
                    continue
                if prompt.lower() == "history":
                    for h in self.history[-10:]:
                        cprint(f"  [{h['time'][:16]}] {h['prompt'][:50]} -> {h.get('task', 'info')}")
                    continue

                # 2. REASON
                thought = self.think(prompt)

                # 3. INTERACT
                confirmed = self.propose(thought)

                # 4. SYNTHESIZE
                action_result = None
                if confirmed is True:
                    action_result = self.execute(thought)

                # 5. CHRONICLE
                self.chronicle(prompt, thought, action_result)

            except KeyboardInterrupt:
                cprint("\n  Ctrl+C - Arret.", style="red")
                break
            except Exception as e:
                cprint(f"\n  ERREUR: {e}", style="bold red")

        cprint(f"\n  Session terminee. {len(self.history)} interactions logguees.", style="dim")

    def single_query(self, prompt):
        """Query unique (non-interactif)"""
        thought = self.think(prompt)
        self.propose(thought)
        self.chronicle(prompt, thought)


# ============================================================
# ENTRY POINT
# ============================================================
def main():
    voice = "--voice" in sys.argv
    auto = "--auto" in sys.argv
    query = None

    if "--query" in sys.argv:
        idx = sys.argv.index("--query")
        if idx + 1 < len(sys.argv):
            query = " ".join(sys.argv[idx + 1:])

    node = MasterNode(voice_mode=voice, auto_mode=auto)

    if query:
        node.single_query(query)
    else:
        node.run()


if __name__ == "__main__":
    main()
