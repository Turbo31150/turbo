"""SQL REST API routes for JARVIS Desktop (FastAPI port 9742).

Endpoints:
    POST /sql/query         — Execute SQL query
    GET  /sql/tables/{db}   — List tables
    GET  /sql/schema/{db}/{table} — Table schema
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ── Resolve turbo root for config import ──
import sys
_turbo_root = str(Path(__file__).resolve().parent.parent.parent)
if _turbo_root not in sys.path:
    sys.path.insert(0, _turbo_root)

from src.config import PATHS, config

sql_router = APIRouter(tags=["sql"])

# ── Database aliases ──
_TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_ALIASES: dict[str, Path] = {
    "etoile": PATHS.get("etoile_db", _TURBO_ROOT / "data" / "etoile.db"),
    "jarvis": PATHS.get("jarvis_db", _TURBO_ROOT / "data" / "jarvis.db"),
    "trading": config.db_trading,
    "predictions": config.db_predictions,
}

_SQL_ALLOWED = re.compile(r"^\s*(SELECT|PRAGMA\s+table_info)\b", re.IGNORECASE)
_SQL_DANGEROUS = re.compile(r"\b(DROP|CREATE|ALTER|ATTACH|DETACH|REINDEX|VACUUM|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
_SQL_BLOCKED_TABLES = re.compile(r"\bsqlite_(master|temp_master|sequence)\b", re.IGNORECASE)
_SQL_QUERY_TIMEOUT = 10  # seconds
_TABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _resolve_db(database: str) -> str:
    db_path = _DB_ALIASES.get(database.lower())
    if not db_path:
        raise HTTPException(404, f"Unknown database '{database}'. Available: {', '.join(_DB_ALIASES)}")
    path_str = str(db_path)
    if not Path(path_str).exists():
        raise HTTPException(404, f"Database '{database}' unavailable")
    return path_str


class SqlQueryRequest(BaseModel):
    database: str
    query: str
    params: list[Any] | None = None


def _exec_query(db_path: str, query: str, params: list) -> dict[str, Any]:
    """Execute read-only SQL query synchronously (run via asyncio.to_thread)."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        rows = [dict(r) for r in cur.fetchmany(1000)]
        truncated = cur.fetchone() is not None
        return {"rows": rows, "count": len(rows), "truncated": truncated}


def _list_tables(db_path: str) -> list[str]:
    """List tables synchronously (run via asyncio.to_thread)."""
    with sqlite3.connect(db_path) as conn:
        return [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]


def _get_schema(db_path: str, table: str) -> dict[str, Any] | None:
    """Get table schema synchronously (run via asyncio.to_thread)."""
    if not _TABLE_NAME.match(table):
        return None
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not row:
            return None
        columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])}
                   for r in conn.execute(f"PRAGMA table_info([{table}])").fetchall()]
        count = (conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone() or (0,))[0]
        return {"schema": row[0], "columns": columns, "row_count": count}


@sql_router.post("/query")
async def sql_query(req: SqlQueryRequest) -> dict[str, Any]:
    db_path = _resolve_db(req.database)
    query = req.query.strip()
    params = req.params or []
    if not _SQL_ALLOWED.match(query):
        raise HTTPException(403, "Only SELECT and PRAGMA table_info allowed (read-only)")
    if _SQL_DANGEROUS.search(query):
        raise HTTPException(403, "DDL statements (DROP, CREATE, ALTER, ATTACH, etc.) are forbidden")
    if _SQL_BLOCKED_TABLES.search(query):
        raise HTTPException(403, "Access to sqlite internal tables is forbidden")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_exec_query, db_path, query, params),
            timeout=_SQL_QUERY_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(408, "Query timed out (max 10s)")
    except sqlite3.Error as e:
        raise HTTPException(400, f"SQL error: {e}")


@sql_router.get("/tables/{database}")
async def sql_tables(database: str) -> dict[str, Any]:
    db_path = _resolve_db(database)
    tables = await asyncio.to_thread(_list_tables, db_path)
    return {"database": database, "tables": tables}


@sql_router.get("/schema/{database}/{table}")
async def sql_schema(database: str, table: str) -> dict[str, Any]:
    if not _TABLE_NAME.match(table):
        raise HTTPException(400, f"Invalid table name: '{table}'")
    db_path = _resolve_db(database)
    result = await asyncio.to_thread(_get_schema, db_path, table)
    if result is None:
        raise HTTPException(404, f"Table '{table}' not found")
    return {"database": database, "table": table, **result}
