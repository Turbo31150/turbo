# JARVIS Etoile v10.3 — Orchestrateur IA Distribue

**Repo prive — Turbo31150**

**Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE.**

```
                    ╔═══════════════════════════════════════════╗
                    ║       JARVIS ETOILE v10.3                 ║
                    ║   Orchestrateur IA Multi-GPU Distribue    ║
                    ║   10 GPU | 78 GB VRAM | 5 Noeuds IA      ║
                    ║   7 Agents | 87 Outils MCP | Voice       ║
                    ╚═══════════════════════════════════════════╝
```

---

## Table des Matieres

1. [Architecture Globale](#architecture-globale)
2. [Benchmark Reel — Resultats & Decisions](#benchmark-reel--resultats--decisions)
3. [Cluster IA — Noeuds & Cles](#cluster-ia--noeuds--cles)
4. [Pipeline Commander — Workflow Detaille](#pipeline-commander--workflow-detaille)
5. [7 Agents Claude SDK](#7-agents-claude-sdk)
6. [Routage Commander (benchmark-tuned)](#routage-commander-benchmark-tuned)
7. [Workflow Consensus Multi-Source](#workflow-consensus-multi-source)
8. [Seuil Thermique GPU](#seuil-thermique-gpu)
9. [87 Outils MCP](#87-outils-mcp)
10. [n8n Workflow Etoile](#n8n-workflow-etoile)
11. [Architecture Vocale — Pipeline v2](#architecture-vocale--pipeline-v2-2026-02-22)
12. [Trading MEXC](#trading-mexc-futures)
13. [Modes de Lancement](#modes-de-lancement)
14. [Structure du Projet](#structure-du-projet)
15. [Bases de Donnees](#bases-de-donnees)
16. [Installation & Configuration](#installation--configuration)
17. [Appels API — Exemples Complets](#appels-api--exemples-complets)
18. [955 Commandes Vocales — Liste Complete](#812-commandes-vocales--liste-complete)

---

## Architecture Globale

```
 UTILISATEUR (voix / clavier / one-shot)
       |
       v
 +-------------------------------------------------------------+
 |                    JARVIS COMMANDER                          |
 |              (Claude Agent SDK - Opus/Sonnet)                |
 |                                                              |
 |  1. classify_task()  --> M1 qwen3-30b (5ms) / heuristique   |
 |  2. decompose_task() --> TaskUnit[]                          |
 |  3. thermal_check()  --> GPU temp < 85C ?                    |
 |  4. enrich_prompt()  --> COMMANDER_PROMPT                    |
 +-----+-------+-------+-------+-------+-------+-------+------+
       |       |       |       |       |       |       |
       v       v       v       v       v       v       v
  +---------+------+-------+--------+------+--------+-----------+
  |ia-deep  |ia-   |ia-    |ia-     |ia-   |ia-     |ia-        |
  |Opus     |fast  |check  |trading |system|bridge  |consensus  |
  |Archi    |Haiku |Sonnet |Sonnet  |Haiku |Sonnet  |Sonnet     |
  +---------+------+-------+--------+------+--------+-----------+
       |       |       |       |       |       |         |
       v       v       v       v       v       v         v
  +------+ +------+ +------+ +------+ +------+ +----------+
  |  M2  | |  OL1 | |  M3  | |GEMINI| |  M1  | |PowerShell|
  |deep- | |qwen3 | |mistr-| |proxy | |qwen3 | | Windows  |
  |seek  | |1.7b  | |al-7b | | .js  | | 30b  | |  SAPI    |
  |3 GPU | |local | |1 GPU | |cloud | |6 GPU | |  87 MCP  |
  |24 GB | |+cloud| |8 GB  | |      | |46 GB | |  tools   |
  | 92%  | | 88%  | | 89%  | | 74%  | | 23%  | |          |
  +------+ +------+ +------+ +------+ +------+ +----------+
       |       |       |       |       |
       +-------+-------+-------+-------+
                       |
                       v
               SYNTHESE COMMANDANT
               [AGENT/modele] attribution
               Score qualite 0-1
               Re-dispatch si < 0.7
```

---

## Benchmark Reel — Resultats & Decisions

### Methodologie (2026-02-20)

Benchmark en 2 phases :
1. **benchmark_cluster.py** — 7 phases automatisees (health, inference, consensus, bridge, agents, stress, erreurs)
2. **benchmark_real_test.py** — 10 niveaux de difficulte envoyes simultanement aux 5 noeuds

Les 10 niveaux testent des capacites croissantes :

```
 Niveau 1  [TRIVIAL]     Inverser une chaine de caracteres
 Niveau 2  [FACILE]      Algorithme LRU Cache
 Niveau 3  [MOYEN]       Debug async avec race condition
 Niveau 4  [MOYEN+]      Refactoring Design Pattern
 Niveau 5  [COMPLEXE]    Pipeline ETL avec gestion d'erreurs
 Niveau 6  [COMPLEXE+]   Analyse de complexite algorithmique
 Niveau 7  [DIFFICILE]   Systeme de cache distribue
 Niveau 8  [DIFFICILE+]  Raisonnement multi-etapes
 Niveau 9  [EXPERT]      Mini interpreteur de langage
 Niveau 10 [EXPERT+]     Architecture distribuee complete
```

### Resultats par Noeud

```
 SCORE GLOBAL (%)
 ┌─────────────────────────────────────────────────────────┐
 │                                                         │
 │  M2 /deepseek-coder   ████████████████████████████ 92%  │  CHAMPION
 │  M3 /mistral-7b       ███████████████████████████  89%  │  SOLIDE
 │  OL1/qwen3:1.7b       ██████████████████████████   88%  │  RAPIDE
 │  GEMINI/gemini-3-pro  ██████████████████████        74%  │  VARIABLE
 │  M1 /qwen3-30b        ██████                       23%  │  TIMEOUT
 │                                                         │
 └─────────────────────────────────────────────────────────┘

 LATENCE MOYENNE (secondes)
 ┌─────────────────────────────────────────────────────────┐
 │                                                         │
 │  OL1   █           0.5s                                 │  LE + RAPIDE
 │  M2    ██          1.3s                                 │
 │  M3    ███         2.5s                                 │
 │  M1    █████████████████ 12.0s  (quand il repond)       │
 │  GEMINI████████████████████████████████████████ 75.0s    │
 │                                                         │
 └─────────────────────────────────────────────────────────┘
```

### Detail par Noeud

#### M2 — deepseek-coder-v2-lite — CHAMPION (92%)

| Metrique | Valeur |
|----------|--------|
| **Score** | 92% (46/50 points) |
| **Fails** | 0 / 10 niveaux |
| **Latence moy** | 1.3s |
| **Limite** | Niveau 10 (meta-analyse) |
| **Forces** | Code, algorithmes, debug, refactoring |
| **Poids** | 1.4 (promu primary) |

#### M3 — mistral-7b — SOLIDE (89%)

| Metrique | Valeur |
|----------|--------|
| **Score** | 89% (44.5/50 points) |
| **Fails** | 0 / 10 niveaux |
| **Latence moy** | 2.5s |
| **Limite** | Aucune (surprenant pour 8GB VRAM) |
| **Forces** | Polyvalent, raisonnement, general |
| **Poids** | 1.0 (promu de 0.5) |

#### OL1 — qwen3:1.7b — PLUS RAPIDE (88%)

| Metrique | Valeur |
|----------|--------|
| **Score** | 88% (44/50 points) |
| **Fails** | 0 / 10 niveaux |
| **Latence moy** | 0.5s (22x plus rapide que M1) |
| **Limite** | Qualite code expert (N9-N10) |
| **Forces** | Vitesse, polyvalence, short answers, web |
| **Poids** | 1.3 (promu de 1.0) |

#### GEMINI — gemini-3-pro — ARCHITECTURE (74%)

| Metrique | Valeur |
|----------|--------|
| **Score** | 74% (37/50 points) |
| **Fails** | 1 / 10 niveaux |
| **Latence moy** | 75s |
| **Limite** | Variable (100% LRU, 0% interpreteur) |
| **Forces** | Architecture, vision, review |
| **Poids** | 1.2 (inchange) |

#### M1 — qwen3-30b — LENT (23%)

| Metrique | Valeur |
|----------|--------|
| **Score** | 23% (11.5/50 points) |
| **Fails** | 7 / 10 niveaux (TIMEOUT) |
| **Latence moy** | 12.0s (meme trivial) |
| **Limite** | Niveau 3 (tout ce qui est > moyen timeout) |
| **Cause** | Chain-of-thought de qwen3-30b (MoE 3B actifs) trop long |
| **Poids** | 0.7 (demote de 1.5) |

### Decisions de Routage

Le benchmark a provoque une **reorganisation complete** du routage :

```
 AVANT (2026-02-19)                    APRES (2026-02-20)
 ─────────────────                     ──────────────────

 short_answer  → [M1]                  short_answer  → [OL1, M3]
 deep_analysis → [M1]                  deep_analysis → [M2, GEMINI]
 code_gen      → [M2, M1]             code_gen      → [M2, M3]
 trading       → [M1, OL1]            trading       → [OL1, M2]
 validation    → [M1, M2]             validation    → [M2, OL1]
 critical      → [M1, OL1]            critical      → [M2, OL1, GEMINI]
 reasoning     → [M1, OL1]            reasoning     → [M2, OL1]
 auto_learn    → [M1]                  auto_learn    → [OL1, M2]
 embedding     → [M1]                  embedding     → [M1]  (seul use case)
 consensus     → [M1,M2,OL1,GEM]      consensus     → [M2,OL1,M3,M1,GEM]
 architecture  → [GEMINI, M1]         architecture  → [GEMINI, M2]
```

### Scripts Benchmark

```bash
# Benchmark rapide (4 phases: health, inference, agents, erreurs)
uv run python benchmark_cluster.py --quick

# Benchmark complet (7 phases incluant consensus, bridge, stress)
uv run python benchmark_cluster.py

# Benchmark reel (10 niveaux de difficulte sur 5 noeuds)
uv run python benchmark_real_test.py
```

Rapports generes dans `data/benchmark_report.json` et `data/benchmark_real_report.json`.

---

## Cluster IA — Noeuds & Cles

### M2 — CHAMPION Code (3 GPU, 24 GB VRAM) — Score: 92%

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://192.168.1.26:1234` |
| **API Key** | `sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4` |
| **GPU** | 3 GPU |
| **VRAM** | 24 GB total |
| **Modele** | `deepseek-coder-v2-lite-instruct` |
| **Poids** | 1.4 |
| **Role** | PRIMARY — Code, analyse, raisonnement, validation |

**Appel M2 (API native v1) :**
```bash
curl -s http://192.168.1.26:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" \
  -d '{
    "model": "deepseek-coder-v2-lite-instruct",
    "input": "VOTRE PROMPT",
    "temperature": 0.3,
    "max_output_tokens": 8192,
    "stream": false,
    "store": false
  }'
```

### OL1 — PLUS RAPIDE + Polyvalent — Score: 88%

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://127.0.0.1:11434` |
| **Version** | Ollama v0.16.1 |
| **Local** | `qwen3:1.7b` (1.36 GB) |
| **Cloud** | minimax-m2.5, glm-5, kimi-k2.5 |
| **Poids** | 1.3 |
| **Role** | SHORT ANSWERS, web search, polyvalent rapide |

**IMPORTANT** : `"think": false` OBLIGATOIRE pour les modeles cloud.

```bash
# Local (0.5s avg)
curl -s http://127.0.0.1:11434/api/chat -d '{
  "model": "qwen3:1.7b",
  "messages": [{"role": "user", "content": "VOTRE PROMPT"}],
  "stream": false
}'

# Cloud web search (minimax)
curl -s http://127.0.0.1:11434/api/chat -d '{
  "model": "minimax-m2.5:cloud",
  "messages": [{"role": "user", "content": "VOTRE PROMPT"}],
  "stream": false,
  "think": false
}'
```

### M3 — SOLIDE General (1 GPU, 8 GB VRAM) — Score: 89%

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://192.168.1.113:1234` |
| **GPU** | 1 GPU |
| **VRAM** | 8 GB |
| **Modele** | `mistral-7b-instruct-v0.3` |
| **Poids** | 1.0 (promu de 0.5) |
| **Role** | FALLBACK FIABLE — review, raisonnement, general |

### GEMINI — Architecture & Vision (Cloud) — Score: 74%

| Parametre | Valeur |
|-----------|--------|
| **Proxy** | `node F:/BUREAU/turbo/gemini-proxy.js` |
| **Modeles** | Gemini 3 Pro / Flash + 2.5 Pro / Flash (fallback) |
| **Timeout** | 2 minutes |
| **Poids** | 1.2 |
| **Role** | Architecture, vision, review (qualite variable) |

```bash
node F:/BUREAU/turbo/gemini-proxy.js "VOTRE PROMPT"
node F:/BUREAU/turbo/gemini-proxy.js --json "VOTRE PROMPT"
node F:/BUREAU/turbo/gemini-proxy.js --ping   # Health check
```

### M1 — Reserve Embedding (6 GPU, 46 GB VRAM) — Score: 23%

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://10.5.0.2:1234` |
| **API Key** | `sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7` |
| **GPU** | RTX 2060 + 4x GTX 1660 Super + RTX 3080 |
| **VRAM** | 46 GB total |
| **CUDA_VISIBLE_DEVICES** | `5,0,1,2,3,4` |
| **Modele permanent** | `qwen/qwen3-30b-a3b-2507` |
| **Poids** | 0.7 (demote de 1.5) |
| **Role** | EMBEDDING ONLY + consensus participant (lent, timeout complexe) |

**Modeles on-demand M1 :**
| Modele | VRAM | Usage |
|--------|------|-------|
| `qwen3-coder-30b` | 18.63 GB | Code specialise |
| `devstral-small-2` | 15.21 GB | Dev tasks |
| `gpt-oss-20b` | 12.11 GB | General purpose |

**Blacklist M1** (gaspillent VRAM) : `nemotron-3-nano`, `glm-4.7-flash`

**ATTENTION** : M1 timeout sur 7/10 requetes complexes. Latence 12s+ meme pour du trivial. Ne pas utiliser en primary sauf embedding.

### LM Studio CLI

```
C:\Users\franc\.lmstudio\bin\lms.exe
```

```bash
lms status          # Status serveur
lms ls              # Modeles charges
lms load qwen/qwen3-30b-a3b-2507 --gpu max
lms unload --all
```

### Health Check Cluster

```bash
# M2 (CHAMPION — verifier en premier)
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models \
  -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('M2 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')"

# OL1 (Ollama)
curl -s --max-time 3 http://127.0.0.1:11434/api/tags \
  | python -c "import sys,json;print('OL1 OK:',len(json.load(sys.stdin).get('models',[])),'modeles')"

# M3
curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models \
  | python -c "import sys,json;d=json.load(sys.stdin);print('M3 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')"

# GEMINI
node F:/BUREAU/turbo/gemini-proxy.js --ping

# M1 (reserve)
curl -s --max-time 3 http://10.5.0.2:1234/api/v1/models \
  -H "Authorization: Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('M1 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')"
```

---

## Pipeline Commander — Workflow Detaille

Le mode Commandant est **PERMANENT** sur tous les modes (interactif, vocal, hybride, one-shot).

### Workflow Complet (schema)

```
 ENTREE UTILISATEUR
 (voix / clavier / one-shot / webhook n8n)
          |
          v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 1: CLASSIFICATION                     |
 |                                                              |
 |  classify_task(input)                                        |
 |  ├── M1 qwen3-30b (5ms avg)  ← si cluster online            |
 |  └── Heuristique fallback (0ms) ← si M1 offline             |
 |                                                              |
 |  Categories: code | analyse | trading | systeme | web |      |
 |               simple | architecture | consensus              |
 +──────────────────────────┬──────────────────────────────────+
                            |
                            v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 2: DECOMPOSITION                      |
 |                                                              |
 |  decompose_task(input, task_type)                            |
 |  ├── Lookup commander_routing[task_type]                     |
 |  ├── Genere TaskUnit[] avec dependances                      |
 |  ├── check_thermal_status() → GPU temp < 85C ?              |
 |  └── Si GPU > 85C → re-routage cascade M1→M2→M3→OL1        |
 |                                                              |
 |  Exemple pour task_type="code":                              |
 |  ┌──────────────────────────────────────────────┐            |
 |  │ t1: ia-fast + M2 (coder)     priority=1     │            |
 |  │ t2: ia-check + M3 (reviewer) priority=2     │ depends t1 |
 |  └──────────────────────────────────────────────┘            |
 +──────────────────────────┬──────────────────────────────────+
                            |
                            v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 3: ENRICHISSEMENT                     |
 |                                                              |
 |  build_commander_enrichment(task_type, subtasks, thermal)    |
 |  ├── Construit le COMMANDER_PROMPT enrichi                   |
 |  ├── Injecte: classification + sous-taches + cibles          |
 |  └── Optionnel: pre-analyse M2 (si complexe)                |
 +──────────────────────────┬──────────────────────────────────+
                            |
                            v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 4: DISPATCH PARALLELE                 |
 |                                                              |
 |  Claude recoit COMMANDER_PROMPT + prompt enrichi             |
 |  ├── Lance agents via Task tool (ia-deep, ia-fast, etc.)    |
 |  ├── Lance IAs directes via mcp__jarvis__lm_query           |
 |  ├── Max 4 outils MCP jarvis en parallele (limite stdio)    |
 |  └── Batch par groupes de 3-4 si > 4 appels                |
 |                                                              |
 |  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          |
 |  │ ia-fast │ │ M2 query│ │ OL1 web │ │ GEMINI  │          |
 |  │ + M2    │ │ direct  │ │ search  │ │ query   │          |
 |  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          |
 |       └──────┬─────┘──────┬────┘──────┬────┘               |
 |              v            v           v                      |
 |         COLLECTE RESULTATS                                   |
 +──────────────────────────┬──────────────────────────────────+
                            |
                            v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 5: VALIDATION                         |
 |                                                              |
 |  ia-check valide chaque resultat                             |
 |  ├── Score qualite 0.0 - 1.0                                |
 |  ├── Si score < 0.7 → RE-DISPATCH (max 2 cycles)           |
 |  └── Cross-validation via consensus (M2+OL1+M3)            |
 +──────────────────────────┬──────────────────────────────────+
                            |
                            v
 +─────────────────────────────────────────────────────────────+
 |                  PHASE 6: SYNTHESE                           |
 |                                                              |
 |  Claude synthetise tous les resultats                        |
 |  ├── Attribution obligatoire: [AGENT/modele]                |
 |  ├── Score global + agents utilises                         |
 |  └── Output vocal (TTS) ou texte selon mode                 |
 +─────────────────────────────────────────────────────────────+
```

### Classification Heuristique (24/24 correct)

Priorite: `code-override > web-override > trading > systeme > analyse > code > web > simple`

- **code-override** : debug, segfault, bug, fix, patch, refactor
- **web-override** : actualite, news, dernieres nouvelles
- **trading** : trading, signal, mexc, breakout, btc, eth, sol (word-boundary)
- **systeme** : ouvre, ferme, fichier, powershell, windows, service (word-boundary)
- **analyse** : analyse, architecture, strategie, benchmark, audit
- **code** : code, fonction, python, script, api, react, flask
- **web** : cherche, recherche, google, documentation
- **simple** : tout le reste

### TaskUnit (Data Structure)

```python
@dataclass
class TaskUnit:
    id: str               # t1, t2, t3...
    prompt: str           # Prompt adapte au role
    task_type: str        # code/analyse/trading/systeme/web/simple
    target: str           # ia-deep/ia-fast/ia-check/.../M1/M2/OL1/GEMINI
    priority: int = 1     # 1=haute, 3=basse
    depends_on: list[str] # IDs des taches prealables
    result: str | None    # Resultat de l'agent/IA
    status: str           # pending/running/done/failed
    quality_score: float  # 0.0 - 1.0
```

---

## 7 Agents Claude SDK

Definis dans `src/agents.py`, utilisant le Claude Agent SDK Python v0.1.35.

### ia-deep (Opus) — Architecte

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Opus |
| **Role** | Analyse profonde, architecture, strategie, logs |
| **Outils** | Read, Glob, Grep, WebSearch, WebFetch, lm_query, consensus, gemini_query, bridge_mesh |
| **IA cible** | M2 (champion) pour enrichir, consensus pour valider |

### ia-fast (Haiku) — Ingenieur Code

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Haiku |
| **Role** | Code rapide, edits, execution |
| **Outils** | Read, Write, Edit, Bash, Glob, Grep, lm_query |
| **IA cible** | M2 (deepseek-coder champion 92%), M3 en fallback |

### ia-check (Sonnet) — Validateur

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Review, validation, score qualite 0-1 |
| **Outils** | Read, Bash, Glob, Grep, lm_query, consensus, gemini_query, bridge_mesh |
| **IA cible** | M2 (champion) + OL1 (rapide) pour cross-validation |

### ia-trading (Sonnet) — Trading MEXC

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Scanner marche, breakout, signaux, positions |
| **Outils** | Read, Bash, Glob, Grep, run_script, lm_query, consensus, ollama_web_search |
| **IA cible** | OL1 (web search), M2 (analyse) |

### ia-system (Haiku) — Systeme Windows

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Haiku |
| **Role** | Fichiers, registre, processus, PowerShell |
| **Outils** | Read, Write, Edit, Bash, Glob, Grep, powershell_run, system_info |

### ia-bridge (Sonnet) — Orchestrateur Multi-Noeuds

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Mesh parallele, consensus etendu, routage intelligent |
| **Outils** | Read, Glob, Grep, bridge_mesh, bridge_query, gemini_query, consensus, lm_query, lm_mcp_query, ollama_web_search |
| **Noeuds** | M2 (champion 92%), OL1 (rapide 88%), M3 (solide 89%), GEMINI (archi 74%), M1 (lent 23%) |

### ia-consensus (Sonnet) — Consensus Multi-Source

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Vote pondere multi-source, detection desaccords |
| **Outils** | Read, Glob, Grep, consensus, bridge_mesh, bridge_query, gemini_query, lm_query, ollama_query, ollama_web_search, lm_cluster_status |
| **Protocole** | Min 3 sources, vote pondere, seuil confiance 0.6 |

---

## Routage Commander (benchmark-tuned)

Matrice definie dans `config.py` → `commander_routing` — **ajustee le 2026-02-20** :

| Type | Agent | IA Cible | Role | Benchmark |
|------|-------|----------|------|-----------|
| **code** | ia-fast | M2 (deepseek) | coder | M2 champion 92% |
| **code** | ia-check | M3 (mistral) | reviewer | M3 solide 89% |
| **analyse** | ia-deep | M2 (deepseek) | analyzer | M2 fiable, M1 timeout |
| **trading** | ia-trading | OL1 (ollama) | scanner | OL1 web search rapide |
| **trading** | - | OL1 | web_data | OL1 cloud natif |
| **trading** | ia-check | M2 (deepseek) | validator | M2 champion |
| **systeme** | ia-system | - | executor | N/A (Windows direct) |
| **web** | - | OL1 | searcher | OL1 plus rapide 0.5s |
| **web** | ia-deep | M2 (deepseek) | synthesizer | M2 champion |
| **simple** | - | OL1 | responder | OL1 rapide (vs M1 12s) |
| **architecture** | ia-bridge | GEMINI | analyzer | GEMINI specialise archi |
| **architecture** | ia-deep | M2 (deepseek) | reviewer | M2 champion |
| **consensus** | ia-consensus | M2 (deepseek) | analyzer | M2 primary |

**Regle** : Les reviewers/validators/synthesizers **dependent** des taches principales.

---

## Workflow Consensus Multi-Source

```
 QUESTION UTILISATEUR
          |
          v
 +──────────────────────────────────────────────+
 |  ia-consensus (ou consensus MCP tool)         |
 |                                               |
 |  1. INTERROGATION PARALLELE (bridge_mesh)     |
 |     ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     |
 |     │  M2  │ │  OL1 │ │  M3  │ │GEMINI│     |
 |     │ w=1.4│ │ w=1.3│ │ w=1.0│ │ w=1.0│     |
 |     └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘     |
 |        │        │        │        │          |
 |        v        v        v        v          |
 |  2. COLLECTE (+ M1 w=0.7 si disponible)      |
 |                                               |
 |  3. VOTE PONDERE                              |
 |     Score = sum(reponse_i * poids_i) / total  |
 |                                               |
 |  4. DETECTION DESACCORDS                      |
 |     Si 2+ sources divergent:                  |
 |     → Re-query avec prompt clarifie           |
 |                                               |
 |  5. VERDICT                                   |
 |     [VERDICT]    Reponse consensuelle         |
 |     [CONFIANCE]  Score 0.0-1.0                |
 |     [SOURCES]    Noeuds + attribution         |
 |     [DESACCORDS] Points de divergence         |
 |     [DETAIL]     Resume par source            |
 |                                               |
 |  Si confiance < 0.6: "CONSENSUS FAIBLE"       |
 |  Si 1 seule source: "SOURCE UNIQUE"           |
 +──────────────────────────────────────────────+
```

### Poids de Vote (benchmark-tuned)

```
 M2  /deepseek-coder  ████████████████ 1.4  (champion 92%, fiable)
 OL1 /qwen3:1.7b      ██████████████   1.3  (88%, plus rapide)
 M3  /mistral-7b       ████████████     1.0  (89%, solide)
 GEM /gemini-3-pro     ████████████     1.0  (74%, variable archi)
 M1  /qwen3-30b        ████████         0.7  (23%, lent timeout)
```

---

## Seuil Thermique GPU

Verifie a chaque `decompose_task()` via `nvidia-smi --query-gpu=temperature.gpu`.

| Niveau | Temperature | Action |
|--------|------------|--------|
| **Normal** | < 75C | Routage standard |
| **Warning** | 75-84C | Preferer M2/OL1, reduire charge M1 |
| **Critical** | >= 85C | Deporter M1 -> M2/OL1/GEMINI, alerte dans prompt |

```python
# Fonction: check_thermal_status() -> dict
# Retourne: {ok, max_temp, status, hot_gpus, recommendation}
```

---

## 87 Outils MCP

Prefixe: `mcp__jarvis__`

### IA & Cluster (4)
| Outil | Description |
|-------|-------------|
| `lm_query` | Interroger M1/M2/M3 directement |
| `lm_models` | Lister les modeles charges |
| `lm_cluster_status` | Status complet du cluster (5 noeuds) |
| `consensus` | Consensus multi-noeuds (M2+OL1+M3+M1+GEMINI) |

### Gemini (1)
| Outil | Description |
|-------|-------------|
| `gemini_query` | Interroger Gemini 3 Pro/Flash via proxy |

### Bridge Multi-Noeuds (2)
| Outil | Description |
|-------|-------------|
| `bridge_query` | Routage intelligent par task_type avec fallback |
| `bridge_mesh` | Requete parallele sur N noeuds simultanement |

### Model Management (7)
| Outil | Description |
|-------|-------------|
| `lm_load_model` | Charger un modele sur M1/M2 |
| `lm_unload_model` | Decharger un modele |
| `lm_switch_coder` | Charger qwen3-coder-30b sur M1 |
| `lm_switch_dev` | Charger devstral sur M1 |
| `lm_gpu_stats` | Stats GPU (VRAM, temp, utilisation) |
| `lm_benchmark` | Benchmark modele (tokens/s) |
| `lm_perf_metrics` | Metriques performance cluster |

### Ollama (7)
| Outil | Description |
|-------|-------------|
| `ollama_query` | Query Ollama local |
| `ollama_models` | Lister modeles Ollama |
| `ollama_pull` | Telecharger un modele |
| `ollama_status` | Status Ollama |
| `ollama_web_search` | Recherche web via cloud (minimax/glm/kimi) |
| `ollama_subagents` | 3 sous-agents paralleles |
| `ollama_trading_analysis` | Analyse trading via Ollama |

### Scripts (3)
| Outil | Description |
|-------|-------------|
| `run_script` | Executer un script indexe (33 scripts) |
| `list_scripts` | Lister les scripts disponibles |
| `list_project_paths` | Lister les chemins projets |

### Windows (47)
| Categorie | Nombre | Exemples |
|-----------|--------|----------|
| Applications | 3 | open_app, close_app, open_url |
| Processus | 2 | kill_process, list_processes |
| Fenetres | 4 | focus_window, minimize, maximize, list_windows |
| Clavier/Souris | 4 | send_keys, click, type_text, hotkey |
| Clipboard | 2 | get_clipboard, set_clipboard |
| Fichiers | 9 | read_file, write_file, copy, move, delete, list, create, search |
| Audio | 3 | volume_up, volume_down, volume_mute |
| Ecran | 2 | screenshot, screen_resolution |
| Systeme | 8 | system_info, gpu_info, network, powershell, lock, shutdown, restart, sleep |
| Services | 3 | list_services, start_service, stop_service |
| Reseau | 3 | wifi_networks, ping, get_ip |
| Registre | 2 | registry_read, registry_write |
| Notifications | 3 | notify, speak, scheduled_tasks |

### Trading (5)
| Outil | Description |
|-------|-------------|
| `trading_pending_signals` | Signaux en attente |
| `trading_execute_signal` | Executer un signal |
| `trading_positions` | Positions ouvertes |
| `trading_status` | Status trading global |
| `trading_close_position` | Fermer une position |

### Brain (4)
| Outil | Description |
|-------|-------------|
| `brain_status` | Etat du cerveau auto-apprenant |
| `brain_analyze` | Analyser un pattern |
| `brain_suggest` | Suggestions basees sur l'historique |
| `brain_learn` | Apprendre un nouveau pattern |

### Skills (5)
| Outil | Description |
|-------|-------------|
| `list_skills` | 86+ skills dynamiques (16 vagues) |
| `create_skill` | Creer une nouvelle skill |
| `remove_skill` | Supprimer une skill |
| `suggest_actions` | Suggestions d'actions contextuelles |
| `action_history` | Historique des actions executees |

---

## n8n Workflow Etoile

### Configuration n8n

| Parametre | Valeur |
|-----------|--------|
| **Version** | v2.4.8 |
| **Port** | 5678 |
| **URL** | `http://127.0.0.1:5678` |
| **API Key** | Via X-N8N-API-KEY header (JWT) |
| **MCP Endpoint** | `http://127.0.0.1:5678/mcp-server/http` |
| **Auto-start** | Hook `startup.ps1` dans `.claude/hooks/` |

### Workflow "Etoile - JARVIS Commander Pipeline v10.3"

**ID** : `4Y2SrFR256HIFT42`
**Status** : ACTIF
**Trigger** : Webhook (`/webhook/etoile-commander`)

```
                    ┌──────────────────┐
                    │  Webhook Etoile  │  POST /webhook/etoile-commander
                    │  (Trigger)       │  Body: {"input": "votre prompt"}
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ 1. Classify      │  M1 qwen3-30b (5ms) / heuristique
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ 2. Route by Type │  Switch 8 branches
                    └──┬───┬───┬───┬───┘
                       │   │   │   │
          ┌────────────┘   │   │   └───────────────┐
          v                v   v                    v
  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
  │3a. M2 Code    │ │3b. M2 Analyse│ │3c. OL1 Trade │ │3d. OL1 Web     │
  │(champion 92%) │ │(deepseek)    │ │(web search)  │ │(qwen3:1.7b)    │
  └───────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────┘
          │                │                │                   │
          └────────┬───────┘────────┬───────┘───────────────────┘
                   v                v
          ┌──────────────────┐
          │4. M2 Verify      │  Score qualite 0.0-1.0
          │Quality (champion)│  JSON: {score, issues, recommendation}
          └────────┬─────────┘
                   │
                   v
          ┌──────────────────┐
          │5. Synthesize     │  Combine tous les resultats
          │(Code Node)       │  Retourne: {synthesis, timestamp, pipeline}
          └──────────────────┘
```

### Autres Workflows n8n

| Workflow | ID | Description |
|----------|-----|-------------|
| Trading Ultimate | `4ovJaOxtAzITyJEd` | Pipeline trading complet |
| Multi IA Consensus | `lJEz0hbG66DceXYA` | Consensus M2+OL1+M3+GEMINI |
| Ancrage Manager | `jGlSm9FWTYb7OKZF` | Gestion ancrages trading |
| Scanner Pro | `PruXHoV67xhxwRZC` | Scanner breakout avance |
| Telegram Signals | `HtIDKlxK6UWHJux8` | Alertes trading Telegram |
| CLAIRE Ultimate | `n7lQHhg1oWn9bs8c` | Scanner complet 5min |
| Cluster Monitor | `4vb15uEx3j4A9YPT` | Monitoring GPU/noeuds |
| Trading V2 Multi IA | `6ssOxO4AOlWiCKNY` | Trading multi-IA |

---

## Architecture Vocale — Pipeline v2 (2026-02-22)

```
Micro (Sony WH-1000XM4 Bluetooth, 16kHz)
       |
       v
 Wake Word (OpenWakeWord "jarvis", ~50ms, CPU)
 OU Push-to-Talk (Ctrl, fallback)
       |
       v
 Whisper Streaming (faster-whisper CUDA, beam=1, VAD 300ms)
 Protocole: SEGMENT: texte partiel -> DONE: texte complet
       |
       v
 Cache LRU (200 entrees)
  +----+----+
  |         |
  HIT      MISS
  |         |
  |    Correction Pipeline
  |    +-- Dictionnaire local (560 commandes, fuzzy match)
  |    +-- Si confiance >= 85%: bypass IA (method=local_fast)
  |    +-- OL1 qwen3:1.7b (correction IA, timeout 3s)
  |         |
  +----+----+
       |
       v
 Command Match (fuzzy matching, 955 cmds dont 156 pipelines)
       |
  +----+----+
  |         |
  v         v
MATCH     NO MATCH
(execute)  (Commander Mode)
  |          |
  |          v
  |     M2 pre-analyse (deepseek-coder, champion)
  |          |
  |          v
  |     Claude dispatche (COMMANDER_PROMPT)
  |
  +-- Si pipeline: execution multi-etapes (;;)
  +-- Si powershell/browser/app: execution directe
       |
       v
 TTS Streaming (Edge TTS, fr-FR-HenriNeural, +10%)
 Fallback: Windows SAPI / PowerShell MediaPlayer
```

| Parametre | Valeur |
|-----------|--------|
| Micro | Sony WH-1000XM4 Bluetooth |
| STT | faster-whisper CUDA, beam=1, streaming |
| Wake word | OpenWakeWord "jarvis" (seuil 0.7, cooldown 1s) |
| Fallback PTT | Ctrl (toujours disponible) |
| Exit confidence | >= 0.85 |
| Commandes | **955 commandes vocales** (dont 156 pipelines) |
| TTS | Edge TTS fr-FR-HenriNeural (+10% rate) |
| Cache | LRU 200 entrees, ~80% commandes en cache |
| Correction IA | OL1 qwen3:1.7b (0.5s, timeout 3s) |
| Warm-up | Ping OL1 toutes les 60s (keep model in GPU) |
| Latence cible | < 1s (cache/local) / < 2s (IA) / < 3s (complexe) |

> **Detail complet des 955 commandes vocales** : voir [`docs/COMMANDES_VOCALES.md`](docs/COMMANDES_VOCALES.md)

---

## Trading MEXC Futures

| Parametre | Valeur |
|-----------|--------|
| **Exchange** | MEXC Futures |
| **Levier** | 10x |
| **Paires** | BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK |
| **TP** | 0.4% |
| **SL** | 0.25% |
| **Taille** | 10 USDT par position |
| **Score min** | 70/100 |
| **DRY_RUN** | false (production) |

### Scripts Trading Indexes

| Script | Chemin | Description |
|--------|--------|-------------|
| mexc_scanner | carV1/python_scripts/scanners/ | Scanner MEXC |
| breakout_detector | carV1/python_scripts/scanners/ | Detection breakout |
| sniper_breakout | carV1/python_scripts/ | Sniper precis |
| hyper_scan_v2 | carV1/python_scripts/ | Scan hyperactif |
| pipeline_intensif_v2 | PROD_INTENSIVE_V1/scripts/ | Pipeline autonome |

---

## Modes de Lancement

| Mode | Flag | Launcher | Description |
|------|------|----------|-------------|
| Interactif | `-i` (defaut) | `JARVIS_VOICE.bat` | REPL Commander |
| Commandant | `-c` | `JARVIS_COMMANDER.bat` | Commander explicite |
| Vocal | `-v` | `JARVIS_VOICE.bat` | Push-to-talk CTRL |
| Hybride | `-k` | `JARVIS_KEYBOARD.bat` | Clavier + TTS |
| Ollama | `-o` | `JARVIS_OLLAMA.bat` | Cloud gratuit |
| One-shot | `"prompt"` | - | Requete unique |
| Status | `-s` | `JARVIS_STATUS.bat` | Cluster check |

**TOUS les modes utilisent le COMMANDER_PROMPT par defaut.**

### Launchers (.bat)

| Launcher | Description |
|----------|-------------|
| `JARVIS_VOICE.bat` | Mode vocal complet |
| `JARVIS_KEYBOARD.bat` | Mode clavier + TTS |
| `JARVIS_COMMANDER.bat` | Commander explicite |
| `JARVIS_STATUS.bat` | Status cluster |
| `JARVIS_OLLAMA.bat` | Mode Ollama cloud |
| `JARVIS_BOOT.bat` | Boot cluster M1+M2 |
| `JARVIS_FINETUNE.bat` | Pipeline fine-tuning |
| `JARVIS_DASHBOARD.bat` | Dashboard web |
| `PIPELINE_10.bat` | 10 paires trading |
| `SNIPER.bat` | Sniper breakout |
| `SNIPER_10.bat` | Sniper 10 paires |
| `TRIDENT.bat` | Triple strategie |
| `SCAN_HYPER.bat` | Scan hyperactif |
| `MONITOR_RIVER.bat` | Monitor flux |

---

## Structure du Projet

```
F:\BUREAU\turbo\
|-- main.py                      # Point d'entree (7 modes: -i -c -v -k -o -s "prompt")
|-- pyproject.toml               # Dependencies (uv, Python 3.13)
|-- gemini-proxy.js              # Proxy Gemini 3 Pro/Flash (timeout 2min, fallback 4 modeles)
|-- benchmark_cluster.py         # Benchmark cluster 7 phases (health/inference/consensus/...)
|-- benchmark_real_test.py       # Benchmark reel 10 niveaux de difficulte
|-- CLAUDE_MULTI_AGENT.md        # Protocole MAO complet
|-- .env                         # Variables d'env (API keys, DB paths)
|-- .gitignore                   # .env, .venv/, __pycache__/, *.db, logs/
|
|-- src/
|   |-- __init__.py              # Package init
|   |-- orchestrator.py          # Moteur principal + COMMANDER_PROMPT + run_*()
|   |-- commander.py             # Pipeline Commander (classify/decompose/verify/synthesize)
|   |-- config.py                # Config cluster + routage benchmark-tuned + thermal
|   |-- agents.py                # 7 agents Claude SDK (deep/fast/check/trading/system/bridge/consensus)
|   |-- tools.py                 # 87 outils MCP SDK (IA, Windows, Trading, Brain, Skills)
|   |-- mcp_server.py            # Serveur MCP stdio pour Claude Code (87 handlers)
|   |-- commands.py              # 955 commandes vocales (18 vagues + 4 extensions categories)
|   |-- commands_pipelines.py    # 144 pipelines multi-etapes (modes, routines, Comet, dev, lifestyle)
|   |-- commands_navigation.py   # 121 commandes navigation (social, IA, services, recherche)
|   |-- commands_maintenance.py  # 126 commandes maintenance (monitoring, nettoyage, securite, inventaire)
|   |-- commands_dev.py          # 100 commandes dev (git, ollama, docker, python, winget, WSL)
|   |-- skills.py                # 86+ skills dynamiques (16 vagues)
|   |-- voice.py                 # Whisper STT + SAPI TTS + push-to-talk
|   |-- voice_correction.py      # Pipeline correction vocale (dict + OL1)
|   |-- cluster_startup.py       # Boot cluster + thermal monitoring + GPU stats
|   |-- trading.py               # Trading MEXC Futures (CCXT)
|   |-- brain.py                 # Auto-apprentissage (patterns, suggestions)
|   |-- executor.py              # Execution commandes/skills
|   |-- windows.py               # API Windows (PowerShell, COM, WMI)
|   |-- database.py              # SQLite persistence (jarvis.db)
|   |-- scenarios.py             # 79+ scenarios validation (tests)
|   |-- output.py                # Schema sortie JSON
|   |-- whisper_worker.py        # Worker Whisper persistent (process separe)
|   |-- dashboard.py             # API dashboard REST
|   |-- systray.py               # System tray icon (Windows)
|
|-- dashboard/
|   |-- server.py                # Serveur HTTP dashboard (stdlib, zero dep)
|   |-- index.html               # UI dashboard (HTML/CSS/JS)
|
|-- data/
|   |-- jarvis.db                # Base SQLite principale (6 tables)
|   |-- benchmark_report.json    # Rapport benchmark cluster
|   |-- benchmark_real_report.json # Rapport benchmark reel 10 niveaux
|   |-- skills.json              # Skills persistantes
|   |-- brain_state.json         # Etat cerveau auto-apprenant
|   |-- jarvis_m1_prompt.txt     # Prompt compact pour M1
|   |-- action_history.json      # Historique actions
|   |-- etoile_workflow.json     # Workflow n8n Etoile (backup)
|
|-- launchers/                   # 14 fichiers .bat
|-- finetuning/                  # Pipeline QLoRA (Qwen3-30B, 55k exemples)
|-- scripts/                     # Scripts startup M1/M2
```

---

## Bases de Donnees

| Base | Chemin | Tables | Usage |
|------|--------|--------|-------|
| **jarvis.db** | `F:\BUREAU\turbo\data\` | 6 (skills, actions, historique...) | Base principale JARVIS |
| **etoile.db** | `F:\BUREAU\` | 6 (agents, api_keys, skills_log, sessions, memories, metrics) | Orchestration distribuee |
| **trading_latest.db** | `F:\BUREAU\carV1\database\` | trades, signaux | Trading carV1 |
| **trading.db** | `F:\BUREAU\TRADING_V2_PRODUCTION\database\` | predictions | Trading v2 |

---

## Installation & Configuration

### Prerequis

- Windows 11 Pro
- Python 3.13
- uv v0.10.2 (`C:\Users\franc\.local\bin\uv.exe`)
- CUDA (pour Whisper + LM Studio)
- LM Studio (M1 + M2 + M3)
- Ollama v0.16.1
- Node.js (pour gemini-proxy.js)
- Gemini CLI v0.25.1
- n8n v2.4.8

### Installation

```bash
cd F:\BUREAU\turbo
uv sync

# Configurer .env
cp .env.example .env
# Editer avec vos cles API
```

### Lancer

```bash
# Interactif (Commander par defaut)
uv run python main.py

# Mode vocal
uv run python main.py -v

# Commander explicite
uv run python main.py -c

# Hybride (clavier + TTS)
uv run python main.py -k

# Status cluster
uv run python main.py -s

# One-shot
uv run python main.py "scanne le marche crypto"
```

### Notes Techniques Windows

- **TOUJOURS** utiliser `127.0.0.1` au lieu de `localhost` (IPv6 = +10s latence)
- PowerShell: `$_` est mange par bash → ecrire des fichiers .ps1
- uv: `powershell -Command "& 'C:\Users\franc\.local\bin\uv.exe' ..."`

---

## Appels API — Exemples Complets

### Query M2 Champion (API native v1)

```bash
curl -s http://192.168.1.26:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" \
  -d '{
    "model": "deepseek-coder-v2-lite-instruct",
    "input": "Ecris un decorateur Python de cache LRU",
    "temperature": 0.3,
    "max_output_tokens": 8192,
    "stream": false,
    "store": false
  }'
# Reponse: {"output":[{"content":"..."}], "stats":{"total_output_tokens":...}}
```

### Consensus Multi-Noeuds

```bash
# M2 + OL1 + M3 + M1 + GEMINI en parallele, puis synthese
# Voir src/tools.py → consensus()
# Ou via MCP: mcp__jarvis__consensus
```

### Trading Signal

```bash
# Via l'agent ia-trading + run_script(mexc_scanner)
uv run python main.py "scanne BTC ETH SOL pour breakout"
```

### Gemini Architecture Review

```bash
node F:/BUREAU/turbo/gemini-proxy.js --json \
  "Review l'architecture de ce pipeline Commander. Points forts et faiblesses?"
```

---

## Protocole MAO (Multi-Agent Orchestrator)

Documentation complete: `CLAUDE_MULTI_AGENT.md`

### Commandes MAO

| Commande | Action |
|----------|--------|
| `MAO check` | Health check M1+M2+M3+OL1+Gemini (5 noeuds) |
| `MAO consensus [question]` | Question sur M2+OL1+M3+GEMINI, synthese |
| `MAO code [description]` | M2 code → M3 review → presentation |
| `MAO archi [sujet]` | GEMINI avis → M2 validation |

### Matrice MAO (benchmark-tuned)

| Tache | Principal | Secondaire | Verificateur |
|-------|-----------|------------|--------------|
| Code nouveau | M2 (champion) | M3 (review) | GEMINI (archi) |
| Bug fix | M2 | M3 (patch) | - |
| Architecture | GEMINI | M2 (faisabilite) | - |
| Refactoring | M2 | M3 (validation) | - |
| Trading | OL1 (web) | M2 (analyse) | - |
| Question simple | OL1 (0.5s) | M3 (2.5s) | - |
| Recherche web | OL1-cloud | GEMINI | - |
| Consensus critique | M2+OL1+M3+GEMINI | Vote pondere | - |
| Embedding | M1 (seul use case) | - | - |

---

## Fine-Tuning

| Parametre | Valeur |
|-----------|--------|
| **Dossier** | `F:\BUREAU\turbo\finetuning\` |
| **Methode** | QLoRA 4-bit + PEFT LoRA |
| **Modele base** | Qwen3-30B-A3B |
| **Dataset** | 55,549 exemples |
| **Launcher** | `JARVIS_FINETUNE.bat` |

**IMPORTANT** : Arreter LM Studio AVANT de lancer le training (conflits GPU).

---

## Dashboard

| Parametre | Valeur |
|-----------|--------|
| **URL** | `http://127.0.0.1:8080` |
| **API** | `/api/cluster` |
| **Server** | `dashboard/server.py` (stdlib, zero dep) |
| **UI** | `dashboard/index.html` |
| **Launcher** | `JARVIS_DASHBOARD.bat` |

---

## Disques

| Disque | Capacite | Libre | Contenu |
|--------|----------|-------|---------|
| **C:\\** | 476 GB | ~82 GB | Systeme, Python, uv |
| **F:\\** | 446 GB | ~104 GB | Projets, modeles LM Studio (~300 GB) |

---



## 955 Commandes Vocales — Liste Complete

**955 commandes** au total dont **156 pipelines** multi-etapes.
Reparties en **14 categories**.

| Categorie | Nb | Description |
|-----------|-----|------------|
| **accessibilite** | 10 | taille_texte_grand, clavier_virtuel, filtre_couleur... |
| **app** | 23 | ouvrir_vscode, ouvrir_terminal, ouvrir_lmstudio... |
| **clipboard** | 13 | copier, coller, couper... |
| **dev** | 115 | docker_ps, docker_images, docker_stop_all... |
| **fenetre** | 13 | minimiser_tout, alt_tab, fermer_fenetre... |
| **fichiers** | 32 | ouvrir_documents, ouvrir_bureau, ouvrir_dossier... |
| **jarvis** | 12 | historique_commandes, jarvis_aide, jarvis_stop... |
| **launcher** | 12 | launch_pipeline_10, launch_sniper_10, launch_sniper_breakout... |
| **media** | 7 | media_play_pause, media_next, media_previous... |
| **navigation** | 148 | ouvrir_chrome, ouvrir_comet, aller_sur_site... |
| **pipeline** | 156 | range_bureau, va_sur_mails_comet, mode_travail... |
| **saisie** | 4 | texte_majuscule, texte_minuscule, ouvrir_emojis... |
| **systeme** | 391 | verrouiller, eteindre, redemarrer... |
| **trading** | 19 | scanner_marche, detecter_breakout, pipeline_trading... |

<details>
<summary><strong>Liste complete des 812 commandes (cliquez pour derouler)</strong></summary>

### ACCESSIBILITE (10)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `taille_texte_grand` | ms_settings | Agrandir la taille du texte systeme | texte plus grand, agrandis le texte |
| `clavier_virtuel` | powershell | Ouvrir le clavier virtuel | clavier virtuel, ouvre le clavier virtuel |
| `filtre_couleur` | ms_settings | Activer/desactiver le filtre de couleur | filtre de couleur, active le filtre couleur |
| `sous_titres` | ms_settings | Parametres des sous-titres | sous-titres, parametres sous-titres |
| `contraste_eleve_toggle` | powershell | Activer/desactiver le contraste eleve | contraste eleve, high contrast |
| `sous_titres_live` | powershell | Activer les sous-titres en direct | sous titres en direct, live captions |
| `filtre_couleur_toggle` | powershell | Activer les filtres de couleur | filtre de couleur, color filter |
| `taille_curseur` | powershell | Changer la taille du curseur | agrandis le curseur, curseur plus grand |
| `narrateur_toggle` | powershell | Activer/desactiver le narrateur | active le narrateur, narrateur windows |
| `sticky_keys_toggle` | powershell | Activer/desactiver les touches remanentes | active les touches remanentes, desactive les touches remanentes |

### APP (23)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_vscode` | app_open | Ouvrir Visual Studio Code | ouvre vscode, ouvrir vscode |
| `ouvrir_terminal` | app_open | Ouvrir un terminal | ouvre le terminal, ouvrir le terminal |
| `ouvrir_lmstudio` | app_open | Ouvrir LM Studio | ouvre lm studio, lance lm studio |
| `ouvrir_discord` | app_open | Ouvrir Discord | ouvre discord, lance discord |
| `ouvrir_spotify` | app_open | Ouvrir Spotify | ouvre spotify, lance spotify |
| `ouvrir_task_manager` | app_open | Ouvrir le gestionnaire de taches | ouvre le gestionnaire de taches, task manager |
| `ouvrir_notepad` | app_open | Ouvrir Notepad | ouvre notepad, ouvre bloc notes |
| `ouvrir_calculatrice` | app_open | Ouvrir la calculatrice | ouvre la calculatrice, lance la calculatrice |
| `fermer_app` | jarvis_tool | Fermer une application | ferme {app}, fermer {app} |
| `ouvrir_app` | app_open | Ouvrir une application par nom | ouvre {app}, ouvrir {app} |
| `ouvrir_paint` | app_open | Ouvrir Paint | ouvre paint, lance paint |
| `ouvrir_wordpad` | app_open | Ouvrir WordPad | ouvre wordpad, lance wordpad |
| `ouvrir_snipping` | app_open | Ouvrir l'Outil Capture | ouvre l'outil capture, lance l'outil capture |
| `ouvrir_magnifier` | hotkey | Ouvrir la loupe Windows | ouvre la loupe windows, loupe windows |
| `fermer_loupe` | hotkey | Fermer la loupe Windows | ferme la loupe, desactive la loupe |
| `ouvrir_obs` | app_open | Ouvrir OBS Studio | ouvre obs, lance obs |
| `ouvrir_vlc` | app_open | Ouvrir VLC Media Player | ouvre vlc, lance vlc |
| `ouvrir_7zip` | app_open | Ouvrir 7-Zip | ouvre 7zip, lance 7zip |
| `store_ouvrir` | powershell | Ouvrir le Microsoft Store | ouvre le store, microsoft store |
| `store_updates` | powershell | Verifier les mises a jour du Store | mises a jour store, store updates |
| `ouvrir_phone_link` | powershell | Ouvrir Phone Link (liaison telephone) | ouvre phone link, liaison telephone |
| `terminal_settings` | powershell | Ouvrir les parametres Windows Terminal | parametres du terminal, reglages terminal |
| `copilot_lancer` | hotkey | Lancer Windows Copilot | lance copilot, ouvre copilot |

### CLIPBOARD (13)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `copier` | hotkey | Copier la selection | copie, copier |
| `coller` | hotkey | Coller le contenu | colle, coller |
| `couper` | hotkey | Couper la selection | coupe, couper |
| `tout_selectionner` | hotkey | Selectionner tout | selectionne tout, tout selectionner |
| `annuler` | hotkey | Annuler la derniere action | annule, annuler |
| `ecrire_texte` | jarvis_tool | Ecrire du texte au clavier | ecris {texte}, tape {texte} |
| `sauvegarder` | hotkey | Sauvegarder le fichier actif | sauvegarde, enregistre |
| `refaire` | hotkey | Refaire la derniere action annulee | refais, redo |
| `recherche_page` | hotkey | Rechercher dans la page | recherche dans la page, cherche dans la page |
| `lire_presse_papier` | jarvis_tool | Lire le contenu du presse-papier | lis le presse-papier, qu'est-ce qui est copie |
| `historique_clipboard` | hotkey | Historique du presse-papier | historique du presse-papier, clipboard history |
| `clipboard_historique` | hotkey | Ouvrir l'historique du presse-papier | historique presse papier, clipboard history |
| `coller_sans_format` | hotkey | Coller sans mise en forme | colle sans format, coller sans mise en forme |

### DEV (115)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `docker_ps` | powershell | Lister les conteneurs Docker | liste les conteneurs, docker ps |
| `docker_images` | powershell | Lister les images Docker | images docker, docker images |
| `docker_stop_all` | powershell | Arreter tous les conteneurs Docker | arrete tous les conteneurs, docker stop all |
| `git_status` | powershell | Git status du projet courant | git status, statut git |
| `git_log` | powershell | Git log recent | git log, historique git |
| `git_pull` | powershell | Git pull origin main | git pull, tire les changements |
| `git_push` | powershell | Git push origin main | git push, pousse les commits |
| `pip_list` | powershell | Lister les packages Python installes | pip list, packages python |
| `python_version` | powershell | Version Python et uv | version python, quelle version python |
| `ouvrir_n8n` | browser | Ouvrir n8n dans le navigateur | ouvre n8n, lance n8n |
| `lm_studio_restart` | powershell | Relancer LM Studio | relance lm studio, redemarre lm studio |
| `ouvrir_jupyter` | browser | Ouvrir Jupyter dans le navigateur | ouvre jupyter, lance jupyter |
| `wsl_lancer` | powershell | Lancer WSL (Windows Subsystem for Linux) | lance wsl, ouvre wsl |
| `wsl_liste` | powershell | Lister les distributions WSL installees | liste les distributions wsl, wsl liste |
| `wsl_shutdown` | powershell | Arreter toutes les distributions WSL | arrete wsl, stoppe wsl |
| `git_branches` | powershell | Lister les branches git | branches git, quelles branches |
| `git_diff` | powershell | Voir les modifications non commitees | git diff, modifications en cours |
| `git_stash` | powershell | Sauvegarder les modifications en stash | git stash, stash les changements |
| `git_stash_pop` | powershell | Restaurer les modifications du stash | git stash pop, restaure le stash |
| `git_last_commit` | powershell | Voir le dernier commit en detail | dernier commit, last commit |
| `git_count` | powershell | Compter les commits du projet | combien de commits, nombre de commits |
| `node_version` | powershell | Version de Node.js | version node, quelle version node |
| `npm_list_global` | powershell | Packages NPM globaux | packages npm globaux, npm global |
| `ollama_restart` | powershell | Redemarrer Ollama | redemarre ollama, restart ollama |
| `ollama_pull` | powershell | Telecharger un modele Ollama | telecharge le modele {model}, ollama pull {model} |
| `ollama_list` | powershell | Lister les modeles Ollama installes | liste les modeles ollama, modeles ollama installes |
| `ollama_remove` | powershell | Supprimer un modele Ollama | supprime le modele {model}, ollama rm {model} |
| `lm_studio_models` | powershell | Modeles charges dans LM Studio (M1, M2, M3) | modeles lm studio, quels modeles lm studio |
| `uv_sync` | powershell | Synchroniser les dependances uv | uv sync, synchronise les dependances |
| `python_test` | powershell | Lancer les tests Python du projet | lance les tests, run tests |
| `python_lint` | powershell | Verifier le code avec ruff | lint le code, ruff check |
| `docker_logs` | powershell | Voir les logs d'un conteneur Docker | logs docker de {container}, docker logs {container} |
| `docker_restart` | powershell | Redemarrer un conteneur Docker | redemarre le conteneur {container}, docker restart {container} |
| `docker_prune` | powershell | Nettoyer les ressources Docker inutilisees | nettoie docker, docker prune |
| `docker_stats` | powershell | Statistiques des conteneurs Docker | stats docker, docker stats |
| `turbo_lines` | powershell | Compter les lignes de code du projet turbo | combien de lignes de code, lignes de code turbo |
| `turbo_size` | powershell | Taille totale du projet turbo | taille du projet turbo, poids du projet |
| `turbo_files` | powershell | Compter les fichiers du projet turbo | combien de fichiers turbo, nombre de fichiers |
| `lms_status` | powershell | Statut du serveur LM Studio local | statut lm studio, lm studio status |
| `lms_list_loaded` | powershell | Modeles actuellement charges dans LM Studio local | modeles charges locaux, lms loaded |
| `lms_load_model` | powershell | Charger un modele dans LM Studio local | charge le modele {model}, lms load {model} |
| `lms_unload_model` | powershell | Decharger un modele de LM Studio local | decharge le modele {model}, lms unload {model} |
| `lms_list_available` | powershell | Lister les modeles disponibles sur le disque | modeles disponibles lm studio, lms list |
| `git_status_turbo` | powershell | Statut git du projet turbo | git status, statut git |
| `git_log_short` | powershell | Derniers 10 commits (resume) | historique git, git log |
| `git_remote_info` | powershell | Informations sur le remote git | remote git, git remote |
| `ouvrir_telegram` | app_open | Ouvrir Telegram Desktop | ouvre telegram, lance telegram |
| `ouvrir_whatsapp` | app_open | Ouvrir WhatsApp Desktop | ouvre whatsapp, lance whatsapp |
| `ouvrir_slack` | app_open | Ouvrir Slack Desktop | ouvre slack, lance slack |
| `ouvrir_teams` | app_open | Ouvrir Microsoft Teams | ouvre teams, lance teams |
| `ouvrir_zoom` | app_open | Ouvrir Zoom | ouvre zoom, lance zoom |
| `bun_version` | powershell | Version de Bun | version bun, quelle version bun |
| `deno_version` | powershell | Version de Deno | version deno, quelle version deno |
| `rust_version` | powershell | Version de Rust/Cargo | version rust, quelle version rust |
| `python_uv_version` | powershell | Version de Python et uv | version python, quelle version python |
| `turbo_recent_changes` | powershell | Fichiers modifies recemment dans turbo | fichiers recents turbo, modifications recentes |
| `turbo_todo` | powershell | Lister les TODO dans le code turbo | liste les todo, todo dans le code |
| `git_blame_file` | powershell | Git blame sur un fichier | git blame de {fichier}, blame {fichier} |
| `git_clean_branches` | powershell | Nettoyer les branches git mergees | nettoie les branches, clean branches |
| `git_contributors` | powershell | Lister les contributeurs du projet | contributeurs git, qui a contribue |
| `git_file_history` | powershell | Historique d'un fichier | historique du fichier {fichier}, git log de {fichier} |
| `git_undo_last` | powershell | Annuler le dernier commit (soft reset) | annule le dernier commit, undo last commit |
| `npm_audit` | powershell | Audit de securite NPM | npm audit, audit securite npm |
| `npm_outdated` | powershell | Packages NPM obsoletes | npm outdated, packages npm a jour |
| `pip_outdated` | powershell | Packages Python obsoletes | pip outdated, packages python a mettre a jour |
| `python_repl` | powershell | Lancer un REPL Python | lance python, python repl |
| `kill_port` | powershell | Tuer le processus sur un port specifique | tue le port {port}, kill port {port} |
| `qui_ecoute_port` | powershell | Quel processus ecoute sur un port | qui ecoute sur le port {port}, quel process sur {port} |
| `ports_dev_status` | powershell | Statut des ports dev courants (3000, 5173, 8080, 8000, 9742) | statut des ports dev, ports dev |
| `ollama_vram_detail` | powershell | Detail VRAM utilisee par chaque modele Ollama | vram ollama detail, ollama vram |
| `ollama_stop_all` | powershell | Decharger tous les modeles Ollama de la VRAM | decharge tous les modeles ollama, ollama stop all |
| `git_reflog` | powershell | Voir le reflog git (historique complet) | git reflog, reflog |
| `git_tag_list` | powershell | Lister les tags git | tags git, git tags |
| `git_search_commits` | powershell | Rechercher dans les messages de commit | cherche dans les commits {requete}, git search {requete} |
| `git_repo_size` | powershell | Taille du depot git | taille du repo git, poids du git |
| `git_stash_list` | powershell | Lister les stash git | liste les stash, git stash list |
| `git_diff_staged` | powershell | Voir les modifications stagees (pret a commit) | diff staged, git diff staged |
| `docker_images_list` | powershell | Lister les images Docker locales | images docker, docker images |
| `docker_volumes` | powershell | Lister les volumes Docker | volumes docker, docker volumes |
| `docker_networks` | powershell | Lister les reseaux Docker | reseaux docker, docker networks |
| `docker_disk_usage` | powershell | Espace disque utilise par Docker | espace docker, docker disk usage |
| `wsl_status` | powershell | Statut de WSL et distributions installees | statut wsl, wsl status |
| `winget_search` | powershell | Rechercher un package via winget | winget search {requete}, cherche {requete} sur winget |
| `winget_list_installed` | powershell | Lister les apps installees via winget | winget list, apps winget |
| `winget_upgrade_all` | powershell | Mettre a jour toutes les apps via winget | winget upgrade all, mets a jour tout winget |
| `code_extensions_list` | powershell | Lister les extensions VSCode installees | extensions vscode, liste les extensions |
| `code_install_ext` | powershell | Installer une extension VSCode | installe l'extension {ext}, vscode install {ext} |
| `ssh_keys_list` | powershell | Lister les cles SSH | cles ssh, ssh keys |
| `npm_cache_clean` | powershell | Nettoyer le cache NPM | nettoie le cache npm, npm cache clean |
| `uv_pip_tree` | powershell | Arbre de dependances Python du projet | arbre de dependances, pip tree |
| `pip_show_package` | powershell | Details d'un package Python installe | details du package {package}, pip show {package} |
| `turbo_imports` | powershell | Imports utilises dans le projet turbo | imports du projet, quels imports |
| `python_format_check` | powershell | Verifier le formatage Python avec ruff format | verifie le formatage, ruff format check |
| `python_type_check` | powershell | Verifier les types Python (pyright/mypy) | verifie les types, type check |
| `curl_test_endpoint` | powershell | Tester un endpoint HTTP | teste l'endpoint {url}, curl {url} |
| `n8n_workflows_list` | powershell | Lister les workflows n8n actifs | workflows n8n, liste les workflows |
| `git_worktree_list` | powershell | Lister les worktrees git | worktrees git, git worktrees |
| `git_submodule_status` | powershell | Statut des submodules git | submodules git, git submodules |
| `git_cherry_unpicked` | powershell | Commits non cherry-picked entre branches | git cherry, commits non picks |
| `git_branch_age` | powershell | Age de chaque branche git | age des branches, branches vieilles |
| `git_commit_stats` | powershell | Statistiques de commits (par jour/semaine) | stats commits, frequence commits |
| `docker_compose_up` | powershell | Docker compose up (demarrer les services) | docker compose up, lance les conteneurs |
| `docker_compose_down` | powershell | Docker compose down (arreter les services) | docker compose down, arrete les conteneurs |
| `docker_compose_logs` | powershell | Voir les logs Docker Compose | logs docker compose, compose logs |
| `docker_compose_ps` | powershell | Statut des services Docker Compose | services docker compose, compose ps |
| `uv_cache_clean` | powershell | Nettoyer le cache uv | nettoie le cache uv, uv cache clean |
| `uv_pip_install` | powershell | Installer un package Python via uv | installe {package} python, uv pip install {package} |
| `turbo_test_file` | powershell | Lancer un fichier de test specifique | teste le fichier {fichier}, pytest {fichier} |
| `turbo_coverage` | powershell | Couverture de tests du projet turbo | coverage turbo, couverture de tests |
| `process_tree` | powershell | Arbre des processus actifs | arbre des processus, process tree |
| `openssl_version` | powershell | Version d'OpenSSL | version openssl, openssl version |
| `git_version` | powershell | Version de Git | version git, git version |
| `cuda_version` | powershell | Version de CUDA installee | version cuda, cuda version |
| `powershell_version` | powershell | Version de PowerShell | version powershell, powershell version |
| `dotnet_version` | powershell | Versions de .NET installees | version dotnet, dotnet version |

### FENETRE (13)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `minimiser_tout` | hotkey | Minimiser toutes les fenetres | minimise tout, montre le bureau |
| `alt_tab` | hotkey | Basculer entre les fenetres | change de fenetre, fenetre suivante |
| `fermer_fenetre` | hotkey | Fermer la fenetre active | ferme la fenetre, ferme ca |
| `maximiser_fenetre` | hotkey | Maximiser la fenetre active | maximise, plein ecran |
| `minimiser_fenetre` | hotkey | Minimiser la fenetre active | minimise, reduis la fenetre |
| `fenetre_gauche` | hotkey | Fenetre a gauche | fenetre a gauche, mets a gauche |
| `fenetre_droite` | hotkey | Fenetre a droite | fenetre a droite, mets a droite |
| `focus_fenetre` | jarvis_tool | Mettre le focus sur une fenetre | focus sur {titre}, va sur la fenetre {titre} |
| `liste_fenetres` | jarvis_tool | Lister les fenetres ouvertes | quelles fenetres sont ouvertes, liste les fenetres |
| `fenetre_haut_gauche` | powershell | Fenetre en haut a gauche | fenetre en haut a gauche, snap haut gauche |
| `fenetre_haut_droite` | powershell | Fenetre en haut a droite | fenetre en haut a droite, snap haut droite |
| `fenetre_bas_gauche` | powershell | Fenetre en bas a gauche | fenetre en bas a gauche, snap bas gauche |
| `fenetre_bas_droite` | powershell | Fenetre en bas a droite | fenetre en bas a droite, snap bas droite |

### FICHIERS (32)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_documents` | powershell | Ouvrir le dossier Documents | ouvre mes documents, ouvrir mes documents |
| `ouvrir_bureau` | powershell | Ouvrir le dossier Bureau | ouvre le bureau, ouvrir le bureau |
| `ouvrir_dossier` | powershell | Ouvrir un dossier specifique | ouvre le dossier {dossier}, ouvrir le dossier {dossier} |
| `ouvrir_telechargements` | powershell | Ouvrir Telechargements | ouvre les telechargements, ouvre mes telechargements |
| `ouvrir_images` | powershell | Ouvrir le dossier Images | ouvre mes images, ouvre mes photos |
| `ouvrir_musique` | powershell | Ouvrir le dossier Musique | ouvre ma musique, ouvre le dossier musique |
| `ouvrir_projets` | powershell | Ouvrir le dossier projets | ouvre mes projets, va dans les projets |
| `ouvrir_explorateur` | hotkey | Ouvrir l'explorateur de fichiers | ouvre l'explorateur, ouvre l'explorateur de fichiers |
| `lister_dossier` | jarvis_tool | Lister le contenu d'un dossier | que contient {dossier}, liste le dossier {dossier} |
| `creer_dossier` | jarvis_tool | Creer un nouveau dossier | cree un dossier {nom}, nouveau dossier {nom} |
| `chercher_fichier` | jarvis_tool | Chercher un fichier | cherche le fichier {nom}, trouve le fichier {nom} |
| `ouvrir_recents` | powershell | Ouvrir les fichiers recents | fichiers recents, ouvre les recents |
| `ouvrir_temp` | powershell | Ouvrir le dossier temporaire | ouvre le dossier temp, fichiers temporaires |
| `ouvrir_appdata` | powershell | Ouvrir le dossier AppData | ouvre appdata, dossier appdata |
| `espace_dossier` | powershell | Taille d'un dossier | taille du dossier {dossier}, combien pese {dossier} |
| `nombre_fichiers` | powershell | Compter les fichiers dans un dossier | combien de fichiers dans {dossier}, nombre de fichiers {dossier} |
| `compresser_dossier` | powershell | Compresser un dossier en ZIP | compresse {dossier}, zip {dossier} |
| `decompresser_zip` | powershell | Decompresser un fichier ZIP | decompresse {fichier}, unzip {fichier} |
| `hash_fichier` | powershell | Calculer le hash SHA256 d'un fichier | hash de {fichier}, sha256 de {fichier} |
| `chercher_contenu` | powershell | Chercher du texte dans les fichiers | cherche {texte} dans les fichiers, grep {texte} |
| `derniers_fichiers` | powershell | Derniers fichiers modifies | derniers fichiers modifies, fichiers recents |
| `doublons_fichiers` | powershell | Trouver les fichiers en double | fichiers en double, doublons |
| `gros_fichiers` | powershell | Trouver les plus gros fichiers | plus gros fichiers, fichiers les plus lourds |
| `fichiers_type` | powershell | Lister les fichiers d'un type | fichiers {ext}, tous les {ext} |
| `renommer_masse` | powershell | Renommer des fichiers en masse | renomme les fichiers {ancien} en {nouveau}, remplace {ancien} par {nouveau} dans les noms |
| `dossiers_vides` | powershell | Trouver les dossiers vides | dossiers vides, repertoires vides |
| `proprietes_fichier` | powershell | Proprietes detaillees d'un fichier | proprietes de {fichier}, details de {fichier} |
| `copier_fichier` | powershell | Copier un fichier vers un dossier | copie {source} dans {destination}, copie {source} vers {destination} |
| `deplacer_fichier` | powershell | Deplacer un fichier | deplace {source} dans {destination}, deplace {source} vers {destination} |
| `explorer_nouvel_onglet` | powershell | Nouvel onglet dans l'Explorateur | nouvel onglet explorateur, onglet explorateur |
| `dossier_captures` | powershell | Ouvrir le dossier captures d'ecran | dossier captures, ouvre les captures |
| `taille_dossiers_bureau` | powershell | Taille de chaque dossier dans F:\BUREAU | taille des projets, poids des dossiers bureau |

### JARVIS (12)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `historique_commandes` | powershell | Voir l'historique des commandes JARVIS | historique des commandes, quelles commandes j'ai utilise |
| `jarvis_aide` | list_commands | Afficher l'aide JARVIS | aide, help |
| `jarvis_stop` | exit | Arreter JARVIS | jarvis stop, jarvis arrete |
| `jarvis_repete` | jarvis_repeat | Repeter la derniere reponse | repete, redis |
| `jarvis_scripts` | jarvis_tool | Lister les scripts disponibles | quels scripts sont disponibles, liste les scripts |
| `jarvis_projets` | jarvis_tool | Lister les projets indexes | quels projets existent, liste les projets |
| `jarvis_notification` | jarvis_tool | Envoyer une notification | notifie {message}, notification {message} |
| `jarvis_skills` | list_commands | Lister les skills/pipelines appris | quels skills existent, liste les skills |
| `jarvis_suggestions` | list_commands | Suggestions d'actions | que me suggeres tu, suggestions |
| `jarvis_brain_status` | jarvis_tool | Etat du cerveau JARVIS | etat du cerveau, brain status |
| `jarvis_brain_learn` | jarvis_tool | Apprendre de nouveaux patterns | apprends, brain learn |
| `jarvis_brain_suggest` | jarvis_tool | Demander une suggestion de skill a l'IA | suggere un skill, brain suggest |

### LAUNCHER (12)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `launch_pipeline_10` | script | Lancer le Pipeline 10 Cycles | lance le pipeline 10 cycles, pipeline 10 cycles |
| `launch_sniper_10` | script | Lancer le Sniper 10 Cycles | lance le sniper 10 cycles, sniper 10 cycles |
| `launch_sniper_breakout` | script | Lancer le Sniper Breakout | lance sniper breakout, sniper breakout |
| `launch_trident` | script | Lancer Trident Execute (dry run) | lance trident, trident execute |
| `launch_hyper_scan` | script | Lancer l'Hyper Scan V2 | lance hyper scan, hyper scan v2 |
| `launch_monitor_river` | script | Lancer le Monitor RIVER Scalp | lance river, monitor river |
| `launch_command_center` | script | Ouvrir le JARVIS Command Center (GUI) | ouvre le command center, command center |
| `launch_electron_app` | script | Ouvrir JARVIS Electron App | lance electron, jarvis electron |
| `launch_widget` | script | Ouvrir le Widget JARVIS | lance le widget jarvis, jarvis widget |
| `launch_disk_cleaner` | script | Lancer le nettoyeur de disque | nettoie le disque, disk cleaner |
| `launch_master_node` | script | Lancer le Master Interaction Node | lance le master node, master interaction |
| `launch_fs_agent` | script | Lancer l'agent fichiers JARVIS | lance l'agent fichiers, fs agent |

### MEDIA (7)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `media_play_pause` | hotkey | Play/Pause media | play, pause |
| `media_next` | hotkey | Piste suivante | suivant, piste suivante |
| `media_previous` | hotkey | Piste precedente | precedent, piste precedente |
| `volume_haut` | hotkey | Augmenter le volume | monte le volume, augmente le volume |
| `volume_bas` | hotkey | Baisser le volume | baisse le volume, diminue le volume |
| `muet` | hotkey | Couper/activer le son | coupe le son, mute |
| `volume_precis` | powershell | Mettre le volume a un niveau precis | mets le volume a {niveau}, volume a {niveau} |

### NAVIGATION (148)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_chrome` | app_open | Ouvrir Google Chrome | ouvre chrome, ouvrir chrome |
| `ouvrir_comet` | app_open | Ouvrir Comet Browser | ouvre comet, ouvrir comet |
| `aller_sur_site` | browser | Naviguer vers un site web | va sur {site}, ouvre {site} |
| `chercher_google` | browser | Rechercher sur Google | cherche {requete}, recherche {requete} |
| `chercher_youtube` | browser | Rechercher sur YouTube | cherche sur youtube {requete}, youtube {requete} |
| `ouvrir_gmail` | browser | Ouvrir Gmail | ouvre gmail, ouvrir gmail |
| `ouvrir_youtube` | browser | Ouvrir YouTube | ouvre youtube, va sur youtube |
| `ouvrir_github` | browser | Ouvrir GitHub | ouvre github, va sur github |
| `ouvrir_tradingview` | browser | Ouvrir TradingView | ouvre tradingview, va sur tradingview |
| `ouvrir_mexc` | browser | Ouvrir MEXC | ouvre mexc, va sur mexc |
| `nouvel_onglet` | hotkey | Ouvrir un nouvel onglet | nouvel onglet, nouveau tab |
| `fermer_onglet` | hotkey | Fermer l'onglet actif | ferme l'onglet, ferme cet onglet |
| `mode_incognito` | powershell | Ouvrir Chrome en mode incognito | mode incognito, navigation privee |
| `historique_chrome` | hotkey | Ouvrir l'historique Chrome | historique chrome, ouvre l'historique |
| `favoris_chrome` | hotkey | Ouvrir les favoris Chrome | ouvre les favoris, favoris |
| `telecharger_chrome` | hotkey | Ouvrir les telechargements Chrome | telechargements chrome, ouvre les downloads |
| `nouvel_onglet` | hotkey | Ouvrir un nouvel onglet Chrome | nouvel onglet, ouvre un onglet |
| `onglet_precedent` | hotkey | Onglet precedent Chrome | onglet precedent, tab precedent |
| `onglet_suivant` | hotkey | Onglet suivant Chrome | onglet suivant, tab suivant |
| `rouvrir_onglet` | hotkey | Rouvrir le dernier onglet ferme | rouvre l'onglet, rouvrir onglet |
| `chrome_favoris` | hotkey | Ouvrir les favoris Chrome | ouvre les favoris, mes favoris |
| `chrome_telechargements` | hotkey | Ouvrir les telechargements Chrome | telechargements chrome, mes telechargements chrome |
| `chrome_plein_ecran` | hotkey | Chrome en plein ecran (F11) | plein ecran, chrome plein ecran |
| `chrome_zoom_plus` | hotkey | Zoom avant Chrome | zoom avant chrome, agrandir la page |
| `chrome_zoom_moins` | hotkey | Zoom arriere Chrome | zoom arriere chrome, reduire la page |
| `chrome_zoom_reset` | hotkey | Reinitialiser le zoom Chrome | zoom normal, zoom 100 |
| `meteo` | browser | Afficher la meteo | meteo, la meteo |
| `ouvrir_twitter` | browser | Ouvrir Twitter/X | ouvre twitter, va sur twitter |
| `ouvrir_reddit` | browser | Ouvrir Reddit | ouvre reddit, va sur reddit |
| `ouvrir_linkedin` | browser | Ouvrir LinkedIn | ouvre linkedin, va sur linkedin |
| `ouvrir_instagram` | browser | Ouvrir Instagram | ouvre instagram, va sur instagram |
| `ouvrir_tiktok` | browser | Ouvrir TikTok | ouvre tiktok, va sur tiktok |
| `ouvrir_twitch` | browser | Ouvrir Twitch | ouvre twitch, va sur twitch |
| `ouvrir_chatgpt` | browser | Ouvrir ChatGPT | ouvre chatgpt, va sur chatgpt |
| `ouvrir_claude` | browser | Ouvrir Claude AI | ouvre claude, va sur claude |
| `ouvrir_perplexity` | browser | Ouvrir Perplexity | ouvre perplexity, va sur perplexity |
| `ouvrir_huggingface` | browser | Ouvrir Hugging Face | ouvre hugging face, va sur hugging face |
| `ouvrir_wikipedia` | browser | Ouvrir Wikipedia | ouvre wikipedia, va sur wikipedia |
| `ouvrir_amazon` | browser | Ouvrir Amazon | ouvre amazon, va sur amazon |
| `ouvrir_leboncoin` | browser | Ouvrir Leboncoin | ouvre leboncoin, va sur leboncoin |
| `ouvrir_netflix` | browser | Ouvrir Netflix | ouvre netflix, va sur netflix |
| `ouvrir_spotify_web` | browser | Ouvrir Spotify Web Player | ouvre spotify web, spotify web |
| `ouvrir_disney_plus` | browser | Ouvrir Disney+ | ouvre disney plus, va sur disney plus |
| `ouvrir_stackoverflow` | browser | Ouvrir Stack Overflow | ouvre stackoverflow, va sur stackoverflow |
| `ouvrir_npmjs` | browser | Ouvrir NPM | ouvre npm, va sur npm |
| `ouvrir_pypi` | browser | Ouvrir PyPI | ouvre pypi, va sur pypi |
| `ouvrir_docker_hub` | browser | Ouvrir Docker Hub | ouvre docker hub, va sur docker hub |
| `ouvrir_google_drive` | browser | Ouvrir Google Drive | ouvre google drive, va sur google drive |
| `ouvrir_google_docs` | browser | Ouvrir Google Docs | ouvre google docs, va sur google docs |
| `ouvrir_google_sheets` | browser | Ouvrir Google Sheets | ouvre google sheets, va sur google sheets |
| `ouvrir_google_maps` | browser | Ouvrir Google Maps | ouvre google maps, va sur google maps |
| `ouvrir_google_calendar` | browser | Ouvrir Google Calendar | ouvre google calendar, ouvre l'agenda |
| `ouvrir_notion` | browser | Ouvrir Notion | ouvre notion, va sur notion |
| `chercher_images` | browser | Rechercher des images sur Google | cherche des images de {requete}, images de {requete} |
| `chercher_reddit` | browser | Rechercher sur Reddit | cherche sur reddit {requete}, reddit {requete} |
| `chercher_wikipedia` | browser | Rechercher sur Wikipedia | cherche sur wikipedia {requete}, wikipedia {requete} |
| `chercher_amazon` | browser | Rechercher sur Amazon | cherche sur amazon {requete}, amazon {requete} |
| `ouvrir_tradingview_web` | browser | Ouvrir TradingView | ouvre tradingview, va sur tradingview |
| `ouvrir_coingecko` | browser | Ouvrir CoinGecko | ouvre coingecko, va sur coingecko |
| `ouvrir_coinmarketcap` | browser | Ouvrir CoinMarketCap | ouvre coinmarketcap, va sur coinmarketcap |
| `ouvrir_mexc_exchange` | browser | Ouvrir MEXC Exchange | ouvre mexc, va sur mexc |
| `ouvrir_dexscreener` | browser | Ouvrir DexScreener | ouvre dexscreener, va sur dexscreener |
| `ouvrir_telegram_web` | browser | Ouvrir Telegram Web | ouvre telegram web, telegram web |
| `ouvrir_whatsapp_web` | browser | Ouvrir WhatsApp Web | ouvre whatsapp web, whatsapp web |
| `ouvrir_slack_web` | browser | Ouvrir Slack Web | ouvre slack web, slack web |
| `ouvrir_teams_web` | browser | Ouvrir Microsoft Teams Web | ouvre teams web, teams web |
| `ouvrir_youtube_music` | browser | Ouvrir YouTube Music | ouvre youtube music, youtube music |
| `ouvrir_prime_video` | browser | Ouvrir Amazon Prime Video | ouvre prime video, va sur prime video |
| `ouvrir_crunchyroll` | browser | Ouvrir Crunchyroll | ouvre crunchyroll, va sur crunchyroll |
| `ouvrir_github_web` | browser | Ouvrir GitHub | ouvre github, va sur github |
| `ouvrir_vercel` | browser | Ouvrir Vercel | ouvre vercel, va sur vercel |
| `ouvrir_crates_io` | browser | Ouvrir crates.io (Rust packages) | ouvre crates io, va sur crates |
| `chercher_video_youtube` | browser | Rechercher sur YouTube | cherche sur youtube {requete}, youtube {requete} |
| `chercher_github` | browser | Rechercher sur GitHub | cherche sur github {requete}, github {requete} |
| `chercher_stackoverflow` | browser | Rechercher sur Stack Overflow | cherche sur stackoverflow {requete}, stackoverflow {requete} |
| `chercher_npm` | browser | Rechercher un package NPM | cherche sur npm {requete}, npm {requete} |
| `chercher_pypi` | browser | Rechercher un package PyPI | cherche sur pypi {requete}, pypi {requete} |
| `ouvrir_google_translate` | browser | Ouvrir Google Translate | ouvre google translate, traducteur |
| `ouvrir_google_news` | browser | Ouvrir Google Actualites | ouvre google news, google actualites |
| `ouvrir_figma` | browser | Ouvrir Figma | ouvre figma, va sur figma |
| `ouvrir_canva` | browser | Ouvrir Canva | ouvre canva, va sur canva |
| `ouvrir_pinterest` | browser | Ouvrir Pinterest | ouvre pinterest, va sur pinterest |
| `ouvrir_udemy` | browser | Ouvrir Udemy | ouvre udemy, va sur udemy |
| `ouvrir_regex101` | browser | Ouvrir Regex101 (testeur de regex) | ouvre regex101, testeur regex |
| `ouvrir_jsonformatter` | browser | Ouvrir un formatteur JSON en ligne | ouvre json formatter, formatte du json |
| `ouvrir_speedtest` | browser | Ouvrir Speedtest | ouvre speedtest, lance un speed test |
| `ouvrir_excalidraw` | browser | Ouvrir Excalidraw (tableau blanc) | ouvre excalidraw, tableau blanc |
| `ouvrir_soundcloud` | browser | Ouvrir SoundCloud | ouvre soundcloud, va sur soundcloud |
| `ouvrir_google_scholar` | browser | Ouvrir Google Scholar | ouvre google scholar, google scholar |
| `chercher_traduction` | browser | Traduire un texte via Google Translate | traduis {requete}, traduction de {requete} |
| `chercher_google_scholar` | browser | Rechercher sur Google Scholar | cherche sur scholar {requete}, article sur {requete} |
| `chercher_huggingface` | browser | Rechercher un modele sur Hugging Face | cherche sur hugging face {requete}, modele {requete} huggingface |
| `chercher_docker_hub` | browser | Rechercher une image Docker Hub | cherche sur docker hub {requete}, image docker {requete} |
| `ouvrir_gmail_web` | browser | Ouvrir Gmail | ouvre gmail, va sur gmail |
| `ouvrir_google_keep` | browser | Ouvrir Google Keep (notes) | ouvre google keep, ouvre keep |
| `ouvrir_google_photos` | browser | Ouvrir Google Photos | ouvre google photos, va sur google photos |
| `ouvrir_google_meet` | browser | Ouvrir Google Meet | ouvre google meet, lance meet |
| `ouvrir_deepl` | browser | Ouvrir DeepL Traducteur | ouvre deepl, va sur deepl |
| `ouvrir_wayback_machine` | browser | Ouvrir la Wayback Machine (archive web) | ouvre wayback machine, wayback machine |
| `ouvrir_codepen` | browser | Ouvrir CodePen | ouvre codepen, va sur codepen |
| `ouvrir_jsfiddle` | browser | Ouvrir JSFiddle | ouvre jsfiddle, va sur jsfiddle |
| `ouvrir_dev_to` | browser | Ouvrir dev.to (communaute dev) | ouvre dev to, va sur dev to |
| `ouvrir_medium` | browser | Ouvrir Medium | ouvre medium, va sur medium |
| `ouvrir_hacker_news` | browser | Ouvrir Hacker News | ouvre hacker news, va sur hacker news |
| `ouvrir_producthunt` | browser | Ouvrir Product Hunt | ouvre product hunt, va sur product hunt |
| `ouvrir_coursera` | browser | Ouvrir Coursera | ouvre coursera, va sur coursera |
| `ouvrir_kaggle` | browser | Ouvrir Kaggle | ouvre kaggle, va sur kaggle |
| `ouvrir_arxiv` | browser | Ouvrir arXiv (articles scientifiques) | ouvre arxiv, va sur arxiv |
| `ouvrir_gitlab` | browser | Ouvrir GitLab | ouvre gitlab, va sur gitlab |
| `ouvrir_bitbucket` | browser | Ouvrir Bitbucket | ouvre bitbucket, va sur bitbucket |
| `ouvrir_leetcode` | browser | Ouvrir LeetCode | ouvre leetcode, va sur leetcode |
| `ouvrir_codewars` | browser | Ouvrir Codewars | ouvre codewars, va sur codewars |
| `chercher_deepl` | browser | Traduire via DeepL | traduis avec deepl {requete}, deepl {requete} |
| `chercher_arxiv` | browser | Rechercher sur arXiv | cherche sur arxiv {requete}, arxiv {requete} |
| `chercher_kaggle` | browser | Rechercher sur Kaggle | cherche sur kaggle {requete}, kaggle {requete} |
| `chercher_leetcode` | browser | Rechercher un probleme LeetCode | cherche sur leetcode {requete}, leetcode {requete} |
| `chercher_medium` | browser | Rechercher sur Medium | cherche sur medium {requete}, medium {requete} |
| `chercher_hacker_news` | browser | Rechercher sur Hacker News | cherche sur hacker news {requete}, hn {requete} |
| `ouvrir_linear` | browser | Ouvrir Linear (gestion de projet dev) | ouvre linear, va sur linear |
| `ouvrir_miro` | browser | Ouvrir Miro (whiteboard collaboratif) | ouvre miro, va sur miro |
| `ouvrir_loom` | browser | Ouvrir Loom (enregistrement ecran) | ouvre loom, va sur loom |
| `ouvrir_supabase` | browser | Ouvrir Supabase | ouvre supabase, va sur supabase |
| `ouvrir_firebase` | browser | Ouvrir Firebase Console | ouvre firebase, va sur firebase |
| `ouvrir_railway` | browser | Ouvrir Railway (deploy) | ouvre railway, va sur railway |
| `ouvrir_cloudflare` | browser | Ouvrir Cloudflare Dashboard | ouvre cloudflare, va sur cloudflare |
| `ouvrir_render` | browser | Ouvrir Render (hosting) | ouvre render, va sur render |
| `ouvrir_fly_io` | browser | Ouvrir Fly.io | ouvre fly io, va sur fly |
| `ouvrir_mdn` | browser | Ouvrir MDN Web Docs | ouvre mdn, va sur mdn |
| `ouvrir_devdocs` | browser | Ouvrir DevDocs.io (toute la doc dev) | ouvre devdocs, va sur devdocs |
| `ouvrir_can_i_use` | browser | Ouvrir Can I Use (compatibilite navigateurs) | ouvre can i use, can i use |
| `ouvrir_bundlephobia` | browser | Ouvrir Bundlephobia (taille des packages) | ouvre bundlephobia, bundlephobia |
| `ouvrir_w3schools` | browser | Ouvrir W3Schools | ouvre w3schools, va sur w3schools |
| `ouvrir_python_docs` | browser | Ouvrir la documentation Python officielle | ouvre la doc python, doc python |
| `ouvrir_rust_docs` | browser | Ouvrir la documentation Rust (The Book) | ouvre la doc rust, doc rust |
| `ouvrir_replit` | browser | Ouvrir Replit (IDE en ligne) | ouvre replit, va sur replit |
| `ouvrir_codesandbox` | browser | Ouvrir CodeSandbox | ouvre codesandbox, va sur codesandbox |
| `ouvrir_stackblitz` | browser | Ouvrir StackBlitz | ouvre stackblitz, va sur stackblitz |
| `ouvrir_typescript_playground` | browser | Ouvrir TypeScript Playground | ouvre typescript playground, typescript playground |
| `ouvrir_rust_playground` | browser | Ouvrir Rust Playground | ouvre rust playground, rust playground |
| `ouvrir_google_trends` | browser | Ouvrir Google Trends | ouvre google trends, google trends |
| `ouvrir_alternativeto` | browser | Ouvrir AlternativeTo (alternatives logiciels) | ouvre alternativeto, alternativeto |
| `ouvrir_downdetector` | browser | Ouvrir DownDetector (status services) | ouvre downdetector, downdetector |
| `ouvrir_virustotal` | browser | Ouvrir VirusTotal (scan fichiers/URLs) | ouvre virustotal, virustotal |
| `ouvrir_haveibeenpwned` | browser | Ouvrir Have I Been Pwned (verification email) | ouvre have i been pwned, haveibeenpwned |
| `chercher_crates_io` | browser | Rechercher un crate Rust | cherche sur crates {requete}, crate rust {requete} |
| `chercher_alternativeto` | browser | Chercher une alternative a un logiciel | alternative a {requete}, cherche une alternative a {requete} |
| `chercher_mdn` | browser | Rechercher sur MDN Web Docs | cherche sur mdn {requete}, mdn {requete} |
| `chercher_can_i_use` | browser | Verifier la compatibilite d'une feature web | can i use {requete}, compatibilite de {requete} |

### PIPELINE (156)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `range_bureau` | pipeline | Ranger le bureau (minimiser toutes les fenetres) | range mon bureau, range le bureau |
| `va_sur_mails_comet` | pipeline | Ouvrir Comet et aller sur Gmail | va sur mes mails, ouvre mes mails sur comet |
| `mode_travail` | pipeline | Mode travail: VSCode + Terminal | mode travail, mode dev |
| `mode_trading` | pipeline | Mode trading: TradingView + MEXC + Dashboard | mode trading, ouvre mon setup trading |
| `rapport_matin` | pipeline | Rapport du matin: Gmail Comet + TradingView + Dashboard | rapport du matin, routine du matin |
| `bonne_nuit` | pipeline | Bonne nuit: minimiser tout + verrouiller le PC | bonne nuit, bonne nuit jarvis |
| `mode_focus` | pipeline | Mode focus: minimiser tout + ne pas deranger | mode focus, mode concentration |
| `mode_cinema` | pipeline | Mode cinema: minimiser tout + ouvrir Netflix | mode cinema, mode film |
| `ouvre_youtube_comet` | pipeline | Ouvrir YouTube dans Comet | ouvre youtube sur comet, youtube comet |
| `ouvre_github_comet` | pipeline | Ouvrir GitHub dans Comet | ouvre github sur comet, ouvre github comet |
| `ouvre_cluster` | pipeline | Ouvrir Dashboard cluster + LM Studio | ouvre le cluster, lance le cluster |
| `ferme_tout` | pipeline | Fermer toutes les fenetres | ferme tout, ferme toutes les fenetres |
| `mode_musique` | pipeline | Mode musique: minimiser tout + ouvrir Spotify | mode musique, lance la musique en fond |
| `mode_gaming` | pipeline | Mode gaming: haute performance + Steam + Game Bar | mode gaming, mode jeu |
| `mode_stream` | pipeline | Mode stream: minimiser tout + OBS + Spotify | mode stream, lance le stream |
| `mode_presentation` | pipeline | Mode presentation: dupliquer ecran + PowerPoint | mode presentation, lance la presentation |
| `mode_lecture` | pipeline | Mode lecture: nuit + minimiser + Comet | mode lecture, mode lire |
| `mode_reunion` | pipeline | Mode reunion: Discord + focus assist | mode reunion, lance la reunion |
| `mode_code_turbo` | pipeline | Mode dev turbo: VSCode + Terminal + LM Studio + Dashboard | mode code turbo, setup dev complet |
| `mode_detente` | pipeline | Mode detente: minimiser + Spotify + lumiere nocturne | mode detente, mode relax |
| `routine_soir` | pipeline | Routine du soir: TradingView + night light + minimiser | routine du soir, routine soir |
| `check_trading_rapide` | pipeline | Check trading: TradingView + MEXC en parallele | check trading rapide, check rapide trading |
| `setup_ia` | pipeline | Setup IA: LM Studio + Dashboard + Terminal | setup ia, lance le setup ia |
| `nettoyage_express` | pipeline | Nettoyage express: corbeille + temp + DNS | nettoyage express, nettoyage rapide |
| `diagnostic_complet` | pipeline | Diagnostic complet: systeme + GPU + RAM + disques | diagnostic complet, diagnostic du pc |
| `debug_reseau` | pipeline | Debug reseau: flush DNS + ping + diagnostic | debug reseau, debug le reseau |
| `veille_securisee` | pipeline | Veille securisee: minimiser + verrouiller + veille | veille securisee, mets en veille en securite |
| `ouvre_reddit_comet` | pipeline | Ouvrir Reddit dans Comet | ouvre reddit sur comet, reddit comet |
| `ouvre_twitter_comet` | pipeline | Ouvrir Twitter/X dans Comet | ouvre twitter sur comet, twitter comet |
| `ouvre_chatgpt_comet` | pipeline | Ouvrir ChatGPT dans Comet | ouvre chatgpt sur comet, chatgpt comet |
| `ouvre_claude_comet` | pipeline | Ouvrir Claude AI dans Comet | ouvre claude sur comet, claude comet |
| `ouvre_linkedin_comet` | pipeline | Ouvrir LinkedIn dans Comet | ouvre linkedin sur comet, linkedin comet |
| `ouvre_amazon_comet` | pipeline | Ouvrir Amazon dans Comet | ouvre amazon sur comet, amazon comet |
| `ouvre_twitch_comet` | pipeline | Ouvrir Twitch dans Comet | ouvre twitch sur comet, twitch comet |
| `ouvre_social_comet` | pipeline | Ouvrir les reseaux sociaux dans Comet (Twitter + Reddit + Discord) | ouvre les reseaux sociaux comet, social comet |
| `ouvre_perplexity_comet` | pipeline | Ouvrir Perplexity dans Comet | ouvre perplexity sur comet, perplexity comet |
| `ouvre_huggingface_comet` | pipeline | Ouvrir Hugging Face dans Comet | ouvre hugging face sur comet, huggingface comet |
| `mode_crypto` | pipeline | Mode crypto: TradingView + MEXC + CoinGecko | mode crypto, mode trading crypto |
| `mode_ia_complet` | pipeline | Mode IA complet: LM Studio + Dashboard + Claude + HuggingFace | mode ia complet, ouvre tout le cluster ia |
| `mode_debug` | pipeline | Mode debug: Terminal + GPU monitoring + logs systeme | mode debug, mode debogage |
| `mode_monitoring` | pipeline | Mode monitoring: Dashboard + GPU + cluster health | mode monitoring, mode surveillance |
| `mode_communication` | pipeline | Mode communication: Discord + Telegram + WhatsApp | mode communication, mode com |
| `mode_documentation` | pipeline | Mode documentation: Notion + Google Docs + Drive | mode documentation, mode docs |
| `mode_focus_total` | pipeline | Mode focus total: minimiser + focus assist + nuit + VSCode | mode focus total, concentration maximale |
| `mode_review` | pipeline | Mode review: VSCode + navigateur Git + Terminal | mode review, mode revue de code |
| `routine_matin` | pipeline | Routine du matin: cluster + dashboard + trading + mails | routine du matin, routine matin |
| `backup_express` | pipeline | Backup express: git add + commit du projet turbo | backup express, sauvegarde rapide |
| `reboot_cluster` | pipeline | Reboot cluster: redemarre Ollama + ping LM Studio | reboot le cluster, redemarre le cluster |
| `pause_travail` | pipeline | Pause: minimiser + verrouiller ecran + Spotify | pause travail, je fais une pause |
| `fin_journee` | pipeline | Fin de journee: backup + nuit + fermer apps dev | fin de journee, termine la journee |
| `ouvre_github_via_comet` | pipeline | Ouvrir GitHub dans Comet | ouvre github sur comet, github comet |
| `ouvre_youtube_via_comet` | pipeline | Ouvrir YouTube dans Comet | ouvre youtube sur comet, youtube comet |
| `ouvre_tradingview_comet` | pipeline | Ouvrir TradingView dans Comet | ouvre tradingview sur comet, tradingview comet |
| `ouvre_coingecko_comet` | pipeline | Ouvrir CoinGecko dans Comet | ouvre coingecko sur comet, coingecko comet |
| `ouvre_ia_comet` | pipeline | Ouvrir toutes les IA dans Comet (ChatGPT + Claude + Perplexity) | ouvre toutes les ia comet, ia comet |
| `mode_cinema_complet` | pipeline | Mode cinema complet: minimiser + nuit + plein ecran + Netflix | mode cinema complet, soiree film |
| `mode_workout` | pipeline | Mode workout: Spotify energique + YouTube fitness + timer | mode workout, mode sport |
| `mode_etude` | pipeline | Mode etude: focus + Wikipedia + Pomodoro mindset | mode etude, mode revision |
| `mode_diner` | pipeline | Mode diner: minimiser + ambiance calme + Spotify | mode diner, ambiance diner |
| `routine_depart` | pipeline | Routine depart: sauvegarder + minimiser + verrouiller + economie | routine depart, je pars |
| `routine_retour` | pipeline | Routine retour: performance + cluster + mails + dashboard | routine retour, je suis rentre |
| `mode_nuit_totale` | pipeline | Mode nuit: fermer tout + nuit + volume bas + verrouiller | mode nuit totale, dodo |
| `dev_morning_setup` | pipeline | Dev morning: git pull + Docker + VSCode + browser tabs travail | dev morning, setup dev du matin |
| `dev_deep_work` | pipeline | Deep work: fermer distractions + VSCode + focus + terminal | deep work, travail profond |
| `dev_standup_prep` | pipeline | Standup prep: git log hier + board + dashboard | standup prep, prepare le standup |
| `dev_deploy_check` | pipeline | Pre-deploy check: tests + git status + Docker status | check avant deploy, pre deploy |
| `dev_friday_report` | pipeline | Rapport vendredi: stats git semaine + dashboard + todos | rapport vendredi, friday report |
| `dev_code_review_setup` | pipeline | Code review setup: GitHub PRs + VSCode + diff terminal | setup code review, prepare la review |
| `audit_securite_complet` | pipeline | Audit securite: Defender + ports + connexions + firewall + autorun | audit securite complet, scan securite total |
| `rapport_systeme_complet` | pipeline | Rapport systeme: CPU + RAM + GPU + disques + uptime + reseau | rapport systeme complet, rapport systeme |
| `maintenance_totale` | pipeline | Maintenance totale: corbeille + temp + prefetch + DNS + thumbnails + check updates | maintenance totale, grand nettoyage |
| `sauvegarde_tous_projets` | pipeline | Backup tous projets: git commit turbo + carV1 + serveur | sauvegarde tous les projets, backup tous les projets |
| `pomodoro_start` | pipeline | Pomodoro: fermer distractions + focus + VSCode + timer 25min | pomodoro, lance un pomodoro |
| `pomodoro_break` | pipeline | Pause Pomodoro: minimiser + Spotify + 5 min | pause pomodoro, break pomodoro |
| `mode_entretien` | pipeline | Mode entretien/call: fermer musique + focus + navigateur | mode entretien, j'ai un call |
| `mode_recherche` | pipeline | Mode recherche: Perplexity + Google Scholar + Wikipedia + Claude | mode recherche, lance le mode recherche |
| `mode_youtube` | pipeline | Mode YouTube: minimiser + plein ecran + YouTube | mode youtube, lance youtube en grand |
| `mode_spotify_focus` | pipeline | Spotify focus: minimiser + Spotify + focus assist | spotify focus, musique et concentration |
| `ouvre_tout_dev_web` | pipeline | Dev web complet: VSCode + terminal + localhost + npm docs | dev web complet, setup dev web |
| `mode_twitch_stream` | pipeline | Mode stream Twitch: OBS + Twitch dashboard + Spotify + chat | mode twitch, setup stream twitch |
| `mode_email_productif` | pipeline | Email productif: Gmail + Calendar + fermer distractions | mode email, traite les mails |
| `mode_podcast` | pipeline | Mode podcast: minimiser + Spotify + volume confortable | mode podcast, lance un podcast |
| `mode_apprentissage` | pipeline | Mode apprentissage: focus + Udemy/Coursera + notes | mode apprentissage, mode formation |
| `mode_news` | pipeline | Mode news: Google Actualites + Reddit + Twitter | mode news, mode actualites |
| `mode_shopping` | pipeline | Mode shopping: Amazon + Leboncoin + comparateur | mode shopping, mode achats |
| `mode_design` | pipeline | Mode design: Figma + Pinterest + Canva | mode design, mode graphisme |
| `mode_musique_decouverte` | pipeline | Decouverte musicale: Spotify + YouTube Music + SoundCloud | decouverte musicale, explore la musique |
| `routine_weekend` | pipeline | Routine weekend: relax + news + musique + Netflix | routine weekend, mode weekend |
| `mode_social_complet` | pipeline | Social complet: Twitter + Reddit + Instagram + LinkedIn + Discord | mode social complet, tous les reseaux |
| `mode_planning` | pipeline | Mode planning: Calendar + Notion + Google Tasks | mode planning, mode planification |
| `mode_brainstorm` | pipeline | Mode brainstorm: Claude + Notion + timer | mode brainstorm, session brainstorm |
| `nettoyage_downloads` | pipeline | Nettoyer les vieux telechargements (>30 jours) | nettoie les telechargements, clean downloads |
| `rapport_reseau_complet` | pipeline | Rapport reseau: IP + DNS + latence + ports + WiFi | rapport reseau complet, rapport reseau |
| `verif_toutes_mises_a_jour` | pipeline | Verifier MAJ: Windows Update + pip + npm + ollama | verifie toutes les mises a jour, check toutes les updates |
| `snapshot_systeme` | pipeline | Snapshot systeme: sauvegarder toutes les stats dans un fichier | snapshot systeme, capture l'etat du systeme |
| `dev_hotfix` | pipeline | Hotfix: nouvelle branche + VSCode + tests | hotfix, lance un hotfix |
| `dev_new_feature` | pipeline | Nouvelle feature: branche + VSCode + terminal + tests | nouvelle feature, dev new feature |
| `dev_merge_prep` | pipeline | Preparation merge: lint + tests + git status + diff | prepare le merge, pre merge |
| `dev_database_check` | pipeline | Check databases: taille + tables de jarvis.db et etoile.db | check les databases, verifie les bases de donnees |
| `dev_live_coding` | pipeline | Live coding: OBS + VSCode + terminal + navigateur localhost | live coding, mode live code |
| `dev_cleanup` | pipeline | Dev cleanup: git clean + cache Python + node_modules check | dev cleanup, nettoie le projet |
| `mode_double_ecran_dev` | pipeline | Double ecran dev: etendre + VSCode gauche + navigateur droite | mode double ecran dev, setup double ecran |
| `mode_presentation_zoom` | pipeline | Presentation Zoom/Teams: fermer distractions + dupliquer ecran + app | mode presentation zoom, setup presentation teams |
| `mode_dashboard_complet` | pipeline | Dashboard complet: JARVIS + TradingView + cluster + n8n | dashboard complet, ouvre tous les dashboards |
| `ferme_tout_sauf_code` | pipeline | Fermer tout sauf VSCode et terminal | ferme tout sauf le code, garde juste vscode |
| `mode_detox_digital` | pipeline | Detox digitale: fermer TOUT + verrouiller + night light | detox digitale, mode detox |
| `mode_musique_travail` | pipeline | Musique de travail: Spotify + focus assist (pas de distractions) | musique de travail, met de la musique pour bosser |
| `check_tout_rapide` | pipeline | Check rapide tout: cluster + GPU + RAM + disques en 1 commande | check tout rapide, etat rapide de tout |
| `mode_hackathon` | pipeline | Mode hackathon: timer + VSCode + terminal + GitHub + Claude | mode hackathon, lance le hackathon |
| `mode_data_science` | pipeline | Mode data science: Jupyter + Kaggle + docs Python + terminal | mode data science, mode datascience |
| `mode_devops` | pipeline | Mode DevOps: Docker + dashboard + terminal + GitHub Actions | mode devops, mode ops |
| `mode_securite_audit` | pipeline | Mode audit securite: Defender + ports + connexions + terminal | mode securite, mode audit securite |
| `mode_trading_scalp` | pipeline | Mode scalping: TradingView multi-timeframe + MEXC + terminal | mode scalping, mode scalp |
| `routine_midi` | pipeline | Routine midi: pause + news + trading check rapide | routine midi, pause midi |
| `routine_nuit_urgence` | pipeline | Mode urgence nuit: tout fermer + sauvegarder + veille immediate | urgence nuit, extinction d'urgence |
| `setup_meeting_rapide` | pipeline | Meeting rapide: micro check + fermer musique + Teams/Discord | meeting rapide, setup meeting |
| `mode_veille_tech` | pipeline | Veille tech: Hacker News + dev.to + Product Hunt + Reddit/programming | veille tech, mode veille technologique |
| `mode_freelance` | pipeline | Mode freelance: factures + mails + calendar + Notion | mode freelance, mode client |
| `mode_debug_production` | pipeline | Debug prod: logs + monitoring + terminal + dashboard | debug production, mode debug prod |
| `mode_apprentissage_code` | pipeline | Mode apprentissage code: LeetCode + VSCode + docs + timer | mode apprentissage code, session leetcode |
| `mode_tutorial` | pipeline | Mode tutorial: YouTube + VSCode + terminal + docs | mode tutorial, mode tuto |
| `mode_backup_total` | pipeline | Backup total: tous les projets + snapshot systeme + rapport | backup total, sauvegarde totale |
| `ouvre_dashboards_trading` | pipeline | Tous les dashboards trading: TV + MEXC + CoinGecko + CoinMarketCap + DexScreener | tous les dashboards trading, ouvre tout le trading |
| `mode_photo_edit` | pipeline | Mode retouche photo: Paint + navigateur refs + Pinterest | mode photo, mode retouche |
| `mode_writing` | pipeline | Mode ecriture: Google Docs + focus + nuit + Claude aide | mode ecriture, mode redaction |
| `mode_video_marathon` | pipeline | Mode marathon video: Netflix + nuit + plein ecran + snacks time | mode marathon, marathon video |
| `ouvre_kaggle_comet` | pipeline | Ouvrir Kaggle dans Comet | ouvre kaggle sur comet, kaggle comet |
| `ouvre_arxiv_comet` | pipeline | Ouvrir arXiv dans Comet | ouvre arxiv sur comet, arxiv comet |
| `ouvre_notion_comet` | pipeline | Ouvrir Notion dans Comet | ouvre notion sur comet, notion comet |
| `ouvre_stackoverflow_comet` | pipeline | Ouvrir Stack Overflow dans Comet | ouvre stackoverflow sur comet, stackoverflow comet |
| `ouvre_medium_comet` | pipeline | Ouvrir Medium dans Comet | ouvre medium sur comet, medium comet |
| `ouvre_gmail_comet` | pipeline | Ouvrir Gmail dans Comet | ouvre gmail sur comet, gmail comet |
| `mode_go_live` | pipeline | Go Live: OBS + Twitch dashboard + Spotify + chat overlay | go live, lance le stream maintenant |
| `mode_end_stream` | pipeline | End stream: fermer OBS + Twitch + recap | arrete le stream, fin du live |
| `mode_daily_report` | pipeline | Daily report: git log + stats code + dashboard + Google Sheets | rapport quotidien, daily report |
| `mode_api_test` | pipeline | Mode API testing: terminal + navigateur API docs + outils test | mode api test, teste les api |
| `mode_conference_full` | pipeline | Conference: fermer distractions + Teams + micro + focus assist | mode conference, mode visio complete |
| `mode_end_meeting` | pipeline | Fin meeting: fermer Teams/Discord/Zoom + restaurer musique | fin du meeting, fin de la reunion |
| `mode_home_theater` | pipeline | Home theater: minimiser + nuit + volume max + Disney+/Netflix plein ecran | mode home theater, mode cinema maison |
| `mode_refactoring` | pipeline | Mode refactoring: VSCode + ruff + tests + git diff | mode refactoring, session refactoring |
| `mode_testing_complet` | pipeline | Mode tests complet: pytest + coverage + lint + terminal | mode testing complet, lance tous les tests |
| `mode_deploy_checklist` | pipeline | Checklist deploy: tests + lint + status git + build check | checklist deploy, mode deploy |
| `mode_documentation_code` | pipeline | Mode doc code: VSCode + readthedocs + terminal + Notion | mode documentation code, documente le code |
| `mode_open_source` | pipeline | Mode open source: GitHub issues + PRs + VSCode + terminal | mode open source, mode contribution |
| `mode_side_project` | pipeline | Mode side project: VSCode + navigateur + terminal + timer 2h | mode side project, mode projet perso |
| `mode_admin_sys` | pipeline | Mode sysadmin: terminal + Event Viewer + services + ports | mode sysadmin, mode administrateur |
| `mode_reseau_complet` | pipeline | Mode reseau complet: ping + DNS + WiFi + ports + IP | mode reseau complet, diagnostic reseau total |
| `mode_finance` | pipeline | Mode finance: banque + budget + trading + calculatrice | mode finance, mode budget |
| `mode_voyage` | pipeline | Mode voyage: Google Flights + Maps + Booking + meteo | mode voyage, planifie un voyage |
| `routine_aperitif` | pipeline | Routine apero: fermer le travail + musique + ambiance | routine apero, aperitif |
| `mode_cuisine` | pipeline | Mode cuisine: YouTube recettes + timer + Spotify musique | mode cuisine, je fais a manger |
| `mode_meditation` | pipeline | Mode meditation: minimiser + nuit + sons relaxants | mode meditation, medite |
| `mode_pair_programming` | pipeline | Pair programming: VSCode Live Share + terminal + Discord | mode pair programming, pair prog |
| `mode_retrospective` | pipeline | Retrospective: bilan semaine + git stats + Notion + Calendar | mode retro, retrospective |
| `mode_demo` | pipeline | Mode demo: dupliquer ecran + navigateur + dashboard + presentation | mode demo, prepare la demo |
| `mode_scrum_master` | pipeline | Mode Scrum: board + standup + Calendar + timer | mode scrum, mode scrum master |

### SAISIE (4)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `texte_majuscule` | powershell | Convertir le presse-papier en majuscules | en majuscules, tout en majuscules |
| `texte_minuscule` | powershell | Convertir le presse-papier en minuscules | en minuscules, tout en minuscules |
| `ouvrir_emojis` | hotkey | Ouvrir le panneau emojis | ouvre les emojis, panneau emojis |
| `ouvrir_dictee` | hotkey | Activer la dictee vocale Windows | dicte, dictee windows |

### SYSTEME (391)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `verrouiller` | powershell | Verrouiller le PC | verrouille le pc, verrouille l'ecran |
| `eteindre` | powershell | Eteindre le PC | eteins le pc, eteindre le pc |
| `redemarrer` | powershell | Redemarrer le PC | redemarre le pc, redemarrer le pc |
| `veille` | powershell | Mettre en veille | mets en veille, veille |
| `capture_ecran` | hotkey | Capture d'ecran | capture ecran, screenshot |
| `info_systeme` | jarvis_tool | Infos systeme | info systeme, infos systeme |
| `info_gpu` | jarvis_tool | Infos GPU | info gpu, infos gpu |
| `info_reseau` | jarvis_tool | Infos reseau | info reseau, infos reseau |
| `processus` | jarvis_tool | Lister les processus | liste les processus, montre les processus |
| `kill_process` | jarvis_tool | Tuer un processus | tue le processus {nom}, kill {nom} |
| `wifi_scan` | jarvis_tool | Scanner les reseaux Wi-Fi | scan wifi, wifi scan |
| `ping_host` | jarvis_tool | Ping un hote | ping {host}, teste la connexion a {host} |
| `vider_corbeille` | powershell | Vider la corbeille | vide la corbeille, nettoie la corbeille |
| `mode_nuit` | hotkey | Activer/desactiver le mode nuit | mode nuit, lumiere bleue |
| `ouvrir_run` | hotkey | Ouvrir la boite Executer | ouvre executer, boite de dialogue executer |
| `recherche_windows` | hotkey | Recherche Windows | recherche windows, cherche sur le pc |
| `centre_notifications` | hotkey | Ouvrir le centre de notifications | ouvre les notifications, notifications |
| `ouvrir_widgets` | hotkey | Ouvrir les widgets | ouvre les widgets, widgets |
| `ouvrir_emojis` | hotkey | Ouvrir le panneau emojis | ouvre les emojis, emojis |
| `projeter_ecran` | hotkey | Projeter l'ecran | projette l'ecran, duplique l'ecran |
| `vue_taches` | hotkey | Vue des taches / bureaux virtuels | vue des taches, bureaux virtuels |
| `bureau_suivant` | hotkey | Passer au bureau virtuel suivant | bureau suivant, prochain bureau |
| `bureau_precedent` | hotkey | Passer au bureau virtuel precedent | bureau precedent, bureau virtuel precedent |
| `ouvrir_parametres` | ms_settings | Ouvrir les parametres Windows | ouvre les parametres, parametres |
| `param_wifi` | ms_settings | Parametres Wi-Fi | parametres wifi, reglages wifi |
| `param_bluetooth` | ms_settings | Parametres Bluetooth | parametres bluetooth, reglages bluetooth |
| `param_affichage` | ms_settings | Parametres d'affichage | parametres affichage, reglages ecran |
| `param_son` | ms_settings | Parametres son | parametres son, reglages audio |
| `param_stockage` | ms_settings | Espace disque et stockage | espace disque, stockage |
| `param_mises_a_jour` | ms_settings | Mises a jour Windows | mises a jour, windows update |
| `param_alimentation` | ms_settings | Parametres d'alimentation | parametres alimentation, economie energie |
| `bluetooth_on` | powershell | Activer le Bluetooth | active le bluetooth, allume bluetooth |
| `bluetooth_off` | powershell | Desactiver le Bluetooth | desactive le bluetooth, coupe bluetooth |
| `luminosite_haut` | powershell | Augmenter la luminosite | augmente la luminosite, plus lumineux |
| `luminosite_bas` | powershell | Baisser la luminosite | baisse la luminosite, moins lumineux |
| `lister_services` | jarvis_tool | Lister les services Windows | liste les services, services windows |
| `demarrer_service` | jarvis_tool | Demarrer un service Windows | demarre le service {nom}, start service {nom} |
| `arreter_service` | jarvis_tool | Arreter un service Windows | arrete le service {nom}, stop service {nom} |
| `resolution_ecran` | jarvis_tool | Resolution de l'ecran | resolution ecran, quelle resolution |
| `taches_planifiees` | jarvis_tool | Taches planifiees Windows | taches planifiees, taches automatiques |
| `mode_avion_on` | ms_settings | Activer le mode avion | active le mode avion, mode avion |
| `micro_mute` | powershell | Couper le microphone | coupe le micro, mute le micro |
| `micro_unmute` | powershell | Reactiver le microphone | reactive le micro, unmute micro |
| `param_camera` | ms_settings | Parametres camera | parametres camera, reglages camera |
| `nouveau_bureau` | hotkey | Creer un nouveau bureau virtuel | nouveau bureau, cree un bureau |
| `fermer_bureau` | hotkey | Fermer le bureau virtuel actif | ferme le bureau, ferme ce bureau |
| `zoom_avant` | hotkey | Zoomer | zoom avant, zoom plus |
| `zoom_arriere` | hotkey | Dezoomer | zoom arriere, zoom moins |
| `zoom_reset` | hotkey | Reinitialiser le zoom | zoom normal, zoom reset |
| `imprimer` | hotkey | Imprimer | imprime, imprimer |
| `renommer` | hotkey | Renommer le fichier selectionne | renomme, renommer |
| `supprimer` | hotkey | Supprimer le fichier/element selectionne | supprime, supprimer |
| `proprietes` | hotkey | Proprietes du fichier selectionne | proprietes, proprietes du fichier |
| `actualiser` | hotkey | Actualiser la page ou le dossier | actualise, rafraichis |
| `verrouiller_rapide` | hotkey | Verrouiller le PC rapidement | verrouille, lock |
| `loupe` | hotkey | Activer la loupe / zoom accessibilite | active la loupe, loupe |
| `loupe_off` | hotkey | Desactiver la loupe | desactive la loupe, ferme la loupe |
| `narrateur` | hotkey | Activer/desactiver le narrateur | active le narrateur, narrateur |
| `clavier_visuel` | powershell | Ouvrir le clavier visuel | clavier visuel, ouvre le clavier |
| `dictee` | hotkey | Activer la dictee vocale Windows | dictee, dictee vocale |
| `contraste_eleve` | hotkey | Activer le mode contraste eleve | contraste eleve, high contrast |
| `param_accessibilite` | ms_settings | Parametres d'accessibilite | parametres accessibilite, reglages accessibilite |
| `enregistrer_ecran` | hotkey | Enregistrer l'ecran (Xbox Game Bar) | enregistre l'ecran, lance l'enregistrement |
| `game_bar` | hotkey | Ouvrir la Xbox Game Bar | ouvre la game bar, game bar |
| `snap_layout` | hotkey | Ouvrir les dispositions Snap | snap layout, disposition fenetre |
| `plan_performance` | powershell | Activer le mode performances | mode performance, performances maximales |
| `plan_equilibre` | powershell | Activer le mode equilibre | mode equilibre, plan equilibre |
| `plan_economie` | powershell | Activer le mode economie d'energie | mode economie, economie d'energie |
| `ipconfig` | jarvis_tool | Afficher la configuration IP | montre l'ip, quelle est mon adresse ip |
| `vider_dns` | powershell | Vider le cache DNS | vide le cache dns, flush dns |
| `param_vpn` | ms_settings | Parametres VPN | parametres vpn, reglages vpn |
| `param_proxy` | ms_settings | Parametres proxy | parametres proxy, reglages proxy |
| `etendre_ecran` | powershell | Etendre l'affichage sur un second ecran | etends l'ecran, double ecran |
| `dupliquer_ecran` | powershell | Dupliquer l'affichage | duplique l'ecran, meme image |
| `ecran_principal_seul` | powershell | Afficher uniquement sur l'ecran principal | ecran principal seulement, un seul ecran |
| `ecran_secondaire_seul` | powershell | Afficher uniquement sur le second ecran | ecran secondaire seulement, second ecran uniquement |
| `focus_assist_on` | powershell | Activer l'aide a la concentration (ne pas deranger) | ne pas deranger, focus assist |
| `focus_assist_off` | powershell | Desactiver l'aide a la concentration | desactive ne pas deranger, reactive les notifications |
| `taskbar_hide` | powershell | Masquer la barre des taches | cache la barre des taches, masque la taskbar |
| `taskbar_show` | powershell | Afficher la barre des taches | montre la barre des taches, affiche la taskbar |
| `night_light_on` | powershell | Activer l'eclairage nocturne | active la lumiere nocturne, night light on |
| `night_light_off` | powershell | Desactiver l'eclairage nocturne | desactive la lumiere nocturne, night light off |
| `info_disques` | powershell | Afficher l'espace disque | espace disque, info disques |
| `vider_temp` | powershell | Vider les fichiers temporaires | vide les fichiers temporaires, nettoie les temp |
| `ouvrir_alarmes` | app_open | Ouvrir l'application Horloge/Alarmes | ouvre les alarmes, alarme |
| `historique_activite` | ms_settings | Ouvrir l'historique d'activite Windows | historique activite, timeline |
| `param_clavier` | ms_settings | Parametres clavier | parametres clavier, reglages clavier |
| `param_souris` | ms_settings | Parametres souris | parametres souris, reglages souris |
| `param_batterie` | ms_settings | Parametres batterie | parametres batterie, etat batterie |
| `param_comptes` | ms_settings | Parametres des comptes utilisateur | parametres comptes, comptes utilisateur |
| `param_heure` | ms_settings | Parametres date et heure | parametres heure, reglages heure |
| `param_langue` | ms_settings | Parametres de langue | parametres langue, changer la langue |
| `windows_security` | app_open | Ouvrir Windows Security | ouvre la securite, securite windows |
| `pare_feu` | ms_settings | Parametres du pare-feu | parametres pare-feu, firewall |
| `partage_proximite` | ms_settings | Parametres de partage a proximite | partage a proximite, nearby sharing |
| `hotspot` | ms_settings | Activer le point d'acces mobile | point d'acces, hotspot |
| `defrag_disque` | powershell | Optimiser les disques (defragmentation) | defragmente, optimise les disques |
| `gestion_disques` | powershell | Ouvrir le gestionnaire de disques | gestionnaire de disques, gestion des disques |
| `variables_env` | powershell | Ouvrir les variables d'environnement | variables d'environnement, variables env |
| `evenements_windows` | powershell | Ouvrir l'observateur d'evenements | observateur d'evenements, event viewer |
| `moniteur_ressources` | powershell | Ouvrir le moniteur de ressources | moniteur de ressources, resource monitor |
| `info_systeme_detaille` | powershell | Ouvrir les informations systeme detaillees | informations systeme detaillees, msinfo |
| `nettoyage_disque` | powershell | Ouvrir le nettoyage de disque Windows | nettoyage de disque, disk cleanup |
| `gestionnaire_peripheriques` | powershell | Ouvrir le gestionnaire de peripheriques | gestionnaire de peripheriques, device manager |
| `connexions_reseau` | powershell | Ouvrir les connexions reseau | connexions reseau, adaptateurs reseau |
| `programmes_installees` | ms_settings | Ouvrir programmes et fonctionnalites | programmes installes, applications installees |
| `demarrage_apps` | ms_settings | Gerer les applications au demarrage | applications demarrage, programmes au demarrage |
| `param_confidentialite` | ms_settings | Parametres de confidentialite | parametres confidentialite, privacy |
| `param_reseau_avance` | ms_settings | Parametres reseau avances | parametres reseau avances, reseau avance |
| `partager_ecran` | hotkey | Partager l'ecran via Miracast | partage l'ecran, miracast |
| `param_imprimantes` | ms_settings | Parametres imprimantes et scanners | parametres imprimantes, imprimante |
| `param_fond_ecran` | ms_settings | Personnaliser le fond d'ecran | fond d'ecran, change le fond |
| `param_couleurs` | ms_settings | Personnaliser les couleurs Windows | couleurs windows, couleur d'accent |
| `param_ecran_veille` | ms_settings | Parametres ecran de verrouillage | ecran de veille, ecran de verrouillage |
| `param_polices` | ms_settings | Gerer les polices installees | polices, fonts |
| `param_themes` | ms_settings | Gerer les themes Windows | themes windows, change le theme |
| `mode_sombre` | powershell | Activer le mode sombre Windows | active le mode sombre, dark mode on |
| `mode_clair` | powershell | Activer le mode clair Windows | active le mode clair, light mode on |
| `param_son_avance` | ms_settings | Parametres audio avances | parametres audio avances, son avance |
| `param_hdr` | ms_settings | Parametres HDR | parametres hdr, active le hdr |
| `ouvrir_regedit` | powershell | Ouvrir l'editeur de registre | ouvre le registre, regedit |
| `ouvrir_mmc` | powershell | Ouvrir la console de gestion (MMC) | console de gestion, mmc |
| `ouvrir_politique_groupe` | powershell | Ouvrir l'editeur de strategie de groupe | politique de groupe, group policy |
| `taux_rafraichissement` | ms_settings | Parametres taux de rafraichissement ecran | taux de rafraichissement, hertz ecran |
| `param_notifications_avance` | ms_settings | Parametres notifications avances | parametres notifications avances, gere les notifications |
| `param_multitache` | ms_settings | Parametres multitache Windows | parametres multitache, multitasking |
| `apps_par_defaut` | ms_settings | Gerer les applications par defaut | applications par defaut, apps par defaut |
| `param_stockage_avance` | ms_settings | Gestion du stockage et assistant | assistant stockage, nettoyage automatique |
| `sauvegarder_windows` | ms_settings | Parametres de sauvegarde Windows | sauvegarde windows, backup windows |
| `restauration_systeme` | powershell | Ouvrir la restauration du systeme | restauration systeme, point de restauration |
| `a_propos_pc` | ms_settings | Informations sur le PC (A propos) | a propos du pc, about pc |
| `param_ethernet` | ms_settings | Parametres Ethernet | parametres ethernet, cable reseau |
| `param_data_usage` | ms_settings | Utilisation des donnees reseau | utilisation donnees, data usage |
| `tracert` | powershell | Tracer la route vers un hote | trace la route vers {host}, traceroute {host} |
| `netstat` | powershell | Afficher les connexions reseau actives | connexions actives, netstat |
| `uptime` | powershell | Temps de fonctionnement du PC | uptime, depuis quand le pc tourne |
| `temperature_cpu` | powershell | Temperature du processeur | temperature cpu, temperature processeur |
| `liste_utilisateurs` | powershell | Lister les utilisateurs du PC | liste les utilisateurs, quels utilisateurs |
| `adresse_mac` | powershell | Afficher les adresses MAC | adresse mac, mac address |
| `vitesse_reseau` | powershell | Tester la vitesse de la carte reseau | vitesse reseau, speed test |
| `param_optionnel` | ms_settings | Gerer les fonctionnalites optionnelles Windows | fonctionnalites optionnelles, optional features |
| `ouvrir_sandbox` | powershell | Ouvrir Windows Sandbox | ouvre la sandbox, sandbox |
| `verifier_fichiers` | powershell | Verifier l'integrite des fichiers systeme | verifie les fichiers systeme, sfc scan |
| `wifi_connecter` | powershell | Se connecter a un reseau Wi-Fi | connecte moi au wifi {ssid}, connecte au wifi {ssid} |
| `wifi_deconnecter` | powershell | Se deconnecter du Wi-Fi | deconnecte le wifi, deconnecte du wifi |
| `wifi_profils` | powershell | Lister les profils Wi-Fi sauvegardes | profils wifi, wifi sauvegardes |
| `clipboard_vider` | powershell | Vider le presse-papier | vide le presse-papier, efface le clipboard |
| `clipboard_compter` | powershell | Compter les caracteres du presse-papier | combien de caracteres dans le presse-papier, taille du presse-papier |
| `recherche_everywhere` | powershell | Rechercher partout sur le PC | recherche partout {terme}, cherche partout {terme} |
| `tache_planifier` | powershell | Creer une tache planifiee | planifie une tache {nom}, cree une tache planifiee {nom} |
| `variables_utilisateur` | powershell | Afficher les variables d'environnement utilisateur | variables utilisateur, mes variables |
| `chemin_path` | powershell | Afficher le PATH systeme | montre le path, affiche le path |
| `deconnexion_windows` | powershell | Deconnexion de la session Windows | deconnecte moi, deconnexion |
| `hibernation` | powershell | Mettre en hibernation | hiberne, hibernation |
| `planifier_arret` | powershell | Planifier un arret dans X minutes | eteins dans {minutes} minutes, arret dans {minutes} minutes |
| `annuler_arret` | powershell | Annuler un arret programme | annule l'arret, annuler shutdown |
| `heure_actuelle` | powershell | Donner l'heure actuelle | quelle heure est-il, quelle heure |
| `date_actuelle` | powershell | Donner la date actuelle | quelle date, quel jour on est |
| `ecran_externe_etendre` | powershell | Etendre sur ecran externe | etends l'ecran, ecran etendu |
| `ecran_duplique` | powershell | Dupliquer l'ecran | duplique l'ecran, ecran duplique |
| `ecran_interne_seul` | powershell | Ecran interne uniquement | ecran principal seulement, ecran interne seul |
| `ecran_externe_seul` | powershell | Ecran externe uniquement | ecran externe seulement, ecran externe seul |
| `ram_usage` | powershell | Utilisation de la RAM | utilisation ram, combien de ram |
| `cpu_usage` | powershell | Utilisation du processeur | utilisation cpu, charge du processeur |
| `cpu_info` | powershell | Informations sur le processeur | quel processeur, info cpu |
| `ram_info` | powershell | Informations detaillees sur la RAM | info ram, details ram |
| `batterie_niveau` | powershell | Niveau de batterie | niveau de batterie, combien de batterie |
| `disque_sante` | powershell | Sante des disques (SMART) | sante des disques, etat des disques |
| `carte_mere` | powershell | Informations carte mere | info carte mere, quelle carte mere |
| `bios_info` | powershell | Informations BIOS | info bios, version bios |
| `top_ram` | powershell | Top 10 processus par RAM | quoi consomme la ram, top ram |
| `top_cpu` | powershell | Top 10 processus par CPU | quoi consomme le cpu, top cpu |
| `carte_graphique` | powershell | Informations carte graphique | quelle carte graphique, info gpu detaille |
| `windows_version` | powershell | Version exacte de Windows | version de windows, quelle version windows |
| `dns_changer_google` | powershell | Changer DNS vers Google (8.8.8.8) | mets le dns google, change le dns en google |
| `dns_changer_cloudflare` | powershell | Changer DNS vers Cloudflare (1.1.1.1) | mets le dns cloudflare, change le dns en cloudflare |
| `dns_reset` | powershell | Remettre le DNS en automatique | dns automatique, reset le dns |
| `ports_ouverts` | powershell | Lister les ports ouverts | ports ouverts, quels ports sont ouverts |
| `ip_publique` | powershell | Obtenir l'IP publique | mon ip publique, quelle est mon ip publique |
| `partage_reseau` | powershell | Lister les partages reseau | partages reseau, dossiers partages |
| `connexions_actives` | powershell | Connexions reseau actives | connexions actives, qui est connecte |
| `vitesse_reseau` | powershell | Vitesse de la carte reseau | vitesse reseau, debit carte reseau |
| `arp_table` | powershell | Afficher la table ARP | table arp, arp |
| `test_port` | powershell | Tester si un port est ouvert sur une machine | teste le port {port} sur {host}, port {port} ouvert sur {host} |
| `route_table` | powershell | Afficher la table de routage | table de routage, routes reseau |
| `nslookup` | powershell | Resolution DNS d'un domaine | nslookup {domaine}, resous {domaine} |
| `certificat_ssl` | powershell | Verifier le certificat SSL d'un site | certificat ssl de {site}, check ssl {site} |
| `voir_logs` | powershell | Voir les logs systeme ou JARVIS | les logs, voir les logs |
| `ouvrir_widgets` | hotkey | Ouvrir le panneau Widgets Windows | ouvre les widgets, widgets windows |
| `partage_proximite_on` | powershell | Activer le partage de proximite | active le partage de proximite, nearby sharing on |
| `screen_recording` | hotkey | Lancer l'enregistrement d'ecran (Game Bar) | enregistre l'ecran, screen recording |
| `game_bar` | hotkey | Ouvrir la Game Bar Xbox | ouvre la game bar, game bar |
| `parametres_notifications` | powershell | Ouvrir les parametres de notifications | parametres notifications, gere les notifications |
| `parametres_apps_defaut` | powershell | Ouvrir les apps par defaut | apps par defaut, applications par defaut |
| `parametres_about` | powershell | A propos de ce PC | a propos du pc, about this pc |
| `verifier_sante_disque` | powershell | Verifier la sante des disques | sante des disques, health check disque |
| `vitesse_internet` | powershell | Tester la vitesse internet | test de vitesse, speed test |
| `historique_mises_a_jour` | powershell | Voir l'historique des mises a jour Windows | historique updates, dernieres mises a jour |
| `taches_planifiees` | powershell | Lister les taches planifiees | taches planifiees, scheduled tasks |
| `demarrage_apps` | powershell | Voir les apps au demarrage | apps au demarrage, startup apps |
| `certificats_ssl` | powershell | Verifier un certificat SSL | verifie le ssl de {site}, certificat ssl {site} |
| `audio_sortie` | powershell | Changer la sortie audio | change la sortie audio, sortie audio |
| `audio_entree` | powershell | Configurer le microphone | configure le micro, entree audio |
| `volume_app` | powershell | Mixer de volume par application | mixer volume, volume par application |
| `micro_mute_toggle` | powershell | Couper/reactiver le micro | coupe le micro, mute le micro |
| `liste_imprimantes` | powershell | Lister les imprimantes | liste les imprimantes, quelles imprimantes |
| `imprimante_defaut` | powershell | Voir l'imprimante par defaut | imprimante par defaut, quelle imprimante |
| `param_imprimantes` | powershell | Ouvrir les parametres imprimantes | parametres imprimantes, settings imprimantes |
| `sandbox_ouvrir` | powershell | Ouvrir Windows Sandbox | ouvre la sandbox, windows sandbox |
| `plan_alimentation_actif` | powershell | Voir le plan d'alimentation actif | quel plan alimentation, power plan actif |
| `batterie_rapport` | powershell | Generer un rapport de batterie | rapport batterie, battery report |
| `ecran_timeout` | powershell | Configurer la mise en veille ecran | timeout ecran, ecran en veille apres |
| `detecter_ecrans` | powershell | Detecter les ecrans connectes | detecte les ecrans, detect displays |
| `param_affichage` | powershell | Ouvrir les parametres d'affichage | parametres affichage, settings display |
| `kill_process_nom` | powershell | Tuer un processus par nom | tue le processus {nom}, kill {nom} |
| `processus_details` | powershell | Details d'un processus | details du processus {nom}, info processus {nom} |
| `diagnostic_reseau` | powershell | Lancer un diagnostic reseau complet | diagnostic reseau, diagnostique le reseau |
| `wifi_mot_de_passe` | powershell | Afficher le mot de passe WiFi actuel | mot de passe wifi, password wifi |
| `ouvrir_evenements` | powershell | Ouvrir l'observateur d'evenements | observateur evenements, event viewer |
| `ouvrir_services` | powershell | Ouvrir les services Windows | ouvre les services, services windows |
| `ouvrir_moniteur_perf` | powershell | Ouvrir le moniteur de performances | moniteur de performance, performance monitor |
| `ouvrir_fiabilite` | powershell | Ouvrir le moniteur de fiabilite | moniteur de fiabilite, reliability monitor |
| `action_center` | hotkey | Ouvrir le centre de notifications | centre de notifications, notification center |
| `quick_settings` | hotkey | Ouvrir les parametres rapides | parametres rapides, quick settings |
| `search_windows` | hotkey | Ouvrir la recherche Windows | recherche windows, windows search |
| `hyper_v_manager` | powershell | Ouvrir le gestionnaire Hyper-V | ouvre hyper-v, lance hyper-v |
| `storage_sense` | powershell | Activer l'assistant de stockage | active l'assistant de stockage, storage sense |
| `creer_point_restauration` | powershell | Creer un point de restauration systeme | cree un point de restauration, point de restauration |
| `voir_hosts` | powershell | Afficher le fichier hosts | montre le fichier hosts, affiche hosts |
| `dxdiag` | powershell | Lancer le diagnostic DirectX | lance dxdiag, diagnostic directx |
| `memoire_diagnostic` | powershell | Lancer le diagnostic memoire Windows | diagnostic memoire, teste la memoire |
| `reset_reseau` | powershell | Reinitialiser la pile reseau | reinitialise le reseau, reset reseau |
| `bitlocker_status` | powershell | Verifier le statut BitLocker | statut bitlocker, etat bitlocker |
| `windows_update_pause` | powershell | Mettre en pause les mises a jour Windows | pause les mises a jour, suspends les mises a jour |
| `mode_developpeur` | powershell | Activer/desactiver le mode developpeur | active le mode developpeur, mode developpeur |
| `remote_desktop` | powershell | Parametres Bureau a distance | bureau a distance, remote desktop |
| `credential_manager` | powershell | Ouvrir le gestionnaire d'identifiants | gestionnaire d'identifiants, credential manager |
| `certmgr` | powershell | Ouvrir le gestionnaire de certificats | gestionnaire de certificats, certificats windows |
| `chkdsk_check` | powershell | Verifier les erreurs du disque | verifie le disque, check disk |
| `file_history` | powershell | Parametres historique des fichiers | historique des fichiers, file history |
| `troubleshoot_reseau` | powershell | Lancer le depannage reseau | depanne le reseau, depannage reseau |
| `troubleshoot_audio` | powershell | Lancer le depannage audio | depanne le son, depannage audio |
| `troubleshoot_update` | powershell | Lancer le depannage Windows Update | depanne windows update, depannage mises a jour |
| `power_options` | powershell | Options d'alimentation avancees | options d'alimentation, power options |
| `copilot_parametres` | ms_settings | Parametres de Copilot | parametres copilot, reglages copilot |
| `cortana_desactiver` | powershell | Desactiver Cortana | desactive cortana, coupe cortana |
| `capture_fenetre` | hotkey | Capturer la fenetre active | capture la fenetre, screenshot fenetre |
| `capture_retardee` | powershell | Capture d'ecran avec delai | capture retardee, screenshot retarde |
| `planificateur_ouvrir` | powershell | Ouvrir le planificateur de taches | planificateur de taches, ouvre le planificateur |
| `creer_tache_planifiee` | powershell | Creer une tache planifiee | cree une tache planifiee, nouvelle tache planifiee |
| `lister_usb` | powershell | Lister les peripheriques USB connectes | liste les usb, peripheriques usb |
| `ejecter_usb` | powershell | Ejecter un peripherique USB en securite | ejecte l'usb, ejecter usb |
| `peripheriques_connectes` | powershell | Lister tous les peripheriques connectes | peripheriques connectes, liste les peripheriques |
| `lister_adaptateurs` | powershell | Lister les adaptateurs reseau | liste les adaptateurs reseau, adaptateurs reseau |
| `desactiver_wifi_adaptateur` | powershell | Desactiver l'adaptateur Wi-Fi | desactive le wifi, coupe l'adaptateur wifi |
| `activer_wifi_adaptateur` | powershell | Activer l'adaptateur Wi-Fi | active l'adaptateur wifi, reactive le wifi |
| `firewall_status` | powershell | Afficher le statut du pare-feu | statut pare-feu, statut firewall |
| `firewall_regles` | powershell | Lister les regles du pare-feu | regles pare-feu, regles firewall |
| `firewall_reset` | powershell | Reinitialiser le pare-feu | reinitialise le pare-feu, reset firewall |
| `ajouter_langue` | ms_settings | Ajouter une langue au systeme | ajoute une langue, installer une langue |
| `ajouter_clavier` | ms_settings | Ajouter une disposition de clavier | ajoute un clavier, nouveau clavier |
| `langues_installees` | powershell | Lister les langues installees | langues installees, quelles langues |
| `synchroniser_heure` | powershell | Synchroniser l'heure avec le serveur NTP | synchronise l'heure, sync heure |
| `serveur_ntp` | powershell | Afficher le serveur NTP configure | serveur ntp, quel serveur ntp |
| `windows_hello` | ms_settings | Parametres Windows Hello | windows hello, hello biometrique |
| `securite_comptes` | ms_settings | Securite des comptes Windows | securite des comptes, securite compte |
| `activation_windows` | powershell | Verifier l'activation Windows | activation windows, windows active |
| `recuperation_systeme` | ms_settings | Options de recuperation systeme | recuperation systeme, options de recuperation |
| `gpu_temperatures` | powershell | Temperatures GPU via nvidia-smi | temperatures gpu, gpu temperature |
| `vram_usage` | powershell | Utilisation VRAM de toutes les GPU | utilisation vram, vram utilisee |
| `disk_io` | powershell | Activite I/O des disques | activite des disques, io disques |
| `network_io` | powershell | Debit reseau en temps reel | debit reseau, trafic reseau |
| `services_failed` | powershell | Services Windows en echec | services en echec, services plantes |
| `event_errors` | powershell | Dernières erreurs systeme (Event Log) | erreurs systeme recentes, derniers errors |
| `boot_time` | powershell | Temps de demarrage du dernier boot | temps de demarrage, boot time |
| `nettoyer_prefetch` | powershell | Nettoyer le dossier Prefetch | nettoie prefetch, vide prefetch |
| `nettoyer_thumbnails` | powershell | Nettoyer le cache des miniatures | nettoie les miniatures, vide le cache miniatures |
| `nettoyer_logs` | powershell | Nettoyer les vieux logs | nettoie les logs, supprime les vieux logs |
| `scan_ports_local` | powershell | Scanner les ports ouverts localement | scan mes ports, scan ports local |
| `connexions_suspectes` | powershell | Verifier les connexions sortantes suspectes | connexions suspectes, qui se connecte dehors |
| `autorun_check` | powershell | Verifier les programmes au demarrage | quoi se lance au demarrage, autorun check |
| `defender_scan_rapide` | powershell | Lancer un scan rapide Windows Defender | scan antivirus, lance un scan defender |
| `defender_status` | powershell | Statut de Windows Defender | statut defender, etat antivirus |
| `top_cpu_processes` | powershell | Top 10 processus par CPU | top cpu, processus gourmands cpu |
| `top_ram_processes` | powershell | Top 10 processus par RAM | top ram, processus gourmands ram |
| `uptime_system` | powershell | Uptime du systeme Windows | uptime, depuis combien de temps le pc tourne |
| `windows_update_check` | powershell | Verifier les mises a jour Windows disponibles | mises a jour windows, windows update |
| `ip_publique_externe` | powershell | Obtenir l'adresse IP publique | ip publique, quelle est mon ip |
| `latence_cluster` | powershell | Ping de latence vers les noeuds du cluster | latence cluster, ping le cluster ia |
| `wifi_info` | powershell | Informations sur la connexion WiFi active | info wifi, quel wifi |
| `espace_disques` | powershell | Espace libre sur tous les disques | espace disque, combien d'espace libre |
| `gros_fichiers_bureau` | powershell | Top 10 plus gros fichiers du bureau | plus gros fichiers, gros fichiers bureau |
| `processus_zombies` | powershell | Detecter les processus qui ne repondent pas | processus zombies, processus bloques |
| `dernier_crash` | powershell | Dernier crash ou erreur critique Windows | dernier crash, derniere erreur critique |
| `temps_allumage_apps` | powershell | Depuis combien de temps chaque app tourne | duree des apps, depuis quand les apps tournent |
| `taille_cache_navigateur` | powershell | Taille des caches navigateur Chrome/Edge | taille cache navigateur, cache chrome |
| `nettoyer_cache_navigateur` | powershell | Vider les caches Chrome et Edge | vide le cache navigateur, nettoie le cache chrome |
| `nettoyer_crash_dumps` | powershell | Supprimer les crash dumps Windows | nettoie les crash dumps, supprime les dumps |
| `nettoyer_windows_old` | powershell | Taille du dossier Windows.old (ancien systeme) | taille windows old, windows old |
| `gpu_power_draw` | powershell | Consommation electrique des GPU | consommation gpu, watt gpu |
| `gpu_fan_speed` | powershell | Vitesse des ventilateurs GPU | ventilateurs gpu, fans gpu |
| `gpu_driver_version` | powershell | Version du driver NVIDIA | version driver nvidia, driver gpu |
| `cluster_latence_detaillee` | powershell | Latence detaillee de chaque noeud du cluster avec modeles | latence detaillee cluster, ping detaille cluster |
| `installed_apps_list` | powershell | Lister les applications installees | liste les applications, apps installees |
| `hotfix_history` | powershell | Historique des correctifs Windows installes | historique hotfix, correctifs installes |
| `scheduled_tasks_active` | powershell | Taches planifiees actives | taches planifiees actives, scheduled tasks |
| `tpm_info` | powershell | Informations sur le module TPM | info tpm, tpm status |
| `printer_list` | powershell | Imprimantes installees et leur statut | liste les imprimantes, imprimantes installees |
| `startup_impact` | powershell | Impact des programmes au demarrage sur le boot | impact demarrage, startup impact |
| `system_info_detaille` | powershell | Infos systeme detaillees (OS, BIOS, carte mere) | infos systeme detaillees, system info |
| `ram_slots_detail` | powershell | Details des barrettes RAM (type, vitesse, slots) | details ram, barrettes ram |
| `cpu_details` | powershell | Details du processeur (coeurs, threads, frequence) | details cpu, info processeur |
| `network_adapters_list` | powershell | Adaptateurs reseau actifs et leur configuration | adaptateurs reseau, interfaces reseau |
| `dns_cache_view` | powershell | Voir le cache DNS local | cache dns, dns cache |
| `recycle_bin_size` | powershell | Taille de la corbeille | taille corbeille, poids corbeille |
| `temp_folder_size` | powershell | Taille du dossier temporaire | taille du temp, dossier temp |
| `last_shutdown_time` | powershell | Heure du dernier arret du PC | dernier arret, quand le pc s'est eteint |
| `bluescreen_history` | powershell | Historique des ecrans bleus (BSOD) | ecrans bleus, bsod |
| `disk_smart_health` | powershell | Etat de sante SMART des disques | sante disques, smart disques |
| `firewall_rules_count` | powershell | Nombre de regles firewall par profil | regles firewall, combien de regles pare-feu |
| `env_variables_key` | powershell | Variables d'environnement cles (PATH, TEMP, etc.) | variables environnement, env vars |
| `sfc_scan` | powershell | Lancer un scan d'integrite systeme (sfc /scannow) | scan integrite, sfc scannow |
| `dism_health_check` | powershell | Verifier la sante de l'image Windows (DISM) | dism health, sante windows |
| `system_restore_points` | powershell | Lister les points de restauration systeme | points de restauration, restore points |
| `usb_devices_list` | powershell | Lister les peripheriques USB connectes | peripheriques usb, usb connectes |
| `bluetooth_devices` | powershell | Lister les peripheriques Bluetooth | peripheriques bluetooth, bluetooth connectes |
| `certificates_list` | powershell | Certificats systeme installes (racine) | certificats installes, certificates |
| `page_file_info` | powershell | Configuration du fichier de pagination (swap) | page file, fichier de pagination |
| `windows_features` | powershell | Fonctionnalites Windows activees | fonctionnalites windows, features windows |
| `power_plan_active` | powershell | Plan d'alimentation actif et ses details | plan alimentation, power plan |
| `bios_version` | powershell | Version du BIOS et date | version bios, bios info |
| `windows_version_detail` | powershell | Version detaillee de Windows (build, edition) | version windows, quelle version windows |
| `network_connections_count` | powershell | Nombre de connexions reseau actives par etat | connexions reseau actives, combien de connexions |
| `drivers_probleme` | powershell | Pilotes en erreur ou problematiques | pilotes en erreur, drivers probleme |
| `shared_folders` | powershell | Dossiers partages sur ce PC | dossiers partages, partages reseau |
| `focus_app_name` | powershell | Mettre le focus sur une application par son nom | va sur {app}, bascule sur {app} |
| `fermer_app_name` | powershell | Fermer une application par son nom | ferme {app}, tue {app} |
| `liste_fenetres_ouvertes` | powershell | Lister toutes les fenetres ouvertes avec leur titre | quelles fenetres sont ouvertes, liste les fenetres |
| `fenetre_toujours_visible` | powershell | Rendre la fenetre active always-on-top | toujours visible, always on top |
| `deplacer_fenetre_moniteur` | hotkey | Deplacer la fenetre active vers l'autre moniteur | fenetre autre ecran, deplace sur l'autre ecran |
| `centrer_fenetre` | powershell | Centrer la fenetre active sur l'ecran | centre la fenetre, fenetre au centre |
| `switch_audio_output` | powershell | Lister et changer la sortie audio | change la sortie audio, switch audio |
| `toggle_wifi` | powershell | Activer/desactiver le WiFi | toggle wifi, active le wifi |
| `toggle_bluetooth` | powershell | Activer/desactiver le Bluetooth | toggle bluetooth, active le bluetooth |
| `toggle_dark_mode` | powershell | Basculer entre mode sombre et mode clair | mode sombre, dark mode |
| `taper_date` | powershell | Taper la date du jour automatiquement | tape la date, ecris la date |
| `taper_heure` | powershell | Taper l'heure actuelle automatiquement | tape l'heure, ecris l'heure |
| `vider_clipboard` | powershell | Vider le presse-papier | vide le presse papier, clear clipboard |
| `dismiss_notifications` | hotkey | Fermer toutes les notifications Windows | ferme les notifications, dismiss notifications |
| `ouvrir_gestionnaire_peripheriques` | powershell | Ouvrir le Gestionnaire de peripheriques | gestionnaire de peripheriques, device manager |
| `ouvrir_gestionnaire_disques` | powershell | Ouvrir la Gestion des disques | gestion des disques, disk management |
| `ouvrir_services_windows` | powershell | Ouvrir la console Services Windows | services windows, console services |
| `ouvrir_registre` | powershell | Ouvrir l'editeur de registre | editeur de registre, regedit |
| `ouvrir_event_viewer` | powershell | Ouvrir l'observateur d'evenements | observateur d'evenements, event viewer |
| `hibernation_profonde` | powershell | Mettre le PC en hibernation profonde | hiberne le pc maintenant, hibernation profonde |
| `restart_bios` | powershell | Redemarrer vers le BIOS/UEFI | redemarre dans le bios, restart bios |
| `taskbar_app_1` | hotkey | Lancer la 1ere app epinglee dans la taskbar | premiere app taskbar, app 1 taskbar |
| `taskbar_app_2` | hotkey | Lancer la 2eme app epinglee dans la taskbar | deuxieme app taskbar, app 2 taskbar |
| `taskbar_app_3` | hotkey | Lancer la 3eme app epinglee dans la taskbar | troisieme app taskbar, app 3 taskbar |
| `taskbar_app_4` | hotkey | Lancer la 4eme app epinglee dans la taskbar | quatrieme app taskbar, app 4 taskbar |
| `taskbar_app_5` | hotkey | Lancer la 5eme app epinglee dans la taskbar | cinquieme app taskbar, app 5 taskbar |
| `fenetre_autre_bureau` | hotkey | Deplacer la fenetre vers le bureau virtuel suivant | fenetre bureau suivant, deplace la fenetre sur l'autre bureau |
| `browser_retour` | hotkey | Page precedente dans le navigateur | page precedente, retour arriere |
| `browser_avancer` | hotkey | Page suivante dans le navigateur | page suivante, avance |
| `browser_rafraichir` | hotkey | Rafraichir la page web | rafraichis la page, reload |
| `browser_hard_refresh` | hotkey | Rafraichir sans cache | hard refresh, rafraichis sans cache |
| `browser_private` | hotkey | Ouvrir une fenetre de navigation privee | navigation privee, fenetre privee |
| `browser_bookmark` | hotkey | Ajouter la page aux favoris | ajoute aux favoris, bookmark |
| `browser_address_bar` | hotkey | Aller dans la barre d'adresse | barre d'adresse, address bar |
| `browser_fermer_tous_onglets` | powershell | Fermer tous les onglets sauf l'actif | ferme tous les onglets, close all tabs |
| `browser_epingler_onglet` | powershell | Epingler/detacher l'onglet actif | epingle l'onglet, pin tab |
| `texte_debut_ligne` | hotkey | Aller au debut de la ligne | debut de ligne, home |
| `texte_fin_ligne` | hotkey | Aller a la fin de la ligne | fin de ligne, end |
| `texte_debut_document` | hotkey | Aller au debut du document | debut du document, tout en haut |
| `texte_fin_document` | hotkey | Aller a la fin du document | fin du document, tout en bas |
| `texte_selectionner_ligne` | hotkey | Selectionner la ligne entiere | selectionne la ligne, select line |
| `texte_supprimer_ligne` | hotkey | Supprimer la ligne entiere (VSCode) | supprime la ligne, delete line |
| `texte_dupliquer_ligne` | hotkey | Dupliquer la ligne (VSCode) | duplique la ligne, duplicate line |
| `texte_deplacer_ligne_haut` | hotkey | Deplacer la ligne vers le haut (VSCode) | monte la ligne, move line up |
| `texte_deplacer_ligne_bas` | hotkey | Deplacer la ligne vers le bas (VSCode) | descends la ligne, move line down |
| `vscode_palette` | hotkey | Ouvrir la palette de commandes VSCode | palette de commandes, command palette |
| `vscode_terminal` | hotkey | Ouvrir/fermer le terminal VSCode | terminal vscode, ouvre le terminal intergre |
| `vscode_sidebar` | hotkey | Afficher/masquer la sidebar VSCode | sidebar vscode, panneau lateral |
| `vscode_go_to_file` | hotkey | Rechercher et ouvrir un fichier dans VSCode | ouvre un fichier vscode, go to file |
| `vscode_go_to_line` | hotkey | Aller a une ligne dans VSCode | va a la ligne, go to line |
| `vscode_split_editor` | hotkey | Diviser l'editeur VSCode en deux | divise l'editeur, split editor |
| `vscode_close_all` | hotkey | Fermer tous les fichiers ouverts dans VSCode | ferme tous les fichiers vscode, close all tabs vscode |
| `explorer_dossier_parent` | hotkey | Remonter au dossier parent dans l'Explorateur | dossier parent, remonte d'un dossier |
| `explorer_nouveau_dossier` | hotkey | Creer un nouveau dossier dans l'Explorateur | nouveau dossier, cree un dossier |
| `explorer_afficher_caches` | powershell | Afficher les fichiers caches dans l'Explorateur | montre les fichiers caches, fichiers caches |
| `explorer_masquer_caches` | powershell | Masquer les fichiers caches | cache les fichiers caches, masque les fichiers invisibles |

### TRADING (19)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `scanner_marche` | script | Scanner le marche MEXC | scanne le marche, scanner le marche |
| `detecter_breakout` | script | Detecter les breakouts | detecte les breakouts, cherche les breakouts |
| `pipeline_trading` | script | Lancer le pipeline intensif | lance le pipeline, pipeline intensif |
| `sniper_breakout` | script | Lancer le sniper breakout | lance le sniper, sniper breakout |
| `river_scalp` | script | Lancer le River Scalp 1min | lance river scalp, river scalp |
| `hyper_scan` | script | Lancer l'hyper scan V2 | lance hyper scan, hyper scan |
| `statut_cluster` | jarvis_tool | Statut du cluster IA | statut du cluster, etat du cluster |
| `modeles_charges` | jarvis_tool | Modeles charges sur le cluster | quels modeles sont charges, liste les modeles |
| `ollama_status` | jarvis_tool | Statut du backend Ollama | statut ollama, etat ollama |
| `ollama_modeles` | jarvis_tool | Modeles Ollama disponibles | modeles ollama, liste modeles ollama |
| `recherche_web_ia` | jarvis_tool | Recherche web via Ollama cloud | recherche web {requete}, cherche sur le web {requete} |
| `consensus_ia` | jarvis_tool | Consensus multi-IA | consensus sur {question}, demande un consensus sur {question} |
| `query_ia` | jarvis_tool | Interroger une IA locale | demande a {node} {prompt}, interroge {node} sur {prompt} |
| `signaux_trading` | jarvis_tool | Signaux de trading en attente | signaux en attente, quels signaux |
| `positions_trading` | jarvis_tool | Positions de trading ouvertes | mes positions, positions ouvertes |
| `statut_trading` | jarvis_tool | Statut global du trading | statut trading, etat du trading |
| `executer_signal` | jarvis_tool | Executer un signal de trading | execute le signal {id}, lance le signal {id} |
| `cluster_health` | powershell | Health check rapide du cluster IA | health check cluster, verifie le cluster ia |
| `ollama_running` | powershell | Modeles Ollama actuellement en memoire | quels modeles ollama tournent, ollama running |

</details
--- Generated 1053 lines for 955 commands ---


---

## Licence

Projet prive — **Turbo31150** — 2026
