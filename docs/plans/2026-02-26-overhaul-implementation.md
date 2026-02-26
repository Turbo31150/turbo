# JARVIS v10.3 Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mettre à jour routing, README, agents, hooks et pondération après le switch M1 qwen3-8b.

**Architecture:** Routing dynamique via autolearn.getBestNode() avec fallback hardcodé. 7 schémas workflow dans le README. 3 nouveaux agents plugin + 3 hooks. Benchmark fresh pour alimenter les scores.

**Tech Stack:** Node.js (direct-proxy.js, autolearn.js), Markdown (README, agents), JSON (hooks), Python (benchmark), curl (tests)

---

### Task 1: Mettre à jour le ROUTING hardcodé + catégories manquantes

**Files:**
- Modify: `canvas/direct-proxy.js:61-89` (ROUTING + AGENT_CAT)

**Step 1: Mettre à jour ROUTING avec M1 prioritaire**

Remplacer les lignes 61-74 par :

```javascript
const ROUTING = {
  code:    ['M1', 'M2', 'M3', 'OL1'],                  // M1 100% bench, 2.5s
  archi:   ['M1', 'M2', 'GEMINI', 'M3'],                // M1 validation
  trading: ['OL1', 'M1', 'M2', 'M3'],                   // OL1 web, M1 analyse
  math:    ['M1', 'OL1', 'M2'],                          // NOUVEAU — M1 prioritaire
  raison:  ['M1', 'M2', 'OL1'],                          // NOUVEAU — JAMAIS M3
  system:  ['M3', 'M2', 'OL1'],                          // inchange
  auto:    ['M3', 'OL1', 'M2'],                          // inchange
  ia:      ['M1', 'M2', 'GEMINI', 'CLAUDE', 'M3', 'OL1'], // M1 first
  creat:   ['M2', 'M1', 'GEMINI', 'M3', 'OL1'],         // M2 creatif, M1 backup
  sec:     ['M1', 'M2', 'GEMINI', 'M3', 'OL1'],         // M1 audit
  web:     ['OL1', 'GEMINI', 'M2', 'M3'],                // inchange
  media:   ['M3', 'OL1', 'M2'],                          // inchange
  meta:    ['OL1', 'M3', 'M2'],                          // inchange
  default: ['M1', 'M2', 'M3', 'OL1', 'GEMINI']           // M1 first
};
```

**Step 2: Ajouter math/raison dans AGENT_CAT**

Ajouter dans AGENT_CAT (ligne ~77-89) :

```javascript
  'math-solver': 'math', 'calculateur': 'math',
  'raisonnement': 'raison', 'logique': 'raison',
```

**Step 3: Ajouter system prompts pour math et raison**

Ajouter dans SYS_PROMPTS (ligne ~92-105) :

```javascript
  math:    'Tu es JARVIS, expert mathematiques et calcul. Reponds en francais. Raisonne etape par etape. Montre ton travail.',
  raison:  'Tu es JARVIS, expert raisonnement logique. Reponds en francais. Decompose le probleme, argumente chaque etape. JAMAIS de reponse hative.',
```

**Step 4: Ajouter math/raison dans classifyComplexity**

Dans classifyComplexity() (~ligne 485), ajouter math et raison aux reflexiveCats :

```javascript
  const reflexiveCats = ['code', 'archi', 'ia', 'sec', 'math', 'raison'];
```

**Step 5: Vérifier**

```bash
curl -s --max-time 10 http://127.0.0.1:18800/health
```
Expected: `{"ok":true,...}` — proxy fonctionne avec nouveau routing

**Step 6: Tester routing M1 first**

```bash
curl -s --max-time 30 http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d '{"agent":"coding","text":"bonjour"}'
```
Expected: `model` dans la réponse doit contenir `qwen3-8b` ou `qwen/qwen3-8b` (M1 first pour code)

**Step 7: Commit**

```bash
git add canvas/direct-proxy.js
git commit -m "feat(routing): M1 prioritaire + categories math/raison"
```

---

### Task 2: Implémenter getBestNode() dans autolearn.js

