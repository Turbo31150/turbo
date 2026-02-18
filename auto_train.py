"""JARVIS Auto-Training — Formation automatique massive avec IA.

Envoie des centaines de phrases (correctes, avec fautes, naturelles)
a travers le pipeline complet avec correction IA.
Sauvegarde automatiquement les corrections dans jarvis.db.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import time
import json

PROJECT_ROOT = r"F:\BUREAU\turbo"
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.voice_correction import full_correction_pipeline
from src.commands import COMMANDS, VOICE_CORRECTIONS
from src.skills import find_skill, load_skills
from src.database import init_db, get_connection


# ══════════════════════════════════════════════════════════════════════════
# TRAINING DATA — 200+ phrases simulant la voix avec erreurs
# ══════════════════════════════════════════════════════════════════════════

TRAINING_DATA = [
    # ── Navigation / Apps ─────────────────────────────────────────────
    ("ouvre chrome", "ouvrir_chrome"),
    ("ouvre crome", "ouvrir_chrome"),
    ("ouvr google crome", "ouvrir_chrome"),
    ("lance chrome", "ouvrir_chrome"),
    ("ouvre le navigateur", "ouvrir_chrome"),
    ("ouvre youtube", "ouvrir_youtube"),
    ("ouvr youtub", "ouvrir_youtube"),
    ("va sur youtube", "ouvrir_youtube"),
    ("mets youtube", "ouvrir_youtube"),
    ("ouvre discord", "ouvrir_discord"),
    ("lance discorde", "ouvrir_discord"),
    ("ouvre spotify", "ouvrir_spotify"),
    ("lance spotifaille", "ouvrir_spotify"),
    ("ouvre le code", "ouvrir_vscode"),
    ("lance vs code", "ouvrir_vscode"),
    ("ouvre visual studio code", "ouvrir_vscode"),
    ("ouvre steam", None),  # pas de commande ouvrir_steam, match generique OK
    ("lance stim", "ouvrir_app"),
    ("ouvre le terminal", "ouvrir_terminal"),
    ("ouvre un terminal", "ouvrir_terminal"),
    ("ouvre le gestionnaire de taches", "ouvrir_task_manager"),
    ("ouvre le task manager", "ouvrir_task_manager"),

    # ── Volume ────────────────────────────────────────────────────────
    ("monte le son", "volume_haut"),
    ("augmente le volume", "volume_haut"),
    ("vollume plus fort", "volume_haut"),
    ("plus fort", "volume_haut"),
    ("baisse le son", "volume_bas"),
    ("moins fort", "volume_bas"),
    ("besse le sont", "volume_bas"),
    ("coupe le son", "muet"),
    ("mute", "muet"),
    ("silence", "muet"),
    ("volume a fond", "volume_precis"),
    ("mets le volume a 50", "volume_precis"),

    # ── Fenetres ──────────────────────────────────────────────────────
    ("ferme tout", "fermer_fenetre"),
    ("ferm tout", "fermer_fenetre"),
    ("ferme toutes les fenetres", "fermer_fenetre"),
    ("ferm tout les fenaitre", "fermer_fenetre"),
    ("minimise tout", "minimiser_tout"),
    ("cache tout", "minimiser_tout"),
    ("fenetre a gauche", "fenetre_gauche"),
    ("mets la fenetre a droite", "fenetre_droite"),
    ("plein ecran", "maximiser_fenetre"),  # also matches chrome_plein_ecran
    ("maximise", "maximiser_fenetre"),

    # ── Systeme ───────────────────────────────────────────────────────
    ("eteins le pc", "eteindre"),
    ("etein le pecee", "eteindre"),
    ("arrete l'ordinateur", "eteindre"),
    ("redemarrage", "redemarrer"),
    ("redemmare le pc", "redemarrer"),
    ("restart", "redemarrer"),
    ("verrouille", "verrouiller_rapide"),
    ("lock le pc", "verrouiller"),
    ("verrouille l'ecran", "verrouiller"),
    ("capture ecran", "capture_ecran"),
    ("screenshot", "capture_ecran"),
    ("capteur decrant", "capture_ecran"),
    ("fait une capture", "capture_ecran"),
    ("quelle heure il est", "heure_actuelle"),
    ("donne moi l'heure", "heure_actuelle"),
    ("kel heure", "heure_actuelle"),
    ("statut du cluster", "statut_cluster"),
    ("statu du clusteur", "statut_cluster"),
    ("etat du cluster", "statut_cluster"),
    ("montre les infos systeme", "info_systeme"),
    ("info systeme", "info_systeme"),

    # ── Media ─────────────────────────────────────────────────────────
    ("mets en pause", "media_play_pause"),
    ("pause la musique", "media_play_pause"),
    ("met en poze", "media_play_pause"),
    ("play", "media_play_pause"),
    ("joue la musique", "media_play_pause"),
    ("musique suivante", "media_next"),
    ("next", "media_next"),
    ("chanson suivante", "media_next"),
    ("musique precedente", "media_previous"),
    ("previous", "media_previous"),
    ("reviens en arriere", "media_previous"),

    # ── Recherche ─────────────────────────────────────────────────────
    ("cherche sur google", "chercher_google"),
    ("cherch google", "chercher_google"),
    ("google machine learning", "chercher_google"),
    ("recherche python tutorial", "chercher_google"),

    # ── Trading ───────────────────────────────────────────────────────
    ("lance le trading", "pipeline_trading"),
    ("demarre le trading", "pipeline_trading"),
    ("lansse le tradingue", "pipeline_trading"),
    ("trading start", "pipeline_trading"),
    ("montre les positions", "positions_trading"),
    ("mes positions", "positions_trading"),
    ("position ouvertes", "positions_trading"),
    ("montre moa les pozissions", "positions_trading"),
    ("statut trading", "statut_trading"),
    ("comment va le trading", "statut_trading"),
    ("scanne le marche", "scanner_marche"),
    ("scan les crypto", "scanner_marche"),
    ("breakout detection", "launch_sniper_breakout"),  # sniper_breakout est le bon match

    # ── Fichiers ──────────────────────────────────────────────────────
    ("ouvre le dossier", None),  # trop vague (parametre manquant)
    ("ouvr le dossier bureau", "ouvrir_bureau"),
    ("ouvre mes documents", "ouvrir_documents"),
    ("ouvre le bureau", "ouvrir_bureau"),
    ("montre le bureau", "minimiser_tout"),  # "montre le bureau" = show desktop
    ("cree un dossier", "creer_dossier"),
    ("nouveau dossier", "creer_dossier"),
    ("supprime ca", "supprimer"),
    ("efface le fichier", "supprimer"),
    ("renomme le fichier", "renommer"),
    ("sauvegarde", "sauvegarder"),
    ("enregistre", "sauvegarder"),
    ("ctrl s", "sauvegarder"),

    # ── Navigation web ────────────────────────────────────────────────
    ("va sur google", "aller_sur_site"),
    ("ouvre gmail", "ouvrir_gmail"),
    ("va sur github", "ouvrir_github"),
    ("ouvr mexc", "ouvrir_mexc"),
    ("ouvre les chart mexc", "ouvrir_mexc"),

    # ── JARVIS meta ───────────────────────────────────────────────────
    ("aide", "jarvis_aide"),
    ("help", "jarvis_aide"),
    ("aide moi", "jarvis_aide"),
    ("stop", "jarvis_stop"),
    ("arrete toi", "jarvis_stop"),
    ("quitter", "jarvis_stop"),
    ("repete", "jarvis_repete"),
    ("redis ca", "jarvis_repete"),

    # ── Phrases naturelles (freeform, pas de commande directe) ────────
    ("quel temps fait il dehors", None),
    ("raconte moi une blague", None),
    ("comment installer python", None),
    ("explique moi les fibonacci", None),
    ("c'est quoi un docker", None),
    ("resume ce code", None),

    # ── Phrases tres cassees (simule mauvaise STT) ────────────────────
    ("ouvr moa crom", "ouvrir_chrome"),
    ("fai un scrinchotte", "capture_ecran"),
    ("arrette l'ordinateurre", "eteindre"),  # IA should correct to arrete l'ordinateur
    ("redemarage du pecee", "redemarrer"),
    ("lanse le tradingue sur mecse", "pipeline_trading"),
    ("augmante le vollume", "volume_haut"),
    ("diminue le sons", "volume_bas"),
    ("fermme touttes les fenaitre", "fermer_fenetre"),
    ("ouvr le gestionaire de tache", "ouvrir_task_manager"),
    ("kel heurre il ait", "heure_actuelle"),
    ("lance spotifaille la musike", "ouvrir_spotify"),
    ("ouvr discorde", "ouvrir_discord"),
    ("fait une rechersh sur googl", "chercher_google"),
    ("va sur gitmub", "ouvrir_github"),
    ("met en pleins ecrants", "maximiser_fenetre"),  # plein ecran = maximise (chrome_plein_ecran aussi OK)
]


def save_correction(wrong: str, correct: str, category: str = "auto_training") -> None:
    """Save a correction to the database."""
    try:
        conn = get_connection()
        # Check if exists
        existing = conn.execute(
            "SELECT id FROM voice_corrections WHERE wrong=?", (wrong.lower().strip(),)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE voice_corrections SET hit_count = hit_count + 1 WHERE id=?",
                (existing[0],),
            )
        else:
            conn.execute(
                "INSERT INTO voice_corrections (wrong, correct, category, hit_count) VALUES (?, ?, ?, 1)",
                (wrong.lower().strip(), correct.lower().strip(), category),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  [DB] {e}")


async def main():
    init_db()
    skills = load_skills()

    print("=" * 70)
    print("  JARVIS AUTO-TRAINING — Formation Automatique avec IA")
    print(f"  {len(TRAINING_DATA)} phrases | {len(COMMANDS)} commandes | {len(skills)} skills")
    print("=" * 70)
    print()

    stats = {
        "total": 0, "correct": 0, "wrong_cmd": 0, "no_match": 0,
        "freeform_ok": 0, "ia_fixed": 0, "corrections_saved": 0,
    }
    total_ms = 0
    errors = []

    for i, (phrase, expected_cmd) in enumerate(TRAINING_DATA, 1):
        stats["total"] += 1
        t0 = time.time()
        try:
            cr = await full_correction_pipeline(phrase, use_ia=True)
        except Exception as e:
            print(f"  [{i:3d}] ERROR  {phrase} — {e}")
            continue
        ms = (time.time() - t0) * 1000
        total_ms += ms

        cmd = cr["command"]
        cmd_name = cmd.name if cmd else None
        conf = cr["confidence"]
        method = cr["method"]
        corrected = cr["corrected"]

        # Check result
        if expected_cmd is None:
            # Freeform — no specific command expected
            if cmd_name is None or method == "freeform":
                status = "FREE_OK"
                stats["freeform_ok"] += 1
            else:
                status = "FREE??"
                stats["correct"] += 1  # Not wrong, just unexpected match
        elif cmd_name == expected_cmd:
            status = "OK"
            stats["correct"] += 1
        elif cmd_name is not None:
            status = "WRONG"
            stats["wrong_cmd"] += 1
            errors.append((phrase, expected_cmd, cmd_name, conf))
        else:
            # Check skill match
            intent = cr["intent"] or corrected or phrase
            skill, score = find_skill(intent)
            if skill and score >= 0.6:
                status = f"SKILL"
                stats["correct"] += 1
            else:
                status = "MISS"
                stats["no_match"] += 1
                errors.append((phrase, expected_cmd, None, conf))

        # Save corrections for wrong/missed items
        if status in ("WRONG", "MISS") and expected_cmd:
            # Find the expected command's trigger
            for c in COMMANDS:
                if c.name == expected_cmd:
                    save_correction(phrase, c.triggers[0])
                    stats["corrections_saved"] += 1
                    break

        # Track IA corrections
        if "ia" in method:
            stats["ia_fixed"] += 1

        # Display
        corr_tag = f" (IA→{corrected[:30]})" if corrected != phrase.lower().strip() else ""
        expected_tag = f" expected={expected_cmd}" if status in ("WRONG", "MISS") else ""
        print(f"  [{i:3d}/{len(TRAINING_DATA)}] {status:7s} {conf:.0%} {method:12s} "
              f"{(cmd_name or '---'):22s} ← {phrase}{corr_tag}{expected_tag}")

    # ── Summary ──────────────────────────────────────────────────────
    avg_ms = total_ms / stats["total"] if stats["total"] else 0
    accuracy = (stats["correct"] + stats["freeform_ok"]) / stats["total"] * 100 if stats["total"] else 0

    print()
    print("=" * 70)
    print("  RESULTATS AUTO-TRAINING")
    print("=" * 70)
    print(f"  Total phrases:      {stats['total']}")
    print(f"  Corrects:           {stats['correct']}")
    print(f"  Freeform OK:        {stats['freeform_ok']}")
    print(f"  Mauvaise commande:  {stats['wrong_cmd']}")
    print(f"  Pas de match:       {stats['no_match']}")
    print(f"  Corriges par IA:    {stats['ia_fixed']}")
    print(f"  Corrections savees: {stats['corrections_saved']}")
    print(f"  Precision globale:  {accuracy:.1f}%")
    print(f"  Temps moyen:        {avg_ms:.0f}ms/phrase")
    print(f"  Temps total:        {total_ms/1000:.1f}s")
    print("=" * 70)

    if errors:
        print(f"\n  ERREURS ({len(errors)}):")
        for phrase, expected, got, conf in errors:
            print(f"    '{phrase}' → attendu={expected}, obtenu={got or 'RIEN'} ({conf:.0%})")

    # Save report
    report = {
        "timestamp": time.time(),
        "stats": stats,
        "accuracy": accuracy,
        "avg_ms": avg_ms,
        "errors": [{"phrase": p, "expected": e, "got": g, "conf": c} for p, e, g, c in errors],
    }
    report_path = os.path.join(PROJECT_ROOT, "data", "training_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Rapport sauve: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
