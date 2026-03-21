---
name: prompt-improvement-loop
description: "Boucle d'amelioration continue des prompts — detecte les prompts basse qualite, les ameliore via le cluster, re-indexe et verifie. Utiliser quand l'utilisateur dit 'ameliorer prompts', 'boucle amelioration', 'prompt quality', ou 'improve library'."
---

Tu dois lancer une boucle d'amelioration continue sur la bibliotheque de prompts.

## Etape 1 — Diagnostic

```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --improve --json
```

Analyse le JSON pour identifier les prompts basse qualite et leurs problemes.

## Etape 2 — Selection

Selectionne les 3-5 prompts les plus prioritaires (score le plus bas).
Lis chaque fichier avec Read tool pour comprendre le contenu actuel.

## Etape 3 — Amelioration via cluster

Pour chaque prompt a ameliorer, dispatche au cluster M1 pour generer une version amelioree :

```bash
curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d '{"model":"qwen3-8b","input":"/nothink\nAmeliore ce prompt en ajoutant: titre clair, sections structurees (##), exemples de code (```), variables {{PLACEHOLDER}}, usage concret. Garde le meme sujet. Prompt original:\n\nCONTENU_DU_PROMPT","temperature":0.3,"max_output_tokens":1024,"stream":false,"store":false}'
```

## Etape 4 — Application

Ecris la version amelioree dans le fichier original avec Edit/Write tool.

## Etape 5 — Re-indexation + verification

```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --index
python3 F:/BUREAU/turbo/scripts/prompt_library.py --stats
```

Verifie que le score moyen a augmente. Si oui, continue avec les prochains prompts. Sinon, ajuste l'approche.

## Etape 6 — Commit si ameliorations significatives

Si >= 3 prompts ameliores :
```bash
cd F:/BUREAU/turbo/knowledge/bibliotheque-prompts-multi-ia && git add -A && git commit -m "improve: amelioration qualite prompts (score +X)"
```

## Cycle continu

Repete les etapes 1-6 jusqu'a ce que tous les prompts aient un score >= 50.
Objectif: score moyen >= 85/100.
