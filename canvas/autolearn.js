// JARVIS Autolearn Engine — Distributed learning on cluster (M1/M2/M3/OL1)
// 3 pillars: Memory Engine, Auto-Tuning, Auto-Review
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');
const MEMORY_FILE = path.join(DATA_DIR, 'memory.json');
const SCORES_FILE = path.join(DATA_DIR, 'routing_scores.json');
const HISTORY_FILE = path.join(DATA_DIR, 'autolearn_history.json');

const MAX_CONVERSATIONS = 200;
const MAX_HISTORY_CYCLES = 50;
const TUNING_INTERVAL = 5 * 60 * 1000;   // 5 min
const REVIEW_INTERVAL = 30 * 60 * 1000;  // 30 min
const PROFILE_INTERVAL = 15 * 60 * 1000; // 15 min
const RELIABILITY_WINDOW = 20;

class AutolearnEngine {
  constructor(callNodeFn, routingRef, sysPromptsRef) {
    this._callNode = callNodeFn;
    this._routing = routingRef;
    this._sysPrompts = sysPromptsRef;

    this._memory = null;
    this._scores = null;
    this._history = null;

    this._tuningTimer = null;
    this._reviewTimer = null;
    this._profileTimer = null;
    this._running = false;

    // Track per-node per-category call results for reliability
    this._callLog = {}; // nodeId -> category -> [{ok, latencyMs, quality, ts}]
  }

  // ── Persistence ───────────────────────────────────────────────────────────

  _load() {
    try { this._memory = JSON.parse(fs.readFileSync(MEMORY_FILE, 'utf8')); }
    catch { this._memory = { conversations: [], profile: { summary: '', topics: {}, preferences: {}, updated_at: null } }; }

    try { this._scores = JSON.parse(fs.readFileSync(SCORES_FILE, 'utf8')); }
    catch { this._scores = { scores: {}, history: [], last_cycle: null }; }

    try { this._history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf8')); }
    catch { this._history = { cycles: [], rollback_stack: [], active_prompts: {}, last_review: null }; }
  }

  _save() {
    try { fs.writeFileSync(MEMORY_FILE, JSON.stringify(this._memory, null, 2)); } catch (e) { console.error('[autolearn] save memory error:', e.message); }
    try { fs.writeFileSync(SCORES_FILE, JSON.stringify(this._scores, null, 2)); } catch (e) { console.error('[autolearn] save scores error:', e.message); }
    try { fs.writeFileSync(HISTORY_FILE, JSON.stringify(this._history, null, 2)); } catch (e) { console.error('[autolearn] save history error:', e.message); }
  }

  // ── Pillar 1: Memory Engine ───────────────────────────────────────────────

  recordConversation(entry) {
    // entry: { agent, category, userText, responseText, nodeId, latencyMs, ts }
    if (!this._memory) return;
    this._memory.conversations.push(entry);
    if (this._memory.conversations.length > MAX_CONVERSATIONS) {
      this._memory.conversations = this._memory.conversations.slice(-MAX_CONVERSATIONS);
    }

    // Update topic frequency
    const cat = entry.category || 'default';
    this._memory.profile.topics[cat] = (this._memory.profile.topics[cat] || 0) + 1;

    // Track in call log for reliability
    const nodeId = entry.nodeId;
    if (nodeId) {
      if (!this._callLog[nodeId]) this._callLog[nodeId] = {};
      if (!this._callLog[nodeId][cat]) this._callLog[nodeId][cat] = [];
      this._callLog[nodeId][cat].push({
        ok: !entry.error,
        latencyMs: entry.latencyMs,
        quality: entry.quality || null,
        ts: entry.ts
      });
      // Keep only last RELIABILITY_WINDOW entries
      if (this._callLog[nodeId][cat].length > RELIABILITY_WINDOW) {
        this._callLog[nodeId][cat] = this._callLog[nodeId][cat].slice(-RELIABILITY_WINDOW);
      }
    }

    this._save();
  }

  async _updateProfileSummary() {
    if (!this._memory || this._memory.conversations.length < 5) return;

    const recent = this._memory.conversations.slice(-20);
    const topicsSummary = Object.entries(this._memory.profile.topics)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([k, v]) => `${k}:${v}`)
      .join(', ');

    const recentTexts = recent.map(c => c.userText?.slice(0, 80) || '').join('\n');

    const prompt = `Analyse ce profil utilisateur JARVIS et resume en 3-4 phrases concises:
Topics frequents: ${topicsSummary}
Messages recents (extrait):
${recentTexts}
Retourne UNIQUEMENT le resume, pas de markdown, pas de titre.`;

    try {
      // M1 for deep profile summary, fallback OL1
      const result = await this._callNodeSafe('M1', prompt, 'OL1');
      if (result) {
        this._memory.profile.summary = result.slice(0, 500);
        this._memory.profile.updated_at = new Date().toISOString();
        this._save();
        console.log('[autolearn] Profile updated via', result.length > 0 ? 'cluster' : 'skip');
      }
    } catch (e) {
      console.error('[autolearn] Profile update failed:', e.message);
    }
  }

