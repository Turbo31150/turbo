"""JARVIS Brain — Autonomous learning and skill formation.

The Brain module analyzes usage patterns, detects repeated action sequences,
and automatically creates/improves skills. It also uses the LM Studio cluster
to generate skill suggestions based on context.

Flow:
1. Actions are logged (via skills.log_action)
2. Brain periodically analyzes patterns in action_history
3. When a repeated sequence is detected → suggest or auto-create a skill
4. LM Studio cluster can be queried for skill optimization
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.skills import (
    load_skills, add_skill, Skill, SkillStep,
    get_action_history, log_action, SKILLS_FILE,
)

BRAIN_FILE = Path(__file__).resolve().parent.parent / "data" / "brain_state.json"


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
        except Exception:
            pass
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
        # Try to extract args from the action string
        args = {}
        if "(" in action and action.endswith(")"):
            try:
                args_str = action[action.index("(") + 1:-1]
                if args_str:
                    args = json.loads(args_str) if args_str.startswith("{") else {}
            except (json.JSONDecodeError, ValueError):
                pass
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
    state["skills_created"].append({
        "name": skill.name,
        "pattern": pattern.actions,
        "count": pattern.count,
        "confidence": pattern.confidence,
        "timestamp": time.time(),
    })
    state["total_analyses"] += 1
    _save_brain_state(state)

    log_action(f"brain:create_skill:{skill.name}", f"Auto-created from {pattern.count}x pattern", True)
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
    if name not in state.get("rejected_patterns", []):
        state.setdefault("rejected_patterns", []).append(name)
    _save_brain_state(state)


def get_brain_status() -> dict:
    """Get brain status for dashboard/voice report."""
    state = _load_brain_state()
    skills = load_skills()
    history = get_action_history(limit=500)

    auto_skills = [s for s in skills if s.category == "auto_learned"]
    custom_skills = [s for s in skills if s.category == "custom"]
    default_skills = [s for s in skills if s.category not in ("auto_learned", "custom")]

    return {
        "total_skills": len(skills),
        "auto_learned": len(auto_skills),
        "custom": len(custom_skills),
        "default": len(default_skills),
        "total_actions": len(history),
        "total_analyses": state.get("total_analyses", 0),
        "last_analysis": state.get("last_analysis", 0),
        "patterns_detected": state.get("patterns_detected", []),
        "rejected_patterns": len(state.get("rejected_patterns", [])),
    }


async def cluster_suggest_skill(context: str, node_url: str = "http://10.5.0.2:1234") -> dict | None:
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
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{node_url}/api/v1/chat",
                json={
                    "model": "qwen/qwen3-30b-a3b-2507",
                    "input": prompt,
                    "temperature": 0.3,
                    "max_output_tokens": 512,
                    "stream": False,
                    "store": False,
                },
            )
            resp.raise_for_status()
            text = resp.json()["output"][0]["content"].strip()

            # Extract JSON from response (may have markdown code blocks)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            return data
    except httpx.ConnectError as e:
        # Cluster unreachable — log for debugging
        import logging
        logging.warning(f"cluster_suggest_skill: Connexion impossible a {node_url} - {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        import logging
        logging.warning(f"cluster_suggest_skill: Erreur parsing JSON - {e}")
        return None
    except Exception as e:
        import logging
        logging.warning(f"cluster_suggest_skill: Erreur inattendue - {type(e).__name__}: {e}")
        return None


def format_brain_report() -> str:
    """Format brain status for voice output."""
    status = get_brain_status()
    lines = [
        f"Cerveau JARVIS: {status['total_skills']} skills total",
        f"  Auto-appris: {status['auto_learned']}",
        f"  Custom: {status['custom']}",
        f"  Par defaut: {status['default']}",
        f"  Actions loguees: {status['total_actions']}",
        f"  Analyses effectuees: {status['total_analyses']}",
    ]
    if status["patterns_detected"]:
        lines.append("  Patterns detectes:")
        for p in status["patterns_detected"][:3]:
            lines.append(f"    - {p['name']} ({p['count']}x, conf={p['confidence']:.0%})")
    return "\n".join(lines)
