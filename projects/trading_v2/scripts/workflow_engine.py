"""
WORKFLOW ENGINE v1.0 - Pipeline Evolutif + Memoire Procedurale
Enchaine des actions, pose des questions, appelle les IA pour rediger.
Auto-compile: 1ere fois ~30s, 2eme fois ~1s (workflow memorise en DB).
Table: macro_workflows (trigger, steps_json, usage_count, last_used)
"""
import sys
import os
import time
import json
import sqlite3
import requests
import importlib.util

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
DB_PATH = os.path.join(ROOT, "database", "trading.db")
SCRIPTS = os.path.join(ROOT, "scripts")
OS_PILOT_PATH = os.path.join(SCRIPTS, "os_pilot.py")
M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_MODEL = "openai/gpt-oss-20b"
M2_TIMEOUT = 30

# Import OS Pilot
spec = importlib.util.spec_from_file_location("os_pilot", OS_PILOT_PATH)
os_pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(os_pilot)

# TTS (optionnel)
try:
    import pyttsx3
    _engine = pyttsx3.init()
    _engine.setProperty('rate', 190)
    _engine.setProperty('volume', 1.0)
    for v in _engine.getProperty('voices'):
        if 'french' in v.name.lower() or 'fr' in v.id.lower():
            _engine.setProperty('voice', v.id)
            break
    TTS_OK = True
except:
    TTS_OK = False

# STT via faster_whisper (meme modele que voice_jarvis)
STT_OK = False
_whisper_model = None
try:
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import numpy as np
    STT_OK = True
except ImportError:
    pass


def speak(text):
    """Feedback vocal + console"""
    print(f"  WORKFLOW: {text}")
    if TTS_OK:
        try:
            _engine.say(text)
            _engine.runAndWait()
        except:
            pass


def _ensure_whisper():
    """Charge whisper a la premiere utilisation (lazy load)"""
    global _whisper_model
    if _whisper_model is None and STT_OK:
        print("  [WHISPER] Chargement pour workflow (lazy)...")
        try:
            _whisper_model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
            print("  [WHISPER] Pret")
        except:
            try:
                _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
                print("  [WHISPER] Pret (CPU fallback)")
            except Exception as e:
                print(f"  [WHISPER] Echec: {e}")
    return _whisper_model