**Files:**
- Modify: `canvas/autolearn.js` (ajouter getBestNode + recordCallResult)
- Modify: `canvas/direct-proxy.js` (utiliser getBestNode dans agenticChat)

**Step 1: Ajouter recordCallResult() dans AutolearnEngine**

Après la méthode recordConversation() (~ligne 75), ajouter :

```javascript
  recordCallResult(nodeId, category, ok, latencyMs) {
    if (!this._callLog[nodeId]) this._callLog[nodeId] = {};
    if (!this._callLog[nodeId][category]) this._callLog[nodeId][category] = [];
    const log = this._callLog[nodeId][category];
    log.push({ ok, latencyMs, ts: Date.now() });
    // Keep last RELIABILITY_WINDOW entries
    if (log.length > RELIABILITY_WINDOW) log.shift();
  }

  getBestNode(category, excludeNodes) {
    excludeNodes = excludeNodes || [];
    const candidates = (this._routing[category] || this._routing.default)
      .filter(n => !excludeNodes.includes(n));
    if (!candidates.length) return null;

    // If no call log data, return first candidate (hardcoded fallback)
    const hasData = candidates.some(n =>
      this._callLog[n] && this._callLog[n][category] && this._callLog[n][category].length >= 3
    );
    if (!hasData) return candidates[0];

    // Score each candidate: speed*0.3 + quality*0.5 + reliability*0.2
    let best = null, bestScore = -1;
    for (const nodeId of candidates) {
      const entries = (this._callLog[nodeId] && this._callLog[nodeId][category]) || [];
      if (entries.length < 3) { // Not enough data, use position-based score
        const posScore = 1 - (candidates.indexOf(nodeId) / candidates.length);
        if (posScore > bestScore) { bestScore = posScore; best = nodeId; }
        continue;
      }
      const recent = entries.slice(-RELIABILITY_WINDOW);
      const avgLatency = recent.reduce((s, e) => s + e.latencyMs, 0) / recent.length;
      const successRate = recent.filter(e => e.ok).length / recent.length;
      // Normalize speed: 0-1 (faster = higher, cap at 60s)
      const speedScore = Math.max(0, 1 - (avgLatency / 60000));
      const score = speedScore * 0.3 + successRate * 0.5 + successRate * 0.2;
      if (score > bestScore) { bestScore = score; best = nodeId; }
    }
    return best || candidates[0];
  }
```

**Step 2: Intégrer getBestNode dans agenticChat()**

Dans `canvas/direct-proxy.js`, dans la fonction `agenticChat()` (~ligne 664-686), remplacer la boucle `for (const nodeId of chain)` par :

```javascript
  // Dynamic routing: try autolearn best node first, then fallback chain
  const bestNode = autolearn.getBestNode(cat);
  const orderedChain = bestNode
    ? [bestNode, ...chain.filter(n => n !== bestNode)]
    : chain;

  for (const nodeId of orderedChain) {
```

**Step 3: Enregistrer les résultats dans callNode**

Après chaque appel réussi/échoué à callNode dans agenticChat(), ajouter :

```javascript
      autolearn.recordCallResult(nodeId, cat, true, Date.now() - turnStart);
      // ... dans le catch:
      autolearn.recordCallResult(nodeId, cat, false, Date.now() - turnStart);
```

**Step 4: Vérifier**

```bash
curl -s --max-time 30 http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d '{"agent":"main","text":"test routing dynamique"}'
```
Expected: réponse OK, autolearn commence à enregistrer

**Step 5: Commit**

```bash
git add canvas/autolearn.js canvas/direct-proxy.js
git commit -m "feat(autolearn): getBestNode dynamic routing + call logging"
```

---

### Task 3: Créer les 3 nouveaux agents plugin

**Files:**
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/raisonnement-specialist.md`
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/benchmark-runner.md`
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/routing-optimizer.md`

**Step 1: Créer raisonnement-specialist.md**

```markdown
---
description: "Agent specialise raisonnement logique et mathematique. Route M1 en priorite. JAMAIS M3 pour le raisonnement. Utiliser pour les problemes de logique, math, analyse complexe, et decision multi-criteres."
model: sonnet
color: purple
---