  getContextInjection(category) {
    if (!this._memory) return '';
    const parts = [];

    // Inject profile summary if available
    if (this._memory.profile.summary) {
      parts.push(`[Profil utilisateur: ${this._memory.profile.summary}]`);
    }

    // Inject recent context for this category (last 3 exchanges)
    const catConvos = this._memory.conversations
      .filter(c => c.category === category)
      .slice(-3);

    if (catConvos.length > 0) {
      const ctx = catConvos.map(c => `Q: ${(c.userText || '').slice(0, 60)}...`).join(' | ');
      parts.push(`[Contexte recent ${category}: ${ctx}]`);
    }

    return parts.join('\n');
  }

  // ── Dynamic Routing — getBestNode ───────────────────────────────────────

  recordCallResult(nodeId, category, ok, latencyMs) {
    if (!this._callLog[nodeId]) this._callLog[nodeId] = {};
    if (!this._callLog[nodeId][category]) this._callLog[nodeId][category] = [];
    const log = this._callLog[nodeId][category];
    log.push({ ok, latencyMs, quality: null, ts: Date.now() });
    if (log.length > RELIABILITY_WINDOW) log.shift();
  }

  getBestNode(category, excludeNodes) {
    excludeNodes = excludeNodes || [];
    const candidates = (this._routing[category] || this._routing.default)
      .filter(n => !excludeNodes.includes(n));
    if (!candidates.length) return null;

    // If no call log data (< 3 entries for any candidate), return first (hardcoded fallback)
    const hasData = candidates.some(n =>
      this._callLog[n] && this._callLog[n][category] && this._callLog[n][category].length >= 3
    );
    if (!hasData) return candidates[0];

    // Score each candidate: speed*0.3 + quality*0.5 + reliability*0.2
    let best = null, bestScore = -1;
    for (const nodeId of candidates) {
      const entries = (this._callLog[nodeId] && this._callLog[nodeId][category]) || [];
      if (entries.length < 3) {
        const posScore = 1 - (candidates.indexOf(nodeId) / candidates.length);
        if (posScore > bestScore) { bestScore = posScore; best = nodeId; }
        continue;
      }
      const recent = entries.slice(-RELIABILITY_WINDOW);
      const avgLatency = recent.reduce((s, e) => s + e.latencyMs, 0) / recent.length;
      const successRate = recent.filter(e => e.ok).length / recent.length;
      const speedScore = Math.max(0, 1 - (avgLatency / 60000));
      const qualityEntries = recent.filter(e => e.quality !== null);
      const qualityScore = qualityEntries.length > 0
        ? qualityEntries.reduce((s, e) => s + e.quality, 0) / qualityEntries.length / 10
        : successRate; // fallback to success rate if no quality data
      const score = speedScore * 0.3 + qualityScore * 0.5 + successRate * 0.2;
      if (score > bestScore) { bestScore = score; best = nodeId; }
    }
    return best || candidates[0];
  }

  // ── Pillar 2: Auto-Tuning ────────────────────────────────────────────────

  _speedScore(latencyMs) {
    // Linear: 500ms=10, 30000ms=1, capped
    if (latencyMs <= 500) return 10;
    if (latencyMs >= 30000) return 1;
    return Math.round(10 - (latencyMs - 500) * 9 / 29500);
  }

  _reliabilityScore(nodeId, cat) {
    const log = this._callLog[nodeId]?.[cat];
    if (!log || log.length === 0) return 5; // neutral default
    const successes = log.filter(e => e.ok).length;
    return Math.round((successes / log.length) * 10);
  }

  async scoreResponse(entry) {
    // OL1 rates quality 1-10, timeout 10s
    const prompt = `/no_think
Note cette reponse IA de 1 a 10 (1=inutile, 10=parfait).
Question: ${(entry.userText || '').slice(0, 150)}
Reponse: ${(entry.responseText || '').slice(0, 300)}
Reponds UNIQUEMENT un chiffre entre 1 et 10.`;

    try {
      const result = await this._callNodeSafe('OL1', prompt, 'M3');
      if (result) {
        const score = parseInt(result.replace(/\D/g, ''));
        if (score >= 1 && score <= 10) return score;
      }
    } catch (e) {
      console.error('[autolearn] scoreResponse failed:', e.message);
    }
    return 5; // default neutral
  }

