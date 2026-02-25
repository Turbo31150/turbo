# Cockpit Autonome v2 — Ameliorations

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Corriger les problemes observes lors des tests du cockpit v1 (boucles infinies query_db, schemas manquants, pas de detection anti-loop)

**Architecture:** Injection des schemas etoile.db dans le prompt systeme, detection anti-loop cote serveur, meilleur feedback d'erreur, alerte visuelle frontend quand >5 tours

**Tech Stack:** Node.js (direct-proxy.js), HTML/CSS/JS (index.html), SQLite3

---

### Task 1: Injecter les schemas etoile.db dans le prompt systeme

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js` (section ETOILE_SUMMARY ~ligne 102-130)

**Step 1: Ajouter l'extraction des schemas au demarrage**

Dans direct-proxy.js, apres le bloc existant ETOILE_SUMMARY, ajouter l'extraction dynamique des schemas de toutes les tables etoile.db :

```javascript
// Apres le bloc ETOILE_SUMMARY existant, ajouter :
let ETOILE_SCHEMAS = '';
try {
  const tables = require('child_process')
    .execFileSync('sqlite3', [ETOILE_DB, '.tables'], { encoding: 'utf8', timeout: 3000 })
    .trim().split(/\s+/);
  for (const t of tables) {
    const schema = require('child_process')
      .execFileSync('sqlite3', [ETOILE_DB, `.schema ${t}`], { encoding: 'utf8', timeout: 3000 })
      .trim();
    if (schema) ETOILE_SCHEMAS += `\n-- Table: ${t}\n${schema}\n`;
  }
  console.log('[Cockpit] Schemas etoile.db charges:', tables.length, 'tables');
} catch (e) {
  console.warn('[Cockpit] Schema extraction failed:', e.message);
}
```

**Step 2: Injecter les schemas dans COCKPIT_TOOLS_PROMPT**

Dans la constante COCKPIT_TOOLS_PROMPT, ajouter une section DB SCHEMAS apres la section ETOILE_SUMMARY :

```
## DB SCHEMAS (etoile.db)
${ETOILE_SCHEMAS}
IMPORTANT: Utilise UNIQUEMENT les colonnes listees ci-dessus pour query_db. Ne devine JAMAIS les noms de colonnes.
```

**Step 3: Verifier le demarrage**

Run: `node F:/BUREAU/turbo/canvas/direct-proxy.js` (dans un terminal separe)
Expected: Log `[Cockpit] Schemas etoile.db charges: N tables`

**Step 4: Tester query_db avec les bons schemas**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"message\":\"combien de launchers dans etoile.db?\",\"agent\":\"OL1\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('Tours:',d.get('turns',0));print('Tools:',[(t['name'],t.get('result',{}).get('ok')) for t in d.get('tools_used',[])])"
```
Expected: 1-2 tours, query_db OK, pas de boucle

**Step 5: Commit**

```bash
git add canvas/direct-proxy.js
git commit -m "feat(cockpit): inject etoile.db schemas into system prompt"
```

---

### Task 2: Detection anti-loop (meme outil echoue 3x → stop)

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js` (fonction agenticChat ~ligne 440)

**Step 1: Ajouter le compteur d'echecs par outil**

Dans la fonction `agenticChat()`, avant la boucle while, ajouter :

```javascript
const toolFailCount = {};  // { "tool_name": count }
const MAX_SAME_FAIL = 3;
```

**Step 2: Incrementer le compteur apres chaque echec**

Dans la boucle, apres l'appel de l'outil, si `result.ok === false` :

```javascript
if (!result.ok) {
  const key = toolName;
  toolFailCount[key] = (toolFailCount[key] || 0) + 1;
  if (toolFailCount[key] >= MAX_SAME_FAIL) {
    toolsUsed.push({ name: toolName, args, result: { ok: false, error: `ANTI-LOOP: ${toolName} a echoue ${MAX_SAME_FAIL}x, arret.` } });
    feedback += `\n[SYSTEM] STOP: ${toolName} a echoue ${MAX_SAME_FAIL} fois. Ne retente PAS cet outil. Reponds avec ce que tu sais.\n`;
    break;  // Sort de la boucle de parsing des outils dans ce tour
  }
}
```

**Step 3: Ajouter un compteur de tours sans progres**

Apres la boucle des outils dans un tour, verifier si tous les outils ont echoue :

```javascript
const allFailed = turnTools.length > 0 && turnTools.every(t => !t.result?.ok);
if (allFailed) {
  noProgressCount = (noProgressCount || 0) + 1;
  if (noProgressCount >= 2) {
    // 2 tours consecutifs sans succes → forcer la sortie
    feedback += '\n[SYSTEM] 2 tours sans progres. Reponds maintenant avec ce que tu sais.\n';
    // Ne pas continuer la boucle agentic
    break;
  }
} else {
  noProgressCount = 0;
}
```

**Step 4: Tester l'anti-loop**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"message\":\"cherche dans la table inexistante_xyz\",\"agent\":\"OL1\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('Tours:',d.get('turns',0));[print(t['name'],t.get('result',{}).get('ok')) for t in d.get('tools_used',[])]"
```
Expected: Max 3-4 tours (pas 15), arret avec message ANTI-LOOP

