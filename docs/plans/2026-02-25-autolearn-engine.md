# JARVIS Autolearn Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un moteur d'apprentissage autonome à JARVIS Canvas — mémoire conversationnelle, auto-tuning routage, auto-review prompts — distribué sur M1/M2/M3/OL1.

**Architecture:** Un module `autolearn.js` exporté vers `direct-proxy.js`. Trois boucles parallèles (memory/tuning/review) utilisent `callNode()` existant pour dispatcher les tâches sur le cluster. Données persistées en JSON dans `canvas/data/`.

**Tech Stack:** Node.js (stdlib), JSON persistence, HTTP cluster calls via callNode()

---

### Task 1: Créer le répertoire data et les fichiers JSON initiaux

**Files:**
- Create: `canvas/data/memory.json`
- Create: `canvas/data/routing_scores.json`
- Create: `canvas/data/autolearn_history.json`

**Step 1: Créer le répertoire et les fichiers vides**

```bash
mkdir -p F:/BUREAU/turbo/canvas/data
```

`canvas/data/memory.json`:
```json
{
  "conversations": [],
  "profile": {
    "top_categories": {},
    "preferred_nodes": {},
    "expertise_level": "unknown",
    "total_messages": 0,
    "summary": ""
  }
}
```

`canvas/data/routing_scores.json`:
```json
{
  "scores": {},
  "history": [],
  "active_routing": null,
  "last_tuning": null
}
```

`canvas/data/autolearn_history.json`:
```json
{
  "cycles": [],
  "active_prompts": {},
  "rollback_stack": []
}
```

**Step 2: Commit**

```bash
git add canvas/data/
git commit -m "feat(autolearn): init data directory with JSON schemas"
```

---

### Task 2: Créer autolearn.js — Module principal avec Memory Engine (Pilier 1)

**Files:**
- Create: `canvas/autolearn.js`

**Step 1: Écrire le module autolearn.js avec le Memory Engine**

Le fichier exporte une classe `AutolearnEngine` qui reçoit la fonction `callNode` en injection de dépendance.

```javascript
// JARVIS Autolearn Engine — Autonomous self-improvement
// 3 Pillars: Memory, Auto-Tuning, Auto-Review
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');
const MEMORY_FILE = path.join(DATA_DIR, 'memory.json');
const SCORES_FILE = path.join(DATA_DIR, 'routing_scores.json');
const HISTORY_FILE = path.join(DATA_DIR, 'autolearn_history.json');

const MAX_CONVERSATIONS = 50;
const MAX_HISTORY = 200;
const TUNING_INTERVAL = 5 * 60 * 1000;   // 5 min
const REVIEW_INTERVAL = 30 * 60 * 1000;  // 30 min
const PROFILE_EVERY_N = 10;              // résumé M1 toutes les 10 conversations

class AutolearnEngine {
  constructor(callNodeFn, routingRef, sysPromptsRef) {
    this.callNode = callNodeFn;
    this.routing = routingRef;          // mutable reference to ROUTING
    this.sysPrompts = sysPromptsRef;    // mutable reference to SYS_PROMPTS
    this.memory = this._load(MEMORY_FILE, { conversations: [], profile: { top_categories: {}, preferred_nodes: {}, expertise_level: 'unknown', total_messages: 0, summary: '' } });
    this.scores = this._load(SCORES_FILE, { scores: {}, history: [], active_routing: null, last_tuning: null });
    this.history = this._load(HISTORY_FILE, { cycles: [], active_prompts: {}, rollback_stack: [] });
    this.responseLog = [];  // in-memory buffer for tuning
    this.tuningTimer = null;
    this.reviewTimer = null;
    this.running = false;
  }

  // ── Persistence ──────────────────────────────────────────────
  _load(file, fallback) {
    try {
      if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (e) { console.error(`[autolearn] load error ${file}:`, e.message); }
    return fallback;
  }

  _save(file, data) {
    try {
      fs.mkdirSync(DATA_DIR, { recursive: true });
      fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf8');
    } catch (e) { console.error(`[autolearn] save error ${file}:`, e.message); }
  }

  // ── Start/Stop ───────────────────────────────────────────────
  start() {
    if (this.running) return;
    this.running = true;
    console.log('[autolearn] Engine started — Memory + Tuning(5min) + Review(30min)');
    this.tuningTimer = setInterval(() => this.runTuningCycle(), TUNING_INTERVAL);
    this.reviewTimer = setInterval(() => this.runReviewCycle(), REVIEW_INTERVAL);
  }

  stop() {
    this.running = false;
    if (this.tuningTimer) clearInterval(this.tuningTimer);
    if (this.reviewTimer) clearInterval(this.reviewTimer);
    console.log('[autolearn] Engine stopped');
  }

  // ══════════════════════════════════════════════════════════════
  // PILIER 1 — MEMORY ENGINE
  // ══════════════════════════════════════════════════════════════

  // Called after every /chat response
  async recordConversation(userMsg, agentId, category, nodeUsed, response, latencyMs) {
    const entry = {
      ts: Date.now(),
      user: userMsg.slice(0, 500),
      agent: agentId,
      cat: category,
      node: nodeUsed,
      response: response.slice(0, 500),
      latency: latencyMs
    };

    this.memory.conversations.push(entry);
    if (this.memory.conversations.length > MAX_CONVERSATIONS) {
      this.memory.conversations = this.memory.conversations.slice(-MAX_CONVERSATIONS);
    }

    // Update profile stats
    this.memory.profile.total_messages++;
    this.memory.profile.top_categories[category] = (this.memory.profile.top_categories[category] || 0) + 1;
    this.memory.profile.preferred_nodes[nodeUsed] = (this.memory.profile.preferred_nodes[nodeUsed] || 0) + 1;

    // Also log for tuning
    this.responseLog.push({ ...entry, score: null });

    this._save(MEMORY_FILE, this.memory);

    // Every N messages, ask M1 for deep profile summary
    if (this.memory.profile.total_messages % PROFILE_EVERY_N === 0) {
      this._updateProfileSummary();
    }
  }

  async _updateProfileSummary() {
    const last10 = this.memory.conversations.slice(-10);
    const topCats = Object.entries(this.memory.profile.top_categories)
      .sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([k, v]) => `${k}(${v})`).join(', ');

    const prompt = `Analyse ces 10 derniers échanges d'un utilisateur avec JARVIS et génère un profil concis (3-4 phrases max):