  async runTuningCycle() {
    console.log('[autolearn] Starting tuning cycle...');
    const nodeIds = ['M1', 'M2', 'M3', 'OL1'];
    const categories = Object.keys(this._routing);
    const newScores = {};

    for (const cat of categories) {
      newScores[cat] = {};
      for (const nodeId of nodeIds) {
        const log = this._callLog[nodeId]?.[cat] || [];
        if (log.length === 0) {
          newScores[cat][nodeId] = null; // no data
          continue;
        }

        const avgLatency = log.reduce((s, e) => s + (e.latencyMs || 5000), 0) / log.length;
        const speed = this._speedScore(avgLatency);
        const reliability = this._reliabilityScore(nodeId, cat);

        // Average quality from scored entries (or neutral 5)
        const qualityEntries = log.filter(e => e.quality !== null);
        const quality = qualityEntries.length > 0
          ? qualityEntries.reduce((s, e) => s + e.quality, 0) / qualityEntries.length
          : 5;

        // Weighted formula: speed×0.3 + quality×0.5 + reliability×0.2
        const final = Math.round((speed * 0.3 + quality * 0.5 + reliability * 0.2) * 10) / 10;
        newScores[cat][nodeId] = { speed, quality: Math.round(quality * 10) / 10, reliability, final };
      }

      // Reorder routing chain by final score (descending)
      const ranked = nodeIds
        .filter(n => newScores[cat][n] !== null)
        .sort((a, b) => (newScores[cat][b]?.final || 0) - (newScores[cat][a]?.final || 0));

      if (ranked.length > 0) {
        // Only reorder if we have data, preserve nodes with no data at the end
        const noData = nodeIds.filter(n => newScores[cat][n] === null);
        this._routing[cat] = [...ranked, ...noData].filter(n => this._routing[cat]?.includes(n));
      }
    }

    this._scores.scores = newScores;
    this._scores.last_cycle = new Date().toISOString();
    this._scores.history.push({ ts: this._scores.last_cycle, scores: JSON.parse(JSON.stringify(newScores)) });
    if (this._scores.history.length > MAX_HISTORY_CYCLES) {
      this._scores.history = this._scores.history.slice(-MAX_HISTORY_CYCLES);
    }

    // Background trend analysis on M1 (non-blocking)
    this._m1TrendAnalysis().catch(e => console.error('[autolearn] Trend analysis failed:', e.message));

    this._save();
    console.log('[autolearn] Tuning cycle complete. Routing updated.');
  }

  async _m1TrendAnalysis() {
    if (this._scores.history.length < 3) return;

    const lastN = this._scores.history.slice(-5);
    const summary = JSON.stringify(lastN.map(h => ({ ts: h.ts, topCats: Object.keys(h.scores).slice(0, 4) })));

    const prompt = `Analyse ces tendances de performance du cluster JARVIS (${lastN.length} cycles).
Donnees: ${summary.slice(0, 500)}
Identifie: 1) noeuds qui se degradent 2) categories sous-performantes 3) recommandations.
Reponds en JSON: {"degrading":[],"weak_cats":[],"recommendations":"..."}`;

    try {
      const result = await this._callNodeSafe('M1', prompt, 'OL1');
      if (result) console.log('[autolearn] M1 trend analysis:', result.slice(0, 200));
    } catch { /* non-critical */ }
  }

  // ── Pillar 3: Auto-Review ────────────────────────────────────────────────