def listen_user(prompt=None, timeout=15):
    """Ecoute vocale ou fallback clavier"""
    if prompt:
        speak(prompt)

    # Essayer STT d'abord
    if STT_OK:
        model = _ensure_whisper()
        if model:
            try:
                sample_rate = 16000
                print("  [MIC] Parle maintenant...")
                audio = sd.rec(int(timeout * sample_rate), samplerate=sample_rate,
                               channels=1, dtype='float32')
                # Attendre silence (detection simple: 2s de silence)
                time.sleep(0.5)
                sd.wait()
                audio_np = audio.flatten()
                # Sauver temporairement
                import tempfile, wave, struct
                tmp = os.path.join(ROOT, "logs", "_wf_audio.wav")
                os.makedirs(os.path.dirname(tmp), exist_ok=True)
                audio_int16 = (audio_np * 32767).astype(np.int16)
                with wave.open(tmp, 'w') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())
                segments, info = model.transcribe(tmp, language="fr")
                text = " ".join(s.text.strip() for s in segments).strip()
                if text and len(text) > 2:
                    print(f"  [STT] \"{text}\"")
                    return text
            except Exception as e:
                print(f"  [STT] Erreur: {e}")

    # Fallback clavier
    try:
        text = input("  WORKFLOW >> (tape ta reponse) ")
        return text.strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def generate_text(context, user_input):
    """Demande a M2 de rediger du contenu"""
    prompt = f"""Redige un texte court et naturel.
CONTEXTE: {context}
INSTRUCTION: {user_input}

Ecris UNIQUEMENT le texte final, sans guillemets, sans commentaire."""

    try:
        payload = {
            "model": M2_MODEL,
            "messages": [
                {"role": "system", "content": "Tu es un redacteur efficace et naturel en francais."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        t0 = time.time()
        r = requests.post(M2_URL, json=payload, timeout=M2_TIMEOUT)
        latency = time.time() - t0
        if r.status_code == 200:
            msg = r.json()['choices'][0]['message']
            content = msg.get('content', '') or msg.get('reasoning_content', '') or msg.get('reasoning', '') or ''
            # Nettoyage GPT-OSS special tokens
            import re
            content = re.sub(r'<\|[^|]*\|>[^<\n]*(?:<\|[^|]*\|>)?', '', content).strip()
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            print(f"  [IA] Genere en {latency:.1f}s ({len(content)} chars)")
            return content
        else:
            return f"(Erreur M2: HTTP {r.status_code})"
    except requests.exceptions.Timeout:
        return "(M2 timeout)"
    except Exception as e:
        return f"(Erreur: {e})"


# ================================================================
# MEMOIRE PROCEDURALE - macro_workflows
# ================================================================

def _init_workflow_db():
    """Cree la table macro_workflows"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS macro_workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT UNIQUE,
            steps_json TEXT NOT NULL,
            usage_count INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            last_used TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  DB init error: {e}")
        return False


def save_workflow(trigger, steps):
    """Sauvegarde un workflow pour auto-compilation future"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT OR REPLACE INTO macro_workflows
                        (trigger, steps_json, last_used)
                        VALUES (?, ?, datetime('now','localtime'))""",
                     (trigger.lower().strip(), json.dumps(steps, ensure_ascii=False)))
        conn.commit()
        conn.close()
        print(f"  MEMORISE: workflow '{trigger}' ({len(steps)} etapes)")
        return True
    except Exception as e:
        print(f"  SAVE error: {e}")
        return False


def load_workflow(trigger):
    """Charge un workflow memorise"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT steps_json FROM macro_workflows WHERE trigger = ?",
                    (trigger.lower().strip(),))
        row = cur.fetchone()
        if row:
            conn.execute("""UPDATE macro_workflows SET usage_count = usage_count + 1,
                            last_used = datetime('now','localtime')
                            WHERE trigger = ?""", (trigger.lower().strip(),))
            conn.commit()
        conn.close()
        if row:
            return json.loads(row[0])
    except:
        pass
    return None


def list_workflows():
    """Liste les workflows memorises"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT trigger, usage_count, last_used FROM macro_workflows ORDER BY usage_count DESC")
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def delete_workflow(trigger):
    """Supprime un workflow"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM macro_workflows WHERE trigger = ?", (trigger.lower().strip(),))
        conn.commit()
        conn.close()
        return True
    except:
        return False


# ================================================================
# WORKFLOW TEMPLATES - Scenarios pre-definis
# ================================================================

WORKFLOW_TEMPLATES = {
    "mail": {
        "detect": ["mail", "email", "e-mail", "envoie un mail", "ecris un mail"],
        "steps": [
            {"action": "OPEN_URL", "params": "https://mail.google.com/mail/u/0/#inbox?compose=new"},
            {"action": "WAIT", "params": "4"},
            {"action": "ASK_USER", "params": "A qui veux-tu ecrire ?", "target": "destinataire"},
            {"action": "TYPE_TEXT", "params": "{destinataire}"},
            {"action": "PRESS_KEY", "params": "tab"},
            {"action": "ASK_USER", "params": "Quel sujet ?", "target": "sujet"},
            {"action": "TYPE_TEXT", "params": "{sujet}"},
            {"action": "PRESS_KEY", "params": "tab"},
            {"action": "INTERACTIVE_GEN", "params": "Que veux-tu dire dans ce mail ?",
             "context": "Email {sujet} pour {destinataire}"},
            {"action": "CONFIRM", "params": "Mail pret. Je l'envoie ?"},
        ],
    },
    "recherche": {
        "detect": ["recherche sur", "cherche des infos", "fais une recherche"],
        "steps": [
            {"action": "ASK_USER", "params": "Quel sujet de recherche ?", "target": "query"},
            {"action": "OPEN_URL", "params": "https://www.google.com/search?q={query}"},
            {"action": "WAIT", "params": "3"},
            {"action": "SPEAK", "params": "Resultats affiches pour: {query}"},
        ],
    },
    "note": {
        "detect": ["ecris une note", "prends en note", "note rapide"],
        "steps": [
            {"action": "OPEN_APP", "params": "notepad"},
            {"action": "WAIT", "params": "2"},
            {"action": "INTERACTIVE_GEN", "params": "Que veux-tu noter ?",
             "context": "Note personnelle rapide"},
        ],
    },
    "message_telegram": {
        "detect": ["envoie un message telegram", "telegram"],
        "steps": [
            {"action": "ASK_USER", "params": "Quel message pour Telegram ?", "target": "message"},
            {"action": "TELEGRAM", "params": "{message}"},
            {"action": "SPEAK", "params": "Message envoye sur Telegram."},
        ],
    },
}


def detect_template(text):
    """Detecte si le texte matche un template de workflow"""
    text_lower = text.lower()
    for name, template in WORKFLOW_TEMPLATES.items():
        for keyword in template["detect"]:
            if keyword in text_lower:
                return name, template
    return None, None


# ================================================================
# MOTEUR D'EXECUTION
# ================================================================

def execute_workflow(trigger, steps, variables=None):
    """Execute une sequence d'etapes avec variables dynamiques"""
    if variables is None:
        variables = {}

    speak(f"Execution du workflow: {trigger}")
    executed_steps = []

    for i, step in enumerate(steps):
        action = step["action"]
        params = step.get("params", "")
        target = step.get("target", "")
        context = step.get("context", "")

        # Substituer les variables {var}
        for var_name, var_val in variables.items():
            params = params.replace("{" + var_name + "}", var_val)
            if context:
                context = context.replace("{" + var_name + "}", var_val)

        print(f"  [{i+1}/{len(steps)}] {action}: {params[:60]}")

        if action == "WAIT":
            time.sleep(float(params) if params else 2)

        elif action == "SPEAK":
            speak(params)

        elif action == "ASK_USER":
            answer = listen_user(params)
            if target and answer:
                variables[target] = answer
                print(f"  VAR[{target}] = \"{answer}\"")

        elif action == "INTERACTIVE_GEN":
            user_input = listen_user(params)
            if user_input:
                speak("Generation par le cluster IA...")
                gen_context = context or trigger
                draft = generate_text(gen_context, user_input)
                if draft and not draft.startswith("("):
                    speak(f"Je propose: {draft[:80]}...")
                    os_pilot.run_command("TYPE_TEXT", draft)
                else:
                    speak("Echec de generation. Tape ton texte manuellement.")

        elif action == "CONFIRM":
            answer = listen_user(params)
            if answer and any(w in answer.lower() for w in ["oui", "yes", "envoie", "vas-y", "go", "ok"]):
                os_pilot.run_command("HOTKEY", "ctrl+enter")
                speak("Envoye.")
            else:
                speak("Annule. Le brouillon est garde.")

        elif action == "TELEGRAM":
            try:
                import requests as req
                token = os.environ.get("TELEGRAM_TOKEN", "")
                chat_id = "2010747443"
                req.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": params}, timeout=10)
            except Exception as e:
                print(f"  Telegram error: {e}")

        else:
            # Action OS Pilot standard
            os_pilot.run_command(action, params if params else None)

        executed_steps.append(step)

    return executed_steps, variables


def run_complex_task(task_text, extra=""):
    """Point d'entree principal - detecte, charge memoire ou template, execute"""
    task_lower = task_text.lower().strip()

    # 1. Verifier memoire procedurale (auto-compilation)
    cached = load_workflow(task_lower)
    if cached:
        speak(f"Protocole memorise detecte. Execution rapide.")
        execute_workflow(task_lower, cached)
        return True

    # 2. Detecter template
    name, template = detect_template(task_lower)
    if template:
        speak(f"Protocole '{name}' reconnu. Premiere execution - apprentissage.")
        steps = template["steps"]
        executed, variables = execute_workflow(task_lower, steps)
        # Sauvegarder pour la prochaine fois
        save_workflow(task_lower, steps)
        speak("Workflow termine et memorise. La prochaine fois, ce sera instantane.")
        return True

    # 3. Inconnu - demander a M2 de planifier
    speak("Commande complexe non reconnue. Je demande au cluster IA de planifier.")
    plan_prompt = f"""L'utilisateur veut: "{task_text}"
Genere un plan d'actions en JSON. Chaque action est:
{{"action": "TYPE", "params": "valeur"}}
Actions disponibles: OPEN_URL, OPEN_APP, TYPE_TEXT, PRESS_KEY, HOTKEY, WAIT, ASK_USER, INTERACTIVE_GEN, SPEAK, CONFIRM
Reponds UNIQUEMENT avec un tableau JSON d'actions."""

    try:
        payload = {
            "model": M2_MODEL,
            "messages": [
                {"role": "system", "content": "Tu es un planificateur d'actions OS. JSON uniquement."},
                {"role": "user", "content": plan_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 800
        }
        r = requests.post(M2_URL, json=payload, timeout=M2_TIMEOUT)
        if r.status_code == 200:
            msg = r.json()['choices'][0]['message']
            content = msg.get('content', '') or msg.get('reasoning_content', '') or ''
            # Extraire JSON
            if "[" in content and "]" in content:
                json_str = content[content.find("["):content.rfind("]") + 1]
                planned_steps = json.loads(json_str)
                speak(f"Plan genere: {len(planned_steps)} etapes. Execution.")
                execute_workflow(task_lower, planned_steps)
                save_workflow(task_lower, planned_steps)
                return True
    except Exception as e:
        print(f"  Planning error: {e}")

    speak("Je n'ai pas reussi a planifier cette tache.")
    return False


# Init DB
_init_workflow_db()


if __name__ == "__main__":
    print("=" * 60)
    print("  WORKFLOW ENGINE v1.0 - Test")
    print("=" * 60)

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = input("  Decris la tache >> ")

    if task.strip():
        run_complex_task(task)
    else:
        # Liste workflows memorises
        wfs = list_workflows()
        if wfs:
            print(f"\n  {len(wfs)} workflows memorises:")
            for trigger, count, last in wfs:
                print(f"    \"{trigger}\" (x{count}, last={last})")
        else:
            print("  Aucun workflow memorise.")
