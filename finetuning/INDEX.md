# Index - Suite Benchmark JARVIS Turbo

## Fichiers créés

### Scripts principaux

#### 1. `benchmark.py` (1,300+ lignes)
**Script de benchmark comparatif - Le cœur du projet**

- **Classe principale**: `JARVISBenchmark`
- **Contient**:
  - 30 prompts de test (3 catégories × 10)
  - Définition des outils JARVIS
  - Chargement modèles (base + LoRA)
  - Génération réponses
  - Calcul métriques (cosine, keywords, relevance)
  - Génération rapport JSON

- **Utilisation**:
  ```bash
  uv run python benchmark.py
  ```

- **Sortie**: `benchmark_results.json`

#### 2. `analyze_results.py` (300+ lignes)
**Analyseur de résultats - Visualisation et rapports**

- **Classe principale**: `BenchmarkAnalyzer`
- **Fonctionnalités**:
  - Chargement JSON résultats
  - Génération rapport texte détaillé
  - Création graphiques (4 graphiques)
  - Calcul d'améliorations
  - Recommandations

- **Utilisation**:
  ```bash
  uv run python analyze_results.py
  ```

- **Sorties**:
  - `benchmark_report.txt` - Rapport texte
  - `benchmark_charts.png` - Graphiques

#### 3. `check_setup.py` (150+ lignes)
**Vérification de configuration**

- **Vérifie**:
  - Version Python
  - PyTorch et CUDA
  - Dépendances (transformers, peft, etc.)
  - Structure répertoires
  - Adaptateurs LoRA
  - Configuration générale

- **Utilisation**:
  ```bash
  uv run python check_setup.py
  ```

- **Résultat**: ✓ CONFIGURATION OK (ou liste des problèmes)

#### 4. `quick_test.py` (100+ lignes)
**Test rapide - Vérification rapide**

- **Fait**:
  - Charge tokenizer + modèle
  - Génère 1 test
  - Valide le setup

- **Utilisation**:
  ```bash
  uv run python quick_test.py
  ```

- **Durée**: ~2-3 min
- **But**: Validation avant benchmark complet

### Fichiers de configuration

#### 5. `benchmark_config.json`
Configuration complète du benchmark

```json
{
  "model": { ... },           // Modèle (quantization, device_map)
  "generation": { ... },      // Paramètres génération
  "benchmark": { ... },       // Nombre prompts, catégories
  "metrics": { ... },         // Métriques à calculer
  "output": { ... },          // Chemins de sortie
  "logging": { ... }          // Verbosité
}
```

### Lancers

#### 6. `run_benchmark.bat`
Launcher Windows - Double-clic pour lancer

```batch
cd F:\BUREAU\turbo
uv run python finetuning\benchmark.py
```

### Documentation

#### 7. `README_BENCHMARK.md` (400+ lignes)
Documentation technique détaillée

- Structure des 30 prompts
- Explications des 3 catégories
- Description des 3 métriques
- Installation des dépendances
- Structure JSON de sortie
- Interprétation des résultats
- Troubleshooting

#### 8. `INSTALLATION.md` (400+ lignes)
Guide d'installation et utilisation complet

- Structure créée
- 5 étapes d'installation
- Configuration du modèle fine-tuné
- Interprétation des résultats
- Troubleshooting
- Performance observée
- Optimisations avancées
- Prochaines étapes

#### 9. `INDEX.md` (ce fichier)
Index et guide de navigation

---

## Workflow recommandé

### 1️⃣ Vérification initiale (5 min)
```bash
cd F:\BUREAU\turbo
uv run python finetuning/check_setup.py
```
**Résultat attendu**: ✓ CONFIGURATION OK

### 2️⃣ Test rapide (5 min)
```bash
uv run python finetuning/quick_test.py
```
**Résultat attendu**: ✓ QUICK TEST RÉUSSI

### 3️⃣ Benchmark complet (3-5 min)
```bash
uv run python finetuning/benchmark.py
```
**Résultat attendu**: JSON report généré

### 4️⃣ Analyse des résultats (1 min)
```bash
uv run python finetuning/analyze_results.py
```
**Résultat attendu**: Rapport texte + graphiques

### 5️⃣ Interprétation
- Ouvrir `benchmark_report.txt`
- Consulter `benchmark_charts.png`
- Comparer avec seuils attendus

---

## Les 30 prompts de test

### Catégorie 1: Commandes vocales JARVIS (10)
Prompts simples et clairs pour tester la compréhension de base

| # | Prompt | Mots-clés attendus |
|----|--------|-------------------|
| 1 | ouvre chrome | chrome, navigateur |
| 2 | status cluster | cluster, gpu, vram |
| 3 | scan MEXC | mexc, scan, trading |
| 4 | lance jarvis voice | jarvis, voice, micro |
| 5 | check GPU | gpu, vram, mémoire |
| 6 | active ollama | ollama, server, modèle |
| 7 | affiche temps | heure, time, date |
| 8 | redemarrage cluster | restart, cluster |
| 9 | close pipeline | close, pipeline, stop |
| 10 | listez les positions | positions, trading |

### Catégorie 2: Corrections vocales (10)
Prompts avec erreurs phonétiques - teste la correction IA

