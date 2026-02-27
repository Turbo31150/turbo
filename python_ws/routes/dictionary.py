"""Dictionary route — Serves all commands, pipelines, domino chains from code + etoile.db."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.dictionary")

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "etoile.db"


def _get_all_commands() -> list[dict]:
    """Return all JarvisCommands as dicts."""
    try:
        from src.commands import COMMANDS
        return [
            {
                "name": c.name,
                "category": c.category,
                "triggers": c.triggers[:5],
                "action_type": c.action_type,
                "description": c.description[:100],
                "confirm": c.confirm,
            }
            for c in COMMANDS
        ]
    except Exception as e:
        logger.warning("Commands unavailable: %s", e)
        return []


def _get_all_pipelines() -> list[dict]:
    """Return all DominoPipelines as dicts."""
    try:
        from src.domino_pipelines import DOMINO_PIPELINES
        return [
            {
                "id": p.id,
                "category": p.category,
                "description": p.description,
                "trigger_vocal": p.trigger_vocal,
                "steps": len(p.steps),
                "priority": p.priority,
            }
            for p in DOMINO_PIPELINES
        ]
    except Exception as e:
        logger.warning("Pipelines unavailable: %s", e)
        return []


def _get_db_data() -> dict[str, Any]:
    """Return pipeline_dictionary, domino_chains, voice_corrections from etoile.db."""
    result: dict[str, Any] = {
        "pipeline_dictionary": [],
        "domino_chains": [],
        "voice_corrections": [],
    }
    if not _DB_PATH.exists():
        return result
    try:
        db = sqlite3.connect(str(_DB_PATH))
        db.row_factory = sqlite3.Row

        # pipeline_dictionary — truncate steps to 100 chars
        rows = db.execute(
            "SELECT id, pipeline_id, trigger_phrase, "
            "SUBSTR(steps, 1, 100) AS steps, category, action_type, "
            "agents_involved, avg_duration_ms FROM pipeline_dictionary"
        ).fetchall()
        result["pipeline_dictionary"] = [dict(r) for r in rows]

        # domino_chains
        rows = db.execute(
            "SELECT id, trigger_cmd, condition, next_cmd, delay_ms, auto, "
            "SUBSTR(description, 1, 80) AS description "
            "FROM domino_chains"
        ).fetchall()
        result["domino_chains"] = [dict(r) for r in rows]

        # voice_corrections — top 500 by hit_count
        rows = db.execute(
            "SELECT id, wrong, correct, category, hit_count "
            "FROM voice_corrections ORDER BY hit_count DESC LIMIT 500"
        ).fetchall()
        result["voice_corrections"] = [dict(r) for r in rows]

        db.close()
    except Exception as e:
        logger.warning("etoile.db read error: %s", e)
    return result


async def handle_dictionary_request(action: str, payload: dict | None) -> dict[str, Any]:
    """Handle dictionary channel requests."""
    payload = payload or {}

    if action == "get_all":
        commands = _get_all_commands()
        pipelines = _get_all_pipelines()
        db = _get_db_data()
        return {
            "commands": commands,
            "pipelines": pipelines,
            "pipeline_dictionary": db["pipeline_dictionary"],
            "domino_chains": db["domino_chains"],
            "voice_corrections": db["voice_corrections"],
            "stats": {
                "commands": len(commands),
                "pipelines": len(pipelines),
                "pipeline_dictionary": len(db["pipeline_dictionary"]),
                "domino_chains": len(db["domino_chains"]),
                "voice_corrections": len(db["voice_corrections"]),
            },
        }

    if action == "get_commands":
        category = payload.get("category")
        commands = _get_all_commands()
        if category:
            commands = [c for c in commands if c["category"] == category]
        return {"commands": commands, "total": len(commands)}

    if action == "get_pipelines":
        return {"pipelines": _get_all_pipelines()}

    if action == "get_chains":
        return {"domino_chains": _get_db_data()["domino_chains"]}

    if action == "get_corrections":
        return {"voice_corrections": _get_db_data()["voice_corrections"]}

    if action == "search":
        query = (payload.get("query") or "").lower().strip()
        if not query:
            return {"error": "Empty query"}
        limit = payload.get("limit", 50)

        # Search commands
        commands = _get_all_commands()
        matched_cmds = []
        for c in commands:
            score = 0
            if query in c["name"]:
                score += 3
            if query in c["description"].lower():
                score += 2
            if any(query in t.lower() for t in c["triggers"]):
                score += 4
            if score > 0:
                matched_cmds.append({**c, "_score": score})
        matched_cmds.sort(key=lambda x: -x["_score"])

        # Search pipelines
        pipelines = _get_all_pipelines()
        matched_pipes = []
        for p in pipelines:
            score = 0
            if query in p["id"]:
                score += 3
            if query in p["description"].lower():
                score += 2
            if any(query in t.lower() for t in p["trigger_vocal"]):
                score += 4
            if score > 0:
                matched_pipes.append({**p, "_score": score})
        matched_pipes.sort(key=lambda x: -x["_score"])

        # Search pipeline_dictionary
        db = _get_db_data()
        matched_dict = []
        for d in db["pipeline_dictionary"]:
            if query in (d.get("trigger_phrase") or "").lower():
                matched_dict.append(d)
        matched_dict = matched_dict[:limit]

        return {
            "commands": matched_cmds[:limit],
            "pipelines": matched_pipes[:limit],
            "pipeline_dictionary": matched_dict,
            "total": len(matched_cmds) + len(matched_pipes) + len(matched_dict),
        }

    return {"error": f"Unknown dictionary action: {action}"}
