#!/usr/bin/env python3
"""
JARVIS Pipeline Engine — Circulating Task System
=================================================
Long tasks are decomposed into typed sections, each section circulates
through the cluster, written by the best-fit node. SQL cache avoids
redundant work. Results saved incrementally. Pipelines are persistent
and reusable.

Architecture:
  DECOMPOSE → CACHE CHECK → ROUTE → EXECUTE → PERSIST → CIRCULATE → ASSEMBLE

Usage:
  python pipeline_engine.py --run "Build a FastAPI auth middleware with JWT"
  python pipeline_engine.py --resume <pipeline_id>
  python pipeline_engine.py --list
  python pipeline_engine.py --reuse <pipeline_id> "New similar task"
  python pipeline_engine.py --daemon
"""

import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Fix Windows cp1252 encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Import orchestrator components ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from devops_orchestrator import (
    PROVIDERS, Provider, query_provider, METRICS,
    send_telegram, classify_intent, _similarity,
    DispatchResult, dispatch_via_openclaw, AGENT_ROUTING,
    log as orch_log,
)

log = logging.getLogger("pipeline")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

TURBO = Path(os.environ.get("TURBO", r"/home/turbo/jarvis-m1-ops"))
DB_PATH = TURBO / "data" / "pipeline.db"


# ── Section Types & Node Strengths ──────────────────────────────────────

class SectionType(str, Enum):
    CODE = "code"
    REASONING = "reasoning"
    REVIEW = "review"
    MATH = "math"
    SUMMARY = "summary"
    DATA = "data"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    CREATIVE = "creative"
    GENERAL = "general"


# Which providers are strongest for each section type
# Order = preference (first = best fit)
NODE_STRENGTHS: dict[SectionType, list[str]] = {
    SectionType.CODE:         ["M1", "M2", "CLAUDE", "OL1", "M3"],
    SectionType.REASONING:    ["M2", "M3", "CLAUDE", "M1", "OL1"],
    SectionType.REVIEW:       ["M2", "CLAUDE", "M1", "M3", "OL1"],
    SectionType.MATH:         ["M1", "M2", "CLAUDE", "M3", "OL1"],
    SectionType.SUMMARY:      ["OL1", "M1", "CLAUDE", "M2", "M3"],
    SectionType.DATA:         ["M1", "OL1", "M2", "CLAUDE", "M3"],
    SectionType.ARCHITECTURE: ["M2", "CLAUDE", "M1", "M3", "OL1"],
    SectionType.SECURITY:     ["M2", "CLAUDE", "M1", "M3", "OL1"],
    SectionType.CREATIVE:     ["CLAUDE", "M2", "M1", "OL1", "M3"],
    SectionType.GENERAL:      ["M1", "OL1", "M2", "CLAUDE", "M3"],
}


@dataclass
class PipelineSection:
    idx: int
    section_type: SectionType
    prompt: str
    response: str = ""
    provider: str = ""
    status: str = "pending"  # pending, cached, running, completed, failed
    latency_ms: float = 0
    from_cache: bool = False


@dataclass
class Pipeline:
    id: str
    name: str
    original_prompt: str
    sections: list[PipelineSection] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    created_at: float = field(default_factory=time.time)


# ── Database ────────────────────────────────────────────────────────────