  async runReviewCycle() {
    console.log('[autolearn] Starting review cycle...');

    // 1. Find low-scoring conversations (quality < 5)
    const lowScored = this._memory.conversations
      .filter(c => c.quality !== undefined && c.quality < 5)
      .slice(-10);

    if (lowScored.length === 0) {
      console.log('[autolearn] No low-scoring conversations to review.');
      this._history.last_review = new Date().toISOString();
      this._save();
      return;
    }

    const categories = [...new Set(lowScored.map(c => c.category))];
    const cycleResult = { ts: new Date().toISOString(), proposals: [], applied: [], rejected: [] };

    for (const cat of categories) {
      const catConvos = lowScored.filter(c => c.category === cat);
      const currentPrompt = this._sysPrompts[cat] || this._sysPrompts.default;

      // Step 1: M2 analyzes weaknesses and proposes new prompt
      const m2Prompt = `/no_think
Analyse ces reponses de faible qualite pour la categorie "${cat}":
${catConvos.map(c => `Q: ${(c.userText || '').slice(0, 80)} | Score: ${c.quality}/10`).join('\n')}

Prompt systeme actuel: "${currentPrompt}"

Propose un prompt systeme ameliore en JSON:
{"new_prompt":"...", "reasoning":"...", "expected_improvement":"..."}
Reponds UNIQUEMENT en JSON valide.`;

      let proposal = null;
      try {
        const m2Result = await this._callNodeSafe('M2', m2Prompt, 'M3');
        if (m2Result) {
          proposal = this._parseJSON(m2Result);
        }
      } catch (e) {
        console.error('[autolearn] M2 review failed:', e.message);
        continue;
      }

      if (!proposal?.new_prompt) {
        cycleResult.rejected.push({ cat, reason: 'M2 no valid proposal' });
        continue;
      }

      // Step 2: M3 validates the proposal (score 0-1, threshold > 0.7)
      const m3Prompt = `/no_think
Valide cette proposition de prompt systeme pour la categorie "${cat}":
Ancien: "${currentPrompt}"
Nouveau: "${proposal.new_prompt}"
Raison: "${proposal.reasoning || ''}"

Note de 0 a 1 si le nouveau prompt est meilleur (>0.7 = approuve).
Reponds en JSON: {"score":0.X, "approved":true/false, "comment":"..."}`;

      let validation = null;
      try {
        const m3Result = await this._callNodeSafe('M3', m3Prompt, 'OL1');
        if (m3Result) validation = this._parseJSON(m3Result);
      } catch (e) {
        console.error('[autolearn] M3 validation failed:', e.message);
      }

      if (!validation || validation.score === undefined || validation.score <= 0.7) {
        cycleResult.rejected.push({ cat, reason: `M3 score ${validation?.score || 'N/A'} <= 0.7` });
        continue;
      }

      // Step 3: M1 meta-review (OUI/NON, timeout 120s -> approve by default)
      let m1Approved = true; // default if timeout
      try {
        const m1Prompt = `/no_think
Meta-review: le prompt systeme pour "${cat}" devrait-il etre modifie?
Ancien: "${currentPrompt.slice(0, 200)}"
Nouveau: "${proposal.new_prompt.slice(0, 200)}"
Score M3: ${validation.score}
Reponds UNIQUEMENT "OUI" ou "NON".`;

        const m1Result = await this._callNodeSafe('M1', m1Prompt, null, 120000);
        if (m1Result) {
          m1Approved = m1Result.trim().toUpperCase().includes('OUI');
        }
      } catch {
        m1Approved = true; // timeout -> approve by default
      }

      if (!m1Approved) {
        cycleResult.rejected.push({ cat, reason: 'M1 meta-review rejected' });
        continue;
      }

      // Step 4: Hot-swap prompt
      const oldPrompt = this._sysPrompts[cat];
      this._history.rollback_stack.push({ cat, prompt: oldPrompt, ts: new Date().toISOString() });
      this._sysPrompts[cat] = proposal.new_prompt;

      cycleResult.applied.push({ cat, old: oldPrompt.slice(0, 80), new: proposal.new_prompt.slice(0, 80) });
      cycleResult.proposals.push(proposal);
      console.log(`[autolearn] Prompt hot-swapped for "${cat}"`);
    }

    this._history.cycles.push(cycleResult);
    if (this._history.cycles.length > MAX_HISTORY_CYCLES) {
      this._history.cycles = this._history.cycles.slice(-MAX_HISTORY_CYCLES);
    }
    this._history.last_review = new Date().toISOString();
    this._history.active_prompts = { ...this._sysPrompts };

    // Check rollback condition
    this._checkRollback();

    this._save();
    console.log(`[autolearn] Review cycle complete: ${cycleResult.applied.length} applied, ${cycleResult.rejected.length} rejected`);
  }

  _checkRollback() {
    // Revert if average quality dropped > 15% over last 3 cycles
    const recentCycles = this._history.cycles.slice(-3);
    if (recentCycles.length < 3) return;

    // Compare quality before first of the 3 cycles vs recent
    const cutoff = new Date(recentCycles[0].ts).getTime();
    const before = this._memory.conversations.filter(c => new Date(c.ts).getTime() < cutoff && c.quality);
    const after = this._memory.conversations.filter(c => new Date(c.ts).getTime() >= cutoff && c.quality);

    if (before.length < 5 || after.length < 5) return;

    const avgBefore = before.reduce((s, c) => s + c.quality, 0) / before.length;
    const avgAfter = after.reduce((s, c) => s + c.quality, 0) / after.length;

    if (avgAfter < avgBefore * 0.85) {
      console.log(`[autolearn] ROLLBACK triggered: quality dropped ${avgBefore.toFixed(1)} -> ${avgAfter.toFixed(1)}`);
      // Revert all prompts from rollback stack
      while (this._history.rollback_stack.length > 0) {
        const entry = this._history.rollback_stack.pop();
        this._sysPrompts[entry.cat] = entry.prompt;
        console.log(`[autolearn] Reverted prompt for "${entry.cat}"`);
      }
      this._save();
    }
  }

