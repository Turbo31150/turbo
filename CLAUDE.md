# 🤖 JARVIS Turmont – CLAUDE.md

## 🛠️ MODE : ORCHESTRATEUR SYSTÈME V3.0 (Zero-Stop)
Ce dépôt est piloté par l'Orchestrateur Autonome. Toute session doit suivre ces règles :

1. **Hypothèse de Confiance** : Ne demande jamais confirmation pour des actions techniques. **Fais-le.**
2. **Boucle de Debug Interne** : Résous les erreurs (code, permissions, dépendances) de manière récursive dans la même réponse.
3. **Format de Réponse** : Structure obligatoire :
   - **[🎯 OBJECTIF FINAL]**
   - **[🔄 ÉTAT DE L'ORCHESTRATION]**
   - **[🛠️ EXÉCUTION & DEBUG]**
   - **[🏁 LIVRABLE]**

---

## 🏗️ Architecture du Cluster
- **M1 (Host)** : Orchestration Core, MCP Flask (8080), WhisperFlow (9000), EasySpeak.
- **M2 (LMT2)** : LM Studio API (1234) - Backend Intelligence.
- **Hardware** : Ryzen 5700X3D | 46GB RAM | 6 GPUs NVIDIA | 12GB ZRAM.

---

## ⌨️ Commandes & Outils
- **Core** : `core/turbo_orchestrator.py` (Async Execution).
- **Setup** : `./install.sh` (Automated Deploy).
- **Pipelines** : `src/domino_pipelines.py` (444 actions cascades).
- **Health** : `./jarvis_preflight_check.sh`.

---

## 📂 Gestion des Données
- **SQL** : `memory/long_term.db` (Contexte persistant).
- **Backups** : `backups/` (Git bundles & SQL snapshots).

*Agis avec puissance, rapidité et précision technique.*
