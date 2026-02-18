# Installation et Utilisation - Benchmark JARVIS

Guide complet pour mettre en place et utiliser le benchmark comparatif Qwen3-30B.

## Structure créée

```
F:\BUREAU\turbo\finetuning\
├── benchmark.py                 # Script principal (1,300+ lignes)
├── analyze_results.py           # Analyseur de résultats
├── check_setup.py              # Vérification configuration
├── quick_test.py               # Test rapide (3 prompts)
├── run_benchmark.bat           # Launcher Windows
├── benchmark_config.json       # Configuration
├── README_BENCHMARK.md         # Documentation détaillée
├── INSTALLATION.md             # Ce fichier
├── output/                     # (À créer) Adaptateurs LoRA
│   └── checkpoint-XXX/
│       └── final/
└── results/                    # (Généré) Résultats benchmarks
    ├── benchmark_results.json
    ├── benchmark_report.txt
    └── benchmark_charts.png
```

## Étape 1 : Vérifier les dépendances

```bash
cd F:\BUREAU\turbo

# Voir la configuration
uv run python finetuning/check_setup.py
```

**Résultat attendu**: ✓ CONFIGURATION OK

Si certaines dépendances manquent:
```bash
uv pip install transformers peft bitsandbytes scikit-learn matplotlib
```

## Étape 2 : Test rapide

```bash
# Lancer un test rapide (3 prompts, ~5 min)
uv run python finetuning/quick_test.py
```

**Résultat attendu**:
- ✓ GPU détecté
- ✓ Modèle chargé
- ✓ Génération fonctionnelle

## Étape 3 : Adapter la configuration (optionnel)

Éditer `benchmark_config.json` si besoin:
- `max_new_tokens`: Réduire pour plus rapide, augmenter pour plus détaillé
- `temperature`: Plus bas (0.0-0.3) pour déterministe, plus haut (0.8-1.0) pour créatif
- `lora_adapter_path`: Chemin personnalisé si nécessaire

## Étape 4 : Lancer le benchmark complet

### Option A : Via PowerShell (recommandé)
```bash
cd F:\BUREAU\turbo
uv run python finetuning/benchmark.py
```

### Option B : Via launcher Windows
Double-cliquez sur:
```
F:\BUREAU\turbo\finetuning\run_benchmark.bat
```

### Résultat attendu
- Durée: ~3-5 minutes
- Génération: 30 tests × 2 modèles
- Métriques: Similarité cosinus, mots-clés, pertinence JARVIS

Sortie:
```
[DÉMARRAGE] Benchmark sur 30 prompts
===================================================================

### COMMANDES_VOCALES (10 tests)
---
[Test 1/30] commandes_vocales - 'ouvre chrome'
  [1/4] Génération réponse modèle de base... (2.31s)
  [2/4] Génération réponse modèle fine-tuné... (1.98s)
  [3/4] Calcul des métriques... OK
  [4/4] Résultats:
      Cosine similarity: 0.823
      Mots-clés (base): 2/4
      Mots-clés (FT):   3/4
      Relevance JARVIS (base): 0.421
      Relevance JARVIS (FT):   0.687
...
```

## Étape 5 : Analyser les résultats

```bash
# Générer rapport texte + graphiques
uv run python finetuning/analyze_results.py
```

**Fichiers générés:**
- `benchmark_report.txt` - Rapport détaillé
- `benchmark_charts.png` - Graphiques comparatifs

## Configuration du modèle fine-tuné

### Localiser les adaptateurs LoRA

Le script détecte automatiquement le dernier adaptateur LoRA créé:

```
F:\BUREAU\turbo\finetuning\output\
├── checkpoint-100/
│   └── final/
│       ├── adapter_config.json     ← Détecté automatiquement
│       ├── adapter_model.bin
│       └── ...
├── checkpoint-200/
│   └── final/
└── checkpoint-300/          ← Le plus récent sera utilisé
    └── final/
```

Pour forcer un adaptateur spécifique, éditer:
```python
# Dans benchmark.py, ligne ~80
self.lora_adapter_path = Path("F:/BUREAU/turbo/finetuning/output/checkpoint-XXX/final")
```

## Interprétation des résultats

### Metrics principales

1. **Cosine Similarity** (0.0-1.0)
   - Score de similarité entre réponses base et fine-tuné
   - Élevé (>0.8): Réponses cohérentes mais peu de changement
   - Moyen (0.5-0.8): Adaptation visible
   - Bas (<0.5): Réponses très différentes

2. **Keyword Matching** (N/total)
   - Nombre de mots-clés trouvés dans la réponse
   - Comparaison: Base vs Fine-tuné
   - Amélioration: FT > Base = bon fine-tuning

3. **JARVIS Relevance** (0.0-1.0)
   - Score de pertinence JARVIS
   - Mesure si la réponse mentionne les bons outils
   - Amélioration FT: Indicateur clé du succès

