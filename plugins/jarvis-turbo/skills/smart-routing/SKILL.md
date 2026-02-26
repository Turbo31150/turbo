---
name: Smart Routing
description: Use when optimizing task routing across the JARVIS cluster based on autotest benchmark data. Maps task types to their best-performing nodes to maximize accuracy and minimize latency.
version: 3.0.0
---

# Smart Routing v3 — M1 Prioritaire OPTIMISE (benchmark 2026-02-25)

## Architecture Cluster

| Noeud | Modele | GPU/VRAM | ctx_len | Specialite |
|-------|--------|----------|---------|------------|
| **M1** | qwen3-8b (rapide) + qwen3-30b (profond) | 6 GPU / 46GB | **8192** | **PRIORITAIRE** — raisonnement, code, math |
| **M2** | deepseek-coder | 3 GPU / 24GB | 4096 | Code champion, review |
| **OL1** | qwen3:1.7b | 5 GPU / 40GB | 4096* | Ultra-rapide, questions simples |
| **M3** | mistral-7b | 1 GPU / 8GB | 4096 | General, validation (PAS raisonnement) |

*OL1: num_ctx=4096 par requete (defaut serveur 40960)

## Settings optimises (MaJ 2026-02-25)

| Parametre | M1 | M2 | M3 | OL1 |
|-----------|----|----|----|----|
| context_length | **8192** (etait 18014) | 4096 | 4096 | 4096/req |
| eval_batch_size | 512 | 512 | 512 | auto |
| flash_attention | true | true | true | auto |
| temperature | 0.2 | 0.2 | 0.2 | 0.2 |
| max_output_tokens | 1024 | 512 | 512 | auto |
| offload_kv_gpu | true | true | true | auto |

## Matrice par domaine x noeud (benchmark v3 OPTIMISE, 2026-02-25)

| Domaine | M1 (qwen3-8b/30b) | OL1 (qwen3) | M2 (deepseek) | M3 (mistral) | Meilleur |
|---------|-----------------|-------------|---------------|--------------|----------|
| **code** | **100% / 2-5s** | 85% / 1.5s | 100% / 6s | 100% / 5s | **M1** (qualite+vitesse) |
| **systeme** | **100% / 1-3s** | 100% / 2s | 100% / 11s | 100% / 5s | **M1** (le plus rapide !) |
| **traduction** | **100% / 1-2s** | 100% / 0.3s | — | 100% / 1s | OL1 (vitesse) ou **M1** (precision) |
| **math** | **100% / 2-23s** | 100% / 3s | 100% / 7s | — | **M1** (meilleur) |
| **raisonnement** | **100% / 6-24s** | 100% / 1.5s | 100% / 8s | — | **M1** (champion) |
| **trading** | **100% / 0.2-18s** | 100% / 2s | 100% / 4s | — | **M1** (analyse) |
| **securite** | **100% / 2-5s** | — | 100% / 6s | 100% / 11s | **M1** (rapide+precis) |
| **web** | **100% / 2-6s** | 100% / 1s | 100% / 6s | 100% / 5s | **M1** ou OL1 (rapide) |

## Regles de routage optimisees

### Priorite par tache
1. **Raisonnement/logique** -> **M1 TOUJOURS** (100%), fallback M2 — **EXCLURE M3**
2. **Code generation** -> **M1** premier choix (100%), M2 review
3. **Math/calcul** -> **M1** (100%, etapes detaillees), OL1 si besoin vitesse
4. **Traduction** -> **M1** (precision), OL1 si vitesse requise
5. **Systeme/commandes** -> **M1** ou OL1 (rapide)
6. **Questions simples** -> OL1 (0.5s) — pas besoin de M1
7. **Architecture** -> GEMINI + M1 validation
8. **Consensus critique** -> M1 + M2 + OL1 + CLAUDE (skip M3 si logique)

### Routage probabiliste (autotest v2)
```
code:          M1(50%) M2(30%) M3(15%) OL1(5%)
math:          M1(50%) OL1(30%) M2(15%) M3(5%)
raisonnement:  M1(50%) M2(30%) OL1(15%) [M3 EXCLU]
traduction:    M1(50%) OL1(30%) M2(15%) M3(5%)
systeme:       M1(50%) OL1(30%) M2(15%) M3(5%)
```

### Anti-patterns decouvertes par autotest
- **M3 + raisonnement** = 40% echec — mistral-7b ne gere pas la logique formelle
- **M1 + 2 modeles charges** = timeout total — TOUJOURS un seul modele sur M1
- **M2 + questions longues** = timeout si VRAM saturee — verifier modeles charges
- **OL1 + traduction espagnol** = 60% — qwen3:1.7b faible en langues rares
- **Tous + calcul mental sans etapes** = echec — toujours ajouter "calcule etape par etape"

### Prompts optimises par noeud
- **M1**: Detaille, "Reflechis etape par etape", peut gerer contexte long (18K tokens)
- **OL1**: Court, direct, "Reponds en francais, concis"
- **M2**: Peut etre detaille, "Montre ton raisonnement etape par etape"
- **M3**: Court, simple, "Reponds brievement" — eviter les taches de logique

### Gestion VRAM M1 (CRITIQUE)
- M1 a 46GB VRAM pour 6 GPU
- **Dual-model**: qwen3-8b (4.7GB, rapide 65 tok/s) + qwen3-30b (17.3GB, profond 9 tok/s) = 22GB/46GB
- /nothink OBLIGATOIRE (prefix input), extraction: dernier type=message dans output[]
- Si QwQ ou autre modele charge -> unload: `curl -s http://10.5.0.2:1234/api/v1/models/unload -d '{"instance_id":"MODEL_ID"}'`
- Verifier: `curl -s http://10.5.0.2:1234/api/v1/models | python3 -c "..."`

## Evolution
Relancer `python3 C:/Users/franc/jarvis_autotest.py 10 10` regulierement pour mettre a jour cette matrice.
