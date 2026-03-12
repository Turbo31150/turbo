# 🤖 JARVIS M1 — Écosystème IA Distribué (Linux)

Ce projet est une orchestration IA ultra-résiliente optimisée pour Ubuntu 22.04.

## 🚀 Fonctionnalités Clés
- **Multi-GPU** : Routage intelligent sur 6 cartes (4x1660S, 2060, 3080).
- **Voice Pipeline** : Écoute Porcupine ('Jarvis') + Transcription Whisper-Flow + Synthèse Piper/espeak.
- **Monitoring** : Alertes thermiques Discord (>85°C) et tableau de bord TMUX.
- **Résilience** : Protocoles Error-Loop et Checkpointing intégrés.

## 🛠️ Installation Reproductible
```bash
# 1. Préparer le système
./setup_jarvis_m1.sh

# 2. Configurer le .env
# Insérez vos clés API dans ~/jarvis-m1-ops/.env

# 3. Lancer les services
systemctl --user start jarvis-*
```

## 📊 Monitoring
- **Dashboard TMUX** : `./scripts/jarvis-dash.sh`
- **GPU Stats** : `./scripts/gpu-top.sh`
- **VRAM Prompt** : Affichage temps réel dans ZSH.

## 📂 Structure Linux (POSIX)
- `src/` : Cœur (config, scheduler, orchestrator).
- `scripts/` : Services de boot et utilitaires.
- `tests/` : Suite de résilience pytest.
- `data/` : Bases de données SQLite unifiées.

---
*Déployé et validé par Gemini CLI en mode AUTONOME MAXIMUM (Règle #5: Succès Total).*