- Catégories fréquentes: ${topCats}
- Total messages: ${this.memory.profile.total_messages}
- Derniers sujets: ${last10.map(c => c.user.slice(0, 80)).join(' | ')}

Réponds UNIQUEMENT avec le profil, rien d'autre.`;

    try {
      console.log('[autolearn] Pilier 1: Profil update via M1...');
      const result = await Promise.race([
        this.callNode('M1', [{ role: 'system', content: 'Tu es un analyste comportemental IA. Sois concis.' }, { role: 'user', content: prompt }]),
        new Promise((_, rej) => setTimeout(() => rej(new Error('M1 timeout')), 120000))
      ]);
      this.memory.profile.summary = result.text.slice(0, 500);
      this.memory.profile.last_profile_update = Date.now();
      this._save(MEMORY_FILE, this.memory);
      console.log('[autolearn] Pilier 1: Profil mis à jour via M1');
    } catch (e) {
      console.log('[autolearn] Pilier 1: M1 timeout, fallback OL1...');
      try {
        const result = await this.callNode('OL1', [{ role: 'system', content: 'Tu es un analyste comportemental IA. Sois concis.' }, { role: 'user', content: prompt }]);
        this.memory.profile.summary = result.text.slice(0, 500);
        this.memory.profile.last_profile_update = Date.now();
        this._save(MEMORY_FILE, this.memory);
        console.log('[autolearn] Pilier 1: Profil mis à jour via OL1 (fallback)');
      } catch (e2) {
        console.error('[autolearn] Pilier 1: Profile update failed:', e2.message);
      }
    }
  }

  // Get context injection for system prompts
  getContextInjection(category) {
    const profile = this.memory.profile;
    if (!profile.summary && profile.total_messages < 3) return '';

    const lastConvs = this.memory.conversations.slice(-3);
    const recentContext = lastConvs.length > 0
      ? `Derniers sujets: ${lastConvs.map(c => c.user.slice(0, 60)).join('; ')}`
      : '';

    return `\n[Contexte utilisateur: ${profile.summary || 'profil en construction'} | Messages: ${profile.total_messages} | ${recentContext}]`;
  }

  // ... Piliers 2 et 3 dans les tasks suivantes
}

