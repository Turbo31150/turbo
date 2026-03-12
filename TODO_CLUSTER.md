# JARVIS CLUSTER TODO LIST

## Priorité : Haute
- [ ] **DEBUG GPU 6** : Le GPU sur le bus `07:00.0` (GTX 1660S) est détecté par `lspci` et `persistenced` mais n'apparaît pas dans `nvidia-smi`. Nécessite un reboot ou investigation riser.
- [ ] **SECURE BOOT MOK** : Finaliser l'installation de `emuV` en effectuant l'Enroll MOK au prochain reboot (voir `enroll_emuv_key.sh`).
- [ ] **TESTS DOMINO LINUX** : Lancer une cascade Domino complète (`domino_matin_complet`) pour valider la migration Bash effectuée.

## Priorité : Moyenne
- [ ] **DASHBOARD VRAM** : Intégrer les métriques `zram` et `emuV` dans le dashboard Electron Etoile.
- [ ] **ROUTAGE INTELLIGENT** : Implémenter `jarvis_router.py` pour dispatcher entre Claude (API), Gemini (CLI), et LM Studio (M2).
- [ ] **VOICE COMPUTER CONTROL** : Ajouter des commandes pour `xdotool` plus complexes (grid navigation).

## Maintenance
- [ ] **GIT SYNC** : Synchroniser les derniers changements de `domino_pipelines.py` vers les repositories miroirs.
- [ ] **LOG ROTATION** : Vérifier que `journalctl` ne dépasse pas 1GB.

---
*Dernière mise à jour : 12 Mars 2026*