def _init_db() -> sqlite3.Connection:
    """Initialize pipeline database with all tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT UNIQUE,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            provider TEXT,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hits INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_cache_hash ON pipeline_cache(prompt_hash);
        CREATE INDEX IF NOT EXISTS idx_cache_category ON pipeline_cache(category);

        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT,
            original_prompt TEXT,
            status TEXT DEFAULT 'pending',
            total_sections INTEGER DEFAULT 0,
            completed_sections INTEGER DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pipeline_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT REFERENCES pipelines(id),
            section_idx INTEGER,
            section_type TEXT,
            prompt TEXT,
            response TEXT,
            provider TEXT,
            status TEXT DEFAULT 'pending',
            latency_ms REAL DEFAULT 0,
            from_cache INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sections_pipeline ON pipeline_sections(pipeline_id, section_idx);

        CREATE TABLE IF NOT EXISTS pipeline_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            pattern TEXT,
            section_types TEXT,  -- JSON array of section types
            description TEXT,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return conn


# ── SQL Cache (3 niveaux : exact → fuzzy → knowledge) ──────────────────

def _hash_prompt(prompt: str) -> str:
    """Create a deterministic hash for cache lookup."""
    return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:32]


def _extract_keywords(text: str, max_kw: int = 12) -> set[str]:
    """Extract meaningful keywords from text (skip stopwords, keep 4+ char words)."""
    _STOP = {"avec", "dans", "pour", "cette", "sont", "nous", "vous", "leur",
             "from", "this", "that", "with", "have", "been", "will", "what",
             "the", "and", "les", "des", "une", "qui", "que", "est", "pas",
             "context", "previous", "steps", "current", "task", "write", "answer"}
    words = set()
    for w in text.lower().split():
        w = w.strip(".,;:!?()[]{}\"'`")
        if len(w) >= 4 and w not in _STOP and not w.startswith("http"):
            words.add(w)
    return set(sorted(words, key=len, reverse=True)[:max_kw])


def cache_lookup(conn: sqlite3.Connection, prompt: str) -> Optional[str]:
    """3-level cache lookup: exact hash → keyword fuzzy → pipeline knowledge base."""

    # Level 1: Exact hash match (instantaneous)
    h = _hash_prompt(prompt)
    row = conn.execute(
        "SELECT response, id FROM pipeline_cache WHERE prompt_hash = ?", (h,)
    ).fetchone()
    if row:
        conn.execute("UPDATE pipeline_cache SET hits = hits + 1 WHERE id = ?", (row["id"],))
        conn.commit()
        log.info("CACHE L1 (exact) for hash %s", h[:8])
        return row["response"]

    # Level 2: Fuzzy keyword match (search similar prompts in cache)
    keywords = _extract_keywords(prompt)
    if len(keywords) >= 3:
        rows = conn.execute(
            "SELECT prompt, response, id FROM pipeline_cache ORDER BY hits DESC LIMIT 100"
        ).fetchall()
        best_score, best_row = 0.0, None
        for r in rows:
            cached_kw = _extract_keywords(r["prompt"])
            if not cached_kw:
                continue
            overlap = len(keywords & cached_kw) / len(keywords | cached_kw)
            if overlap > best_score:
                best_score = overlap
                best_row = r
        if best_score >= 0.5 and best_row:
            conn.execute("UPDATE pipeline_cache SET hits = hits + 1 WHERE id = ?", (best_row["id"],))
            conn.commit()
            log.info("CACHE L2 (fuzzy %.0f%%) for prompt", best_score * 100)
            return best_row["response"]

    # Level 3: Search completed pipeline sections as knowledge base
    knowledge = _search_pipeline_knowledge(conn, prompt, keywords)
    if knowledge:
        log.info("CACHE L3 (knowledge) found %d relevant sections", len(knowledge))
        # Don't return as direct answer — inject as context prefix
        # Return None here, but store in a thread-local for context injection
        _KNOWLEDGE_CONTEXT.value = knowledge
        return None

    return None


# Thread-local storage for knowledge context injection
import threading
_KNOWLEDGE_CONTEXT = threading.local()


def _get_knowledge_context() -> str:
    """Retrieve knowledge context found during cache lookup."""
    ctx = getattr(_KNOWLEDGE_CONTEXT, "value", None)
    if ctx:
        _KNOWLEDGE_CONTEXT.value = None  # consume once
        return ctx
    return ""


def _search_pipeline_knowledge(conn: sqlite3.Connection, prompt: str,
                                keywords: set[str]) -> Optional[str]:
    """Search completed pipeline sections for relevant prior knowledge."""
    if len(keywords) < 2:
        return None

    # Search in completed sections
    rows = conn.execute("""
        SELECT ps.section_type, ps.response, ps.provider, p.name as pipeline_name
        FROM pipeline_sections ps
        JOIN pipelines p ON ps.pipeline_id = p.id
        WHERE ps.status IN ('completed', 'cached')
          AND ps.response IS NOT NULL
          AND length(ps.response) > 50
        ORDER BY ps.created_at DESC LIMIT 50
    """).fetchall()

    relevant = []
    for r in rows:
        response_kw = _extract_keywords(r["response"][:300])
        overlap = len(keywords & response_kw)
        if overlap >= 3:  # at least 3 keywords in common for relevance
            relevant.append({
                "type": r["section_type"],
                "text": r["response"][:400],
                "source": r["pipeline_name"],
                "score": overlap
            })

    if not relevant:
        return None

    # Sort by relevance, take top 3
    relevant.sort(key=lambda x: x["score"], reverse=True)
    parts = []
    for r in relevant[:3]:
        parts.append(f"[Prior knowledge from '{r['source']}' ({r['type']})]:\n{r['text']}")

    return "\n\n".join(parts)


def cache_store(conn: sqlite3.Connection, prompt: str, response: str,
                provider: str = "", category: str = ""):
    """Store a result in the cache for future reuse."""
    h = _hash_prompt(prompt)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_cache (prompt_hash, prompt, response, provider, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (h, prompt[:500], response, provider, category)
        )
        conn.commit()
    except sqlite3.Error as e:
        log.warning("Cache store failed: %s", e)


# ── Task Decomposer ────────────────────────────────────────────────────

# Decomposition prompts — sent to a fast local node to split the task
_DECOMPOSE_SYSTEM = """You are a task decomposer. Given a complex task, break it into 3-7 ordered sections.
Each section has a TYPE and a PROMPT.

Types: code, reasoning, review, math, summary, data, architecture, security, creative, general

Output ONLY valid JSON array, no markdown:
[{"type": "reasoning", "prompt": "Analyze requirements for..."}, {"type": "code", "prompt": "Write the function..."}, ...]

