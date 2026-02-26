---
name: model-swap
description: Charger/decharger un modele sur un noeud LM Studio (M1/M2/M3)
args: node model
---

Gere les modeles LM Studio sur le cluster. Arguments : `$ARGUMENTS` = "<noeud> <modele>"
Exemples : `model-swap M2 deepseek-coder`, `model-swap M1 qwen3-coder-30b`

Noeuds disponibles :
- M1: http://10.5.0.2:1234 (Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7)
- M2: http://192.168.1.26:1234 (Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4)
- M3: http://192.168.1.113:1234 (Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux)

Etapes :
1. Lister les modeles charges sur le noeud cible (GET /v1/models)
2. Si un modele est deja charge, demander confirmation avant de le decharger
3. Charger le nouveau modele (POST /v1/models/load)
4. Verifier que le chargement est OK

Utilise curl avec les headers d'auth du noeud cible. Timeout 120s pour M1 (lent).
