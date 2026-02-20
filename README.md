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
11. [Architecture Vocale](#architecture-vocale)
12. [Trading MEXC](#trading-mexc-futures)
13. [Modes de Lancement](#modes-de-lancement)
14. [Structure du Projet](#structure-du-projet)
15. [Bases de Donnees](#bases-de-donnees)
16. [Installation & Configuration](#installation--configuration)
17. [Appels API — Exemples Complets](#appels-api--exemples-complets)

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

## Architecture Vocale

```
Micro (Sony WH-1000XM4 Bluetooth)
       |
       v
 Whisper (faster-whisper CUDA, GPU)
       |
       v
 Correction Pipeline
 ├── Dictionnaire local (438 commandes)
 └── OL1 qwen3:1.7b (correction IA, timeout 8s)
       |
       v
 Command Match (fuzzy matching, 438 cmds)
       |
  +----+----+
  |         |
  v         v
MATCH     NO MATCH
(execute)  (Commander Mode)
             |
             v
        M2 pre-analyse (deepseek-coder, champion)
             |
             v
        Claude dispatche (COMMANDER_PROMPT)
             |
             v
        TTS (Windows SAPI)
```

| Parametre | Valeur |
|-----------|--------|
| Micro | Sony WH-1000XM4 Bluetooth |
| STT | faster-whisper CUDA |
| Wake word | "jarvis" → attend commande |
| Exit confidence | >= 0.85 |
| Commandes | 438 commandes vocales |
| TTS | Windows SAPI |
| Cache micro | check_microphone() 30s |

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
|   |-- commands.py              # 438 commandes vocales (18 vagues)
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

## Licence

Projet prive — **Turbo31150** — 2026