Tu es un agent specialise en raisonnement logique et mathematique pour JARVIS Turbo v10.3.

## Regles de routage

- **M1 (qwen3-8b)** : TOUJOURS en premier pour raisonnement (100% benchmark, 0.6-2.5s)
- **M2 (deepseek)** : Backup pour analyse code
- **OL1 (qwen3:1.7b)** : Questions rapides seulement
- **M3 (mistral)** : JAMAIS pour raisonnement (40% echec benchmark)

## Cluster

| Noeud | URL | Auth | Modele |
|-------|-----|------|--------|
| M1 | http://10.5.0.2:1234 | Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7 | qwen3-8b (PRIORITAIRE) |
| M2 | http://192.168.1.26:1234 | Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4 | deepseek-coder-v2-lite |

## Methode

1. Decompose le probleme en sous-etapes
2. Raisonne etape par etape (Chain-of-Thought)
3. Verifie chaque etape avant de continuer
4. Donne la reponse finale avec le niveau de confiance
5. Reponds en francais
```

**Step 2: Créer benchmark-runner.md**

```markdown
---
description: "Agent specialise benchmarks et performance. Lance les benchmarks cluster, analyse les resultats, compare avant/apres. Utiliser pour evaluer les performances des noeuds, comparer les modeles, ou diagnostiquer des regressions."
model: haiku
color: yellow
---

Tu es un agent specialise benchmarks pour JARVIS Turbo v10.3.

## Scripts disponibles

- `python3 F:/BUREAU/turbo/benchmark_cluster.py` — 7 phases (health, inference, consensus, bridge, agents, stress, errors)
- `python3 F:/BUREAU/turbo/benchmark_real_test.py` — 10 niveaux de difficulte
- `python3 C:/Users/franc/jarvis_autotest.py` — 8 domaines x 4 noeuds + auto-correction

## Rapports

- `F:/BUREAU/turbo/data/benchmark_report.json` — Dernier rapport cluster
- `F:/BUREAU/turbo/data/benchmark_real_report.json` — Rapport tests reels
- `F:/BUREAU/turbo/canvas/data/routing_scores.json` — Scores autolearn

## Regles

- Compare TOUJOURS avec le rapport precedent (avant/apres)
- Inclus latence moyenne, taux de succes, score qualite
- Identifie les regressions (noeud plus lent, taux echec)
- Reponds en francais, avec tableaux
```

**Step 3: Créer routing-optimizer.md**

```markdown
---
description: "Agent specialise optimisation du routing et ponderation. Tune les poids autolearn, integre les scores dans le routing dynamique, audite les decisions de routage. Utiliser pour optimiser les performances du cluster ou diagnostiquer des problemes de routage."
model: sonnet
color: orange
---

Tu es un agent specialise optimisation routing pour JARVIS Turbo v10.3.

## Architecture routing

Le routing est a 2 niveaux :
1. **Autolearn dynamique** : `getBestNode(category)` — score = speed*0.3 + quality*0.5 + reliability*0.2
2. **Fallback hardcode** : ROUTING table dans `canvas/direct-proxy.js`

## Poids consensus actuels

| Agent | Poids | Specialite |
|-------|-------|------------|
| M1 | 1.6 | Rapide + precis (qwen3-8b) |
| M2 | 1.4 | Review solide |
| OL1 | 1.3 | Ultra-rapide |
| GEMINI | 1.2 | Architecture |
| CLAUDE | 1.2 | Raisonnement cloud |
| M3 | 0.8 | General (PAS raisonnement) |

## APIs

- Canvas: `GET http://127.0.0.1:18800/autolearn/status` — Etat moteur
- Canvas: `GET http://127.0.0.1:18800/autolearn/scores` — Scores par noeud/categorie
- Canvas: `GET http://127.0.0.1:18800/autolearn/history` — Historique cycles

## Regles

