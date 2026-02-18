# Benchmark Comparatif - Qwen3-30B vs Fine-tuné

Script Python pour comparer les performances du modèle Qwen3-30B de base vs le modèle fine-tuné avec LoRA sur des prompts JARVIS.

## Structure

### 30 Prompts de Test (3 catégories)

#### 1. Commandes vocales JARVIS (10 tests)
- `ouvre chrome` → devrait mentionner navigateur/chrome
- `status cluster` → devrait mentionner GPU/VRAM/cluster
- `scan MEXC` → devrait mentionner trading/positions/marché
- `lance jarvis voice` → devrait mentionner voice/audio/écoute
- `check GPU` → devrait mentionner GPU/VRAM/mémoire
- `active ollama` → devrait mentionner ollama/serveur/modèle
- `affiche temps` → devrait mentionner heure/time/date
- `redemarrage cluster` → devrait mentionner restart/cluster
- `close pipeline` → devrait mentionner close/pipeline/stop
- `listez les positions` → devrait mentionner positions/trading/portefeuille

#### 2. Corrections vocales (10 tests)
Tests de correction d'erreurs vocales :
- `ouvres crom` → doit corriger en `ouvre chrome`
- `statu cluteur` → doit corriger en `status cluster`
- `skan mexik` → doit corriger en `scan mexc`
- etc.

Le modèle fine-tuné devrait mieux corriger ces erreurs phonétiques.

#### 3. Tool Routing (10 tests)
Prompts qui nécessitent un routage vers des outils spécifiques :
- `monte le son` → devrait router vers `volume_up`
- `baisse le volume` → devrait router vers `volume_down`
- `redemarrer la machine` → devrait router vers système
- etc.

## Métriques de Comparaison

### 1. Similarité Cosinus
Mesure la similarité entre les embeddings des réponses du modèle de base et du modèle fine-tuné.
- **Score**: 0.0 à 1.0
- **Interprétation**: Plus élevé = réponses plus similaires (peut indiquer peu d'amélioration)

### 2. Correspondance Mots-clés
Compte les mots-clés attendus présents dans la réponse.
- **Format**: N/total (ex: 3/4)
- **Amélioration**: Les scores devraient être plus élevés avec le modèle fine-tuné

### 3. Pertinence JARVIS
Score de 0.0 à 1.0 mesurant si la réponse mentionne des outils/commandes JARVIS valides.
- **Calcul**: % de termes JARVIS trouvés dans la réponse
- **Objectif**: Le fine-tuning devrait améliorer ce score

## Installation des dépendances

```bash
cd F:\BUREAU\turbo
uv pip install transformers peft bitsandbytes scikit-learn
```

## Utilisation

### Lancer le benchmark

```bash
cd F:\BUREAU\turbo
uv run python finetuning/benchmark.py
```

### Structure du répertoire attendue

```
F:\BUREAU\turbo\finetuning\
├── benchmark.py                 # Ce script
├── README_BENCHMARK.md         # Cette documentation
├── output/                      # Dossier contenant les adaptateurs LoRA
│   └── checkpoint-XXX/
│       └── final/
│           ├── adapter_config.json
│           ├── adapter_model.bin
│           └── ...
└── benchmark_results.json       # Résultats générés
```

## Sortie

Le script génère :

1. **Console output** : Progression en temps réel avec scores pour chaque test
2. **JSON report** : `benchmark_results.json` avec :
   - Métadonnées (modèle, adaptateur, device, timestamp)
   - Statistiques globales
   - Statistiques par catégorie
   - Détails complets de chaque test

### Structure JSON

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
    "commandes_vocales": { ... },
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
      "jarvis_relevance_finetuned": 0.687
    },
    ...
  ]
}
```

## Configuration

### Modèle de base
- **ID HuggingFace**: `Qwen/Qwen3-30B-A3B`
- **Quantization**: 4-bit (avec double quant)
- **Device map**: `auto` (multi-GPU supporté)

### Adaptateur LoRA
- **Chemin automatique**: Détecte le dernier dossier `output/.../final`
- **Si absent**: Le script fonctionne avec le modèle de base seul (sans comparaison fine-tuning)

### Paramètres de génération
- **Max new tokens**: 128
- **Temperature**: 0.7
- **Top-p**: 0.9
- **Sampling**: Activé

## Notes d'optimisation

1. **PyTorch 2.10+**: Utilise `total_memory` (pas `total_mem`)
2. **Multi-GPU**: Device map `auto` distribue automatiquement
3. **Mémoire**: 4-bit quantization + double quant pour ~30GB VRAM sur modèle 30B
4. **Embeddings**: Basés sur les hidden states du dernier layer

## Interprétation des résultats

### Bon fine-tuning
- Similarité cosinus > 0.7 (réponses cohérentes)
- Correspondance mots-clés FT > base (meilleure précision)
- Pertinence JARVIS FT > base (meilleur routage)

### Exemple d'interprétation

```
Prompt: "monte le son"
Base:     keyword_match=1, relevance=0.3
Fine-tuned: keyword_match=3, relevance=0.8
↓
Fine-tuning améliore le routage vers les bons outils
```

## Troubleshooting

| Problème | Solution |
|----------|----------|
| CUDA out of memory | Réduire batch size ou augmenter quantization |
| Adaptateur LoRA non trouvé | Vérifier le chemin `output/.../final/adapter_config.json` |
| Import error (transformers, peft) | `uv pip install transformers peft bitsandbytes` |
| Lenteur | Réduire `max_new_tokens` ou utiliser CPU pour test rapide |

## Performance attendue

- **Chargement modèles**: ~2-3 min (premier chargement)
- **Par test**: ~3-5s (génération + métriques)
- **Total 30 tests**: ~90-150s (~2-3 min)
- **Rapport**: ~5-10s

## Fichiers générés

```
F:\BUREAU\turbo\finetuning\
├── benchmark_results.json          # Rapport complet JSON
├── benchmark_results_summary.txt   # (Optionnel) Résumé texte
└── benchmark_results_charts.html   # (Optionnel) Graphiques interactifs
```

---

**Date de création**: 2026-02-18
**Auteur**: Claude Code / JARVIS Turbo
**Version**: 1.0
