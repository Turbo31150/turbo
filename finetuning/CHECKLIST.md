# Checklist - Benchmark JARVIS

## Avant de lancer le benchmark

### Configuration système
- [ ] Python 3.13+ installé
- [ ] PyTorch 2.0+ installé
- [ ] CUDA 11.8+ (optionnel, GPU recommandé)
- [ ] GPU avec 20GB+ VRAM (ou CPU fallback)
- [ ] 100GB+ disque libre

### Installation dépendances
- [ ] Installer: `uv pip install transformers peft bitsandbytes scikit-learn matplotlib`
- [ ] Vérifier imports: `uv run python finetuning/check_setup.py` → OK

### Structure fichiers
- [ ] Répertoire `F:\BUREAU\turbo\finetuning\` existe
- [ ] Tous les scripts Python présents (4 fichiers)
- [ ] Fichier configuration JSON présent
- [ ] Documentation présente (6 fichiers)

### Modèles
- [ ] Vérifier: `uv run python finetuning/check_setup.py`
- [ ] Connexion HuggingFace OK (pour télécharger Qwen)
- [ ] Espace disque pour cache modèles (~50GB)

### Adaptateurs LoRA (optionnel)
- [ ] Adapter LoRA présent OU
- [ ] Benchmark fonctionnera sans (test modèle base seul)
- [ ] Si présent: Vérifier `adapter_config.json` + `adapter_model.bin`

---

## Lancer le benchmark

### Étape 1: Vérification (1 min)
```bash
cd F:\BUREAU\turbo
uv run python finetuning/check_setup.py
```
- [ ] Affiche: "✓ CONFIGURATION OK"
- [ ] Tous les imports OK
- [ ] GPU détecté (ou CPU OK)
- [ ] Pas d'erreurs

### Étape 2: Test rapide (5 min)
```bash
uv run python finetuning/quick_test.py
```
- [ ] Affiche: "✓ QUICK TEST RÉUSSI"
- [ ] Modèle charge
- [ ] Génération fonctionne
- [ ] Pas d'OOM errors

### Étape 3: Benchmark complet (3-5 min)
```bash
uv run python finetuning/benchmark.py
```
- [ ] Modèles chargent
- [ ] 30 tests lancés
- [ ] Pas d'erreurs lors de la génération
- [ ] Metrics calculés
- [ ] JSON report généré: `benchmark_results.json`

### Étape 4: Analyse (1 min)
```bash
uv run python finetuning/analyze_results.py
```
- [ ] Rapport texte généré: `benchmark_report.txt`
- [ ] Graphiques générés: `benchmark_charts.png`
- [ ] Pas d'erreurs

---

## Fichiers de sortie attendus

### Fichiers générés
- [ ] `benchmark_results.json` (50-100 KB)
  - Métadonnées
  - Statistiques
  - 30 résultats détaillés

- [ ] `benchmark_report.txt` (10-20 KB)
  - Rapport lisible
  - Top 5 améliorations
  - Recommandations

- [ ] `benchmark_charts.png` (500KB-1MB)
  - 4 graphiques
  - PNG 300 DPI

### Validation JSON
- [ ] JSON valide (peut être ouvert)
- [ ] Contient "statistics" key
- [ ] Contient "results" array avec 30 items
- [ ] Contient "by_category" groupes

### Validation Rapport
- [ ] Texte lisible
- [ ] Contient statistiques globales
- [ ] Contient comparaison par catégorie
- [ ] Contient recommandations

### Validation Graphiques
- [ ] PNG lisible
- [ ] 4 graphiques visibles
- [ ] Légendes lisibles
- [ ] Titre du document

---

## Interprétation des résultats

### Métriques globales
- [ ] Lire `avg_cosine_similarity`: _____
  - [ ] Élevée (>0.8)? Réponses similaires
  - [ ] Basse (<0.5)? Réponses différentes

- [ ] Lire `avg_relevance_base`: _____
- [ ] Lire `avg_relevance_finetuned`: _____
- [ ] Calculer amélioration: (FT - Base) / Base * 100 = _____%
  - [ ] >10% ? Efficace ✓
  - [ ] 5-10% ? Modéré ~
  - [ ] <5% ? Insuffisant ✗

### Par catégorie
- [ ] Lire `commandes_vocales` scores
  - [ ] Relevance base: _____
  - [ ] Relevance FT: _____

- [ ] Lire `corrections_vocales` scores
  - [ ] Relevance base: _____
  - [ ] Relevance FT: _____

- [ ] Lire `tool_routing` scores
  - [ ] Relevance base: _____
  - [ ] Relevance FT: _____

### Mots-clés
- [ ] Base moyenne: _____ / 4
- [ ] FT moyenne: _____ / 4
- [ ] Amélioration > 0.5 ? ✓

---

## Troubleshooting

### Si GPU out of memory
- [ ] Réduire `max_new_tokens`: 128 → 64
- [ ] Fermer applications gourmandes
- [ ] Essayer 8-bit quantization
- [ ] Re-lancer

### Si import error
- [ ] Réinstaller: `uv pip install --force-reinstall transformers peft bitsandbytes`
- [ ] Vérifier versions
- [ ] Re-lancer

### Si très lent
- [ ] Vérifier GPU: `uv run python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Vérifier device: `uv run python -c "import torch; print(torch.cuda.current_device())"`
- [ ] Réduire max_new_tokens
- [ ] Considérer CPU fallback

