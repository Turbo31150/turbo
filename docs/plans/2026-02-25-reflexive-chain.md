# Reflexive Multi-IA Chain + Smart Anti-Loop — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remplacer la boucle agentique mono-noeud par une chaine reflexive OL1→M1→M2 avec detection anti-boucle par repetition et UI collapsible.

**Architecture:** Nouvelle fonction `reflexiveChat()` dans direct-proxy.js qui orchestre 3 noeuds sequentiellement, chacun avec son budget de tours et detection de repetitions par hash. Un classifieur `classifyComplexity()` decide automatiquement entre mode simple (1 noeud) et reflexif (3 noeuds). Le frontend affiche des badges de chaine collapsibles.

**Tech Stack:** Node.js (direct-proxy.js), HTML/CSS/JS (index.html), crypto (md5 pour hashes)

---

### Task 1: Anti-loop v2 — Detection par repetition dans agenticChat existant

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js:101` (MAX_TOOL_TURNS)
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js:468-571` (agenticChat)

**Step 1: Reduire MAX_TOOL_TURNS de 15 a 8**

A la ligne 101, changer :

```javascript
const MAX_TOOL_TURNS = 8;
```

**Step 2: Ajouter la detection par repetition (hash des appels)**

Dans `agenticChat()`, apres la ligne 484 (`const MAX_SAME_FAIL = 3;`), ajouter :

```javascript
const callHashes = new Set();  // anti-loop v2: detect repeated identical calls
```

Puis dans la boucle, apres `const toolCall = parseToolCall(aiResult.text);` (ligne 504), AVANT l'execution de l'outil (ligne 510), ajouter :

```javascript
// Anti-loop v2: detect repeated identical tool call (same name + same args)
const callHash = toolCall.name + ':' + JSON.stringify(toolCall.args);
if (callHashes.has(callHash)) {
  console.log('[cockpit] ANTI-LOOP-V2: repeated call ' + toolCall.name + ', stopping');
  const stopMsg = '[SYSTEM] STOP: Appel identique detecte (' + toolCall.name + '). Reponds avec les resultats que tu as deja.';
  messages.push({ role: 'assistant', content: aiResult.text });
  messages.push({ role: 'user', content: stopMsg });
  for (const nodeId of chain) {
    try {
      const final = await callNode(nodeId, messages);
      return { text: final.text, model: final.model, provider: final.provider, tools_used: toolHistory, turns: turn + 1, anti_loop: 'repeated_call' };
    } catch (_) {}
  }
  return { text: stopMsg, model: lastModel, provider: lastProvider, tools_used: toolHistory, turns: turn + 1, anti_loop: 'repeated_call' };
}
callHashes.add(callHash);
```

**Step 3: Tester l'anti-loop v2**

Run: `cd F:/BUREAU/turbo && node -e "const dp = require('./canvas/direct-proxy.js'); console.log('loaded OK');"` (ou verifier que le fichier parse sans erreur)

Puis redemarrer le proxy et tester :
```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"data-analyst\",\"text\":\"liste les fichiers du bureau\"}"
```
Expected: Max 2-3 tours au lieu de 15 (list_dir repete = stop immediat)

**Step 4: Commit**

```bash
cd F:/BUREAU/turbo && git add canvas/direct-proxy.js && git commit -m "feat(cockpit): anti-loop v2 — repetition detection + MAX_TOOL_TURNS 15→8"
```

---

### Task 2: Classifieur de complexite

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js` (nouvelle fonction avant agenticChat, ~ligne 466)

**Step 1: Creer la fonction classifyComplexity**

Inserer AVANT la ligne `// ── Agentic loop ──` (ligne 467) :

```javascript
// ── Complexity classifier — simple vs reflexive ──────────────────────────
function classifyComplexity(userText, agentCat) {
  // Force reflexive for certain categories
  const reflexiveCats = ['code', 'archi', 'ia', 'sec'];
  if (reflexiveCats.includes(agentCat)) return 'reflexive';

  // Force simple for lightweight categories
  const simpleCats = ['meta', 'media', 'default'];
  if (simpleCats.includes(agentCat)) return 'simple';

  // Keyword detection
  const complexKeywords = /\b(analyse|compare|cherche.*explique|détaillé|pourquoi|comment.*fonctionne|refactor|debug|optimise|audit|review|évalue|synthèse|résume.*tout|en détail)\b/i;
  if (complexKeywords.test(userText)) return 'reflexive';

  // Length heuristic: long messages are likely complex
  if (userText.length > 120) return 'reflexive';

  // Tool-implying keywords
  const toolKeywords = /\b(query_db|etoile|base de données|sql|fichier|dossier|pipeline|execute|lance|cherche dans)\b/i;
  if (toolKeywords.test(userText)) return 'reflexive';

  return 'simple';
}
```

**Step 2: Verifier le parse**