Rules:
- Each section should be completable in <60 seconds by any AI model
- Sections build on each other (later sections can reference earlier results)
- Include a review section at the end for quality check
- Keep prompts specific and self-contained (include necessary context)
"""


def decompose_task(prompt: str, conn: sqlite3.Connection) -> list[PipelineSection]:
    """Break a long task into typed sections using a local model."""
    # First check if we have a template that matches
    template = _find_template(conn, prompt)
    if template:
        log.info("Using template '%s' for decomposition", template["name"])
        types = json.loads(template["section_types"])
        conn.execute(
            "UPDATE pipeline_templates SET usage_count = usage_count + 1 WHERE id = ?",
            (template["id"],)
        )
        conn.commit()
        sections = []
        for i, t in enumerate(types):
            sections.append(PipelineSection(
                idx=i,
                section_type=SectionType(t.get("type", "general")),
                prompt=t.get("prompt_template", "").replace("{TASK}", prompt) if t.get("prompt_template") else prompt,
            ))
        return sections

    # Use M1 (fastest local) to decompose
    decompose_prompt = f"{_DECOMPOSE_SYSTEM}\n\nTask to decompose:\n{prompt}"

    # Try M1 first, then OL1
    for provider_id in ["M1", "OL1", "M2"]:
        provider = PROVIDERS.get(provider_id)
        if not provider or not provider.is_available():
            continue
        try:
            # Temporarily increase max_tokens for decomposition
            old_max = provider.max_tokens
            provider.max_tokens = 512
            response = query_provider(provider, decompose_prompt)
            provider.max_tokens = old_max

            if not response:
                continue

            # Parse JSON from response (handle markdown code fences)
            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parts = json.loads(text)
            sections = []
            for i, part in enumerate(parts):
                st = part.get("type", "general")
                try:
                    section_type = SectionType(st)
                except ValueError:
                    section_type = SectionType.GENERAL
                sections.append(PipelineSection(
                    idx=i,
                    section_type=section_type,
                    prompt=part.get("prompt", prompt),
                ))

            log.info("Decomposed into %d sections via %s: %s",
                     len(sections), provider_id,
                     [s.section_type.value for s in sections])
            return sections

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("Decomposition parse error via %s: %s", provider_id, e)
            continue
        except Exception as e:
            log.warning("Decomposition failed via %s: %s", provider_id, e)
            continue

    # Fallback: manual decomposition based on intent classification
    log.warning("Auto-decomposition failed, using heuristic fallback")
    return _heuristic_decompose(prompt)


def _heuristic_decompose(prompt: str) -> list[PipelineSection]:
    """Fallback decomposition using keyword heuristics."""
    prompt_lower = prompt.lower()
    sections = []

    # Always start with analysis
    sections.append(PipelineSection(0, SectionType.REASONING,
        f"Analyze the requirements and constraints for: {prompt}"))

    # Detect what kind of work this is
    if any(kw in prompt_lower for kw in ["code", "function", "class", "implement", "write", "script", "api"]):
        sections.append(PipelineSection(len(sections), SectionType.ARCHITECTURE,
            f"Design the architecture/structure for: {prompt}"))
        sections.append(PipelineSection(len(sections), SectionType.CODE,
            f"Write the implementation for: {prompt}"))

    if any(kw in prompt_lower for kw in ["calcul", "math", "formula", "equation", "compute"]):
        sections.append(PipelineSection(len(sections), SectionType.MATH,
            f"Solve the mathematical aspects of: {prompt}"))

    if any(kw in prompt_lower for kw in ["secur", "vuln", "audit", "xss", "inject"]):
        sections.append(PipelineSection(len(sections), SectionType.SECURITY,
            f"Security analysis for: {prompt}"))

    if any(kw in prompt_lower for kw in ["data", "database", "sql", "csv", "json", "parse"]):
        sections.append(PipelineSection(len(sections), SectionType.DATA,
            f"Data handling aspects of: {prompt}"))

    # Always end with review + summary
    sections.append(PipelineSection(len(sections), SectionType.REVIEW,
        f"Review and validate the complete solution for: {prompt}"))
    sections.append(PipelineSection(len(sections), SectionType.SUMMARY,
        f"Summarize the final solution in a clear, actionable format for: {prompt}"))

    return sections


def _find_template(conn: sqlite3.Connection, prompt: str) -> Optional[dict]:
    """Find a matching pipeline template by pattern similarity."""
    rows = conn.execute("SELECT * FROM pipeline_templates ORDER BY usage_count DESC LIMIT 20").fetchall()
    for row in rows:
        pattern = row["pattern"]
        if pattern and _similarity(pattern, prompt) > 0.4:
            return dict(row)
    return None


# ── Section Router ──────────────────────────────────────────────────────

def route_section(section: PipelineSection) -> list[str]:
    """Get ordered provider list for a section, based on type strengths + availability."""
    strength_order = NODE_STRENGTHS.get(section.section_type, NODE_STRENGTHS[SectionType.GENERAL])
    available = [pid for pid in strength_order if pid in PROVIDERS and PROVIDERS[pid].is_available()]
    if not available:
        # Emergency: try anything that's up
        available = [pid for pid, p in PROVIDERS.items() if p.is_available()]
    return available


# ── Section Executor ────────────────────────────────────────────────────

def _try_openclaw(prompt: str, section_type: str, timeout: int = 45) -> Optional[str]:
    """Try dispatching via OpenClaw gateway with strict timeout.
    If OpenClaw takes >45s, skip it and let direct provider dispatch handle it."""
    SECTION_TO_AGENT = {
        "code": "coding",
        "reasoning": "deep-reasoning",
        "review": "code-champion",
        "math": "analysis-engine",
        "summary": "fast-chat",
        "data": "data-analyst",
        "architecture": "deep-work",
        "security": "securite-audit",
        "creative": "creative-brainstorm",
        "general": "fast-chat",
    }
    agent = SECTION_TO_AGENT.get(section_type, "fast-chat")

    # Use a thread with timeout to avoid OpenClaw internal cascade eating minutes
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(dispatch_via_openclaw, prompt, agent)
        try:
            result = future.result(timeout=timeout)
            if result.get("response") and len(result["response"]) > 20:
                return result["response"]
        except concurrent.futures.TimeoutError:
            log.warning("OpenClaw timeout (%ds) for [%s] — skipping to direct dispatch", timeout, section_type)
            future.cancel()
        except Exception as e:
            log.debug("OpenClaw dispatch failed: %s", e)
    return None


def execute_section(section: PipelineSection, context: str, conn: sqlite3.Connection) -> PipelineSection:
    """Execute a single section: cache check → OpenClaw → route → query → persist."""

    # 1. Build the full prompt with context from previous sections
    full_prompt = section.prompt
    if context:
        full_prompt = f"Context from previous steps:\n{context}\n\n---\nCurrent task:\n{section.prompt}"

    # 2. Cache check (3 levels: exact → fuzzy → knowledge)
    cached = cache_lookup(conn, full_prompt)
    if cached:
        section.response = cached
        section.status = "cached"
        section.from_cache = True
        section.latency_ms = 0
        log.info("  Section %d [%s] → CACHE HIT", section.idx, section.section_type.value)
        return section

    # 2.1 Inject prior knowledge as context if Level 3 found something
    prior_knowledge = _get_knowledge_context()
    if prior_knowledge:
        full_prompt = (
            f"Prior knowledge (from previous pipelines):\n{prior_knowledge}\n\n---\n{full_prompt}"
        )
        log.info("  Section %d [%s] — injected prior knowledge as context", section.idx, section.section_type.value)

    # 2.5. Try OpenClaw gateway first (40 agents, distributes to best fit)
    start_oc = time.time()
    oc_response = _try_openclaw(full_prompt, section.section_type.value)
    if oc_response:
        elapsed = (time.time() - start_oc) * 1000
        section.response = oc_response
        section.provider = "OpenClaw"
        section.latency_ms = elapsed
        section.status = "completed"
        cache_store(conn, full_prompt, oc_response, "OpenClaw", section.section_type.value)
        log.info("  Section %d [%s] → OpenClaw OK %.0fms (%d chars)",
                 section.idx, section.section_type.value, elapsed, len(oc_response))
        return section

    # 3. Route to best-fit providers (direct fallback if OpenClaw unavailable)
    providers_chain = route_section(section)
    if not providers_chain:
        section.status = "failed"
        section.response = "No providers available"
        return section

    # 4. Execute with fallback chain — temporarily boost max_tokens for pipeline work
    section.status = "running"
    for pid in providers_chain:
        provider = PROVIDERS[pid]
        # Pipeline sections need more tokens than quick dispatch
        old_max = provider.max_tokens
        provider.max_tokens = max(provider.max_tokens, 512)
        start = time.time()
        try:
            response = query_provider(provider, full_prompt)
            elapsed = (time.time() - start) * 1000

            if response:
                section.response = response
                section.provider = pid
                section.latency_ms = elapsed
                section.status = "completed"
                provider.record_success()
                METRICS.record(pid, f"pipeline_{section.section_type.value}", True, elapsed)

                # 5. Persist to cache
                cache_store(conn, full_prompt, response, pid, section.section_type.value)

                log.info("  Section %d [%s] → %s OK %.0fms (%d chars)",
                         section.idx, section.section_type.value, pid, elapsed, len(response))
                return section
            else:
                provider.record_fail()

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            provider.record_fail()
            log.warning("  Section %d [%s] → %s FAIL: %s",
                        section.idx, section.section_type.value, pid, str(e)[:80])
        finally:
            provider.max_tokens = old_max

    section.status = "failed"
    return section


# ══════════════════════════════════════════════════════════════════════════
# ── COLLABORATIVE ZERO-TIMEOUT ENGINE ────────────────────────────────────
# Tasks are pre-written as chunks. Each chunk is tiny (≤15s per node).
# If a node is slow/dead → skip INSTANTLY to next. No waiting.
# Every chunk is saved to SQL immediately. Nothing is ever lost.
# The task circulates permanently until complete.
# ══════════════════════════════════════════════════════════════════════════

# Fast timeout per node — if a node can't answer in 15s, it's too slow
_FAST_TIMEOUT = 15

# Chunk prompts — pre-written sub-tasks for each section type
_CHUNK_TEMPLATES = {
    SectionType.CODE: [
        ("imports", "Write ONLY the import statements and constants needed for: {TASK}. No explanation, just code."),
        ("core", "Write ONLY the core function/class implementation for: {TASK}. No imports, no tests."),
        ("integration", "Write ONLY the integration code (API endpoint, CLI, or glue code) for: {TASK}. No imports."),
    ],
    SectionType.REASONING: [
        ("analysis", "Analyze the key requirements and constraints for: {TASK}. Be concise, max 150 words."),
        ("solution", "Propose the best solution approach for: {TASK}. Max 150 words."),
    ],
    SectionType.REVIEW: [
        ("review", "Review and list any issues with this solution: {TASK}. Max 100 words."),
    ],
    SectionType.ARCHITECTURE: [
        ("components", "List the key components/modules needed for: {TASK}. Max 100 words."),
        ("design", "Describe how the components connect and interact for: {TASK}. Max 150 words."),
    ],
    SectionType.SUMMARY: [
        ("summary", "Summarize the final solution concisely for: {TASK}. Max 200 words."),
    ],
    SectionType.MATH: [
        ("setup", "Set up the mathematical formulation for: {TASK}. Max 100 words."),
        ("solve", "Solve and show the result for: {TASK}. Max 150 words."),
    ],
    SectionType.SECURITY: [
        ("threats", "Identify top 3 security threats for: {TASK}. Max 100 words."),
        ("mitigations", "Propose mitigations for each threat in: {TASK}. Max 150 words."),
    ],
    SectionType.DATA: [
        ("schema", "Design the data schema/structure for: {TASK}. Max 100 words."),
        ("queries", "Write key queries/operations for: {TASK}. Max 150 words."),
    ],
    SectionType.CREATIVE: [
        ("ideas", "Brainstorm 3 creative approaches for: {TASK}. Max 150 words."),
    ],
    SectionType.GENERAL: [
        ("answer", "Answer concisely: {TASK}. Max 200 words."),
    ],
}


@dataclass
class Chunk:
    """A tiny piece of work — written by one node, saved immediately."""
    name: str
    prompt: str
    response: str = ""
    provider: str = ""
    latency_ms: float = 0
    status: str = "pending"  # pending, cached, completed, failed


def _get_fast_providers() -> list[tuple[str, Provider]]:
    """Get available providers sorted by speed (fastest first). Skip dead ones."""
    available = []
    for pid, p in PROVIDERS.items():
        if not p.is_available():
            continue
        if p.is_cloud and p.circuit_open:
            continue
        available.append((pid, p))
    # Sort: local first, then by weight (proxy for reliability)
    available.sort(key=lambda x: (not x[1].is_cloud, x[1].weight), reverse=True)
    return available


def _query_fast(provider: Provider, prompt: str, timeout: int = _FAST_TIMEOUT) -> str:
    """Query a provider with HARD fast timeout. No waiting."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(query_provider, provider, prompt)
        try:
            result = future.result(timeout=timeout)
            return result or ""
        except concurrent.futures.TimeoutError:
            future.cancel()
            return ""
        except Exception:
            return ""


