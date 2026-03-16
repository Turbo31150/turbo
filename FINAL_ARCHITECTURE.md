# JARVIS Turmont — Architecture Linux Finale (v12.6.5)

## 🏗️ Structure du Cluster
- **Master (M1)** : Orchestrateur central sur Ubuntu 22.04 LTS.
- **Inférence IA** : 
    - **Ollama** : Local (127.0.0.1:11434) avec `deepseek-r1:7b` et `qwen2.5:1.5b`.
    - **Gemini Proxy** : Pont Claude SDK vers Gemini 2.0/3.0.
- **Multi-GPU** : 6 cartes (4x1660S, 2060, 3080) pilotées via `nvidia-smi` et `gpu_dispatcher.py`.

## 🎙️ Pipeline Vocale
1. **Wake Word** : Porcupine ('Hey Jarvis') intégré nativement.
2. **STT** : Whisper-Flow via WebSocket temps réel.
3. **Brain** : `jarvis_brain_connector.py` (Ollama -> MCP Tools).
4. **TTS** : Piper (100% local) avec modèle Siwis-Medium.

## ⚙️ Optimisations Système
- **ZRAM** : 12GB (zstd) activés avec swappiness 100.
- **NVIDIA Persistence** : Mode actif sur tous les GPUs.
- **Monitoring** : Dashboard TMUX (`jarvis-dash`) + VRAM live dans le prompt Zsh.
- **Services** : 12 unités `systemd --user` orchestrées par `jarvis-ctl.sh`.

## 🛡️ Sécurité & Stabilité
- **Validation Data** : Bases `etoile.db` et `jarvis.db` réparées et peuplées (462 commandes).
- **Exécuteur** : Refondu pour la compatibilité Bash/Linux (redirection des appels Windows).
- **Tests** : Suite de régression `pytest` stabilisée à 93%.

---
*Rapport généré par Gemini CLI en mode Autonome Maximum.*