```bash
cd F:/BUREAU/turbo && node -e "require('./canvas/direct-proxy.js')" 2>&1 | head -5
```
Expected: Pas d'erreur de syntaxe

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo && git add canvas/direct-proxy.js && git commit -m "feat(cockpit): complexity classifier — simple vs reflexive routing"
```

---

### Task 3: reflexiveChat() — Chaine OL1→M1→M2

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js` (nouvelle fonction apres classifyComplexity)

**Step 1: Creer la fonction reflexiveChat**

Inserer apres `classifyComplexity()` et avant `async function agenticChat()`. Le code complet est fourni dans le design doc `2026-02-25-reflexive-chain-design.md`.

La fonction :
1. Itere sur REFLEXIVE_CHAIN (OL1, M1, M2)
2. Pour chaque etape, lance une boucle agentique locale avec budget (4/3/2 tours)
3. Detecte les repetitions par hash (callHashes Set)
4. Accumule le contexte d'une etape a la suivante
5. Retourne `{ text, mode:'reflexive', chain:[...], tools_used, turns }`

Voir le code complet dans le design doc section "reflexiveChat".

Important : la fonction doit gerer le Safety Gate (needs_confirm) et les fallbacks (si un noeud est offline, essayer les autres du ROUTING).

**Step 2: Verifier le parse**

```bash
cd F:/BUREAU/turbo && node -e "require('./canvas/direct-proxy.js')" 2>&1 | head -5
```

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo && git add canvas/direct-proxy.js && git commit -m "feat(cockpit): reflexiveChat — OL1→M1→M2 chain with per-step anti-loop"
```

---

### Task 4: Integrer le classifieur dans la route /chat

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/direct-proxy.js:727-751` (handler POST /chat)

**Step 1: Remplacer l'appel direct a agenticChat par le classifieur**

Dans le handler `POST /chat` (ligne 734), remplacer :

```javascript
const result = await agenticChat(agentId, text);
```

Par :

```javascript
const complexity = classifyComplexity(text, AGENT_CAT[agentId] || 'default');
console.log('[cockpit] complexity=' + complexity + ' agent=' + agentId);
const result = complexity === 'reflexive'
  ? await reflexiveChat(agentId, text)
  : await agenticChat(agentId, text);
```

**Step 2: Ajouter `mode: 'simple'` dans les retours de agenticChat**

Dans `agenticChat()`, a chaque `return`, ajouter `mode: 'simple'`. Les lignes concernees :
- Ligne 506 (reponse sans outil)
- Ligne 534 (anti-loop fail stop)
- Ligne 537 (anti-loop fail fallback)
- Ligne 556 (no progress stop)
- Ligne 559 (no progress fallback)
- Ligne 570 (limite de tours)

Ajouter aussi les retours anti-loop v2 (Task 1).

**Step 3: Tester les deux modes**

```bash
# Simple (question courte)
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"main\",\"text\":\"salut\"}" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('Mode:',d.get('mode'),'Tours:',d.get('turns'))"
```
Expected: `Mode: simple Tours: 1`

```bash
# Reflexive (question complexe avec outil)
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"data-analyst\",\"text\":\"analyse les entrees par type dans etoile.db et explique les tendances\"}" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('Mode:',d.get('mode'),'Tours:',d.get('turns'),'Chain:',len(d.get('chain',[])))"
```
Expected: `Mode: reflexive Tours: 3-6 Chain: 3`

**Step 4: Commit**

```bash
cd F:/BUREAU/turbo && git add canvas/direct-proxy.js && git commit -m "feat(cockpit): route /chat uses classifier — simple or reflexive chain"
```

---

### Task 5: UI — Badges de chaine collapsibles

**Files:**
- Modify: `F:/BUREAU/turbo/canvas/index.html` (CSS + addCockpitMsg)

**Step 1: Ajouter le CSS pour les badges de chaine**

Dans la section `<style>` de index.html, ajouter apres les styles `.tool-badge` existants :

```css
/* Chain badges */
.chain-row{display:flex;gap:4px;margin-bottom:6px;flex-wrap:wrap}
.chain-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:3px;font-size:10px;font-family:var(--font-mono);letter-spacing:.5px;text-transform:uppercase;cursor:pointer;transition:all .2s;border:1px solid var(--border)}
.chain-badge[data-role="recherche"]{border-color:#f9731644;color:#f97316;background:#f9731610}
.chain-badge[data-role="analyse"]{border-color:#c084fc44;color:#c084fc;background:#c084fc10}
.chain-badge[data-role="review"]{border-color:#10b98144;color:#10b981;background:#10b98110}
.chain-badge .chain-dur{opacity:.5;font-size:9px}
.chain-detail{display:none;margin:4px 0 8px 0;padding:6px 10px;background:var(--bg-input);border-radius:3px;border-left:2px solid var(--border);font-size:11px;font-family:var(--font-mono);color:var(--text-dim);line-height:1.5;max-height:200px;overflow-y:auto}
.chain-detail.open{display:block}
.chain-badge:hover{filter:brightness(1.3)}
.mode-badge{font-size:9px;padding:1px 6px;border-radius:2px;font-family:var(--font-mono);letter-spacing:.5px;text-transform:uppercase}
.mode-badge.reflexive{background:#c084fc20;color:#c084fc;border:1px solid #c084fc44}
.mode-badge.simple{background:#f9731610;color:var(--text-dim);border:1px solid var(--border)}
```

