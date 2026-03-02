"""SQL REST API routes for JARVIS Desktop (FastAPI port 9742).

Endpoints:
    POST /sql/query         — Execute SQL query
    GET  /sql/tables/{db}   — List tables
    GET  /sql/schema/{db}/{table} — Table schema
"""

from __future__ import annotations

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

_SQL_ALLOWED = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|EXPLAIN|PRAGMA\s+table_info)\b", re.IGNORECASE)
_TABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _resolve_db(database: str) -> str:
    db_path = _DB_ALIASES.get(database.lower())
    if not db_path:
        raise HTTPException(404, f"Unknown database '{database}'. Available: {', '.join(_DB_ALIASES)}")
    path_str = str(db_path)
    if not Path(path_str).exists():
        raise HTTPException(404, f"Database not found: {path_str}")
    return path_str


class SqlQueryRequest(BaseModel):
    database: str
    query: str
    params: list[Any] | None = None


@sql_router.post("/query")
async def sql_query(req: SqlQueryRequest):
    db_path = _resolve_db(req.database)
    query = req.query.strip()
    params = req.params or []
    if not _SQL_ALLOWED.match(query):
        raise HTTPException(403, "Only SELECT, INSERT, UPDATE, DELETE, WITH, EXPLAIN, PRAGMA table_info allowed")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            upper = query.upper().lstrip()
            if upper.startswith("SELECT") or upper.startswith("PRAGMA"):
                rows = [dict(r) for r in cur.fetchmany(1000)]
                truncated = cur.fetchone() is not None
                return {"rows": rows, "count": len(rows), "truncated": truncated}
            else:
                affected = cur.rowcount
                conn.commit()
                return {"affected": affected}
    except sqlite3.Error as e:
        raise HTTPException(400, f"SQL error: {e}")


@sql_router.get("/tables/{database}")
async def sql_tables(database: str):
    db_path = _resolve_db(database)
    with sqlite3.connect(db_path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    return {"database": database, "tables": tables}


@sql_router.get("/schema/{database}/{table}")
async def sql_schema(database: str, table: str):
    if not _TABLE_NAME.match(table):
        raise HTTPException(400, f"Invalid table name: '{table}'")
    db_path = _resolve_db(database)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not row:
            raise HTTPException(404, f"Table '{table}' not found")
        columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])}
                   for r in conn.execute(f"PRAGMA table_info([{table}])").fetchall()]
        count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    return {"database": database, "table": table, "schema": row[0], "columns": columns, "row_count": count}
