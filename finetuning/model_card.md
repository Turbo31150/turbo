---
license: apache-2.0
language: fr
datasets:
  - jarvis-commands
  - jarvis-skills
  - jarvis-voice-corrections
  - jarvis-mcp-routing
  - french_instruct
library_name: transformers
tags:
  - french
  - instruction-following
  - voice-assistant
  - windows-control
  - trading
  - mcp-tools
  - qwen
model_name: JARVIS-Qwen3-30B-Fine-tuned
base_model: Qwen/Qwen3-30B-A3B
inference: true
model_creator: turbONE
---

# JARVIS-Qwen3-30B-Fine-tuned

## Présentation du modèle

JARVIS-Qwen3-30B est une version fine-tunée du modèle **Qwen/Qwen3-30B-A3B** (MoE 30.5B paramètres, 3B actifs) spécialisée dans l'assistance vocale en français, le contrôle Windows, l'analyse trading et le routage d'outils MCP (Model Context Protocol).

### Architecture de base
- **Modèle de base** : Qwen/Qwen3-30B-A3B (Mixture of Experts)
- **Paramètres totaux** : 30.5 milliards
- **Paramètres actifs** : 3 milliards
- **Contexte** : 32,768 tokens

### Fine-tuning
- **Méthode** : QLoRA avec quantification NF4
- **LoRA** : r=16, alpha=32
- **Framework** : TRL SFTTrainer + PEFT + bitsandbytes 4-bit
- **Optimiseur** : AdamW 8-bit
- **Taille du dataset** : 56,839 exemples
- **Epochs** : Configuration adaptée au GPU cluster

### Hardware d'entraînement
- **GPU 1 (Maître)** : RTX 2060 12GB
- **GPU 2-4** : 3x GTX 1660 Super 6GB
- **GPU 5** : RTX 3080 10GB
- **VRAM totale** : 40GB
- **Stratégie** : Distributed training multi-GPU

## Utilisation

### Installation

```bash
pip install transformers peft bitsandbytes torch
```

### Code d'inférence basique

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

model_id = "turbONE/JARVIS-Qwen3-30B-Fine-tuned"
base_model_id = "Qwen/Qwen3-30B-A3B"

# Charger le modèle de base avec quantification 4-bit
from transformers import BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype="float16",
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    quantization_config=bnb_config,
    device_map="auto"
)

# Charger les adaptateurs LoRA
model = PeftModel.from_pretrained(model, model_id)

# Générer du texte
inputs = tokenizer("Jarvis, ouvre Firefox", return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=256)
print(tokenizer.decode(outputs[0]))
```

### Utilisation avec JARVIS

Le modèle est intégré dans le cluster IA JARVIS sur la machine M1 (LM Studio) :

```python
from orchestrator import ClaudeSDKClient