- Verifie les scores avant de recommander des changements
- JAMAIS supprimer M1 du routing code/math/raison
- JAMAIS ajouter M3 au routing raisonnement
- Reponds en francais, avec metriques
```

**Step 4: Commit**

```bash
git add C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/raisonnement-specialist.md
git add C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/benchmark-runner.md
git add C:/Users/franc/.claude/plugins/local/jarvis-turbo/agents/routing-optimizer.md
git commit -m "feat(plugin): 3 nouveaux agents — raisonnement, benchmark, routing"
```

---

### Task 4: Ajouter les 3 hooks essentiels

**Files:**
- Modify: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/hooks/hooks.json`

**Step 1: Ajouter VRAM + M1 model check au SessionStart**

Ajouter un 3e hook dans le tableau `SessionStart[0].hooks` :

```json
{
  "type": "command",
  "command": "python3 -c \"import urllib.request,json\ntry:\n r=urllib.request.urlopen(urllib.request.Request('http://10.5.0.2:1234/api/v1/models',headers={'Authorization':'Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'}),timeout=5)\n d=json.loads(r.read());loaded=[m.get('key','?') for m in d.get('models',[]) if m.get('loaded_instances')]\n has_8b=any('qwen3-8b' in m for m in loaded)\n if not has_8b: print('WARNING: M1 qwen3-8b NOT loaded! Loaded:',','.join(loaded))\nexcept Exception as e: print('M1 check failed:',e)\" 2>/dev/null || true",
  "timeout": 8000
}
```

**Step 2: Ajouter hook PreToolUse routing-logger**

Ajouter une nouvelle section `PreToolUse` dans hooks.json :

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "python3 -c \"import json,datetime,sqlite3,sys\ntry:\n db=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db')\n db.execute('CREATE TABLE IF NOT EXISTS routing_log(id INTEGER PRIMARY KEY,ts TEXT,category TEXT,node TEXT,latency_ms REAL,success INTEGER)')\n db.commit();db.close()\nexcept: pass\" 2>/dev/null || true",
        "timeout": 3000
      }
    ]
  }
],
```

**Step 3: Ajouter hook Stop metrics-saver**

Ajouter une nouvelle section `Stop` dans hooks.json :

```json
"Stop": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "python3 -c \"import json,datetime,sqlite3\ntry:\n db=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db')\n db.execute('INSERT INTO sessions(ts,event,data) VALUES(?,?,?)',(datetime.datetime.now().isoformat(),'session_end',json.dumps({'source':'hook'})))\n db.commit();db.close()\nexcept: pass\" 2>/dev/null || true",
        "timeout": 5000
      }
    ]
  }
]
```

**Step 4: Vérifier JSON valide**

```bash
python3 -c "import json; json.load(open('C:/Users/franc/.claude/plugins/local/jarvis-turbo/hooks/hooks.json')); print('JSON OK')"
```
Expected: `JSON OK`

**Step 5: Commit**

```bash
git -C C:/Users/franc/.claude/plugins/local/jarvis-turbo add hooks/hooks.json
git -C C:/Users/franc/.claude/plugins/local/jarvis-turbo commit -m "feat(hooks): VRAM check + routing logger + metrics saver"
```

---

### Task 5: Mettre à jour le README avec les 7 schémas

**Files:**
- Modify: `README.md` (sections ciblées)

**Step 1: Mettre à jour la section M1 config**

Chercher les références à `qwen3-30b` et remplacer par la nouvelle config :
- Model: `qwen/qwen3-8b` (dual-instance)
- VRAM: 4.7 GB × 2 = ~10 GB (sur 46 GB)
- Latence: 0.6-2.5s
- Débit: 65 tok/s

**Step 2: Remplacer la matrice de routage**

Remplacer par la nouvelle matrice avec M1 prioritaire et les nouvelles catégories math/raison.

**Step 3: Insérer les 7 schémas workflow**

Insérer les schémas du design approuvé :
1. Architecture globale (6 noeuds, VRAM, latences)
2. Routing dynamique (autolearn + fallback)
3. Consensus vote pondéré
4. Autolearn Engine (3 piliers)
5. Pipeline Hook (4 hooks)
6. Agents plugin (7 existants + 3 nouveaux)
7. Workflow complet requête-à-réponse

**Step 4: Mettre à jour les poids consensus**

M1: 1.6, M2: 1.4, OL1: 1.3, GEMINI: 1.2, CLAUDE: 1.2, M3: 0.8

**Step 5: Mettre à jour le compteur slash commands**

17 → 27 commandes

**Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): 7 schemas workflow + M1 qwen3-8b + routing M1 prio"
```

