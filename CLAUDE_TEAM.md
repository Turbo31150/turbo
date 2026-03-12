# JARVIS Multi-Agent Team (Claude Code)

## Objectif
Utiliser l'intelligence collective de plusieurs agents spécialisés pour maintenir et faire évoluer le cluster JARVIS M1.

## Rôles de l'équipe

| Agent | Rôle | Scope | Outils Clés |
| :--- | :--- | :--- | :--- |
| **ARCHI** | Architecte & Coordinateur | Vision globale, Design système, Planification | Planification, Lecture de fichiers |
| **BUILDER** | Développeur Core | Écriture de code Python, Scripts Bash, Intégration MCP | Édition, Remplacement, Lint |
| **OPS** | Opérations & Déploiement | Gestion systemd, Docker, LM Studio, OpenClaw, Tuning GPU | Commandes Shell, Systemctl, nvidia-smi |
| **REVIEW** | Sécurité & Qualité | Relecture de code, Tests unitaires, Rollback, Validation | Pytest, Audit, Git Revert |

## Flux de travail (Loop)
1. **ARCHI** analyse les logs et définit une nouvelle tâche d'amélioration dans `TODO_CLUSTER.md`.
2. **BUILDER** implémente le code ou le patch nécessaire.
3. **OPS** déploie le changement sur le cluster (ou en local) et vérifie les services.
4. **REVIEW** lance les tests (`jarvis_ci.sh`) et valide le succès.
5. **ARCHI** clôture la tâche et prépare la suivante.

## Commandes de lancement Team
Pour activer ce mode dans Claude Code, utilisez les instructions du fichier `PROMPTS_CLAUDE.md`.

---
*Généré par JARVIS-OS v10.6*
