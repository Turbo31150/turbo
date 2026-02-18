"""Test du pipeline vocal JARVIS avec Ollama fallback.

Simule des phrases vocales (comme si tapees au clavier en mode hybride)
et verifie que le pipeline correction -> matching -> execution fonctionne.
"""

import asyncio
import sys
sys.path.insert(0, "F:/BUREAU/turbo")

from src.voice_correction import full_correction_pipeline
from src.config import config


# Phrases de test — simule des transcriptions vocales (avec erreurs typiques Whisper)
TEST_PHRASES = [
    # === Commandes directes (doivent matcher) ===
    "ouvre chrome",
    "ouvre youtube",
    "statut du cluster",
    "status ollama",
    "mes positions",
    "statut trading",
    "capture ecran",
    "monte le volume",
    "coupe le son",
    "ouvre gmail",
    # === Avec erreurs de transcription ===
    "ouvres chrom",          # "ouvre chrome" mal transcrit
    "statu du clustere",     # "statut du cluster"
    "ouver yutube",          # "ouvre youtube"
    "mais position",         # "mes positions"
    "status olama",          # "status ollama"
    # === Phrases longues (freeform -> IA analyse) ===
    "recherche les tendances crypto du jour",
    "quels sont les signaux de trading en attente",
    "donne moi un resume du marche",
    # === Commandes implicites (un seul mot) ===
    "chrome",
    "gmail",
    "scanner",
    "cluster",
    "trading",
    "aide",
]


async def test_pipeline():
    print("=" * 70)
    print(f"  TEST PIPELINE VOCAL JARVIS — {len(TEST_PHRASES)} phrases")
    print(f"  LM Studio M1: {config.get_node_url('M1')}")
    ol = config.get_ollama_node("OL1")
    print(f"  Ollama OL1:    {ol.url if ol else 'NON CONFIGURE'}")
    print("=" * 70)

    # Test connectivity
    import httpx
    print("\n[CONNECTIVITY]")
    async with httpx.AsyncClient(timeout=3) as c:
        for name in ["M1", "M2"]:
            node = config.get_node(name)
            if not node:
                print(f"  {name}: NON CONFIGURE")
                continue
            try:
                r = await c.get(f"{node.url}/api/v1/models")
                r.raise_for_status()
                cnt = len(r.json().get("models", []))
                print(f"  {name}: ONLINE ({cnt} modeles)")
            except Exception:
                print(f"  {name}: OFFLINE")
        if ol:
            try:
                r = await c.get(f"{ol.url}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                print(f"  OL1: ONLINE ({len(models)} modeles: {', '.join(models[:5])})")
            except Exception:
                print(f"  OL1: OFFLINE")

    # Run pipeline on each phrase
    print("\n[PIPELINE TESTS]")
    stats = {"matched": 0, "freeform": 0, "total": 0}

    for phrase in TEST_PHRASES:
        stats["total"] += 1
        result = await full_correction_pipeline(phrase)

        cmd_name = result["command"].name if result["command"] else "—"
        conf = result["confidence"]
        method = result["method"]

        if result["command"]:
            stats["matched"] += 1
            icon = "OK"
        else:
            stats["freeform"] += 1
            icon = "??"

        # Show corrections if any
        corrections = ""
        if result["corrected"] != result["cleaned"]:
            corrections = f" -> [{result['corrected']}]"
        if result["intent"] and result["intent"] != result["corrected"]:
            corrections += f" -> intent:[{result['intent']}]"

        print(f"  [{icon}] \"{phrase}\"{corrections}")
        print(f"       -> cmd={cmd_name} conf={conf:.2f} method={method}")

    # Summary
    print("\n" + "=" * 70)
    print(f"  RESULTATS: {stats['matched']}/{stats['total']} matchees, "
          f"{stats['freeform']} freeform")
    pct = stats["matched"] / stats["total"] * 100 if stats["total"] else 0
    print(f"  Taux de match: {pct:.0f}%")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_pipeline())