module.exports = AutolearnEngine;
```

**Step 2: Commit**

```bash
git add canvas/autolearn.js
git commit -m "feat(autolearn): memory engine (pilier 1) — conversations + profil M1"
```

---

### Task 3: Ajouter le Pilier 2 — Auto-Tuning Loop dans autolearn.js

**Files:**
- Modify: `canvas/autolearn.js` (ajouter après getContextInjection)

**Step 1: Ajouter les méthodes de scoring et tuning**

Ajouter dans la classe `AutolearnEngine`, après `getContextInjection()`:

```javascript
  // ══════════════════════════════════════════════════════════════
  // PILIER 2 — AUTO-TUNING LOOP
  // ══════════════════════════════════════════════════════════════

  _speedScore(latencyMs) {
    if (latencyMs < 2000) return 10;
    if (latencyMs < 5000) return 7;
    if (latencyMs < 10000) return 4;
    return 2;
  }

  _reliabilityScore(nodeId, category) {
    const key = `${nodeId}:${category}`;
    const recent = this.responseLog.filter(r => `${r.node}:${r.cat}` === key).slice(-20);
    if (recent.length === 0) return 5; // neutral
    const successes = recent.filter(r => r.score === null || r.score >= 5).length;
    return Math.round((successes / recent.length) * 10);
  }

  async scoreResponse(entry) {
    // Ask OL1 to rate the response quality (1-10)
    const prompt = `Note cette réponse IA de 1 à 10 (1=mauvais, 10=excellent).
Catégorie: ${entry.cat}
Question: ${entry.user.slice(0, 200)}
Réponse: ${entry.response.slice(0, 300)}

Réponds UNIQUEMENT avec un chiffre de 1 à 10.`;

    try {
      const result = await Promise.race([
        this.callNode('OL1', [{ role: 'user', content: prompt }]),
        new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 10000))
      ]);
      const num = parseInt(result.text.replace(/[^0-9]/g, ''));
      return (num >= 1 && num <= 10) ? num : 5;
    } catch (e) {
      return 5; // neutral on failure
    }
  }

  async runTuningCycle() {
    if (!this.running) return;
    const unscored = this.responseLog.filter(r => r.score === null).slice(0, 5);
    if (unscored.length === 0) return;

    console.log(`[autolearn] Pilier 2: Tuning cycle — ${unscored.length} réponses à scorer`);

    // Score unscored responses via OL1
    for (const entry of unscored) {
      entry.score = await this.scoreResponse(entry);
    }

    // Aggregate scores by node×category
    const agg = {};
    for (const r of this.responseLog.filter(r => r.score !== null)) {
      const key = `${r.node}:${r.cat}`;
      if (!agg[key]) agg[key] = { speeds: [], qualities: [], node: r.node, cat: r.cat };
      agg[key].speeds.push(this._speedScore(r.latency));
      agg[key].qualities.push(r.score);
    }

    // Calculate composite scores
    const newScores = {};
    for (const [key, data] of Object.entries(agg)) {
      const avgSpeed = data.speeds.reduce((a, b) => a + b, 0) / data.speeds.length;
      const avgQuality = data.qualities.reduce((a, b) => a + b, 0) / data.qualities.length;
      const reliability = this._reliabilityScore(data.node, data.cat);
      newScores[key] = {
        speed: +avgSpeed.toFixed(1),
        quality: +avgQuality.toFixed(1),
        reliability,
        final: +(avgSpeed * 0.3 + avgQuality * 0.5 + reliability * 0.2).toFixed(2),
        samples: data.speeds.length
      };
    }

    this.scores.scores = newScores;
    this.scores.last_tuning = Date.now();

    // Reorder ROUTING based on scores
    let changes = 0;
    for (const cat of Object.keys(this.routing)) {
      const nodeScores = this.routing[cat]
        .map(nodeId => ({ nodeId, score: newScores[`${nodeId}:${cat}`]?.final || 5 }))
        .sort((a, b) => b.score - a.score);

      const newOrder = nodeScores.map(n => n.nodeId);
      const oldOrder = this.routing[cat];
      if (JSON.stringify(newOrder) !== JSON.stringify(oldOrder)) {
        console.log(`[autolearn] Pilier 2: ${cat}: ${oldOrder.join('→')}  =>  ${newOrder.join('→')}`);
        this.routing[cat] = newOrder;
        changes++;
      }
    }

    // Ask M1 for trend analysis (background, non-blocking)
    this._m1TrendAnalysis(newScores).catch(() => {});

    this.scores.history.push({ ts: Date.now(), changes, scores_snapshot: Object.keys(newScores).length });
    if (this.scores.history.length > 100) this.scores.history = this.scores.history.slice(-100);
    this._save(SCORES_FILE, this.scores);

    console.log(`[autolearn] Pilier 2: Tuning terminé — ${changes} catégories réordonnées`);
  }

  async _m1TrendAnalysis(scores) {
    const summary = Object.entries(scores)
      .map(([k, v]) => `${k}: speed=${v.speed} quality=${v.quality} final=${v.final}`)
      .join('\n');

    const prompt = `Analyse ces scores de performance d'un cluster IA et identifie les tendances:
${summary}

Donne 2-3 recommandations courtes pour optimiser le routage.`;

    try {
      const result = await Promise.race([
        this.callNode('M1', [{ role: 'system', content: 'Tu es un analyste performance IA. Sois concis.' }, { role: 'user', content: prompt }]),
        new Promise((_, rej) => setTimeout(() => rej(new Error('M1 timeout')), 120000))
      ]);
      console.log(`[autolearn] Pilier 2: M1 trend analysis: ${result.text.slice(0, 200)}`);
    } catch (e) {
      console.log('[autolearn] Pilier 2: M1 trend analysis skipped (timeout)');
    }
  }
