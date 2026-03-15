"""db_boot_validator.py — Validation SQL complete au demarrage JARVIS.

Verifie l'integrite de toutes les bases SQLite, precharge les corrections
vocales et commandes en cache memoire, et log un rapport de boot.

Usage:
    from src.db_boot_validator import validate_all_databases, get_voice_cache
    report = validate_all_databases()
    corrections = get_voice_cache()["corrections"]  # dict wrong->correct
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.db_boot_validator")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Toutes les bases a valider au boot
ALL_DATABASES: dict[str, Path] = {
    "jarvis": DATA_DIR / "jarvis.db",
    "etoile": DATA_DIR / "etoile.db",
    "sniper": DATA_DIR / "sniper.db",
    "scheduler": DATA_DIR / "scheduler.db",
    "pipeline": DATA_DIR / "pipeline.db",
    "conversations": DATA_DIR / "conversations.db",
    "agent_memory": DATA_DIR / "agent_memory.db",
    "task_queue": DATA_DIR / "task_queue.db",
    "sessions": DATA_DIR / "sessions.db",
    "workflows": DATA_DIR / "workflows.db",
    "conversation_checkpoints": DATA_DIR / "conversation_checkpoints.db",
    "browser_memory": DATA_DIR / "browser_memory.db",
    "audit_trail": DATA_DIR / "audit_trail.db",
    "decisions": DATA_DIR / "decisions.db",
    "auto_heal": DATA_DIR / "auto_heal.db",
    "log_analysis": DATA_DIR / "log_analysis.db",
    "devops_metrics": DATA_DIR / "devops_metrics.db",
    "rollback": DATA_DIR / "rollback.db",
    "process_gc": DATA_DIR / "process_gc.db",
}

# Cache memoire precharge au boot
_voice_cache: dict[str, Any] = {
    "corrections": {},       # wrong -> correct
    "commands_count": 0,
    "skills_count": 0,
    "pipelines": [],         # trigger_phrase list
    "loaded": False,
    "loaded_at": 0,
}


def _check_single_db(name: str, db_path: Path) -> dict[str, Any]:
    """Verifie une base SQLite: existence, integrite, tables, taille."""
    if not db_path.exists():
        return {"status": "missing", "path": str(db_path)}

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")

        # Integrite
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

        # Tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]

        # Indexes
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        index_names = [i[0] for i in indexes]

        # Taille et row counts
        total_rows = 0
        table_stats = {}
        for tname in table_names:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                total_rows += count
                table_stats[tname] = count
            except sqlite3.Error:
                table_stats[tname] = -1

        size_kb = round(db_path.stat().st_size / 1024, 1)
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        return {
            "status": "ok" if integrity == "ok" else "corrupted",
            "integrity": integrity,
            "tables": len(table_names),
            "table_names": table_names,
            "indexes": len(index_names),
            "total_rows": total_rows,
            "table_stats": table_stats,
            "size_kb": size_kb,
            "journal_mode": journal,
        }
    except sqlite3.Error as e:
        return {"status": "error", "error": str(e), "path": str(db_path)}


def _preload_voice_cache() -> dict[str, Any]:
    """Precharge les corrections vocales et stats depuis jarvis.db."""
    global _voice_cache
    cache = {
        "corrections": {},
        "commands_count": 0,
        "skills_count": 0,
        "pipelines": [],
        "loaded": False,
        "loaded_at": 0,
    }

    jarvis_db = ALL_DATABASES["jarvis"]
    if not jarvis_db.exists():
        return cache

    try:
        conn = sqlite3.connect(str(jarvis_db), timeout=5)
        conn.row_factory = sqlite3.Row

        # Corrections vocales → cache memoire
        try:
            rows = conn.execute("SELECT wrong, correct FROM voice_corrections").fetchall()
            for r in rows:
                cache["corrections"][r["wrong"]] = r["correct"]
            logger.info("Precharge %d corrections vocales", len(cache["corrections"]))
        except sqlite3.Error:
            pass

        # Compteurs commandes et skills
        try:
            cache["commands_count"] = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        except sqlite3.Error:
            pass
        try:
            cache["skills_count"] = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        except sqlite3.Error:
            pass

        conn.close()
    except sqlite3.Error as e:
        logger.warning("Erreur preload jarvis.db: %s", e)

    # Pipelines depuis etoile.db
    etoile_db = ALL_DATABASES["etoile"]
    if etoile_db.exists():
        try:
            conn = sqlite3.connect(str(etoile_db), timeout=5)
            try:
                rows = conn.execute("SELECT trigger_phrase FROM pipeline_dictionary").fetchall()
                cache["pipelines"] = [r[0] for r in rows]
            except sqlite3.Error:
                pass
            conn.close()
        except sqlite3.Error:
            pass

    cache["loaded"] = True
    cache["loaded_at"] = time.time()
    _voice_cache = cache
    return cache


def _log_boot_report(report: dict[str, Any]):
    """Log le rapport de boot dans etoile.db/boot_log."""
    etoile_db = ALL_DATABASES["etoile"]
    if not etoile_db.exists():
        return

    try:
        conn = sqlite3.connect(str(etoile_db), timeout=5)
        conn.execute("""CREATE TABLE IF NOT EXISTS boot_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            duration_s REAL,
            phases TEXT,
            report TEXT
        )""")
        conn.execute(
            "INSERT INTO boot_log (ts, duration_s, phases, report) VALUES (?, ?, ?, ?)",
            (time.time(), report.get("duration_ms", 0) / 1000,
             "db_validation", json.dumps(report, default=str)),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.debug("Impossible de logger le boot report: %s", e)


def validate_all_databases(repair: bool = True) -> dict[str, Any]:
    """Valide toutes les bases SQLite au demarrage.

    Args:
        repair: Si True, tente de reparer (WAL checkpoint, ANALYZE) les bases OK.

    Returns:
        Rapport complet: status par base, cache precharge, duree totale.
    """
    t0 = time.time()
    report: dict[str, Any] = {
        "ts": t0,
        "databases": {},
        "summary": {"total": 0, "ok": 0, "missing": 0, "corrupted": 0, "error": 0},
        "voice_cache": {},
    }

    logger.info("=" * 50)
    logger.info("DB BOOT VALIDATOR — Verification de %d bases", len(ALL_DATABASES))
    logger.info("=" * 50)

    for name, db_path in ALL_DATABASES.items():
        result = _check_single_db(name, db_path)
        report["databases"][name] = result
        report["summary"]["total"] += 1
        status = result.get("status", "error")

        if status == "ok":
            report["summary"]["ok"] += 1
            # Optionally repair/optimize
            if repair:
                try:
                    conn = sqlite3.connect(str(db_path), timeout=5)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.execute("ANALYZE")
                    conn.close()
                except sqlite3.Error:
                    pass
            logger.info("  [OK] %-25s %4d tables  %6.1f KB  %5d rows",
                        name, result.get("tables", 0), result.get("size_kb", 0),
                        result.get("total_rows", 0))
        elif status == "missing":
            report["summary"]["missing"] += 1
            logger.warning("  [--] %-25s MANQUANTE", name)
        elif status == "corrupted":
            report["summary"]["corrupted"] += 1
            logger.error("  [!!] %-25s CORROMPUE: %s", name, result.get("integrity"))
        else:
            report["summary"]["error"] += 1
            logger.error("  [ERR] %-25s %s", name, result.get("error"))

    # Precharger le cache vocal
    report["voice_cache"] = _preload_voice_cache()

    report["duration_ms"] = round((time.time() - t0) * 1000, 1)

    # Resultat global
    s = report["summary"]
    healthy = s["ok"] == s["total"] - s["missing"]  # OK si pas de corruption/erreur
    report["healthy"] = healthy

    logger.info("-" * 50)
    logger.info("DB BOOT: %d/%d OK, %d manquantes, %d corrompues, %d erreurs | %.0fms",
                s["ok"], s["total"], s["missing"], s["corrupted"], s["error"],
                report["duration_ms"])
    logger.info("CACHE VOCAL: %d corrections, %d commandes SQL, %d skills, %d pipelines",
                len(report["voice_cache"].get("corrections", {})),
                report["voice_cache"].get("commands_count", 0),
                report["voice_cache"].get("skills_count", 0),
                len(report["voice_cache"].get("pipelines", [])))
    logger.info("=" * 50)

    # Log dans etoile.db
    _log_boot_report(report)

    return report


def get_voice_cache() -> dict[str, Any]:
    """Retourne le cache vocal precharge. Precharge si pas encore fait."""
    if not _voice_cache.get("loaded"):
        _preload_voice_cache()
    return _voice_cache


def apply_voice_correction(text: str) -> str:
    """Applique les corrections vocales du cache au texte brut STT.

    Supporte les corrections de mots simples, bigrammes et trigrammes.
    """
    cache = get_voice_cache()
    corrections = cache.get("corrections", {})
    if not corrections:
        return text

    words = text.lower().split()
    corrected = False

    # Passe 1: trigrammes (3 mots)
    i = 0
    while i < len(words) - 2:
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
        if trigram in corrections:
            words[i] = corrections[trigram]
            words[i+1] = ""
            words[i+2] = ""
            corrected = True
            i += 3
        else:
            i += 1

    # Passe 2: bigrammes (2 mots)
    cleaned = [w for w in words if w]
    words = cleaned
    i = 0
    while i < len(words) - 1:
        bigram = f"{words[i]} {words[i+1]}"
        if bigram in corrections:
            words[i] = corrections[bigram]
            words[i+1] = ""
            corrected = True
            i += 2
        else:
            i += 1

    # Passe 3: mots simples
    cleaned = [w for w in words if w]
    words = cleaned
    for i, word in enumerate(words):
        if word in corrections:
            words[i] = corrections[word]
            corrected = True

    if corrected:
        return " ".join(w for w in words if w)
    return text


def get_db_boot_summary() -> str:
    """Retourne un resume texte du dernier boot pour les commandes vocales."""
    cache = get_voice_cache()
    if not cache.get("loaded"):
        return "Cache vocal non charge"
    return (
        f"{cache['commands_count']} commandes SQL, "
        f"{cache['skills_count']} skills, "
        f"{len(cache['corrections'])} corrections vocales, "
        f"{len(cache['pipelines'])} pipelines"
    )