| # | Prompt brut | Correctif attendu | Mots-clés |
|----|------------|-------------------|-----------|
| 11 | ouvres crom | ouvre chrome | chrome |
| 12 | statu cluteur | status cluster | status, cluster |
| 13 | skan mexik | scan mexc | scan, mexc |
| 14 | lance jarvi voix | lance jarvis voice | jarvis, voice |
| 15 | chek geeypee | check gpu | gpu |
| 16 | activ olamo | active ollama | ollama |
| 17 | affiche tamps | affiche temps | time |
| 18 | redemaraje cluter | redemarrage cluster | restart |
| 19 | clos pipelan | close pipeline | pipeline |
| 20 | listé les pozision | listez positions | positions |

### Catégorie 3: Tool Routing (10)
Prompts nécessitant un routage vers les bons outils

| # | Prompt | Tool attendu | Mots-clés |
|----|--------|-------------|-----------|
| 21 | monte le son | volume_up | volume |
| 22 | baisse le volume | volume_down | volume |
| 23 | redemarrer la machine | system_restart | restart |
| 24 | affiche les fichiers | file_list | fichiers |
| 25 | execute le script trading | trading_run | trading |
| 26 | active le cache micro | audio_cache | cache, micro |
| 27 | affiche la température GPU | gpu_monitor | temperature |
| 28 | cherche dans les logs | log_search | search, logs |
| 29 | envoie un message | notification | send |
| 30 | charge le modele qwen | model_load | load, qwen |

---

## Les 3 métriques de benchmark

### 1. Similarité Cosinus
```
Score: 0.0 à 1.0
Formula: cosine_similarity(embedding(resp_base), embedding(resp_ft))
```
- Mesure la similitude entre réponses
- Élevée: Peut signifier peu de changement
- Basse: Réponses très différentes

### 2. Correspondance Mots-clés
```
Score: N/total (ex: 3/4)
Calcul: Nombre de mots-clés présents dans la réponse
```
- Directement interprétable
- Amélioration: FT > Base = bon fine-tuning
- Plus haut = mieux

### 3. Pertinence JARVIS
```
Score: 0.0 à 1.0
Calcul: % de termes JARVIS trouvés dans réponse
```
- La métrique la plus importante
- Mesure si la réponse est pertinente JARVIS
- Amélioration FT > Base = succès

---

## Structure de sortie JSON

### `benchmark_results.json`

```json
{
  "metadata": {
    "base_model": "Qwen/Qwen3-30B-A3B",
    "lora_adapter": "F:/BUREAU/turbo/finetuning/output/.../final",
    "device": "cuda",
    "timestamp": "2026-02-18T10:30:45.123456"
  },
  "statistics": {
    "total_tests": 30,
    "avg_cosine_similarity": 0.845,
    "avg_keyword_match_base": 2.1,
    "avg_keyword_match_finetuned": 2.8,
    "avg_relevance_base": 0.562,
    "avg_relevance_finetuned": 0.723
  },
  "by_category": {
    "commandes_vocales": {
      "count": 10,
      "avg_cosine": 0.812,
      "avg_keyword_base": 2.3,
      "avg_keyword_ft": 3.1,
      "avg_relevance_base": 0.601,
      "avg_relevance_ft": 0.758
    },
    "corrections_vocales": { ... },
    "tool_routing": { ... }
  },
  "results": [
    {
      "prompt_id": "test_01",
      "category": "commandes_vocales",
      "prompt": "ouvre chrome",
      "keywords_expected": ["chrome", "navigateur", "open", "lancer"],
      "base_model_response": "...",
      "finetuned_response": "...",
      "cosine_similarity_score": 0.823,
      "keyword_match_base": 2,
      "keyword_match_finetuned": 3,
      "jarvis_relevance_base": 0.421,
      "jarvis_relevance_finetuned": 0.687,
      "timestamp": "2026-02-18T10:30:45.123456"
    },
    ...
  ]
}
```

---

## Chemins et ressources

### Répertoires clés
```
F:\BUREAU\turbo\finetuning\
├── Scripts: .py files
├── Config: .json files
├── Docs: .md files
├── Launcher: .bat files
├── output/                 ← Adaptateurs LoRA (à créer)
└── benchmark_results.json  ← Généré
```

### Modèle de base
- **ID**: `Qwen/Qwen3-30B-A3B`
- **Téléchargement**: HuggingFace Transformers (auto)
- **Cache**: `~/.cache/huggingface/hub/`

### Adaptateurs LoRA
- **Chemin**: `F:/BUREAU/turbo/finetuning/output/*/final/`
- **Détection**: Automatique (dernier dossier)
- **Requis**: `adapter_config.json` + `adapter_model.bin`

---

## Quickstart (copier-coller)

```bash
# Aller au répertoire
cd F:\BUREAU\turbo

# Vérifier configuration
uv run python finetuning/check_setup.py

# Test rapide
uv run python finetuning/quick_test.py

# Lancer benchmark
uv run python finetuning/benchmark.py

# Analyser résultats
uv run python finetuning/analyze_results.py

# Consulter rapports
type finetuning\benchmark_report.txt
# Ouvrir finetuning\benchmark_charts.png
```

---

## Support et documentation

| Besoin | Fichier |
|--------|---------|
| Installation | `INSTALLATION.md` |
| Technique | `README_BENCHMARK.md` |
| Rapide | `quick_test.py` (exécuter) |
| Debug | `check_setup.py` (exécuter) |
| Navigation | `INDEX.md` (ce fichier) |

---

**Version**: 1.0
**Date**: 2026-02-18
**Auteur**: Claude Code / JARVIS Turbo
**Status**: Production-ready ✓
