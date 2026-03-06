"""JARVIS Brain v2 — Autonomous learning, feedback loop, quality scoring.

v2 adds:
- SkillQuality: per-skill success_rate, avg_duration, user_satisfaction
- Temporal decay: unused skills lose confidence over time
- Skill composition: combine existing skills into pipelines
- Context-aware suggestions: time-of-day, GPU load, recent actions
- Feedback loop: record_feedback() updates skill quality scores

Flow:
1. Actions are logged (via skills.log_action)
2. Brain periodically analyzes patterns in action_history
3. When a repeated sequence is detected → suggest or auto-create a skill
4. Feedback from execution updates SkillQuality metrics
5. Decay cycle demotes unused skills, promotes successful ones
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("jarvis.brain")

from src.config import prepare_lmstudio_input, build_lmstudio_payload
from src.skills import (
    load_skills, add_skill, Skill, SkillStep,
    get_action_history, log_action,
)

BRAIN_FILE = Path(__file__).resolve().parent.parent / "data" / "brain_state.json"
QUALITY_FILE = Path(__file__).resolve().parent.parent / "data" / "skill_quality.json"

# Decay: halve confidence every 7 days of non-use
DECAY_HALF_LIFE_SECONDS = 7 * 24 * 3600


# ── Skill Quality Metrics ────────────────────────────────────────────────

@dataclass
class SkillQuality:
    """Per-skill quality metrics tracked via feedback loop."""
    skill_name: str
    executions: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0
    satisfaction_sum: float = 0  # sum of 0-1 ratings
    last_executed: float = 0
    last_feedback: float = 0
    confidence: float = 0.5  # ML confidence [0, 1]

    @property
    def success_rate(self) -> float:
        return self.successes / max(1, self.executions)

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / max(1, self.executions)

    @property
    def user_satisfaction(self) -> float:
        rated = self.successes + self.failures
        return self.satisfaction_sum / max(1, rated)

    @property
    def composite_score(self) -> float:
        """Weighted composite: 40% success + 30% satisfaction + 30% confidence."""
        return (
            0.4 * self.success_rate
            + 0.3 * self.user_satisfaction
            + 0.3 * self.confidence
        )

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "executions": self.executions,
            "successes": self.successes,
            "failures": self.failures,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "satisfaction_sum": round(self.satisfaction_sum, 3),
            "last_executed": self.last_executed,
            "confidence": round(self.confidence, 4),
            "success_rate": f"{self.success_rate:.1%}",
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "composite_score": round(self.composite_score, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> SkillQuality:
        return cls(
            skill_name=d["skill_name"],
            executions=d.get("executions", 0),
            successes=d.get("successes", 0),
            failures=d.get("failures", 0),
            total_duration_ms=d.get("total_duration_ms", 0),
            satisfaction_sum=d.get("satisfaction_sum", 0),
            last_executed=d.get("last_executed", 0),
            last_feedback=d.get("last_feedback", 0),
            confidence=d.get("confidence", 0.5),
        )


def _load_quality_db() -> dict[str, SkillQuality]:
    """Load skill quality metrics from disk."""
    if QUALITY_FILE.exists():
        try:
            data = json.loads(QUALITY_FILE.read_text(encoding="utf-8"))
            return {k: SkillQuality.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return {}


def _save_quality_db(db: dict[str, SkillQuality]):
    """Save skill quality metrics to disk."""
    QUALITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v.to_dict() for k, v in db.items()}
    QUALITY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_feedback(
    skill_name: str,
    success: bool,
    duration_ms: float = 0,
    satisfaction: float = 0.7,
):
    """Record execution feedback for a skill (called after each execution)."""
    db = _load_quality_db()
    q = db.get(skill_name, SkillQuality(skill_name=skill_name))

    q.executions += 1
    if success:
        q.successes += 1
    else:
        q.failures += 1
    q.total_duration_ms += duration_ms
    q.satisfaction_sum += satisfaction
    q.last_executed = time.time()
    q.last_feedback = time.time()

    # Update ML confidence via exponential moving average
    outcome = 1.0 if success else 0.0
    alpha = 0.2  # learning rate
    q.confidence = q.confidence * (1 - alpha) + outcome * alpha

    db[skill_name] = q
    _save_quality_db(db)
    logger.debug("Feedback recorded: %s success=%s conf=%.3f", skill_name, success, q.confidence)


def apply_decay():
    """
    Apply temporal decay to all skill confidence scores.

    Skills unused for a long time lose confidence exponentially.
    """
    db = _load_quality_db()
    now = time.time()
    decayed = 0

    for name, q in db.items():
        if q.last_executed <= 0:
            continue
        age = now - q.last_executed
        if age > 3600:  # Only decay after 1 hour of non-use
            decay_factor = math.exp(-math.log(2) * age / DECAY_HALF_LIFE_SECONDS)
            new_conf = max(0.05, q.confidence * decay_factor)
            if abs(new_conf - q.confidence) > 0.001:
                q.confidence = new_conf
                decayed += 1

    if decayed > 0:
        _save_quality_db(db)
        logger.info("Decay applied to %d skills", decayed)
    return decayed


def get_skill_rankings(top_n: int = 10) -> list[dict]:
    """Get skills ranked by composite score."""
    db = _load_quality_db()
    ranked = sorted(db.values(), key=lambda q: -q.composite_score)
    return [q.to_dict() for q in ranked[:top_n]]


def get_skill_quality(skill_name: str) -> dict | None:
    """Get quality metrics for a specific skill."""
    db = _load_quality_db()
    q = db.get(skill_name)
    if q is not None:
        return q.to_dict()
    return None


# ── Context-Aware Suggestions ────────────────────────────────────────────

def suggest_contextual_skills(max_suggestions: int = 3) -> list[dict]:
    """Suggest skills based on current context (time, recent actions, GPU load)."""
    hour = time.localtime().tm_hour
    suggestions = []

    # Time-based suggestions
    if 6 <= hour <= 9:
        suggestions.append({
            "reason": "morning_routine",
            "skills": ["status", "gpu", "trading_scan"],
            "label": "Routine matinale: cluster status + GPU + trading scan",
        })
    elif 22 <= hour or hour <= 2:
        suggestions.append({
            "reason": "night_maintenance",
            "skills": ["audit", "cache_cleanup", "backup"],
            "label": "Maintenance nocturne: audit + cache + backup",
        })

    # Recent action patterns
    history = get_action_history(limit=10)
    recent_tools = [h.get("action", "").split(":")[0] for h in history if h.get("action")]

    if "trading" in " ".join(recent_tools).lower():
        suggestions.append({
            "reason": "trading_context",
            "skills": ["positions", "signals", "trading_feedback"],
            "label": "Contexte trading: positions + signaux + feedback",
        })

    if any("error" in t.lower() or "fail" in t.lower() for t in recent_tools):
        suggestions.append({
            "reason": "error_context",
            "skills": ["heal_cluster", "breakers", "audit"],
            "label": "Erreurs detectees: heal + breakers + audit",
        })

    # GPU load suggestion
    try:
        from src.cluster_startup import check_thermal_status
        thermal = check_thermal_status()
        if thermal.get("status") == "warning":
            suggestions.append({
                "reason": "thermal_warning",
                "skills": ["gpu_status", "thermal_monitor"],
                "label": f"GPU chaud ({thermal.get('max_temp', '?')}C): monitoring recommande",
            })
    except (ImportError, OSError):
        pass

    return suggestions[:max_suggestions]


# ── Skill Composition ────────────────────────────────────────────────────

def compose_skills(
    name: str,
    skill_names: list[str],
    triggers: list[str] | None = None,
    description: str = "",
) -> Skill | None:
    """Compose multiple existing skills into a new pipeline skill."""
    existing = {s.name: s for s in load_skills()}
    steps = []

    for sname in skill_names:
        skill = existing.get(sname)
        if not skill:
            logger.warning("compose_skills: skill %r not found", sname)
            return None
        steps.extend(skill.steps)

    if not steps:
        return None

    composed = Skill(
        name=name,
        description=description or f"Pipeline compose: {' → '.join(skill_names)}",
        triggers=triggers or [f"pipeline {name}", f"lance {name}"],
        steps=steps,
        category="composed",
        created_at=time.time(),
    )
    add_skill(composed)
    log_action(f"brain:compose:{name}", f"Composed from {skill_names}", True)
    return composed


@dataclass
class PatternMatch:
    """A detected repeated action pattern."""
    actions: list[str]
    count: int
    confidence: float
    suggested_name: str
    suggested_triggers: list[str]


def _load_brain_state() -> dict:
    """Load persistent brain state."""
    BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if BRAIN_FILE.exists():
        try:
            return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("brain_state load failed: %s", exc)
    return {
        "patterns_detected": [],
        "skills_created": [],
        "last_analysis": 0,
        "total_analyses": 0,
        "rejected_patterns": [],
    }


def _save_brain_state(state: dict):
    """Save brain state."""
    BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRAIN_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_patterns(min_repeat: int = 2, window: int = 50) -> list[PatternMatch]:
    """Detect repeated action sequences in history.

    Scans the action history for sequences of 2-5 actions that appear
    at least min_repeat times within the last `window` actions.
    """
    history = get_action_history(limit=window)
    if len(history) < 4:
        return []

    actions = [h["action"] for h in history]
    patterns: list[PatternMatch] = []

    # Check for sequences of length 2..5
    for seq_len in range(2, min(6, len(actions))):
        seq_counter: Counter = Counter()
        for i in range(len(actions) - seq_len + 1):
            seq = tuple(actions[i:i + seq_len])
            seq_counter[seq] += 1

        for seq, count in seq_counter.most_common(5):
            if count >= min_repeat:
                # Don't suggest if already a skill
                existing = load_skills()
                seq_tools = [_extract_tool(a) for a in seq]
                already_exists = any(
                    [s.tool for s in sk.steps] == seq_tools
                    for sk in existing
                )
                if already_exists:
                    continue

                name = _generate_skill_name(seq)
                triggers = _generate_triggers(seq)
                confidence = min(1.0, count / 5)  # 5 repeats = 100% confidence

                patterns.append(PatternMatch(
                    actions=list(seq),
                    count=count,
                    confidence=confidence,
                    suggested_name=name,
                    suggested_triggers=triggers,
                ))

    # Sort by confidence (highest first), deduplicate
    patterns.sort(key=lambda p: (-p.confidence, -len(p.actions)))
    return patterns[:5]


def _extract_tool(action_str: str) -> str:
    """Extract tool name from action string like 'tool_name({args})'."""
    if "(" in action_str:
        return action_str.split("(")[0]
    if ":" in action_str:
        return action_str.split(":")[0]
    return action_str


def _generate_skill_name(seq: tuple[str, ...]) -> str:
    """Generate a skill name from an action sequence."""
    tools = [_extract_tool(a) for a in seq]
    # Use first and last tool for naming
    if len(tools) == 2:
        return f"auto_{tools[0]}_{tools[1]}"
    return f"auto_{'_'.join(tools[:2])}_x{len(tools)}"


def _generate_triggers(seq: tuple[str, ...]) -> list[str]:
    """Generate voice triggers for a detected pattern."""
    tools = [_extract_tool(a) for a in seq]
    name = " et ".join(tools[:3])
    return [
        name,
        f"lance {tools[0]} puis {tools[-1]}",
        f"pipeline {tools[0]}",
    ]


def auto_create_skill(pattern: PatternMatch) -> Skill:
    """Create a skill from a detected pattern."""
    steps = []
    for action in pattern.actions:
        tool = _extract_tool(action)
        steps.append(tool)
        # Try to extract args from the action string
        args = {}
        if "(" in action and action.endswith(")"):
            try:
                args_str = action[action.index("(") + 1:-1]
                if args_str:
                    args = json.loads(args_str) if args_str.startswith("{") else {}
            except (json.JSONDecodeError, ValueError) as exc:
                logger.debug("Auto-step arg parsing failed for %r: %s", action, exc)
        steps.append(SkillStep(tool=tool, args=args, description=f"Auto: {tool}"))

    skill = Skill(
        name=pattern.suggested_name,
        description=f"Skill auto-appris ({pattern.count}x detecte). Actions: {', '.join(pattern.actions[:3])}",
        triggers=pattern.suggested_triggers,
        steps=steps,
        category="auto_learned",
        created_at=time.time(),
    )
    add_skill(skill)

    # Record in brain state
    state = _load_brain_state()
    state["skills_created"] = state.get("skills_created", [])[-99:] + [{
        "name": skill.name,
        "pattern": pattern.actions,
        "count": pattern.count,
        "confidence": pattern.confidence,
        "timestamp": time.time(),
    }]
    state["total_analyses"] += 1
    _save_brain_state(state)

    log_action(f"brain:create_skill:{skill.name}", f"Auto-created from {pattern.count}x pattern", True)

    # Emit event_bus notification
    try:
        from src.event_bus import event_bus
        event_bus.emit_sync("brain.skill_created", {
            "name": skill.name,
            "triggers": pattern.suggested_triggers,
            "confidence": pattern.confidence,
            "source": "pattern_detection",
        })
    except Exception:
        pass

    return skill


def analyze_and_learn(auto_create: bool = False, min_confidence: float = 0.6) -> dict:
    """Main brain analysis: detect patterns and optionally auto-create skills.

    Returns analysis report dict.
    """
    state = _load_brain_state()
    patterns = detect_patterns()

    report = {
        "patterns_found": len(patterns),
        "patterns": [],
        "skills_created": [],
        "total_skills": len(load_skills()),
        "history_size": len(get_action_history(limit=500)),
    }

    for p in patterns:
        p_info = {
            "actions": p.actions,
            "count": p.count,
            "confidence": p.confidence,
            "suggested_name": p.suggested_name,
        }
        report["patterns"].append(p_info)

        # Auto-create if confidence is high enough
        if auto_create and p.confidence >= min_confidence:
            # Check if pattern was previously rejected
            rejected = state.get("rejected_patterns", [])
            if p.suggested_name in rejected:
                continue

            skill = auto_create_skill(p)
            report["skills_created"].append(skill.name)

    state["last_analysis"] = time.time()
    state["total_analyses"] = state.get("total_analyses", 0) + 1
    state["patterns_detected"] = [
        {"name": p.suggested_name, "count": p.count, "confidence": p.confidence}
        for p in patterns
    ]
    _save_brain_state(state)

    return report


def reject_pattern(name: str):
    """Mark a pattern as rejected (won't auto-create)."""
    state = _load_brain_state()
    rejected = state.get("rejected_patterns", [])
    if name not in rejected:
        rejected.append(name)
        state["rejected_patterns"] = rejected
        _save_brain_state(state)
        rejected.append(name)
        state["rejected_patterns"] = rejected[-200:]
    _save_brain_state(state)


def get_brain_status() -> dict:
    """Get brain status for dashboard/voice report."""
    state = _load_brain_state()
    skills = load_skills()
    history = get_action_history(limit=500)

    auto_skills = [s for s in skills if s.category == "auto_learned"]
    custom_skills = [s for s in skills if s.category == "custom"]
    composed_skills = [s for s in skills if s.category == "composed"]
    default_skills = [s for s in skills if s.category not in ("auto_learned", "custom", "composed")]

    # Quality metrics summary
    quality_db = _load_quality_db()
    top_skills = get_skill_rankings(5)
    avg_confidence = sum(q.confidence for q in quality_db.values()) / max(1, len(quality_db))
    total_executions = sum(q.executions for q in quality_db.values())

    return {
        "total_skills": len(skills),
        "auto_learned": len(auto_skills),
        "custom": len(custom_skills),
        "composed": len(composed_skills),
        "default": len(default_skills),
        "total_actions": len(history),
        "total_analyses": state.get("total_analyses", 0),
        "last_analysis": state.get("last_analysis", 0),
        "patterns_detected": state.get("patterns_detected", []),
        "rejected_patterns": len(state.get("rejected_patterns", [])),
        "quality": {
            "tracked_skills": len(quality_db),
            "total_executions": total_executions,
            "avg_confidence": round(avg_confidence, 3),
            "top_skills": top_skills,
        },
        "suggestions": suggest_contextual_skills(),
    }


async def cluster_suggest_skill(context: str, node_url: str = "") -> dict | None:
    """Ask the LM Studio cluster for skill suggestions based on context.

    Uses M1 (deep analysis) for best results.
    """
    import httpx

    prompt = (
        "Tu es JARVIS, un assistant IA autonome. "
        f"Contexte actuel: {context}\n\n"
        "Suggere UN nouveau skill (pipeline d'actions) utile. "
        "Reponds en JSON strict:\n"
        '{"name": "...", "description": "...", "triggers": ["...", "..."], '
        '"steps": [{"tool": "...", "args": {}, "description": "..."}]}\n\n'
        "Outils disponibles: system_info, gpu_info, lm_cluster_status, lm_query, "
        "list_processes, kill_process, open_app, close_app, volume_up, volume_down, "
        "trading_status, trading_pending_signals, consensus, screenshot, "
        "list_folder, read_text_file, notify, speak.\n\n"
        "Reponds UNIQUEMENT avec le JSON, rien d'autre."
    )

    try:
        from src.config import config
        if not node_url:
            m1 = config.get_node("M1")
            node_url = m1.url if m1 else "http://10.5.0.2:1234"
        model = "qwen/qwen3-8b"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{node_url}/api/v1/chat",
                json=build_lmstudio_payload(
                    model, prepare_lmstudio_input(prompt, "M1", model),
                    max_output_tokens=512,
                ),
            )
            resp.raise_for_status()
            from src.tools import extract_lms_output
            raw_body = resp.json()
            logger.debug("cluster_suggest_skill raw response: %.300s", raw_body)
            text = extract_lms_output(raw_body).strip()

            # Extract JSON from response (may have markdown code blocks)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            return data
    except httpx.ConnectError as e:
        logger.warning("cluster_suggest_skill: Connexion impossible a %s - %s", node_url, e)
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("cluster_suggest_skill: Erreur parsing JSON - %s", e)
        return None
    except (httpx.HTTPError, OSError, ValueError) as e:
        logger.warning("cluster_suggest_skill: Erreur inattendue - %s: %s", type(e).__name__, e)
        return None


