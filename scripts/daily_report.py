#!/usr/bin/env python3
"""Script standalone — Génère le rapport quotidien JARVIS.

Usage:
    python3 scripts/daily_report.py                  # Rapport du jour
    python3 scripts/daily_report.py 2026-03-14       # Rapport d'une date spécifique
    python3 scripts/daily_report.py --summary        # Résumé texte uniquement
    python3 scripts/daily_report.py --json            # JSON uniquement (stdout)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.daily_report_generator import DailyReportGenerator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JARVIS Daily Report Generator",
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date cible YYYY-MM-DD (defaut: aujourd'hui)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Afficher uniquement le resume texte (format Telegram)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_only",
        help="Sortie JSON uniquement (stdout)",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Ne pas generer le fichier HTML",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Logs detailles",
    )

    args = parser.parse_args()

    # Configuration logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    generator = DailyReportGenerator()

    # Mode résumé texte
    if args.summary:
        summary = generator.get_summary(args.date)
        print(summary)
        return

    # Génération complète
    report = generator.generate(args.date)

    # Mode JSON uniquement
    if args.json_only:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return

    # Génération HTML
    if not args.no_html:
        html_path = generator.generate_html(args.date)
        print(f"Rapport HTML : {html_path}", file=sys.stderr)

    # Afficher le résumé
    summary = generator.get_summary(args.date)
    print(summary)

    # Afficher les recommandations
    recs = report.get("recommendations", [])
    if recs:
        print(f"\n{'=' * 30}")
        print(f"Rapport genere avec succes pour {report['date']}")
        print(f"  JSON : {_ROOT / 'data' / 'reports' / (report['date'] + '.json')}")
        if not args.no_html:
            print(f"  HTML : {_ROOT / 'data' / 'reports' / (report['date'] + '.html')}")


if __name__ == "__main__":
    main()
