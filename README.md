<<<<<<< HEAD
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
=======
# 🤖 JARVIS Turmont — Le Cluster Résilient (Ubuntu 22.04)

Architecture consolidée et optimisée pour une autonomie totale sur cluster multi-GPU.

## 🏗️ Structure du Cluster
- **Nœuds** : M1 (Master Local), M2 (Réseau), OL1 (Ollama Local).
- **GPU** : 6 cartes NVIDIA (RTX 3080, RTX 2060, 4x GTX 1660S).
- **VRAM** : Monitoring temps réel intégré au prompt Zsh.
- **ZRAM** : 12GB configurés pour l'inférence lourde.

## 🎙️ Intelligence & Voix
- **Voice Pipeline V3** : Porcupine (Wake word) → Whisper-Flow (STT) → brain_connector (Ollama) → Piper (TTS).
- **MCP Server** : 81 compétences opérationnelles dans `jarvis.db`.
- **Navigation Web** : Agent Comet migré vers Firefox Linux.

## 🛡️ Systèmes de Résilience
- **Auto-Heal Engine** : Surveillance des ports 8901, 9742, 18800, 11434.
- **Recovery Engine** : Diagnostic et auto-fix des erreurs systemd (Missing modules, NVIDIA failures).
- **Watchdog Dashboard** : Session TMUX `JARVIS_DASH` auto-relancée en cas de crash.

## 🚀 Commandes Rapides
- `jarvis-ctl status` : État des 14 services.
- `jarvis-ctl health` : Check des endpoints.
- `jarvis-dash` : Dashboard TMUX complet.
- `gloop "..."` : Lancer une tâche en mode Résilience Ultime.

---
*Architecture finalisée le 12 Mars 2026. Mode Unstoppable Activé.*
>>>>>>> 634aefd (feat: JARVIS Linux Full Port — apprentissage conversationnel, 443 dominos, 11 modules Linux)
