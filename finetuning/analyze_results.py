#!/usr/bin/env python3
"""
Analyser et visualiser les résultats du benchmark JARVIS
Génère des rapports texte et graphiques depuis benchmark_results.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import statistics

try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    print("[AVERTISSEMENT] matplotlib non disponible, graphiques désactivés")
    plt = None


class BenchmarkAnalyzer:
    """Analyser les résultats du benchmark"""

    def __init__(self, json_file: str = "F:/BUREAU/turbo/finetuning/benchmark_results.json"):
        """Charger les résultats"""
        self.json_file = Path(json_file)
        self.data = None
        self.load_data()

    def load_data(self) -> bool:
        """Charger les données JSON"""
        if not self.json_file.exists():
            print(f"[ERREUR] Fichier non trouvé: {self.json_file}")
            return False

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            print(f"[OK] Données chargées: {len(self.data['results'])} tests")
            return True
        except Exception as e:
            print(f"[ERREUR] Chargement JSON: {e}")
            return False

    def generate_text_report(self, output_file: str = None) -> str:
        """Générer un rapport texte détaillé"""
        if not self.data:
            return ""

        if output_file is None:
            output_file = self.json_file.parent / "benchmark_report.txt"

        stats = self.data["statistics"]
        by_category = self.data["by_category"]

        report_lines = [
            "=" * 100,
            "RAPPORT DÉTAILLÉ - BENCHMARK JARVIS COMPARATIF",
            "=" * 100,
            "",
            "[MÉTADONNÉES]",
            f"  Modèle de base: {self.data['metadata']['base_model']}",
            f"  LoRA adapters: {self.data['metadata']['lora_adapter'] or 'Aucun'}",
            f"  Device: {self.data['metadata']['device']}",
            f"  Timestamp: {self.data['metadata']['timestamp']}",
            "",
            "[STATISTIQUES GLOBALES]",
            f"  Total tests: {stats['total_tests']}",
            f"  Similarité cosinus moyenne: {stats['avg_cosine_similarity']:.4f}",
            f"  Correspondance mots-clés (base): {stats['avg_keyword_match_base']:.2f}",
            f"  Correspondance mots-clés (fine-tuné): {stats['avg_keyword_match_finetuned']:.2f}",
            f"  Amélioration mots-clés: +{(stats['avg_keyword_match_finetuned'] - stats['avg_keyword_match_base']):.2f} (+{(stats['avg_keyword_match_finetuned']/stats['avg_keyword_match_base']*100 - 100) if stats['avg_keyword_match_base'] > 0 else 0:.1f}%)",
            f"  Pertinence JARVIS (base): {stats['avg_relevance_base']:.4f}",
            f"  Pertinence JARVIS (fine-tuné): {stats['avg_relevance_finetuned']:.4f}",
            f"  Amélioration pertinence: +{(stats['avg_relevance_finetuned'] - stats['avg_relevance_base']):.4f} (+{(stats['avg_relevance_finetuned']/stats['avg_relevance_base']*100 - 100) if stats['avg_relevance_base'] > 0 else 0:.1f}%)",
            "",
            "[PAR CATÉGORIE]",
            f"{'Catégorie':<25} {'Tests':<8} {'Cosine':<10} {'KW(B)':<10} {'KW(FT)':<10} {'Rel(B)':<10} {'Rel(FT)':<10}",
            "-" * 100,
        ]

        for category, cat_stats in by_category.items():
            report_lines.append(
                f"{category:<25} {cat_stats['count']:<8} "
                f"{cat_stats['avg_cosine']:<10.4f} "
                f"{cat_stats['avg_keyword_base']:<10.2f} "
                f"{cat_stats['avg_keyword_ft']:<10.2f} "
                f"{cat_stats['avg_relevance_base']:<10.4f} "
                f"{cat_stats['avg_relevance_ft']:<10.4f}"
            )

        report_lines.extend([
            "",
            "[TOP 5 TESTS - PLUS GRANDE AMÉLIORATION (Pertinence JARVIS)]",
            "-" * 100,
        ])

        # Trier par amélioration de pertinence
        results_with_improvement = []
        for result in self.data["results"]:
            improvement = result["jarvis_relevance_finetuned"] - result["jarvis_relevance_base"]
            results_with_improvement.append((result, improvement))

        top_improvements = sorted(results_with_improvement, key=lambda x: x[1], reverse=True)[:5]

        for i, (result, improvement) in enumerate(top_improvements, 1):
            report_lines.append(
                f"{i}. '{result['prompt']}' (catégorie: {result['category']})\n"
                f"   Pertinence base: {result['jarvis_relevance_base']:.4f} "
                f"→ FT: {result['jarvis_relevance_finetuned']:.4f} "
                f"(+{improvement:.4f})\n"
                f"   Mots-clés: {result['keyword_match_base']}/{len(result['keywords_expected'])} "
                f"→ {result['keyword_match_finetuned']}/{len(result['keywords_expected'])}"
            )

        report_lines.extend([
            "",
            "[TOP 5 TESTS - MOINS BONNE PERFORMANCE (Pertinence JARVIS)]",
            "-" * 100,
        ])

        worst_performance = sorted(results_with_improvement, key=lambda x: x[1])[:5]

        for i, (result, improvement) in enumerate(worst_performance, 1):
            report_lines.append(
                f"{i}. '{result['prompt']}' (catégorie: {result['category']})\n"
                f"   Pertinence base: {result['jarvis_relevance_base']:.4f} "
                f"→ FT: {result['jarvis_relevance_finetuned']:.4f} "
                f"({improvement:+.4f})\n"
                f"   Mots-clés: {result['keyword_match_base']}/{len(result['keywords_expected'])} "
                f"→ {result['keyword_match_finetuned']}/{len(result['keywords_expected'])}"
            )

        report_lines.extend([
            "",
            "[RECOMMANDATIONS]",
            "-" * 100,
        ])

        # Analyser les résultats pour recommandations
        avg_improvement = stats["avg_relevance_finetuned"] - stats["avg_relevance_base"]

        if avg_improvement > 0.1:
            report_lines.append("✓ Fine-tuning EFFICACE: amélioration significative de la pertinence JARVIS")
        elif avg_improvement > 0.05:
            report_lines.append("~ Fine-tuning MODÉRÉ: amélioration légère, peut nécessiter plus de données d'entraînement")
        else:
            report_lines.append("✗ Fine-tuning INSUFFISANT: peu ou pas d'amélioration, revoir stratégie")

        kw_improvement = stats["avg_keyword_match_finetuned"] - stats["avg_keyword_match_base"]
        if kw_improvement > 0.5:
            report_lines.append("✓ Correspondance mots-clés: AMÉLIORÉE (le modèle comprend mieux les commandes)")
        elif kw_improvement > 0:
            report_lines.append("~ Correspondance mots-clés: légèrement améliorée")
        else:
            report_lines.append("✗ Correspondance mots-clés: pas d'amélioration ou dégradation")

        worst_category = min(by_category.items(), key=lambda x: x[1]["avg_relevance_ft"])[0]
        report_lines.append(f"⚠ Catégorie la plus faible: '{worst_category}', focus d'amélioration suggéré")

        report_lines.extend([
            "",
            "=" * 100,
        ])

        report_text = "\n".join(report_lines)

        # Sauvegarder
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_text)

        print(report_text)
        print(f"\n[OK] Rapport sauvegardé: {output_file}")
        return report_text

    def generate_charts(self) -> bool:
        """Générer des graphiques"""
        if not plt:
            print("[AVERTISSEMENT] matplotlib non disponible, graphiques ignorés")
            return False

        if not self.data:
            return False

        stats = self.data["statistics"]
        by_category = self.data["by_category"]

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("JARVIS Benchmark: Modèle Base vs Fine-tuné", fontsize=16, fontweight="bold")

        # 1. Comparaison par catégorie - Pertinence
        ax = axes[0, 0]
        categories = list(by_category.keys())
        base_rel = [by_category[c]["avg_relevance_base"] for c in categories]
        ft_rel = [by_category[c]["avg_relevance_ft"] for c in categories]

        x = np.arange(len(categories))
        width = 0.35

        ax.bar(x - width/2, base_rel, width, label="Base", alpha=0.8, color="skyblue")
        ax.bar(x + width/2, ft_rel, width, label="Fine-tuné", alpha=0.8, color="orange")

        ax.set_ylabel("Pertinence JARVIS", fontweight="bold")
        ax.set_title("Pertinence JARVIS par Catégorie")
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha="right")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        # 2. Correspondance mots-clés
        ax = axes[0, 1]
        base_kw = [by_category[c]["avg_keyword_base"] for c in categories]
        ft_kw = [by_category[c]["avg_keyword_ft"] for c in categories]

        ax.bar(x - width/2, base_kw, width, label="Base", alpha=0.8, color="lightgreen")
        ax.bar(x + width/2, ft_kw, width, label="Fine-tuné", alpha=0.8, color="lightcoral")

        ax.set_ylabel("Correspondance Mots-clés", fontweight="bold")
        ax.set_title("Mots-clés Trouvés par Catégorie")
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha="right")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        # 3. Distribution des scores de pertinence
        ax = axes[1, 0]
        all_base_rel = [r["jarvis_relevance_base"] for r in self.data["results"]]
        all_ft_rel = [r["jarvis_relevance_finetuned"] for r in self.data["results"]]

        ax.hist(all_base_rel, bins=10, alpha=0.6, label="Base", color="skyblue", edgecolor="black")
        ax.hist(all_ft_rel, bins=10, alpha=0.6, label="Fine-tuné", color="orange", edgecolor="black")

        ax.set_xlabel("Score de Pertinence JARVIS", fontweight="bold")
        ax.set_ylabel("Nombre de tests", fontweight="bold")
        ax.set_title("Distribution des Scores de Pertinence")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        # 4. Statistiques globales
        ax = axes[1, 1]
        ax.axis("off")

        metrics_text = (
            "RÉSUMÉ STATISTIQUE\n\n"
            f"Total tests: {stats['total_tests']}\n"
            f"Similarité cosinus: {stats['avg_cosine_similarity']:.4f}\n\n"
            "PERTINENCE JARVIS\n"
            f"  Base: {stats['avg_relevance_base']:.4f}\n"
            f"  FT:   {stats['avg_relevance_finetuned']:.4f}\n"
            f"  Δ:    +{(stats['avg_relevance_finetuned'] - stats['avg_relevance_base']):.4f}\n\n"
            "MOTS-CLÉS\n"
            f"  Base: {stats['avg_keyword_match_base']:.2f}\n"
            f"  FT:   {stats['avg_keyword_match_finetuned']:.2f}\n"
            f"  Δ:    +{(stats['avg_keyword_match_finetuned'] - stats['avg_keyword_match_base']):.2f}"
        )

        ax.text(
            0.1, 0.9, metrics_text,
            transform=ax.transAxes,
            fontsize=11,
            verticalalignment="top",
            fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5)
        )

        plt.tight_layout()

        # Sauvegarder
        output_file = self.json_file.parent / "benchmark_charts.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"[OK] Graphiques sauvegardés: {output_file}")

        return True


def main():
    """Point d'entrée"""
    analyzer = BenchmarkAnalyzer()

    if not analyzer.data:
        return 1

    # Générer rapport texte
    analyzer.generate_text_report()

    # Générer graphiques
    analyzer.generate_charts()

    return 0


if __name__ == "__main__":
    sys.exit(main())