  // ── API Methods ──────────────────────────────────────────────────────────

  getStatus() {
    return {
      running: this._running,
      pillars: {
        memory: {
          total_messages: this._memory?.conversations?.length || 0,
          profile_summary: this._memory?.profile?.summary?.slice(0, 100) || '',
          profile_updated: this._memory?.profile?.updated_at || null,
          top_topics: Object.entries(this._memory?.profile?.topics || {})
            .sort((a, b) => b[1] - a[1]).slice(0, 5)
        },
        tuning: {
          last_cycle: this._scores?.last_cycle || null,
          history_count: this._scores?.history?.length || 0,
          current_routing: { ...this._routing }
        },
        review: {
          last_review: this._history?.last_review || null,
          cycles_count: this._history?.cycles?.length || 0,
          rollback_stack_size: this._history?.rollback_stack?.length || 0,
          applied_prompts: Object.keys(this._history?.active_prompts || {}).length
        }
      }
    };
  }

  getMemory() {
    return {
      profile: this._memory?.profile || {},
      recent: (this._memory?.conversations || []).slice(-10).map(c => ({
        agent: c.agent,
        category: c.category,
        userText: (c.userText || '').slice(0, 100),
        nodeId: c.nodeId,
        quality: c.quality,
        ts: c.ts
      }))
    };
  }

  getScores() {
    return {
      current: this._scores?.scores || {},
      routing: { ...this._routing },
      last_cycle: this._scores?.last_cycle || null,
      history: (this._scores?.history || []).slice(-5)
    };
  }

  getHistory() {
    return {
      cycles: (this._history?.cycles || []).slice(-10),
      active_prompts: this._history?.active_prompts || {},
      rollback_stack: (this._history?.rollback_stack || []).slice(-5),
      last_review: this._history?.last_review || null
    };
  }

  async triggerReview() {
    console.log('[autolearn] Manual review triggered');
    await this.runReviewCycle();
    return { ok: true, message: 'Review cycle completed' };
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  start() {
    this._load();
    this._running = true;

    this._tuningTimer = setInterval(() => {
      this.runTuningCycle().catch(e => console.error('[autolearn] tuning error:', e.message));
    }, TUNING_INTERVAL);

    this._reviewTimer = setInterval(() => {
      this.runReviewCycle().catch(e => console.error('[autolearn] review error:', e.message));
    }, REVIEW_INTERVAL);

    this._profileTimer = setInterval(() => {
      this._updateProfileSummary().catch(e => console.error('[autolearn] profile error:', e.message));
    }, PROFILE_INTERVAL);

    console.log('[autolearn] Engine started — memory | tuning (5min) | review (30min) | profile (15min)');
  }

  stop() {
    this._running = false;
    if (this._tuningTimer) { clearInterval(this._tuningTimer); this._tuningTimer = null; }
    if (this._reviewTimer) { clearInterval(this._reviewTimer); this._reviewTimer = null; }
    if (this._profileTimer) { clearInterval(this._profileTimer); this._profileTimer = null; }
    this._save();
    console.log('[autolearn] Engine stopped');
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  async _callNodeSafe(primaryNode, prompt, fallbackNode, timeout) {
    const messages = [{ role: 'user', content: prompt }];
    try {
      const result = await this._callNode(primaryNode, messages);
      return result?.text || null;
    } catch (e) {
      if (fallbackNode) {
        try {
          const result = await this._callNode(fallbackNode, messages);
          return result?.text || null;
        } catch { /* both failed */ }
      }
      return null;
    }
  }

  _parseJSON(str) {
    if (!str) return null;
    // Try direct parse
    try { return JSON.parse(str); } catch {}
    // Try extracting JSON from markdown code blocks
    const match = str.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match) try { return JSON.parse(match[1].trim()); } catch {}
    // Try finding first { ... }
    const braceMatch = str.match(/\{[\s\S]*\}/);
    if (braceMatch) try { return JSON.parse(braceMatch[0]); } catch {}
    return null;
  }
}

module.exports = AutolearnEngine;