def format_brain_report() -> str:
    """Format brain status for voice output."""
    status = get_brain_status()
    lines = [
        f"Cerveau JARVIS v2: {status['total_skills']} skills total",
        f"  Auto-appris: {status['auto_learned']} | Composes: {status['composed']}",
        f"  Custom: {status['custom']} | Par defaut: {status['default']}",
        f"  Actions loguees: {status['total_actions']}",
        f"  Analyses effectuees: {status['total_analyses']}",
    ]

    # Quality metrics
    q = status.get("quality", {})
    if q.get("tracked_skills"):
        lines.append(f"  Qualite: {q['tracked_skills']} skills suivis, "
                     f"{q['total_executions']} executions, "
                     f"confiance moy={q['avg_confidence']:.1%}")
        if q.get("top_skills"):
            lines.append("  Top skills:")
            for s in q["top_skills"][:3]:
                lines.append(f"    - {s['skill_name']}: score={s['composite_score']:.2f} "
                             f"({s['success_rate']} succes)")

    if status["patterns_detected"]:
        lines.append("  Patterns detectes:")
        for p in status["patterns_detected"][:3]:
            lines.append(f"    - {p['name']} ({p['count']}x, conf={p['confidence']:.0%})")

    # Context suggestions
    suggestions = status.get("suggestions", [])
    if suggestions:
        lines.append("  Suggestions contextuelles:")
        for s in suggestions:
            lines.append(f"    → {s['label']}")

    return "\n".join(lines)
