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
_DB_ALIASES: dict[str, Path] = {
    "etoile": PATHS.get("etoile_db", Path("F:/BUREAU/turbo/data/etoile.db")),
    "jarvis": PATHS.get("jarvis_db", Path("F:/BUREAU/turbo/data/jarvis.db")),
    "trading": config.db_trading,
    "predictions": config.db_predictions,
}

_SQL_FORBIDDEN = re.compile(r"\b(DROP|ALTER|TRUNCATE|ATTACH|DETACH|PRAGMA\s+(?!table_info))\b", re.IGNORECASE)


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
    if _SQL_FORBIDDEN.search(query):
        raise HTTPException(403, "Forbidden SQL operation (DROP/ALTER/TRUNCATE not allowed)")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        upper = query.upper().lstrip()
        if upper.startswith("SELECT") or upper.startswith("PRAGMA"):
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return {"rows": rows, "count": len(rows)}
        else:
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return {"affected": affected}
    except sqlite3.Error as e:
        raise HTTPException(400, f"SQL error: {e}")


@sql_router.get("/tables/{database}")
async def sql_tables(database: str):
    db_path = _resolve_db(database)
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    conn.close()
    return {"database": database, "tables": tables}


@sql_router.get("/schema/{database}/{table}")
async def sql_schema(database: str, table: str):
    db_path = _resolve_db(database)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"Table '{table}' not found")
    # Also get column info
    columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])}
               for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    conn.close()
    return {"database": database, "table": table, "schema": row[0], "columns": columns, "row_count": count}