```

**Step 2: Commit**

```bash
git add canvas/autolearn.js
git commit -m "feat(autolearn): auto-tuning loop (pilier 2) — scoring OL1 + reorder routing + M1 trends"
```

---

### Task 4: Ajouter le Pilier 3 — Auto-Review Cycle dans autolearn.js

**Files:**
- Modify: `canvas/autolearn.js` (ajouter après _m1TrendAnalysis)

**Step 1: Ajouter les méthodes auto-review**

```javascript
  // ══════════════════════════════════════════════════════════════
  // PILIER 3 — AUTO-REVIEW CYCLE
  // ══════════════════════════════════════════════════════════════

  async runReviewCycle() {
    if (!this.running) return;
    const weakResponses = this.responseLog
      .filter(r => r.score !== null && r.score < 5)
      .slice(-10);

    if (weakResponses.length < 2) {
      console.log('[autolearn] Pilier 3: Pas assez de réponses faibles, skip');
      return;
    }

    console.log(`[autolearn] Pilier 3: Review cycle — ${weakResponses.length} réponses faibles`);

    const cycle = { ts: Date.now(), weak_count: weakResponses.length, proposals: [], applied: [] };

    // Step 1: M2 analyse les faiblesses et propose des améliorations
    const weakSummary = weakResponses.map(r =>
      `[${r.cat}] Q: "${r.user.slice(0, 100)}" → Score: ${r.score}/10 (node: ${r.node})`
    ).join('\n');

    const currentPrompts = Object.entries(this.sysPrompts)
      .map(([k, v]) => `${k}: "${v}"`)
      .join('\n');

    let m2Proposals = [];
    try {
      console.log('[autolearn] Pilier 3: M2 analyse faiblesses...');
      const m2Result = await this.callNode('M2', [{
        role: 'system',
        content: 'Tu es un expert en prompt engineering. Analyse les faiblesses et propose des améliorations.'
      }, {
        role: 'user',
        content: `Voici des réponses IA mal notées:\n${weakSummary}\n\nPrompts système actuels:\n${currentPrompts}\n\nPour chaque catégorie affectée, propose un nouveau prompt système amélioré. Format JSON:\n[{"category":"xxx","new_prompt":"xxx","reason":"xxx"}]`
      }]);

      try {
        const jsonMatch = m2Result.text.match(/\[[\s\S]*\]/);
        if (jsonMatch) m2Proposals = JSON.parse(jsonMatch[0]);
      } catch (e) {
        console.log('[autolearn] Pilier 3: M2 JSON parse failed, skip');
        return;
      }
    } catch (e) {
      console.error('[autolearn] Pilier 3: M2 failed:', e.message);
      return;
    }

    if (m2Proposals.length === 0) {
      console.log('[autolearn] Pilier 3: Aucune proposition M2');
      return;
    }

    // Step 2: M3 valide chaque proposition
    console.log(`[autolearn] Pilier 3: M3 valide ${m2Proposals.length} propositions...`);
    const validatedProposals = [];

    for (const prop of m2Proposals.slice(0, 3)) {
      try {
        const m3Result = await this.callNode('M3', [{
          role: 'system',
          content: 'Tu es un validateur de prompts IA. Évalue la qualité de cette proposition.'
        }, {
          role: 'user',
          content: `Prompt actuel (${prop.category}): "${this.sysPrompts[prop.category] || 'aucun'}"\nProposition: "${prop.new_prompt}"\nRaison: ${prop.reason}\n\nNote cette proposition de 0.0 à 1.0. Réponds UNIQUEMENT avec un nombre.`
        }]);

        const score = parseFloat(m3Result.text.replace(/[^0-9.]/g, ''));
        prop.m3_score = (score >= 0 && score <= 1) ? score : 0.5;
        if (prop.m3_score > 0.7) validatedProposals.push(prop);

        console.log(`[autolearn] Pilier 3: M3 ${prop.category} → ${prop.m3_score}`);
      } catch (e) {
        console.log(`[autolearn] Pilier 3: M3 validation failed for ${prop.category}`);
      }
    }

    // Step 3: M1 méta-review (optional, background)
    for (const prop of validatedProposals) {
      try {
        const m1Result = await Promise.race([
          this.callNode('M1', [{
            role: 'system', content: 'Tu es un architecte IA senior. Valide ou rejette cette modification.'
          }, {
            role: 'user',
            content: `Changement de prompt pour "${prop.category}":\nAvant: "${this.sysPrompts[prop.category]}"\nAprès: "${prop.new_prompt}"\nScore M3: ${prop.m3_score}\n\nApprouves-tu? Réponds OUI ou NON + raison courte.`
          }]),
          new Promise((_, rej) => setTimeout(() => rej(new Error('M1 timeout')), 120000))
        ]);
        prop.m1_approved = m1Result.text.toLowerCase().includes('oui');
        console.log(`[autolearn] Pilier 3: M1 ${prop.category} → ${prop.m1_approved ? 'APPROUVÉ' : 'REJETÉ'}`);
      } catch (e) {
        prop.m1_approved = true; // M1 timeout = default approve
        console.log(`[autolearn] Pilier 3: M1 timeout → approuvé par défaut`);
      }
    }

    // Step 4: Apply validated & approved changes
    for (const prop of validatedProposals) {
      if (prop.m1_approved && prop.category && this.sysPrompts[prop.category]) {
        // Save rollback
        this.history.rollback_stack.push({
          ts: Date.now(),
          category: prop.category,
          old_prompt: this.sysPrompts[prop.category],
          trigger: 'auto-review'
        });

        // Hot-swap
        const oldPrompt = this.sysPrompts[prop.category];
        this.sysPrompts[prop.category] = prop.new_prompt;
        this.history.active_prompts[prop.category] = { prompt: prop.new_prompt, applied_at: Date.now(), m3_score: prop.m3_score };

        cycle.applied.push({ category: prop.category, old: oldPrompt.slice(0, 100), new: prop.new_prompt.slice(0, 100) });
        console.log(`[autolearn] Pilier 3: ★ PROMPT MIS À JOUR: ${prop.category}`);
      }
    }

    cycle.proposals = m2Proposals.map(p => ({ cat: p.category, score: p.m3_score, approved: p.m1_approved }));
    this.history.cycles.push(cycle);
    if (this.history.cycles.length > MAX_HISTORY) this.history.cycles = this.history.cycles.slice(-MAX_HISTORY);

    // Rollback check: if last 3 cycles degraded average scores
    this._checkRollback();

    this._save(HISTORY_FILE, this.history);
    console.log(`[autolearn] Pilier 3: Review terminé — ${cycle.applied.length} prompts mis à jour`);
  }

  _checkRollback() {
    const recentCycles = this.history.cycles.slice(-3);
    if (recentCycles.length < 3) return;

    for (const [cat, data] of Object.entries(this.history.active_prompts)) {
      const recentScores = this.responseLog
        .filter(r => r.cat === cat && r.score !== null && r.ts > data.applied_at)
        .map(r => r.score);

      const beforeScores = this.responseLog
        .filter(r => r.cat === cat && r.score !== null && r.ts <= data.applied_at)
        .slice(-20)
        .map(r => r.score);

      if (recentScores.length >= 5 && beforeScores.length >= 5) {
        const avgAfter = recentScores.reduce((a, b) => a + b, 0) / recentScores.length;
        const avgBefore = beforeScores.reduce((a, b) => a + b, 0) / beforeScores.length;

        if (avgAfter < avgBefore * 0.85) {  // >15% degradation
          const rollback = this.history.rollback_stack.filter(r => r.category === cat).pop();
          if (rollback) {
            console.log(`[autolearn] ROLLBACK: ${cat} — score dégradé ${avgBefore.toFixed(1)} → ${avgAfter.toFixed(1)}`);
            this.sysPrompts[cat] = rollback.old_prompt;
            delete this.history.active_prompts[cat];
          }
        }
      }
    }
  }