---

### Task 6: Lancer le benchmark et alimenter autolearn

**Step 1: Health check cluster**

```bash
curl -s --max-time 3 http://10.5.0.2:1234/api/v1/models -H "Authorization: Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" | python3 -c "import sys,json;d=json.load(sys.stdin);loaded=[m for m in d.get('models',[]) if m.get('loaded_instances')];print('M1 OK:',len(loaded),'modeles')"
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" | python3 -c "import sys,json;d=json.load(sys.stdin);loaded=[m for m in d.get('models',[]) if m.get('loaded_instances')];print('M2 OK:',len(loaded),'modeles')"
curl -s --max-time 3 http://127.0.0.1:11434/api/tags | python3 -c "import sys,json;print('OL1 OK:',len(json.load(sys.stdin).get('models',[])),'modeles')"
```
Expected: M1 OK, M2 OK, OL1 OK

**Step 2: Lancer benchmark cluster**

```bash
cd F:/BUREAU/turbo && python3 benchmark_cluster.py
```
Expected: 7 phases passent, rapport généré dans `data/benchmark_report.json`

**Step 3: Lancer benchmark réel 10 niveaux**

```bash
cd F:/BUREAU/turbo && python3 benchmark_real_test.py
```
Expected: 10 niveaux testés, rapport dans `data/benchmark_real_report.json`

**Step 4: Envoyer 5 requêtes test au proxy pour alimenter autolearn**

```bash
for q in "ecris un quicksort en python" "calcule 17*23+45" "explique la recursivite" "quelle heure est-il" "compare M1 et M2"; do
  curl -s --max-time 30 http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"main\",\"text\":\"$q\"}" > /dev/null
  echo "Sent: $q"
done
```

**Step 5: Vérifier que autolearn enregistre**

```bash
curl -s http://127.0.0.1:18800/autolearn/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('Conversations:',d.get('stats',{}).get('totalConversations',0))"
```
Expected: `Conversations: 5` (ou plus)

**Step 6: Commit les rapports**

```bash
git add data/benchmark_report.json data/benchmark_real_report.json
git commit -m "bench: fresh benchmark Feb-26 with M1/qwen3-8b"
```

---

### Task 7: Mettre à jour CLAUDE.md avec les nouveaux poids

**Files:**
- Modify: `C:/Users/franc/.claude/CLAUDE.md` (poids consensus + matrice routage)

**Step 1: Mettre à jour les poids**

Remplacer le tableau des poids :

```
| Agent | Poids | Specialite |
|-------|-------|------------|
| **M1** | **1.6** | **RAPIDE — code, math, raisonnement (100% benchmark, 0.6-2.5s)** |
| M2 | 1.4 | Code review, debug |
| OL1 | 1.3 | Vitesse, questions simples |
| GEMINI | 1.2 | Architecture, vision |
| CLAUDE | 1.2 | Raisonnement profond cloud |
| M3 | 0.8 | General, validation (PAS raisonnement) |
```

**Step 2: Mettre à jour la matrice de routage**

Remplacer `Code nouveau | **M1** (100%, 30B)` par `Code nouveau | **M1** (100%, 8B, 0.6-2.5s)`

**Step 3: Mettre à jour la section M1**

Remplacer la description M1 pour refléter qwen3-8b dual-instance.

**Step 4: Commit**

```bash
git add C:/Users/franc/.claude/CLAUDE.md
git commit -m "docs(claude.md): poids M1 1.6, M3 0.8 + qwen3-8b config"
```
