# 🚀 GUIDE DE MIGRATION : JARVIS Turmont (Windows) → Ubuntu 22.04 (M1)

Ce document décrit le passage de l'architecture JARVIS Turmont vers le cluster Linux M1.

## 📁 Changements de Structure
- **Paths** : Tous les chemins Windows `/home/turbo/jarvis-m1-ops` ont été convertis en `/home/turbo/jarvis-m1-ops`.
- **Launchers** : Les fichiers `.bat` ont été remplacés par des services `systemd` (6 vagues).
- **Environment** : Utilisation de `uv` pour l'isolation Python 3.12 et Node.js 20.

## 🛠️ Architecture Linux (M1 - 6 GPUs)
1. **Core Cluster** :
   - `jarvis-proxy.service` (Gemini & Node.js proxy)
   - `jarvis-mcp.service` (Python Flask MCP server)
2. **AI Engines** :
   - Ollama (Local & Cloud via minimax-m2.5:cloud)
   - LM Studio (M1 prioritaires via 127.0.0.1:1234)
3. **Voice Pipeline** :
   - `faster-whisper` sur CUDA (WhisperFlow)
   - `openwakeword` (Wake Word Porcupine compatible Linux)
4. **Monitoring** :
   - Dashboard TMUX via `./scripts/jarvis-dash.sh`.
   - `nvidia-smi` intégré.

## 🚀 Commandes de Contrôle
- **Démarrer tout** : `systemctl --user start jarvis-*`
- **Arrêter tout** : `systemctl --user stop jarvis-*`
- **Statut global** : `./scripts/jarvis-dash.sh`
- **Logs temps réel** : `journalctl --user -u jarvis-master -f`

## ⚙️ Configuration (.env)
Assurez-vous d'avoir rempli les clés API :
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `PORCUPINE_ACCESS_KEY`

---
*Migration effectuée avec succès par Gemini CLI en mode autonome.*