def collaborative_execute_section(section: PipelineSection, context: str,
                                   conn: sqlite3.Connection) -> PipelineSection:
    """
    ZERO-TIMEOUT collaborative execution:
    1. Pre-write chunk prompts from templates
    2. For each chunk: SQL check → fast query (15s max) → save SQL → next
    3. Each chunk goes to a different node (round-robin)
    4. If a node is slow → skip instantly, try next
    5. Assemble chunks into section response
    """
    # ── Step 0: SQL check — do we already know the answer? ──
    full_prompt = section.prompt
    if context:
        full_prompt = f"Context:\n{context[:500]}\n\n{section.prompt}"

    cached = cache_lookup(conn, full_prompt)
    if cached:
        section.response = cached
        section.status = "cached"
        section.from_cache = True
        section.latency_ms = 0
        log.info("  S%d [%s] → SQL CACHE", section.idx, section.section_type.value)
        return section

    # Inject prior knowledge if available
    prior = _get_knowledge_context()
    if prior:
        full_prompt = f"Prior knowledge:\n{prior[:400]}\n\n{full_prompt}"

    # ── Step 1: Pre-write chunk prompts ──
    templates = _CHUNK_TEMPLATES.get(section.section_type, _CHUNK_TEMPLATES[SectionType.GENERAL])
    chunks = []
    for name, template in templates:
        chunk_prompt = template.replace("{TASK}", section.prompt)
        chunks.append(Chunk(name=name, prompt=chunk_prompt))

    # ── Step 2: Get available providers ──
    providers = _get_fast_providers()
    if not providers:
        section.status = "failed"
        section.response = "No providers available"
        return section

    # ── Step 3: Execute chunks — round-robin, fast timeout, SQL save ──
    total_start = time.time()
    chunk_results = []
    node_idx = 0

    for chunk in chunks:
        # SQL check for this specific chunk
        chunk_cached = cache_lookup(conn, chunk.prompt)
        if chunk_cached:
            chunk.response = chunk_cached
            chunk.status = "cached"
            chunk.provider = "CACHE"
            chunk_results.append(chunk)
            log.info("    chunk [%s] → SQL CACHE", chunk.name)
            continue

        # Try providers round-robin — skip instantly if slow
        wrote = False
        attempts = 0
        while attempts < len(providers) and not wrote:
            pid, provider = providers[node_idx % len(providers)]
            node_idx += 1
            attempts += 1

            # Boost tokens for pipeline chunks
            old_max = provider.max_tokens
            provider.max_tokens = max(provider.max_tokens, 512)

            start = time.time()
            try:
                # Include context from previous chunks in this section
                if chunk_results:
                    prev_text = "\n".join(c.response[:200] for c in chunk_results if c.response)
                    enriched = f"Previous chunks:\n{prev_text}\n\nNow write:\n{chunk.prompt}"
                else:
                    enriched = chunk.prompt
                if context:
                    enriched = f"Context:\n{context[:300]}\n\n{enriched}"

                response = _query_fast(provider, enriched, timeout=_FAST_TIMEOUT)
                elapsed = (time.time() - start) * 1000

                if response and len(response) > 10:
                    chunk.response = response
                    chunk.provider = pid
                    chunk.latency_ms = elapsed
                    chunk.status = "completed"
                    provider.record_success()
                    wrote = True

                    # ── SQL SAVE immediately ──
                    cache_store(conn, chunk.prompt, response, pid, section.section_type.value)
                    # Also save to pipeline_sections as sub-entry
                    _save_chunk_to_db(conn, section, chunk)

                    log.info("    chunk [%s] → %s OK %.0fms (%d chars)",
                             chunk.name, pid, elapsed, len(response))
                else:
                    provider.record_fail()
                    log.debug("    chunk [%s] → %s EMPTY, next node", chunk.name, pid)
            except Exception as e:
                provider.record_fail()
                log.debug("    chunk [%s] → %s FAIL: %s", chunk.name, pid, str(e)[:60])
            finally:
                provider.max_tokens = old_max

        if not wrote:
            chunk.status = "failed"
            log.warning("    chunk [%s] FAILED — all nodes tried", chunk.name)

        chunk_results.append(chunk)

    # ── Step 4: Assemble chunks ──
    total_elapsed = (time.time() - total_start) * 1000
    completed_chunks = [c for c in chunk_results if c.status in ("completed", "cached")]

    if completed_chunks:
        parts = []
        for c in completed_chunks:
            parts.append(c.response)
        section.response = "\n\n".join(parts)
        section.provider = "+".join(c.provider for c in completed_chunks if c.provider != "CACHE")
        section.latency_ms = total_elapsed
        section.status = "completed"

        # Save assembled result to cache
        cache_store(conn, full_prompt, section.response, section.provider, section.section_type.value)

        contributors = ["%s(%s,%.0fms)" % (c.provider, c.name, c.latency_ms)
                        for c in completed_chunks if c.provider != "CACHE"]
        log.info("  S%d [%s] ASSEMBLED %d/%d chunks in %.0fms [%s]",
                 section.idx, section.section_type.value,
                 len(completed_chunks), len(chunks), total_elapsed,
                 " → ".join(contributors) if contributors else "ALL CACHE")
    else:
        section.status = "failed"
        section.latency_ms = total_elapsed

    return section