### Exemple d'interprétation

```
Prompt: "monte le son"

Base Model:
  - Keyword match: 1/4 ("volume")
  - Relevance: 0.25 (peu pertinent)
  - Réponse: "volume audio..."

Fine-tuned:
  - Keyword match: 3/4 ("volume", "audio", "son")
  - Relevance: 0.85 (très pertinent)
  - Réponse: "volume_up_tool, audio system, son augmenté..."

Conclusion: ✓ Fine-tuning efficace pour cette catégorie
```

## Troubleshooting

### Problème: CUDA out of memory

**Solution:**
```python
# Dans benchmark.py, réduire:
"max_new_tokens": 64,  # Au lieu de 128
"temperature": 0.5,    # Plus bas = moins variable
```

### Problème: Importation échoue

```bash
# Réinstaller les dépendances
uv pip install --force-reinstall transformers peft bitsandbytes scikit-learn
```

### Problème: Adaptateur LoRA non trouvé

Le script affichera:
```
[AVERTISSEMENT] Aucun adaptateur LoRA trouvé dans F:\BUREAU\turbo\finetuning\output
[OK] Benchmark comparera le modèle de base uniquement
```

**Solution:**
1. Placer les adaptateurs dans: `F:\BUREAU\turbo\finetuning\output/final/`
2. Vérifier `adapter_config.json` existe

### Problème: Benchmark très lent

**Causes possibles:**
- CPU uniquement (GPU non détecté)
- Autres processus utilisent GPU
- `max_new_tokens` trop élevé

**Solutions:**
1. Vérifier GPU: `uv run python -c "import torch; print(torch.cuda.is_available())"`
2. Réduire `max_new_tokens`: 128 → 64
3. Fermer applications gourmandes (Chrome, VS Code, etc.)

## Performance observée

### Sur GPU RTX 4090 (24GB)
- Chargement modèles: 2-3 min
- Par test: 3-5s (base) + 3-5s (FT) + 1s (métriques)
- 30 tests: ~2-3 min
- Total: ~5-6 min

### Sur GPU RTX 3090 (24GB)
- Chargement modèles: 3-4 min
- Par test: 4-6s
- 30 tests: ~3-4 min
- Total: ~6-8 min

### Sur CPU Intel i9
- Chargement modèles: 10+ min
- Par test: 30-60s
- 30 tests: ~30-60 min
- Total: ~45+ min (déconseillé)

## Optimisations avancées

### Paralléliser plusieurs GPU

```python
# benchmark.py supporte déjà device_map="auto"
# Cela distribute automatiquement sur tous les GPU disponibles

# Vérifier répartition:
# GPU 0: Layers 0-20
# GPU 1: Layers 21-40
# etc.
```

### Réduire la mémoire

```python
# Utiliser 8-bit au lieu de 4-bit:
"load_in_8bit": True,
"load_in_4bit": False,

# Gain: -5GB VRAM
# Perte: Peu de différence qualitative
```

### Augmenter la vitesse

```json
{
  "max_new_tokens": 64,
  "temperature": 0.5,
  "top_p": 0.8
}
```

## Fichiers de sortie

### benchmark_results.json
Rapport complet avec:
- Métadonnées
- Statistiques globales + par catégorie
- Détails de chaque test

```json
{
  "metadata": { ... },
  "statistics": {
    "total_tests": 30,
    "avg_cosine_similarity": 0.823,
    "avg_relevance_base": 0.421,
    "avg_relevance_finetuned": 0.687,
    ...
  },
  "by_category": { ... },
  "results": [
    {
      "prompt_id": "test_01",
      "prompt": "ouvre chrome",
      "cosine_similarity_score": 0.823,
      "keyword_match_base": 2,
      "keyword_match_finetuned": 3,
      ...
    },
    ...
  ]
}
```

### benchmark_report.txt
Rapport lisible avec:
- Résumé exécutif
- Top 5 améliorations
- Top 5 faiblesses
- Recommandations

### benchmark_charts.png
Graphiques:
1. Pertinence JARVIS par catégorie
2. Mots-clés trouvés
3. Distribution des scores
4. Résumé statistique

## Prochaines étapes

1. **Valider le fine-tuning**
   - Si amélioration > 10%: Fine-tuning efficace ✓
   - Si amélioration < 5%: Revoir stratégie

2. **Intégrer au cluster**
   - Copier adaptateur LoRA à `F:\BUREAU\turbo\cluster\models\qwen-lora\`
   - Mettre à jour `cluster_startup.py`
   - Relancer cluster

3. **Itérer**
   - Collecter plus de données JARVIS
   - Fine-tuner à nouveau
   - Re-benchmarker

---

**Support**: Consulter `README_BENCHMARK.md` pour détails techniques
**Dernière mise à jour**: 2026-02-18