**Step 2: Modifier l'appel a addCockpitMsg**

Ligne 701, changer :

```javascript
addCockpitMsg(r,mi,agentId,data.tools_used||[],data.turns||1,data.mode||'simple',data.chain||[]);
```

**Step 3: Modifier la signature de addCockpitMsg**

Ligne 772, changer :

```javascript
function addCockpitMsg(text,modelInfo,agentUsed,toolsUsed,turns,mode,chain){
```

**Step 4: Ajouter le rendu des chain badges**

Apres le bloc tool badges (apres `d.appendChild(badges);` ~ligne 797), ajouter :

```javascript
  // Chain badges (reflexive mode)
  if(mode==='reflexive'&&chain&&chain.length>0){
    var chainRow=el('div','chain-row');
    var modeBadge=el('span','mode-badge reflexive');
    modeBadge.textContent='reflexive';
    chainRow.appendChild(modeBadge);
    chain.forEach(function(step,idx){
      var cb=el('span','chain-badge');
      cb.setAttribute('data-role',step.role);
      var dur=step.duration_ms<1000?step.duration_ms+'ms':(step.duration_ms/1000).toFixed(1)+'s';
      cb.textContent=step.node+' '+step.turns+'t '+dur;
      cb.title=step.role+' — '+step.model+' — '+step.turns+' tour(s)';
      var detail=el('div','chain-detail');
      var detailText=step.role.toUpperCase()+' ('+step.node+'/'+step.model+')\n';
      if(step.tools_used&&step.tools_used.length>0){
        detailText+='Outils: '+step.tools_used.map(function(t){return t.tool}).join(', ')+'\n';
      }
      if(step.summary)detailText+='\n'+step.summary;
      detail.textContent=detailText;
      cb.onclick=function(){detail.classList.toggle('open')};
      chainRow.appendChild(cb);
      chainRow.appendChild(detail);
    });
    d.appendChild(chainRow);
  }
```

**Step 5: Ajouter mode badge dans la section tool badges existante**

Apres le turnBadge (apres `badges.appendChild(turnBadge);` ~ligne 796) :

```javascript
    if(mode){var mb=el('span','mode-badge '+mode);mb.textContent=mode;badges.appendChild(mb)}
```

**Step 6: Tester visuellement**

Ouvrir http://127.0.0.1:18800/ et envoyer :
- "salut" → mode simple, pas de chain badges
- "analyse les donnees dans etoile.db en detail" → mode reflexive, 3 badges colores
- Cliquer sur un badge → detail se deplie

**Step 7: Commit**

```bash
cd F:/BUREAU/turbo && git add canvas/index.html && git commit -m "feat(cockpit): chain badges UI — collapsible reflexive chain display"
```

---

### Task 6: Copie portable + test E2E + push

**Step 1: Mettre a jour la copie portable**

```bash
cp F:/BUREAU/turbo/canvas/index.html "C:/Users/franc/Desktop/JARVIS_Cockpit_Portable.html"
```

**Step 2: Redemarrer le proxy**

```bash
taskkill //F //IM node.exe //FI "WINDOWTITLE eq *direct-proxy*" 2>/dev/null; cd F:/BUREAU/turbo && node canvas/direct-proxy.js &
```
Expected: Logs `[etoile] Schemas loaded: N tables`

**Step 3: Test E2E simple**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"main\",\"text\":\"bonjour\"}" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('Mode:',d.get('mode'),'OK')"
```
Expected: `Mode: simple OK`

**Step 4: Test E2E reflexive**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"data-analyst\",\"text\":\"combien d entrees par type dans etoile.db\"}" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('Mode:',d.get('mode'),'Tours:',d.get('turns'),'Chain:',len(d.get('chain',[])))"
```
Expected: `Mode: reflexive Tours: 3-6 Chain: 2-3`

**Step 5: Test anti-loop (appel repete)**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d "{\"agent\":\"data-analyst\",\"text\":\"liste les fichiers du bureau\"}" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('Tours:',d.get('turns'),'Anti-loop:',d.get('anti_loop','none'))"
```
Expected: Max 3-4 tours (list_dir repete 2x = stop)

**Step 6: Commit final + push**

```bash
cd F:/BUREAU/turbo && git add -A && git status
# Si des fichiers non commites restent :
git commit -m "feat(cockpit): reflexive chain v1 — complete implementation"
git push
```