def _save_chunk_to_db(conn: sqlite3.Connection, section: PipelineSection, chunk: Chunk):
    """Save individual chunk to DB for granular recovery."""
    try:
        conn.execute("""
            INSERT INTO pipeline_cache (prompt_hash, prompt, response, provider, category)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(prompt_hash) DO UPDATE SET
                response = excluded.response, provider = excluded.provider, hits = hits
        """, (
            _hash_prompt(chunk.prompt),
            chunk.prompt[:500],
            chunk.response[:3000],
            chunk.provider,
            f"chunk_{chunk.name}",
        ))
        conn.commit()
    except sqlite3.Error:
        pass  # non-critical


# ── Circulating Multi-Node Writer (legacy, kept for --circulate CLI) ─────

def circulate_write(prompt: str, conn: sqlite3.Connection,
                    max_passes: int = 5, target_length: int = 1500) -> str:
    """
    Circulating writer: each node adds its part to build the full response.
    No single node needs to generate everything — they collaborate.

    Pass 1: Node A writes the beginning
    Pass 2: Node B continues from where A stopped
    Pass 3: Node C adds more / reviews / corrects
    ...until target_length reached or max_passes exhausted.
    """
    # Check cache first
    cached = cache_lookup(conn, prompt)
    if cached and len(cached) >= target_length // 2:
        return cached

    # Get all available providers — prefer local over cloud, then by weight
    # Skip cloud providers with open circuit breakers (likely dead credits)
    available = sorted(
        [(pid, p) for pid, p in PROVIDERS.items()
         if p.is_available() and not (p.is_cloud and p.circuit_open)],
        key=lambda x: (not x[1].is_cloud, x[1].weight),  # local first, then by weight
        reverse=True
    )
    if not available:
        # Emergency: try anything at all
        available = [(pid, p) for pid, p in PROVIDERS.items() if p.is_available()]
    if not available:
        return ""

    accumulated = ""
    contributors = []

    for pass_num in range(max_passes):
        if len(accumulated) >= target_length:
            break

        # Round-robin: pick the next provider
        pid, provider = available[pass_num % len(available)]

        if pass_num == 0:
            # First pass: start writing
            pass_prompt = f"Write the first part of the answer to this question (respond in 200-400 words, be specific):\n{prompt}"
        else:
            # Continuation: add to existing
            pass_prompt = (
                f"Continue and complete this answer. DO NOT repeat what's already written. "
                f"Add new information, examples, or corrections.\n\n"
                f"Question: {prompt}\n\n"
                f"Already written ({len(accumulated)} chars):\n{accumulated[-800:]}\n\n"
                f"Continue from here:"
            )

        old_max = provider.max_tokens
        provider.max_tokens = max(provider.max_tokens, 512)
        start = time.time()
        try:
            response = query_provider(provider, pass_prompt)
            elapsed = (time.time() - start) * 1000
            if response:
                accumulated += ("\n\n" if accumulated else "") + response
                contributors.append(f"{pid}({elapsed:.0f}ms)")
                provider.record_success()
                log.info("  Circulate pass %d: %s added %d chars (total=%d)",
                         pass_num + 1, pid, len(response), len(accumulated))
            else:
                provider.record_fail()
                log.warning("  Circulate pass %d: %s EMPTY response", pass_num + 1, pid)
        except Exception as e:
            provider.record_fail()
            log.warning("  Circulate pass %d: %s FAIL: %s", pass_num + 1, pid, str(e)[:80])
        finally:
            provider.max_tokens = old_max

    if accumulated:
        # Add attribution
        attribution = f"\n\n[Contributors: {' → '.join(contributors)}]"
        result = accumulated + attribution
        cache_store(conn, prompt, result, ",".join(c.split("(")[0] for c in contributors), "circulated")
        return result

    return ""


