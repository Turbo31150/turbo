# 🚀 JARVIS DEVOPS MASTER PROMPTS

Ce fichier contient les prompts optimisés pour piloter le cluster JARVIS Turmont via Claude Code et Gemini CLI.

---

## 🦾 PROMPTS POUR CLAUDE CODE (`claude`)

### 1. Intégration Totale + Personnalisation Linux
> **Flags recommandés :** `claude --permission-mode acceptEdits --add-dir /home/turbo/jarvis /etc/systemd/system`

```text
Permission mode: acceptEdits, add-dir /home/turbo/jarvis /etc/systemd/system /home/turbo/.local/bin

Crée un système Linux "JARVIS-OS" complet basé sur Ubuntu 22.04 LTS :
1. Script install.sh : Drivers NVIDIA 535+, Docker, Kubernetes (vcluster), Python/Node, synchronisation GitHub https://github.com/Turbo31150/turbo
2. Systemd timers cascading : health.py (30min: GPU nvidia-smi, Docker ps, nodes ping), audit.py (journalier: analyse logs, crypto MEXC)
3. Intègre le serveur MCP Flask (interne Python : /home/turbo/jarvis/mcp-server) pour le contrôle du cluster
4. Zsh custom : Panneaux tmux (JARVIS dashboard, crypto live, GPU stats), alias devops
5. Cloud-init reproductible pour déploiement VPS multi-node
6. Teste tout, active les timers, et prépare le commit/push sur le repo turbo

Génère TOUS les fichiers, applique les changements et valide.
```

### 2. Monitoring GPU/Cluster + Discord
```text
Analyse mon cluster JARVIS (M1: Ryzen 7 5700X3D, 6 GPUs 1660S/2060/3080 ; M2 LM Studio ; server 3x Quadro).
Crée jarvis-cluster-health.py :
- nvidia-smi sur tous les GPUs (alerte si température/mémoire > 80%)
- Statut Docker/K8s (vcluster nodes, openclaw/whisperflow)
- Prix MEXC BTC/ETH + Alerte Discord via Webhook si KO
- Logs JSON structurés pour systemd
Ajoute le timer.service (30min) + audit quotidien.
Intègre au serveur MCP Flask pour les appels distants.
```

---

## ♊ PROMPTS POUR GEMINI CLI (`gemini`)

### 1. Santé JARVIS + Shell Custom
> **Flags recommandés :** `gemini --allow-edits --add-dir /home/turbo/jarvis`

```text
/compress  # Optimisation des tokens
Permission: full bash/edit

Génère jarvis-health.py pour mon JARVIS Turmont (GitHub turbo) :
- Statut multi-GPU NVIDIA Quadro/RTX
- Ping des nœuds du cluster (vcluster, whisperflow)
- Check crypto MEXC
- Alertes Discord + logs JSON
Crée zshrc.jarvis : alias (jarvis-health, gpu-watch), configuration dashboard tmux.
Installe le timer Systemd (30min), vérifie avec python3, et active via sudo systemctl.
```

### 2. Contrôle JARVIS via MCP Flask
```text
Intègre mon serveur Flask MCP (/home/turbo/jarvis/mcp-server) à JARVIS.
Ajoute les outils (tools) suivants : 
- gpu_scale(nodes:int)
- run_wave(wave:1-6)
- crypto_trade(symbol:str)
Génère un client Gemini pour les appels : gemini-wave3.
Teste à distance sur le cluster M1/serveur.
```

---

## 🛠️ COMMANDES DE CONTRÔLE RAPIDE (M1 MASTER)
```bash
# Monitoring
jarvis-health  # Santé GPUs et prix Crypto
gpu-watch      # Monitoring NVIDIA temps réel
jarvis-dash    # Cockpit Tmux Multi-fenêtres

# Services
status         # État de tous les daemons JARVIS
restart-jarvis # Relance tout le cluster
logs           # Logs du serveur principal
```
