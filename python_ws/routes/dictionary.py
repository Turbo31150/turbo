"""Dictionary route — CRUD + search for commands, pipelines, domino chains from code + etoile.db."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.dictionary")

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "etoile.db"

# Allowed action_types for validation
_VALID_ACTION_TYPES = {
    "powershell", "curl", "python", "pipeline", "condition",
    "system", "media", "browser", "voice", "shortcut", "script",
}

# Allowed categories — loaded dynamically from DB + fallback
_VALID_CATEGORIES_FALLBACK = {
    "system", "media", "navigation", "trading", "dev", "ia",
    "communication", "productivity", "entertainment", "accessibility",
    "fichiers", "daily", "cluster", "voice", "custom",
}
_valid_categories_cache: set | None = None


def _get_valid_categories() -> set:
    """Load categories from DB (cached). Any existing category is valid + custom always allowed."""
    global _valid_categories_cache
    if _valid_categories_cache is not None:
        return _valid_categories_cache
    try:
        db = _db_conn()
        rows = db.execute("SELECT DISTINCT category FROM pipeline_dictionary WHERE category IS NOT NULL").fetchall()
        db.close()
        cats = {r[0] for r in rows if r[0]}
        cats.add("custom")
        _valid_categories_cache = cats
        return cats
    except Exception:
        return _VALID_CATEGORIES_FALLBACK


def _invalidate_categories_cache():
    """Clear cache after add/edit/delete."""
    global _valid_categories_cache
    _valid_categories_cache = None


def _db_conn() -> sqlite3.Connection:
    """Open a connection with row_factory set."""
    db = sqlite3.connect(str(_DB_PATH))
    db.row_factory = sqlite3.Row
    return db


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

    # ── CRUD: add_command ──
    if action == "add_command":
        name = (payload.get("name") or "").strip()
        category = (payload.get("category") or "").strip().lower()
        triggers = payload.get("triggers") or []
        action_type = (payload.get("action_type") or "pipeline").strip().lower()
        description = (payload.get("description") or "").strip()
        confirm = bool(payload.get("confirm", False))
        steps = payload.get("steps") or ""

        if not name:
            return {"error": "name is required"}
        if category and category not in _get_valid_categories():
            return {"error": f"Invalid category: {category}. Valid: {sorted(_get_valid_categories())}"}
        if action_type not in _VALID_ACTION_TYPES:
            return {"error": f"Invalid action_type: {action_type}. Valid: {sorted(_VALID_ACTION_TYPES)}"}

        trigger_phrase = triggers[0] if triggers else name
        pipeline_id = name.lower().replace(" ", "_")

        try:
            db = _db_conn()
            # Check trigger uniqueness
            existing = db.execute(
                "SELECT id FROM pipeline_dictionary WHERE trigger_phrase = ?",
                (trigger_phrase,)
            ).fetchone()
            if existing:
                db.close()
                return {"error": f"Trigger '{trigger_phrase}' already exists (id={existing['id']})"}

            db.execute(
                "INSERT INTO pipeline_dictionary "
                "(pipeline_id, trigger_phrase, steps, category, action_type, agents_involved, avg_duration_ms, usage_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)",
                (pipeline_id, trigger_phrase, steps, category or "custom",
                 action_type, "", datetime.now().isoformat())
            )
            db.commit()
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            _invalidate_categories_cache()
            logger.info("Added command '%s' (id=%d)", name, new_id)
            return {"ok": True, "id": new_id, "pipeline_id": pipeline_id}
        except Exception as e:
            logger.error("add_command error: %s", e)
            return {"error": str(e)}

    # ── CRUD: edit_command ──
    if action == "edit_command":
        pipeline_id = payload.get("pipeline_id")
        record_id = payload.get("id")
        fields = payload.get("fields") or {}

        if not pipeline_id and not record_id:
            return {"error": "pipeline_id or id is required"}
        if not fields:
            return {"error": "fields dict is required"}

        # Validate fields
        allowed_fields = {"trigger_phrase", "steps", "category", "action_type", "agents_involved", "avg_duration_ms", "pipeline_id"}
        invalid = set(fields.keys()) - allowed_fields
        if invalid:
            return {"error": f"Invalid fields: {invalid}. Allowed: {sorted(allowed_fields)}"}

        if "category" in fields and fields["category"] not in _VALID_CATEGORIES:
            return {"error": f"Invalid category: {fields['category']}"}
        if "action_type" in fields and fields["action_type"] not in _VALID_ACTION_TYPES:
            return {"error": f"Invalid action_type: {fields['action_type']}"}

        try:
            db = _db_conn()
            set_parts = [f"{k} = ?" for k in fields]
            values = list(fields.values())
            if record_id:
                values.append(record_id)
                where = "id = ?"
            else:
                values.append(pipeline_id)
                where = "pipeline_id = ?"

            cursor = db.execute(
                f"UPDATE pipeline_dictionary SET {', '.join(set_parts)} WHERE {where}",
                values
            )
            db.commit()
            affected = cursor.rowcount
            db.close()
            if affected == 0:
                return {"error": "No matching record found"}
            _invalidate_categories_cache()
            logger.info("Edited command %s (%d rows)", pipeline_id or record_id, affected)
            return {"ok": True, "affected": affected}
        except Exception as e:
            logger.error("edit_command error: %s", e)
            return {"error": str(e)}

    # ── CRUD: delete_command ──
    if action == "delete_command":
        record_id = payload.get("pipeline_id") or payload.get("id")
        if not record_id:
            return {"error": "pipeline_id or id is required"}
        try:
            db = _db_conn()
            # Try by id first (numeric), fallback to pipeline_id (string)
            if isinstance(record_id, int) or (isinstance(record_id, str) and record_id.isdigit()):
                cursor = db.execute("DELETE FROM pipeline_dictionary WHERE id = ?", (int(record_id),))
            else:
                cursor = db.execute("DELETE FROM pipeline_dictionary WHERE pipeline_id = ?", (record_id,))
            db.commit()
            affected = cursor.rowcount
            db.close()
            if affected == 0:
                return {"error": f"No record found for '{record_id}'"}
            _invalidate_categories_cache()
            logger.info("Deleted command '%s' (%d rows)", record_id, affected)
            return {"ok": True, "deleted": affected}
        except Exception as e:
            logger.error("delete_command error: %s", e)
            return {"error": str(e)}

    # ── CRUD: add_chain ──
    if action == "add_chain":
        trigger_cmd = (payload.get("trigger_cmd") or "").strip()
        next_cmd = (payload.get("next_cmd") or "").strip()
        if not trigger_cmd or not next_cmd:
            return {"error": "trigger_cmd and next_cmd are required"}
        condition = payload.get("condition", "")
        delay_ms = int(payload.get("delay_ms", 0))
        auto = 1 if payload.get("auto", True) else 0
        description = (payload.get("description") or "").strip()

        try:
            db = _db_conn()
            db.execute(
                "INSERT INTO domino_chains (trigger_cmd, condition, next_cmd, delay_ms, auto, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (trigger_cmd, condition, next_cmd, delay_ms, auto, description)
            )
            db.commit()
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            logger.info("Added chain '%s' -> '%s' (id=%d)", trigger_cmd, next_cmd, new_id)
            return {"ok": True, "id": new_id}
        except Exception as e:
            logger.error("add_chain error: %s", e)
            return {"error": str(e)}

    # ── CRUD: delete_chain ──
    if action == "delete_chain":
        chain_id = payload.get("id")
        if not chain_id:
            return {"error": "id is required"}
        try:
            db = _db_conn()
            cursor = db.execute("DELETE FROM domino_chains WHERE id = ?", (int(chain_id),))
            db.commit()
            affected = cursor.rowcount
            db.close()
            if affected == 0:
                return {"error": f"No chain found with id={chain_id}"}
            logger.info("Deleted chain id=%s", chain_id)
            return {"ok": True, "deleted": affected}
        except Exception as e:
            logger.error("delete_chain error: %s", e)
            return {"error": str(e)}

    # ── CRUD: add_correction ──
    if action == "add_correction":
        wrong = (payload.get("wrong") or "").strip()
        correct = (payload.get("correct") or "").strip()
        if not wrong or not correct:
            return {"error": "wrong and correct are required"}
        category = (payload.get("category") or "general").strip()
        try:
            db = _db_conn()
            # Check if correction already exists
            existing = db.execute(
                "SELECT id FROM voice_corrections WHERE wrong = ?", (wrong,)
            ).fetchone()
            if existing:
                db.execute("UPDATE voice_corrections SET correct = ?, category = ? WHERE id = ?",
                           (correct, category, existing["id"]))
                db.commit()
                db.close()
                return {"ok": True, "id": existing["id"], "updated": True}
            db.execute(
                "INSERT INTO voice_corrections (wrong, correct, category, hit_count) VALUES (?, ?, ?, 0)",
                (wrong, correct, category)
            )
            db.commit()
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            logger.info("Added correction '%s' -> '%s' (id=%d)", wrong, correct, new_id)
            return {"ok": True, "id": new_id}
        except Exception as e:
            logger.error("add_correction error: %s", e)
            return {"error": str(e)}

    # ── CRUD: reload_dict ──
    if action == "reload_dict":
        try:
            _get_db_data.cache_clear() if hasattr(_get_db_data, 'cache_clear') else None
            _invalidate_categories_cache()
            data = _get_db_data()
            logger.info("Dictionary reloaded: %d dict, %d chains, %d corrections",
                        len(data["pipeline_dictionary"]), len(data["domino_chains"]),
                        len(data["voice_corrections"]))
            return {"ok": True, "stats": {
                "pipeline_dictionary": len(data["pipeline_dictionary"]),
                "domino_chains": len(data["domino_chains"]),
                "voice_corrections": len(data["voice_corrections"]),
            }}
        except Exception as e:
            return {"error": str(e)}

    # ── CRUD: get_stats ──
    if action == "get_stats":
        try:
            db = _db_conn()
            stats = {}
            for table in ["pipeline_dictionary", "domino_chains", "voice_corrections"]:
                stats[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            # Category distribution
            cats = db.execute(
                "SELECT category, COUNT(*) as cnt FROM pipeline_dictionary GROUP BY category ORDER BY cnt DESC"
            ).fetchall()
            stats["categories"] = {r["category"]: r["cnt"] for r in cats}
            db.close()
            return {"stats": stats}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown dictionary action: {action}"}