# ── Parallel Section Executor ───────────────────────────────────────────

def execute_independent_sections(sections: list[PipelineSection], context: str,
                                  conn: sqlite3.Connection) -> list[PipelineSection]:
    """Execute independent sections in parallel across different nodes."""
    results = []

    def _exec(section):
        return execute_section(section, context, conn)

    with ThreadPoolExecutor(max_workers=min(len(sections), 4)) as pool:
        futures = {pool.submit(_exec, s): s for s in sections}
        try:
            for f in as_completed(futures, timeout=180):
                try:
                    results.append(f.result())
                except Exception as e:
                    section = futures[f]
                    section.status = "failed"
                    section.response = str(e)[:200]
                    results.append(section)
        except TimeoutError:
            for f, section in futures.items():
                if not f.done():
                    section.status = "failed"
                    section.response = "Parallel timeout"
                    results.append(section)

    return sorted(results, key=lambda s: s.idx)


# ── Circulating Executor ────────────────────────────────────────────────

def _build_context(sections: list[PipelineSection], up_to: int) -> str:
    """Build context from completed sections for the next section."""
    parts = []
    for s in sections[:up_to]:
        if s.status in ("completed", "cached") and s.response:
            parts.append(f"[Step {s.idx + 1} - {s.section_type.value}]:\n{s.response[:500]}")
    return "\n\n".join(parts)


def execute_pipeline(pipeline: Pipeline, conn: sqlite3.Connection,
                     parallel_independent: bool = True) -> Pipeline:
    """
    Execute all sections of a pipeline, circulating through the cluster.

    Sections execute sequentially by default (each builds on previous context).
    Independent sections (same idx group) can run in parallel.
    Results are saved to DB after each section completes.
    """
    pipeline.status = "running"
    _save_pipeline(conn, pipeline)

    log.info("=== Pipeline '%s' — %d sections ===", pipeline.name, len(pipeline.sections))

    for section in pipeline.sections:
        # Build context from all completed sections so far
        context = _build_context(pipeline.sections, section.idx)

        # Execute section — collaborative zero-timeout engine (chunks + round-robin)
        section = collaborative_execute_section(section, context, conn)

        # Persist section result immediately
        _save_section(conn, pipeline.id, section)

        if section.status == "failed":
            log.warning("Section %d failed — attempting circulation repair", section.idx)
            # CIRCULATION: Try a different approach with a different node
            section = _circulate_repair(section, context, conn, pipeline.id)
            if section.status == "failed":
                log.error("Section %d unrecoverable — pipeline degraded", section.idx)
                # Don't abort — continue with what we have

        # Update pipeline progress
        completed = sum(1 for s in pipeline.sections if s.status in ("completed", "cached"))
        conn.execute(
            "UPDATE pipelines SET completed_sections = ?, updated_at = datetime('now') WHERE id = ?",
            (completed, pipeline.id)
        )
        conn.commit()

    # Assemble final result
    pipeline.result = _assemble_result(pipeline)
    pipeline.status = "completed" if any(
        s.status in ("completed", "cached") for s in pipeline.sections
    ) else "failed"
    _save_pipeline(conn, pipeline)

    log.info("=== Pipeline '%s' %s — %d/%d sections OK ===",
             pipeline.name, pipeline.status,
             sum(1 for s in pipeline.sections if s.status in ("completed", "cached")),
             len(pipeline.sections))

    return pipeline


def _circulate_repair(section: PipelineSection, context: str,
                      conn: sqlite3.Connection, pipeline_id: str) -> PipelineSection:
    """Circulate a failed section to alternative providers with a rephrased prompt."""
    # Rephrase the prompt to be simpler / shorter
    repair_prompt = f"Please answer concisely (max 200 words):\n{section.prompt}"
    if context:
        repair_prompt = f"Context:\n{context[:300]}\n\n{repair_prompt}"

    # Try ALL available providers (skip the one that already failed)
    for pid, provider in PROVIDERS.items():
        if pid == section.provider or not provider.is_available():
            continue
        start = time.time()
        try:
            response = query_provider(provider, repair_prompt)
            elapsed = (time.time() - start) * 1000
            if response:
                section.response = response
                section.provider = f"{pid}(repair)"
                section.latency_ms = elapsed
                section.status = "completed"
                cache_store(conn, section.prompt, response, pid, section.section_type.value)
                _save_section(conn, pipeline_id, section)
                log.info("  Section %d REPAIRED via %s (%.0fms)", section.idx, pid, elapsed)
                return section
        except Exception:
            continue

    return section