**Step 5: Commit**

```bash
git add canvas/direct-proxy.js
git commit -m "feat(cockpit): anti-loop detection — stop after 3 same-tool failures"
```

---

### Task 3: Meilleur feedback d'erreur + HINT dans retour outil

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js` (outils query_db et pipeline)

**Step 1: Enrichir le retour d'erreur de query_db**

Dans l'outil `query_db`, quand la requete echoue, ajouter un HINT avec les tables disponibles :

```javascript
query_db(args) {
  try {
    // ... existing code ...
  } catch (e) {
    const tables = require('child_process')
      .execFileSync('sqlite3', [ETOILE_DB, '.tables'], { encoding: 'utf8', timeout: 2000 })
      .trim();
    return {
      ok: false,
      error: e.message,
      hint: `Tables disponibles: ${tables}. Verifie les noms de colonnes dans le schema injecte.`
    };
  }
}
```

**Step 2: Enrichir le retour d'erreur de pipeline**

Meme logique pour pipeline quand le nom n'est pas trouve — inclure les entites proches :

```javascript
// Deja fait en v1 (fuzzy match avec suggestions)
// Verifier que le hint inclut les suggestions
```

**Step 3: Ajouter le HINT dans le feedback agentic**

Dans agenticChat(), quand on construit le feedback pour l'IA, inclure le hint :

```javascript
if (result.hint) {
  feedback += `\nHINT: ${result.hint}\n`;
}
```

**Step 4: Tester**

```bash
curl -s -X POST http://127.0.0.1:18800/tool -H "Content-Type: application/json" -d "{\"tool\":\"query_db\",\"args\":{\"query\":\"SELECT * FROM fake_table\"}}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('OK:',d.get('ok'));print('Hint:',d.get('hint','none'))"
```
Expected: ok=false, hint contient les tables disponibles

**Step 5: Commit**

```bash
git add canvas/direct-proxy.js
git commit -m "feat(cockpit): enriched error hints for query_db and pipeline tools"
```

---

### Task 4: Badge orange frontend quand >5 tours

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/index.html` (fonction addCockpitMsg + CSS)

**Step 1: Ajouter le CSS pour le badge warning**

```css
.tour-warning {
  background: #f59e0b;
  color: #000;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 0.75rem;
  font-weight: 600;
  animation: pulse-warning 1.5s ease-in-out infinite;
}
@keyframes pulse-warning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
```

**Step 2: Modifier addCockpitMsg pour afficher le badge**

Dans la fonction `addCockpitMsg()`, apres la ligne qui affiche les tours :

```javascript
// Si turns > 5, ajouter un badge warning
if (data.turns && data.turns > 5) {
  const warn = document.createElement('span');
  warn.className = 'tour-warning';
  warn.textContent = '⚠ ' + data.turns + ' tours — possible boucle';
  metaDiv.appendChild(warn);
}
```

**Step 3: Tester visuellement**

Ouvrir http://127.0.0.1:18800/ et envoyer une requete qui prend plusieurs tours.
Expected: Si >5 tours, badge orange pulsant visible

**Step 4: Commit**

```bash
git add canvas/index.html
git commit -m "feat(cockpit): orange warning badge when >5 agentic turns"
```

---

### Task 5: Verification finale et commit global

**Step 1: Redemarrer le proxy**

```bash
# Kill ancien proxy
taskkill /F /IM node.exe /FI "WINDOWTITLE eq *direct-proxy*" 2>/dev/null
# Relancer
cd F:/BUREAU/turbo && node canvas/direct-proxy.js &
```

**Step 2: Test E2E — query_db avec schemas**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"message\":\"combien d'entrees par type dans etoile.db?\",\"agent\":\"OL1\"}"
```
Expected: 1-3 tours, query_db reussit, pas de boucle

**Step 3: Test E2E — anti-loop**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"message\":\"lis la table telegram_config dans etoile\",\"agent\":\"OL1\"}"
```
Expected: Si table inexistante, max 3-4 tours avec ANTI-LOOP, hint inclut tables disponibles

**Step 4: Verifier le badge orange**

Ouvrir http://127.0.0.1:18800/ et verifier visuellement

**Step 5: Commit final si pas deja fait**

```bash
git add canvas/direct-proxy.js canvas/index.html
git commit -m "feat(cockpit-v2): schema injection + anti-loop + error hints + tour warning"
```