```

**Step 2: Commit**

```bash
git add canvas/autolearn.js
git commit -m "feat(autolearn): auto-review cycle (pilier 3) — M2 propose + M3 valide + M1 meta + rollback"
```

---

### Task 5: Ajouter les méthodes status/API dans autolearn.js

**Files:**
- Modify: `canvas/autolearn.js` (ajouter avant `module.exports`)

**Step 1: Méthodes status**

```javascript
  // ══════════════════════════════════════════════════════════════
  // API METHODS
  // ══════════════════════════════════════════════════════════════

  getStatus() {
    return {
      running: this.running,
      memory: {
        total_messages: this.memory.profile.total_messages,
        conversations_stored: this.memory.conversations.length,
        profile_summary: this.memory.profile.summary || 'building...',
        last_profile_update: this.memory.profile.last_profile_update || null
      },
      tuning: {
        last_cycle: this.scores.last_tuning,
        categories_tracked: Object.keys(this.scores.scores).length,
        total_cycles: this.scores.history.length,
        interval_min: TUNING_INTERVAL / 60000
      },
      review: {
        total_cycles: this.history.cycles.length,
        active_prompt_overrides: Object.keys(this.history.active_prompts).length,
        rollback_stack_size: this.history.rollback_stack.length,
        interval_min: REVIEW_INTERVAL / 60000
      }
    };
  }

  getMemory() {
    return {
      profile: this.memory.profile,
      recent_conversations: this.memory.conversations.slice(-10).map(c => ({
        ts: c.ts,
        user: c.user.slice(0, 100),
        cat: c.cat,
        node: c.node,
        latency: c.latency
      }))
    };
  }

  getScores() {
    return {
      scores: this.scores.scores,
      current_routing: { ...this.routing },
      last_tuning: this.scores.last_tuning,
      history: this.scores.history.slice(-10)
    };
  }

  getHistory() {
    return {
      cycles: this.history.cycles.slice(-20),
      active_prompts: this.history.active_prompts,
      rollback_count: this.history.rollback_stack.length
    };
  }

  async triggerReview() {
    console.log('[autolearn] Manual review trigger');
    await this.runReviewCycle();
    return { ok: true, message: 'Review cycle completed' };
  }