# ── Pipeline Persistence ────────────────────────────────────────────────

def _save_pipeline(conn: sqlite3.Connection, pipeline: Pipeline):
    """Save/update pipeline metadata to DB."""
    conn.execute("""
        INSERT OR REPLACE INTO pipelines (id, name, original_prompt, status,
            total_sections, completed_sections, result, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        pipeline.id, pipeline.name, pipeline.original_prompt[:1000],
        pipeline.status, len(pipeline.sections),
        sum(1 for s in pipeline.sections if s.status in ("completed", "cached")),
        pipeline.result[:5000] if pipeline.result else None,
    ))
    conn.commit()


def _save_section(conn: sqlite3.Connection, pipeline_id: str, section: PipelineSection):
    """Save/update a section result to DB."""
    # Check if exists
    existing = conn.execute(
        "SELECT id FROM pipeline_sections WHERE pipeline_id = ? AND section_idx = ?",
        (pipeline_id, section.idx)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE pipeline_sections SET response = ?, provider = ?, status = ?,
                latency_ms = ?, from_cache = ? WHERE id = ?
        """, (section.response[:3000], section.provider, section.status,
              section.latency_ms, int(section.from_cache), existing["id"]))
    else:
        conn.execute("""
            INSERT INTO pipeline_sections (pipeline_id, section_idx, section_type,
                prompt, response, provider, status, latency_ms, from_cache)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pipeline_id, section.idx, section.section_type.value,
              section.prompt[:1000], section.response[:3000], section.provider,
              section.status, section.latency_ms, int(section.from_cache)))
    conn.commit()


def _assemble_result(pipeline: Pipeline) -> str:
    """Assemble the final result from all completed sections."""
    parts = []
    for s in pipeline.sections:
        if s.status in ("completed", "cached") and s.response:
            src = "CACHE" if s.from_cache else s.provider
            parts.append(f"## {s.section_type.value.upper()} [{src}]\n{s.response}")
    return "\n\n---\n\n".join(parts)


# ── Pipeline Templates (Reuse) ─────────────────────────────────────────

def save_as_template(conn: sqlite3.Connection, pipeline: Pipeline):
    """Save a successful pipeline as a reusable template."""
    if pipeline.status != "completed":
        return

    section_types = json.dumps([
        {"type": s.section_type.value, "prompt_template": s.prompt}
        for s in pipeline.sections
    ])

    try:
        conn.execute("""
            INSERT OR REPLACE INTO pipeline_templates (name, pattern, section_types, description)
            VALUES (?, ?, ?, ?)
        """, (
            f"auto_{pipeline.id[:8]}",
            pipeline.original_prompt[:200],
            section_types,
            f"Auto-saved from pipeline {pipeline.id}",
        ))
        conn.commit()
        log.info("Saved pipeline as template '%s'", f"auto_{pipeline.id[:8]}")
    except sqlite3.Error as e:
        log.warning("Template save failed: %s", e)


# ── Resume Pipeline ─────────────────────────────────────────────────────

def resume_pipeline(conn: sqlite3.Connection, pipeline_id: str) -> Optional[Pipeline]:
    """Resume an incomplete pipeline from DB."""
    row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)).fetchone()
    if not row:
        log.error("Pipeline %s not found", pipeline_id)
        return None

    sections_rows = conn.execute(
        "SELECT * FROM pipeline_sections WHERE pipeline_id = ? ORDER BY section_idx",
        (pipeline_id,)
    ).fetchall()

    sections = []
    for sr in sections_rows:
        try:
            st = SectionType(sr["section_type"])
        except ValueError:
            st = SectionType.GENERAL
        sections.append(PipelineSection(
            idx=sr["section_idx"],
            section_type=st,
            prompt=sr["prompt"],
            response=sr["response"] or "",
            provider=sr["provider"] or "",
            status=sr["status"],
            latency_ms=sr["latency_ms"],
            from_cache=bool(sr["from_cache"]),
        ))

    pipeline = Pipeline(
        id=row["id"],
        name=row["name"],
        original_prompt=row["original_prompt"],
        sections=sections,
        status=row["status"],
        result=row["result"] or "",
    )

    # Re-execute only pending/failed sections
    pending = [s for s in pipeline.sections if s.status in ("pending", "failed")]
    if not pending:
        log.info("Pipeline %s already completed", pipeline_id)
        return pipeline

    log.info("Resuming pipeline %s — %d sections pending", pipeline_id, len(pending))
    return execute_pipeline(pipeline, conn)


# ── List Pipelines ──────────────────────────────────────────────────────

def list_pipelines(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """List recent pipelines with status."""
    rows = conn.execute("""
        SELECT id, name, status, total_sections, completed_sections,
               created_at, updated_at
        FROM pipelines ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def list_cache_stats(conn: sqlite3.Connection) -> dict:
    """Get cache statistics."""
    total = conn.execute("SELECT COUNT(*) as c FROM pipeline_cache").fetchone()["c"]
    hits = conn.execute("SELECT SUM(hits) as h FROM pipeline_cache").fetchone()["h"] or 0
    top = conn.execute(
        "SELECT category, COUNT(*) as c FROM pipeline_cache GROUP BY category ORDER BY c DESC LIMIT 5"
    ).fetchall()
    return {
        "total_entries": total,
        "total_hits": hits,
        "top_categories": {r["category"]: r["c"] for r in top},
    }


# ── Main Pipeline Entry Point ──────────────────────────────────────────

def _find_similar_pipeline(conn: sqlite3.Connection, prompt: str) -> Optional[Pipeline]:
    """Check if a similar pipeline already completed — reuse its result."""
    rows = conn.execute("""
        SELECT id, name, original_prompt, result, status
        FROM pipelines WHERE status = 'completed' AND result IS NOT NULL
        ORDER BY created_at DESC LIMIT 20
    """).fetchall()

    keywords = _extract_keywords(prompt)
    for row in rows:
        existing_kw = _extract_keywords(row["original_prompt"])
        if not existing_kw:
            continue
        overlap = len(keywords & existing_kw) / len(keywords | existing_kw)
        if overlap >= 0.45:
            log.info("REUSE pipeline '%s' (similarity=%.0f%%)", row["name"], overlap * 100)
            # Bump its template usage
            conn.execute(
                "UPDATE pipeline_templates SET usage_count = usage_count + 1 "
                "WHERE pattern LIKE ?", (f"%{row['original_prompt'][:50]}%",)
            )
            conn.commit()
            return Pipeline(
                id=row["id"], name=row["name"],
                original_prompt=row["original_prompt"],
                status="reused", result=row["result"],
            )
    return None


def run_pipeline(prompt: str, name: str = "", telegram: bool = True) -> Pipeline:
    """Full pipeline execution: decompose → execute → persist → notify."""
    conn = _init_db()

    # Phase 0: Check if a similar pipeline already completed — instant reuse
    existing = _find_similar_pipeline(conn, prompt)
    if existing:
        log.info("Pipeline REUSED from '%s' — skipping execution", existing.name)
        if telegram and existing.result:
            _send_pipeline_report(existing)
        conn.close()
        return existing

    # Create pipeline
    pipeline_id = str(uuid.uuid4())[:12]
    pipeline = Pipeline(
        id=pipeline_id,
        name=name or prompt[:50],
        original_prompt=prompt,
    )

    # Phase 1: Decompose
    log.info("Phase 1: Decomposing task...")
    pipeline.sections = decompose_task(prompt, conn)
    if not pipeline.sections:
        pipeline.status = "failed"
        pipeline.result = "Failed to decompose task"
        _save_pipeline(conn, pipeline)
        return pipeline

    _save_pipeline(conn, pipeline)
    for s in pipeline.sections:
        _save_section(conn, pipeline_id, s)

    # Phase 2: Execute (circulating)
    log.info("Phase 2: Executing %d sections...", len(pipeline.sections))
    pipeline = execute_pipeline(pipeline, conn)

    # Phase 3: Save as template for reuse
    if pipeline.status == "completed":
        save_as_template(conn, pipeline)

    # Phase 4: Notify
    if telegram and pipeline.result:
        _send_pipeline_report(pipeline)

    conn.close()
    return pipeline


def _send_pipeline_report(pipeline: Pipeline):
    """Send pipeline results to Telegram."""
    sections_summary = []
    for s in pipeline.sections:
        src = "CACHE" if s.from_cache else s.provider
        status_icon = "OK" if s.status in ("completed", "cached") else "FAIL"
        sections_summary.append(
            f"  {s.idx + 1}. [{s.section_type.value}] {status_icon} via {src} ({s.latency_ms:.0f}ms)"
        )

    msg = (
        f"PIPELINE {pipeline.status.upper()}: {pipeline.name}\n"
        f"Sections:\n" + "\n".join(sections_summary) + "\n\n"
        f"Result (truncated):\n{pipeline.result[:1500]}"
    )
    try:
        send_telegram(msg)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


# ── Daemon Mode (Continuous) ────────────────────────────────────────────

def daemon_loop(interval: int = 300):
    """Continuous loop: check for queued tasks, execute, persist."""
    conn = _init_db()
    log.info("Pipeline daemon started (interval=%ds)", interval)

    while True:
        # Check for pending pipelines to resume
        pending = conn.execute(
            "SELECT id FROM pipelines WHERE status IN ('pending', 'running') "
            "ORDER BY created_at ASC LIMIT 5"
        ).fetchall()

        for row in pending:
            try:
                resume_pipeline(conn, row["id"])
            except Exception as e:
                log.error("Daemon error on pipeline %s: %s", row["id"], e)

        time.sleep(interval)


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Pipeline Engine")
    parser.add_argument("--run", type=str, help="Run a new pipeline with this prompt")
    parser.add_argument("--resume", type=str, help="Resume pipeline by ID")
    parser.add_argument("--list", action="store_true", help="List recent pipelines")
    parser.add_argument("--cache-stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--reuse", type=str, help="Reuse a pipeline template")
    parser.add_argument("--circulate", type=str, help="Circulating multi-node writer for a prompt")
    parser.add_argument("--passes", type=int, default=5, help="Max circulation passes (default 5)")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram notification")
    parser.add_argument("--name", type=str, default="", help="Pipeline name")
    parser.add_argument("prompt", nargs="?", default="", help="Task prompt (with --reuse)")

    args = parser.parse_args()

    if args.run:
        pipeline = run_pipeline(args.run, name=args.name, telegram=not args.no_telegram)
        print(f"\nPipeline {pipeline.id} — {pipeline.status}")
        print(f"Sections: {sum(1 for s in pipeline.sections if s.status in ('completed', 'cached'))}/{len(pipeline.sections)}")
        if pipeline.result:
            print(f"\n{'='*60}\n{pipeline.result[:2000]}\n{'='*60}")

    elif args.resume:
        conn = _init_db()
        pipeline = resume_pipeline(conn, args.resume)
        if pipeline:
            print(f"Pipeline {pipeline.id} — {pipeline.status}")
        conn.close()

    elif args.list:
        conn = _init_db()
        pipelines = list_pipelines(conn)
        if not pipelines:
            print("No pipelines found.")
        for p in pipelines:
            print(f"  {p['id']}  {p['status']:10s}  {p['completed_sections']}/{p['total_sections']}  {p['name']}")
        conn.close()

    elif args.circulate:
        conn = _init_db()
        result = circulate_write(args.circulate, conn, max_passes=args.passes)
        if result:
            print(f"\n{'='*60}\n{result}\n{'='*60}")
            if not args.no_telegram:
                try:
                    send_telegram(f"CIRCULATE RESULT:\n{result[:2000]}")
                except Exception:
                    pass
        else:
            print("Circulation failed — no providers available")
        conn.close()

    elif args.cache_stats:
        conn = _init_db()
        stats = list_cache_stats(conn)
        print(f"Cache: {stats['total_entries']} entries, {stats['total_hits']} hits")
        for cat, count in stats["top_categories"].items():
            print(f"  {cat}: {count}")
        conn.close()

    elif args.daemon:
        daemon_loop()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