### Si adaptateur LoRA non trouvé
- [ ] Vérifier chemin: `F:/BUREAU/turbo/finetuning/output/*/final/`
- [ ] Vérifier `adapter_config.json` existe
- [ ] Benchmark fonctionne sans (modèle base seul)

---

## Prochaines étapes selon résultats

### Si efficace (>10% amélioration)
- [ ] Valider résultats
- [ ] Déployer adaptateurs LoRA au cluster
- [ ] Intégrer aux launchers JARVIS
- [ ] Monitorer en production
- [ ] Documenter résultats

### Si modéré (5-10% amélioration)
- [ ] Analyser catégories faibles
- [ ] Collecter plus de données JARVIS
- [ ] Ré-entraîner avec meilleure config
- [ ] Re-benchmarker
- [ ] Comparer résultats

### Si insuffisant (<5% amélioration)
- [ ] Analyser dataset d'entraînement
- [ ] Revoir hyperparamètres
- [ ] Augmenter nombre d'epochs
- [ ] Essayer différent learning rate
- [ ] Re-benchmarker

---

## Documentation à consulter

### Pour débuter
- [ ] Lire: `QUICKSTART.txt` (5 min)
- [ ] Exécuter: `check_setup.py` (1 min)

### Pour installer
- [ ] Lire: `INSTALLATION.md` (15 min)

### Pour techniques
- [ ] Lire: `README_BENCHMARK.md` (20 min)
- [ ] Lire: `FEATURES.md` (20 min)

### Pour navigation
- [ ] Lire: `INDEX.md` (10 min)

### Pour questions
- [ ] Consulter: `troubleshooting` section dans README_BENCHMARK.md

---

## Validation finale

### Avant de considérer "terminé"
- [ ] Tous les 30 tests complétés
- [ ] Pas d'erreurs majeures
- [ ] JSON report généré et valide
- [ ] Rapport texte lisible
- [ ] Graphiques affichés correctement

### Avant de déployer
- [ ] Fine-tuning efficace (>10% ou critères définis)
- [ ] Pas de régression sur tests existants
- [ ] Recommendations revues
- [ ] Résultats documentés

### Avant d'archiver
- [ ] JSON report sauvegardé
- [ ] Rapport texte sauvegardé
- [ ] Graphiques sauvegardés
- [ ] Métadonnées conservées
- [ ] Configuration notée

---

## Timing attendu

| Étape | Durée | Cumul |
|-------|-------|-------|
| Vérification | 1 min | 1 min |
| Test rapide | 5 min | 6 min |
| Benchmark | 3-5 min | 9-11 min |
| Analyse | 1 min | 10-12 min |
| **Total** | **~10 min** | **10-12 min** |

---

## Commandes de référence

```bash
# Aller au répertoire
cd F:\BUREAU\turbo

# Vérifier configuration
uv run python finetuning/check_setup.py

# Test rapide
uv run python finetuning/quick_test.py

# Benchmark
uv run python finetuning/benchmark.py

# Analyser
uv run python finetuning/analyze_results.py

# Voir rapport
type finetuning\benchmark_report.txt

# Voir JSON
type finetuning\benchmark_results.json

# Voir graphiques
# (Ouvrir avec image viewer)
finetuning\benchmark_charts.png
```

---

## Status du projet

- [ ] Tous les fichiers créés
- [ ] Documentation complète
- [ ] Scripts testés
- [ ] Configuration validée
- [ ] Prêt pour benchmark ✓

---

**Date**: 2026-02-18
**Version**: 1.0
**Status**: Production-ready