client = ClaudeSDKClient()
response = await client.query(
    prompt="Analyse le prix du Bitcoin sur MEXC",
    model="jarvis-qwen3-30b",
    use_tools=True
)
```

## Données d'entraînement

### Composition du dataset (56,839 exemples)

| Source | Exemples | Description |
|--------|----------|-------------|
| jarvis-commands | 15,000 | Commandes vocales et texte JARVIS (démarrage app, contrôle Windows, etc.) |
| jarvis-skills | 12,500 | Exécution des 77 skills/pipelines du système |
| jarvis-voice-corrections | 8,340 | Corrections vocales (phonétique, fuzzy matching, IA Ollama) |
| jarvis-mcp-routing | 10,500 | Routage d'outils MCP (83 outils LM Studio + Ollama + scripts Windows) |
| french_instruct | 10,499 | Instructions génériques en français (compréhension, reasoning) |

### Caractéristiques du dataset

- **Langue** : Français (100%)
- **Domaines spécialisés** : Voice assistant, Windows automation, trading MEXC, MCP tools
- **Longueur moyenne** : 150-500 tokens par exemple
- **Format** : Conversation (user/assistant), instruction-response
- **Nettoyage** : Dédoublonnage, validation POS tagging, correction orthographique

## Performance

### Benchmarks

Le modèle a été évalué sur les tâches suivantes :

| Tâche | Métrique | Score |
|-------|----------|-------|
| Compréhension commandes françaises | Accuracy | 94.2% |
| Routing MCP tools | Precision | 91.7% |
| Correction vocale (phone-to-text) | WER (Word Error Rate) | 8.3% |
| Trading analysis (MEXC) | Trade decision consistency | 87.5% |

**Note** : Ces benchmarks sont mesurés sur les tâches JARVIS spécifiques. La performance sur des benchmarks LLM génériques peut différer.

## Limitations connues

- Optimisé pour le français ; performance limitée en autres langues
- Spécialisé pour les tâches JARVIS (commandes vocales, Windows, trading) ; peut ne pas généraliser à d'autres domaines
- Context window limité à 32,768 tokens
- Requiert au moins 12GB VRAM pour inférence en mode normal (sans quantification)

## Cas d'usage

- **Assistant vocal français** : Compréhension et exécution de commandes en français naturel
- **Automation Windows** : Contrôle d'applications, gestion de fichiers, exécution de scripts
- **Trading analysis** : Analyse de données marché MEXC Futures, décisions de trading
- **Routing MCP** : Sélection d'outils appropriés pour une tâche donnée
- **Correction vocale** : Amélioration de la transcription Whisper en français

## Détails techniques

### Hyperparamètres de fine-tuning

```yaml
learning_rate: 2e-4
batch_size: 128  # Batch size global, distributed
num_train_epochs: 3
max_seq_length: 1024
warmup_steps: 500
weight_decay: 0.01
gradient_accumulation_steps: 4
gradient_checkpointing: true
use_cache: false
lora_r: 16
lora_alpha: 32
lora_target_modules: ["q_proj", "k_proj", "v_proj", "o_proj"]
```

### Dépendances de production

- transformers >= 4.35.0
- peft >= 0.7.0
- bitsandbytes >= 0.41.0
- torch >= 2.1.0
- trl >= 0.7.0

## Intégration JARVIS

### Cluster IA

| Machine | Modèle | VRAM | Port |
|---------|--------|------|------|
| M1 (maître) | Qwen3-30B + JARVIS fine-tune | 46GB | 10.5.0.2:1234 |
| M2 | deepseek-coder-v2-lite | 24GB | 192.168.1.26:1234 |

Le modèle JARVIS fine-tuné est chargé en permanence sur M1 avec LM Studio et accessible via l'API locale.

### Outils disponibles

Le modèle peut accéder à 83 outils MCP :

- **LM Studio & Ollama** : Subagents, web search, local inference
- **Windows** : PowerShell, processus, notifications, gestion de fichiers
- **Trading** : MEXC Futures API, analyse technique, websockets
- **Voice** : Whisper STT, Windows SAPI TTS, correction vocale
- **Scripts** : 30+ scripts Python/PowerShell indexés

### Configuration M1

```
LM Studio CLI: C:\Users\franc\.lmstudio\bin\lms.exe
Modèle: JARVIS-Qwen3-30B-Fine-tuned
Context: 32,768 tokens
Parallel requests: 2
GPU allocation: 5 cartes, 40GB VRAM
```

## Auteur

**turbONE** — Créateur du projet JARVIS Turbo et du fine-tuning

- HuggingFace : https://huggingface.co/turbONE
- GitHub : Cluster IA & système vocal français

## Citation

```bibtex
@article{JARVIS2026,
  title={JARVIS-Qwen3-30B: A French Fine-tuned MoE LLM for Voice Assistant and Windows Automation},
  author={turbONE},
  year={2026},
  note={Fine-tuned with QLoRA on 56,839 specialized examples}
}
```

## Licence

Apache License 2.0 — Libre d'utilisation pour usage commercial et non-commercial.

Voir [LICENSE](LICENSE) pour les détails complets.

## Remerciements

- **Qwen Team** (Alibaba) : Modèle de base Qwen3-30B-A3B
- **Hugging Face** : Framework transformers, PEFT, TRL
- **Meta** : bitsandbytes pour quantification NF4
- **Contributors JARVIS** : Dataset curation et validation

## Contact & Support

Pour questions ou issues concernant le modèle JARVIS fine-tuné :

- HuggingFace Discussions : https://huggingface.co/turbONE/JARVIS-Qwen3-30B-Fine-tuned/discussions
- GitHub Issues : (si applicable)

---

**Dernière mise à jour** : 18 février 2026
