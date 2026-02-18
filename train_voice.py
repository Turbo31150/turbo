"""JARVIS Voice Training — Entrainement du pipeline vocal par clavier ou voix.

Modes:
  python train_voice.py              Mode interactif (tape des phrases)
  python train_voice.py --batch      Phrases de test auto-generees
  python train_voice.py --voice      Entrainement par voix reelle (Ctrl PTT)

Pour chaque phrase:
1. Pipeline complet: nettoyage → correction → phonetique → fuzzy match → IA
2. Affiche le resultat: commande detectee, confiance, suggestions
3. Tu valides (Entree) ou corriges (tape la bonne commande)
4. Sauvegarde la correction dans la base SQL
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import time

PROJECT_ROOT = r"F:\BUREAU\turbo"
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.voice_correction import full_correction_pipeline, VoiceSession, format_suggestions
from src.commands import COMMANDS, match_command, correct_voice_text, VOICE_CORRECTIONS
from src.skills import find_skill, load_skills
from src.database import init_db, get_connection


# ── Phrases de test pour le batch mode ────────────────────────────────────

TRAINING_PHRASES = [
    # Commandes claires
    "ouvre chrome",
    "ferme tout",
    "volume a fond",
    "baisse le son",
    "mets en pause la musique",
    "statut du cluster",
    "ouvre youtube",
    "capture ecran",
    "eteins le pc",
    "redemarrage",
    # Erreurs de transcription typiques
    "ouvre crome",
    "ferm tout",
    "vollume a font",
    "besse le sont",
    "met en poze la musike",
    "statu du clusteur",
    "ouvr youtub",
    "capteur decrant",
    "etein le pecee",
    "redemmarage",
    # Phrases naturelles (pas des commandes directes)
    "hey jarvis quelle heure il est",
    "dis moi la meteo",
    "lance le trading",
    "montre moi les positions",
    "scanne les crypto",
    "je veux voir les logs",
    "nettoie le bureau",
    "sauvegarde tout",
    "ouvre le fichier config",
    "recherche dans les fichiers",
    # Phrases ambigues
    "ouvre le truc la",
    "fait le machin",
    "mets ca bien",
    "regarde un peu",
    "analyse ca",
    # Accents et variations
    "éteins l'écran",
    "où est le fichier",
    "crée un nouveau dossier",
    "supprime ça",
    "vérifie le réseau",
]


def save_correction(wrong: str, correct: str, category: str = "training") -> None:
    """Save a voice correction to the database."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO voice_corrections (wrong, correct, category, hit_count) VALUES (?, ?, ?, 1)",
            (wrong.lower().strip(), correct.lower().strip(), category),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  [DB ERROR] {e}")


def print_result(cr: dict, duration_ms: float) -> None:
    """Pretty-print pipeline result."""
    print(f"\n  {'─' * 55}")
    print(f"  RAW:        {cr['raw']}")
    if cr['cleaned'] != cr['raw'].lower().strip():
        print(f"  CLEANED:    {cr['cleaned']}")
    if cr['corrected'] != cr['cleaned']:
        print(f"  CORRECTED:  {cr['corrected']}")
    if cr['intent'] and cr['intent'] != cr['corrected']:
        print(f"  INTENT:     {cr['intent']}")

    cmd = cr['command']
    conf = cr['confidence']
    method = cr['method']

    if cmd:
        print(f"  MATCH:      {cmd.name} ({cmd.description})")
        print(f"  CONFIANCE:  {conf:.0%} (method={method})")
        if cr['params']:
            print(f"  PARAMS:     {cr['params']}")
    else:
        print(f"  MATCH:      AUCUN (method={method})")

    # Skill match
    intent_text = cr['intent'] or cr['corrected'] or cr['raw']
    skill, skill_score = find_skill(intent_text)
    if skill and skill_score >= 0.5:
        print(f"  SKILL:      {skill.name} (score={skill_score:.2f}, {len(skill.steps)} etapes)")

    if cr['suggestions']:
        top3 = cr['suggestions'][:3]
        for s_cmd, s_score in top3:
            print(f"  SUGGESTION: {s_cmd.name} ({s_score:.0%}) — {s_cmd.triggers[0]}")

    print(f"  DUREE:      {duration_ms:.0f}ms")
    print(f"  {'─' * 55}")


