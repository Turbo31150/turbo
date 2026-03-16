# GUIDE D'EXPLOITATION JARVIS TURMONT (Ubuntu 22.04)

## 🏗️ ARCHITECTURE CONSOLIDÉE
- **Orchestrateur** : `jarvis-ws` (port 9742)
- **Cerveau (MCP)** : `jarvis-mcp` (port 8901)
- **Gateway IA** : `vcluster_gateway.py` (Abstraie M1, M2, OL1)
- **Auto-Heal** : `scripts/auto_heal.py` (Redémarre les services si DOWN)
- **Sentinel** : `scripts/trading_sentinel.py` (Surveillance crypto MEXC)

## 🚀 COMMANDES CRITIQUES
- **Statut Global** : `./jarvis-ctl.sh status`
- **Santé Endpoints** : `./jarvis-ctl.sh health`
- **Dashboard TMUX** : `jarvis-dash` (alias zsh)
- **Refaire Inférence** : `ollama run deepseek-r1:7b`

## 🛡️ SÉCURITÉ & RÉSILIENCE
- **Secrets** : Protection pre-commit Git active.
- **Récupération** : Les ports 8901, 18800 et 9742 sont auto-libérés par l'Auto-Healer.
- **VRAM** : Monitoring temps réel intégré au prompt Zsh.

## 🎙️ VOCAL (VOIX V3)
- **Wake Word** : 'Hey Jarvis' (Porcupine)
- **Filtrage** : VAD (webrtcvad) actif pour économie CPU.
- **TTS** : Piper (Local) + modèle Siwis-Medium.

---
*Système stabilisé et optimisé par Gemini CLI — 12 Mars 2026.*