```

**Step 2: Commit**

```bash
git add canvas/autolearn.js
git commit -m "feat(autolearn): API methods — status, memory, scores, history, trigger"
```

---

### Task 6: Intégrer autolearn.js dans direct-proxy.js

**Files:**
- Modify: `canvas/direct-proxy.js:1-270`

**Step 1: Ajouter l'import et l'initialisation après les constantes existantes**

Après la ligne `const CANVAS_HTML = ...` (ligne 9), ajouter:

```javascript
const AutolearnEngine = require('./autolearn');
```

Après la déclaration de `SYS_PROMPTS` (après ligne 88), ajouter:

```javascript
// ── Autolearn Engine ─────────────────────────────────────────────────────────
const autolearn = new AutolearnEngine(callNode, ROUTING, SYS_PROMPTS);
```

**Step 2: Modifier routeAndCall pour injecter le contexte mémoire et mesurer la latence**

Remplacer la fonction `routeAndCall` (lignes 156-179) par:

```javascript
async function routeAndCall(agentId, userText) {
  const cat = AGENT_CAT[agentId] || 'default';
  const chain = ROUTING[cat] || ROUTING.default;
  const baseSysPrompt = SYS_PROMPTS[cat] || SYS_PROMPTS.default;

  // Inject memory context
  const contextInjection = autolearn.getContextInjection(cat);
  const sysProm = baseSysPrompt + contextInjection;

  const messages = [
    { role: 'system', content: sysProm },
    { role: 'user', content: userText }
  ];

  const errors = [];
  for (const nodeId of chain) {
    try {
      console.log(`[chat] ${agentId} (${cat}) -> ${nodeId}/${NODES[nodeId].model}`);
      const start = Date.now();
      const result = await callNode(nodeId, messages);
      const latency = Date.now() - start;
      console.log(`[chat] OK from ${nodeId} (${result.text.length} chars, ${latency}ms)`);

      // Record for autolearn
      autolearn.recordConversation(userText, agentId, cat, nodeId, result.text, latency);

      return result;
    } catch (e) {
      console.log(`[chat] ${nodeId} FAILED: ${e.message}`);
      errors.push(`${nodeId}: ${e.message}`);
    }
  }
  throw new Error('All nodes failed: ' + errors.join(' | '));
}
```

**Step 3: Ajouter les endpoints autolearn dans le serveur HTTP**

Avant le `} else {` final (ligne 260, le 404), ajouter les routes autolearn:

```javascript
  } else if (req.method === 'GET' && req.url === '/autolearn/status') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getStatus()));
  } else if (req.method === 'GET' && req.url === '/autolearn/memory') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getMemory()));
  } else if (req.method === 'GET' && req.url === '/autolearn/scores') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getScores()));
  } else if (req.method === 'GET' && req.url === '/autolearn/history') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(autolearn.getHistory()));
  } else if (req.method === 'POST' && req.url === '/autolearn/trigger') {
    autolearn.triggerReview().then(r => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(r));
    }).catch(e => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    });
  } else {
```

**Step 4: Démarrer l'engine au lancement du serveur**

Modifier le `server.listen` callback (ligne 266-269) pour ajouter `autolearn.start()`:

```javascript
server.listen(PORT, '127.0.0.1', () => {
  console.log(`JARVIS Direct Proxy on http://127.0.0.1:${PORT}`);
  console.log('Nodes: M1(qwen3-30b), M2(deepseek), M3(mistral), OL1(qwen3)');
  console.log('Zero OpenClaw dependency');
  autolearn.start();
});
```

**Step 5: Commit**

```bash
git add canvas/direct-proxy.js
git commit -m "feat(autolearn): integrate engine into proxy — memory injection + tuning + review + 5 API endpoints"
```

---

### Task 7: Ajouter un panneau autolearn dans le canvas HTML

**Files:**
- Modify: `canvas/index.html`

**Step 1: Ajouter un indicateur autolearn dans la barre de statut du canvas**

Dans l'index.html, chercher la section des badges cluster (`.hbar` ou `.cluster-badges`) et ajouter un badge autolearn qui affiche le statut. Ajouter aussi un petit panneau déroulant avec les stats.

Le badge appelle `PROXY + '/autolearn/status'` toutes les 30 secondes et affiche:
- Vert si running + memory > 0
- Orange si running mais 0 messages
- Rouge si non running

Ajouter un `onclick` qui affiche un panneau avec: profil mémoire, scores par noeud, derniers cycles review.

**Step 2: Commit**

```bash
git add canvas/index.html
git commit -m "feat(autolearn): canvas UI — status badge + autolearn panel"
```

---

### Task 8: Test end-to-end et commit final

**Step 1: Restart proxy**

```bash
# Kill existing proxy
taskkill /F /IM node.exe /FI "WINDOWTITLE eq *18800*" 2>/dev/null
# Start fresh
cd F:/BUREAU/turbo/canvas && node direct-proxy.js &
```

**Step 2: Test health + autolearn status**

```bash
curl -s http://127.0.0.1:18800/health
curl -s http://127.0.0.1:18800/autolearn/status
```

Expected: `{"running":true, "memory":{...}, "tuning":{...}, "review":{...}}`

**Step 3: Test chat (triggers memory recording)**

```bash
curl -s -X POST http://127.0.0.1:18800/chat -H "Content-Type: application/json" -d '{"agent":"coding","text":"écris un hello world en python"}'
```

**Step 4: Verify memory was recorded**

```bash
curl -s http://127.0.0.1:18800/autolearn/memory
```

Expected: `total_messages: 1`, recent conversation visible

**Step 5: Test manual review trigger**

```bash
curl -s -X POST http://127.0.0.1:18800/autolearn/trigger
```

**Step 6: Final commit + push**

```bash
git add -A canvas/
git commit -m "feat(autolearn): JARVIS autonomous learning engine — memory + tuning + review"
git push
```