async def train_interactive() -> None:
    """Interactive training mode — type phrases, validate or correct."""
    init_db()
    skills = load_skills()
    n_cmds = len(COMMANDS)
    n_corrections = len(VOICE_CORRECTIONS)

    print("=" * 60)
    print("  JARVIS VOICE TRAINING — Mode Interactif")
    print(f"  {n_cmds} commandes | {len(skills)} skills | {n_corrections} corrections")
    print("=" * 60)
    print()
    print("  Tape une phrase comme si tu parlais a JARVIS.")
    print("  Apres le resultat:")
    print("    Entree        = correct (valide)")
    print("    texte + Entree = correction (enregistre)")
    print("    'skip'         = passer")
    print("    'exit'         = quitter")
    print()

    stats = {"total": 0, "correct": 0, "corrected": 0, "skipped": 0}

    while True:
        try:
            raw = input("\n[TRAIN] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue
        if raw.lower() == "exit":
            break

        stats["total"] += 1
        t0 = time.time()
        cr = await full_correction_pipeline(raw, use_ia=True)
        duration_ms = (time.time() - t0) * 1000

        print_result(cr, duration_ms)

        # Ask for validation
        try:
            feedback = input("  [OK/correction] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if feedback.lower() == "skip":
            stats["skipped"] += 1
            continue
        elif feedback.lower() == "exit":
            break
        elif feedback == "":
            # Validated as correct
            stats["correct"] += 1
            print("  -> Valide!")
        else:
            # User provided correction — auto-clean with IA before saving
            clean_feedback = feedback
            try:
                ia_clean = await full_correction_pipeline(feedback, use_ia=True)
                if ia_clean["corrected"] and ia_clean["corrected"] != feedback.lower().strip():
                    clean_feedback = ia_clean["corrected"]
                    print(f"  [IA auto-clean] '{feedback}' → '{clean_feedback}'")
            except Exception:
                pass
            stats["corrected"] += 1
            save_correction(raw, clean_feedback)
            print(f"  -> Correction sauvee: '{raw}' → '{clean_feedback}'")

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTATS ENTRAINEMENT")
    print(f"  Total: {stats['total']} | Corrects: {stats['correct']} | "
          f"Corriges: {stats['corrected']} | Passes: {stats['skipped']}")
    if stats['total'] > 0:
        accuracy = stats['correct'] / stats['total'] * 100
        print(f"  Precision brute: {accuracy:.0f}%")
    print("=" * 60)


async def train_batch() -> None:
    """Batch training — test all predefined phrases automatically."""
    init_db()
    skills = load_skills()

    print("=" * 60)
    print("  JARVIS VOICE TRAINING — Mode Batch")
    print(f"  {len(TRAINING_PHRASES)} phrases de test")
    print("=" * 60)

    results = {"matched": 0, "unmatched": 0, "low_conf": 0}
    total_ms = 0

    for i, phrase in enumerate(TRAINING_PHRASES, 1):
        t0 = time.time()
        cr = await full_correction_pipeline(phrase, use_ia=False)  # No IA for batch speed
        ms = (time.time() - t0) * 1000
        total_ms += ms

        cmd = cr['command']
        conf = cr['confidence']
        intent = cr['intent'] or cr['corrected'] or phrase

        skill, skill_score = find_skill(intent)

        if cmd and conf >= 0.65:
            status = "OK"
            results["matched"] += 1
        elif skill and skill_score >= 0.65:
            status = f"SKILL({skill.name})"
            results["matched"] += 1
        elif cmd and conf >= 0.4:
            status = "LOW"
            results["low_conf"] += 1
        else:
            status = "MISS"
            results["unmatched"] += 1

        cmd_name = cmd.name if cmd else (f"skill:{skill.name}" if skill else "---")
        print(f"  [{i:3d}/{len(TRAINING_PHRASES)}] {status:6s} {conf:.0%} {cmd_name:25s} ← {phrase}")

    avg_ms = total_ms / len(TRAINING_PHRASES) if TRAINING_PHRASES else 0
    matched_pct = results['matched'] / len(TRAINING_PHRASES) * 100 if TRAINING_PHRASES else 0

    print("\n" + "=" * 60)
    print("  RESULTATS BATCH")
    print(f"  Matches: {results['matched']} | Low conf: {results['low_conf']} | Miss: {results['unmatched']}")
    print(f"  Precision: {matched_pct:.0f}%")
    print(f"  Temps moyen: {avg_ms:.0f}ms/phrase | Total: {total_ms:.0f}ms")
    print("=" * 60)


async def train_voice() -> None:
    """Voice training — use real mic + Whisper, then validate."""
    from src.voice import listen_voice, start_whisper, stop_whisper, check_microphone

    if not check_microphone():
        print("[ERREUR] Aucun micro detecte. Utilise le mode interactif (sans --voice).")
        return

    init_db()
    print("=" * 60)
    print("  JARVIS VOICE TRAINING — Mode Vocal (Ctrl PTT)")
    print("=" * 60)
    print("  Maintiens CTRL, parle, relache. Puis valide ou corrige.")
    print()

    print("[WHISPER] Chargement du modele...")
    start_whisper()

    stats = {"total": 0, "correct": 0, "corrected": 0}

    try:
        while True:
            raw = await listen_voice(timeout=15.0, use_ptt=True)
            if not raw:
                continue

            stats["total"] += 1
            print(f"\n  [VOICE] {raw}")

            t0 = time.time()
            cr = await full_correction_pipeline(raw, use_ia=True)
            ms = (time.time() - t0) * 1000

            print_result(cr, ms)

            try:
                feedback = input("  [OK/correction/exit] > ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if feedback.lower() == "exit":
                break
            elif feedback == "":
                stats["correct"] += 1
                print("  -> Valide!")
            else:
                stats["corrected"] += 1
                save_correction(raw, feedback)
                print(f"  -> Correction sauvee: '{raw}' → '{feedback}'")
    finally:
        stop_whisper()

    print(f"\n  Total: {stats['total']} | Corrects: {stats['correct']} | Corriges: {stats['corrected']}")


async def main():
    args = sys.argv[1:]
    if "--batch" in args:
        await train_batch()
    elif "--voice" in args:
        await train_voice()
    else:
        await train_interactive()


if __name__ == "__main__":
    asyncio.run(main())
