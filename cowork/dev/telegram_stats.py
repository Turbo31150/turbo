#!/usr/bin/env python3
"""telegram_stats.py — Statistiques d'utilisation Telegram JARVIS.

Usage:
    python dev/telegram_stats.py --daily
    python dev/telegram_stats.py --weekly
    python dev/telegram_stats.py --commands
    python dev/telegram_stats.py --voice-stats
    python dev/telegram_stats.py --report
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Chemin de la base de donnees ---
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "telegram_stats.db"


def get_db() -> sqlite3.Connection:
    """Ouvre (ou cree) la base SQLite et initialise le schema si necessaire."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Cree les tables si elles n'existent pas encore."""
    conn.executescript("""
        -- Table principale : chaque message Telegram entrant
        CREATE TABLE IF NOT EXISTS messages (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
            chat_id       INTEGER NOT NULL,
            user_id       INTEGER,
            username      TEXT,
            msg_type      TEXT    NOT NULL CHECK(msg_type IN ('text','voice','command','callback','photo','document','other')),
            command_name  TEXT,                 -- ex: /start, /help, /trading (NULL si pas une commande)
            text_length   INTEGER DEFAULT 0,
            voice_duration_s REAL DEFAULT 0,    -- duree en secondes (messages vocaux)
            response_time_ms REAL,              -- temps de reponse du bot en ms
            success       INTEGER DEFAULT 1,    -- 1 = OK, 0 = erreur
            error_message TEXT                   -- details erreur si success=0
        );

        -- Index pour les requetes frequentes
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_messages_msg_type  ON messages(msg_type);
        CREATE INDEX IF NOT EXISTS idx_messages_command   ON messages(command_name);

        -- Table de sessions (optionnel, pour tracking duree conversation)
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id    INTEGER NOT NULL,
            started_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
            ended_at   TEXT,
            msg_count  INTEGER DEFAULT 0
        );

        -- Table meta : version schema + infos generales
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');
        INSERT OR IGNORE INTO meta(key, value) VALUES ('created_at', strftime('%Y-%m-%dT%H:%M:%S','now','localtime'));
    """)
    conn.commit()


# ---------------------------------------------------------------------------
#  Fonctions d'insertion (utilisables par le bot Telegram)
# ---------------------------------------------------------------------------

def record_message(
    chat_id: int,
    msg_type: str,
    user_id: int | None = None,
    username: str | None = None,
    command_name: str | None = None,
    text_length: int = 0,
    voice_duration_s: float = 0.0,
    response_time_ms: float | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> int:
    """Enregistre un message entrant dans la base. Retourne l'id insere."""
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO messages
           (chat_id, user_id, username, msg_type, command_name,
            text_length, voice_duration_s, response_time_ms, success, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chat_id, user_id, username, msg_type, command_name,
            text_length, voice_duration_s, response_time_ms,
            1 if success else 0, error_message,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


# ---------------------------------------------------------------------------
#  Requetes statistiques
# ---------------------------------------------------------------------------

def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    """Convertit les Row SQLite en liste de dicts serialisables JSON."""
    return [dict(r) for r in rows]


def daily_stats() -> dict:
    """Statistiques du jour courant : messages par type, volume, erreurs."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Nombre total de messages aujourd'hui
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM messages WHERE date(timestamp) = ?", (today,)
    ).fetchone()["total"]

    # Repartition par type
    by_type = _rows_to_list(conn.execute(
        """SELECT msg_type, COUNT(*) AS count
           FROM messages WHERE date(timestamp) = ?
           GROUP BY msg_type ORDER BY count DESC""",
        (today,),
    ).fetchall())

    # Temps de reponse moyen / min / max (en ms)
    perf = dict(conn.execute(
        """SELECT
             ROUND(AVG(response_time_ms), 1)  AS avg_ms,
             ROUND(MIN(response_time_ms), 1)  AS min_ms,
             ROUND(MAX(response_time_ms), 1)  AS max_ms
           FROM messages
           WHERE date(timestamp) = ? AND response_time_ms IS NOT NULL""",
        (today,),
    ).fetchone())

    # Taux d'erreur
    errors = conn.execute(
        "SELECT COUNT(*) AS errors FROM messages WHERE date(timestamp) = ? AND success = 0",
        (today,),
    ).fetchone()["errors"]

    # Heures les plus actives (top 5)
    active_hours = _rows_to_list(conn.execute(
        """SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour, COUNT(*) AS count
           FROM messages WHERE date(timestamp) = ?
           GROUP BY hour ORDER BY count DESC LIMIT 5""",
        (today,),
    ).fetchall())

    conn.close()
    return {
        "period": "daily",
        "date": today,
        "total_messages": total,
        "by_type": by_type,
        "response_time": perf,
        "error_count": errors,
        "error_rate_pct": round(errors / total * 100, 2) if total > 0 else 0.0,
        "active_hours_top5": active_hours,
    }


def weekly_stats() -> dict:
    """Statistiques des 7 derniers jours avec tendance quotidienne."""
    conn = get_db()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    # Totaux de la semaine
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM messages WHERE date(timestamp) >= ?", (week_ago,)
    ).fetchone()["total"]

    # Repartition par jour
    by_day = _rows_to_list(conn.execute(
        """SELECT date(timestamp) AS day, COUNT(*) AS count
           FROM messages WHERE date(timestamp) >= ?
           GROUP BY day ORDER BY day""",
        (week_ago,),
    ).fetchall())

    # Repartition par type sur la semaine
    by_type = _rows_to_list(conn.execute(
        """SELECT msg_type, COUNT(*) AS count
           FROM messages WHERE date(timestamp) >= ?
           GROUP BY msg_type ORDER BY count DESC""",
        (week_ago,),
    ).fetchall())

    # Temps de reponse moyen par jour
    perf_by_day = _rows_to_list(conn.execute(
        """SELECT date(timestamp) AS day,
                  ROUND(AVG(response_time_ms), 1) AS avg_ms,
                  COUNT(*) AS sample_count
           FROM messages
           WHERE date(timestamp) >= ? AND response_time_ms IS NOT NULL
           GROUP BY day ORDER BY day""",
        (week_ago,),
    ).fetchall())

    # Erreurs de la semaine
    errors = conn.execute(
        "SELECT COUNT(*) AS errors FROM messages WHERE date(timestamp) >= ? AND success = 0",
        (week_ago,),
    ).fetchone()["errors"]

    # Utilisateurs uniques
    unique_users = conn.execute(
        "SELECT COUNT(DISTINCT user_id) AS unique_users FROM messages WHERE date(timestamp) >= ? AND user_id IS NOT NULL",
        (week_ago,),
    ).fetchone()["unique_users"]

    conn.close()
    return {
        "period": "weekly",
        "from": week_ago,
        "to": today,
        "total_messages": total,
        "daily_average": round(total / 7, 1),
        "by_day": by_day,
        "by_type": by_type,
        "response_time_by_day": perf_by_day,
        "error_count": errors,
        "error_rate_pct": round(errors / total * 100, 2) if total > 0 else 0.0,
        "unique_users": unique_users,
    }


def command_stats() -> dict:
    """Classement des commandes les plus utilisees (all-time + 7 jours)."""
    conn = get_db()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Top commandes all-time
    all_time = _rows_to_list(conn.execute(
        """SELECT command_name, COUNT(*) AS count,
                  ROUND(AVG(response_time_ms), 1) AS avg_response_ms,
                  SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors
           FROM messages
           WHERE msg_type = 'command' AND command_name IS NOT NULL
           GROUP BY command_name ORDER BY count DESC""",
    ).fetchall())

    # Top commandes 7 jours
    recent = _rows_to_list(conn.execute(
        """SELECT command_name, COUNT(*) AS count,
                  ROUND(AVG(response_time_ms), 1) AS avg_response_ms,
                  SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors
           FROM messages
           WHERE msg_type = 'command' AND command_name IS NOT NULL
                 AND date(timestamp) >= ?
           GROUP BY command_name ORDER BY count DESC""",
        (week_ago,),
    ).fetchall())

    # Commandes uniques totales
    unique_count = conn.execute(
        "SELECT COUNT(DISTINCT command_name) AS unique_commands FROM messages WHERE msg_type = 'command' AND command_name IS NOT NULL"
    ).fetchone()["unique_commands"]

    # Total appels commande
    total_calls = conn.execute(
        "SELECT COUNT(*) AS total FROM messages WHERE msg_type = 'command'"
    ).fetchone()["total"]

    conn.close()
    return {
        "period": "all_time_and_7days",
        "unique_commands": unique_count,
        "total_command_calls": total_calls,
        "all_time_ranking": all_time,
        "last_7_days_ranking": recent,
    }


def voice_stats() -> dict:
    """Statistiques des messages vocaux : duree, frequence, heures."""
    conn = get_db()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Totaux vocaux
    totals = dict(conn.execute(
        """SELECT
             COUNT(*) AS total_voice_messages,
             ROUND(SUM(voice_duration_s), 1) AS total_duration_s,
             ROUND(AVG(voice_duration_s), 1) AS avg_duration_s,
             ROUND(MIN(voice_duration_s), 1) AS min_duration_s,
             ROUND(MAX(voice_duration_s), 1) AS max_duration_s
           FROM messages WHERE msg_type = 'voice'""",
    ).fetchone())

    # Vocaux des 7 derniers jours
    recent_totals = dict(conn.execute(
        """SELECT
             COUNT(*) AS total,
             ROUND(SUM(voice_duration_s), 1) AS total_duration_s,
             ROUND(AVG(voice_duration_s), 1) AS avg_duration_s
           FROM messages WHERE msg_type = 'voice' AND date(timestamp) >= ?""",
        (week_ago,),
    ).fetchone())

    # Temps de reponse pour les vocaux (transcription + traitement)
    perf = dict(conn.execute(
        """SELECT
             ROUND(AVG(response_time_ms), 1) AS avg_ms,
             ROUND(MIN(response_time_ms), 1) AS min_ms,
             ROUND(MAX(response_time_ms), 1) AS max_ms
           FROM messages
           WHERE msg_type = 'voice' AND response_time_ms IS NOT NULL""",
    ).fetchone())

    # Heures preferees pour les vocaux
    voice_hours = _rows_to_list(conn.execute(
        """SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour, COUNT(*) AS count
           FROM messages WHERE msg_type = 'voice'
           GROUP BY hour ORDER BY count DESC LIMIT 5""",
    ).fetchall())

    # Taux d'erreur vocal
    voice_errors = conn.execute(
        "SELECT COUNT(*) AS errors FROM messages WHERE msg_type = 'voice' AND success = 0"
    ).fetchone()["errors"]

    conn.close()
    return {
        "all_time": totals,
        "last_7_days": recent_totals,
        "response_time": perf,
        "preferred_hours_top5": voice_hours,
        "error_count": voice_errors,
        "error_rate_pct": round(
            voice_errors / totals["total_voice_messages"] * 100, 2
        ) if totals["total_voice_messages"] > 0 else 0.0,
    }


def full_report() -> dict:
    """Rapport complet : combine daily + weekly + commands + voice + meta."""
    conn = get_db()

    # Informations generales de la base
    total_all = conn.execute("SELECT COUNT(*) AS total FROM messages").fetchone()["total"]
    first_msg = conn.execute(
        "SELECT MIN(timestamp) AS first FROM messages"
    ).fetchone()["first"]
    last_msg = conn.execute(
        "SELECT MAX(timestamp) AS last FROM messages"
    ).fetchone()["last"]
    db_size = os.path.getsize(DB_PATH) if DB_PATH.exists() else 0

    # Distribution par heure (all-time, pour heatmap)
    hourly_dist = _rows_to_list(conn.execute(
        """SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour, COUNT(*) AS count
           FROM messages GROUP BY hour ORDER BY hour"""
    ).fetchall())

    # Distribution par jour de la semaine (0=dimanche ... 6=samedi en SQLite)
    weekday_dist = _rows_to_list(conn.execute(
        """SELECT
             CASE CAST(strftime('%w', timestamp) AS INTEGER)
               WHEN 0 THEN 'dimanche' WHEN 1 THEN 'lundi' WHEN 2 THEN 'mardi'
               WHEN 3 THEN 'mercredi' WHEN 4 THEN 'jeudi' WHEN 5 THEN 'vendredi'
               WHEN 6 THEN 'samedi'
             END AS day_name,
             COUNT(*) AS count
           FROM messages GROUP BY day_name ORDER BY count DESC"""
    ).fetchall())

    # Top 10 utilisateurs
    top_users = _rows_to_list(conn.execute(
        """SELECT user_id, username, COUNT(*) AS msg_count
           FROM messages WHERE user_id IS NOT NULL
           GROUP BY user_id ORDER BY msg_count DESC LIMIT 10"""
    ).fetchall())

    # Performance globale
    global_perf = dict(conn.execute(
        """SELECT
             ROUND(AVG(response_time_ms), 1) AS avg_ms,
             ROUND(MIN(response_time_ms), 1) AS min_ms,
             ROUND(MAX(response_time_ms), 1) AS max_ms,
             COUNT(response_time_ms)          AS sample_count
           FROM messages WHERE response_time_ms IS NOT NULL"""
    ).fetchone())

    # Percentiles de temps de reponse (P50, P90, P95, P99)
    percentiles = {}
    sample_count = global_perf.get("sample_count", 0) or 0
    if sample_count > 0:
        all_times = [
            r["response_time_ms"]
            for r in conn.execute(
                "SELECT response_time_ms FROM messages WHERE response_time_ms IS NOT NULL ORDER BY response_time_ms"
            ).fetchall()
        ]
        for p in (50, 90, 95, 99):
            idx = min(int(len(all_times) * p / 100), len(all_times) - 1)
            percentiles[f"p{p}_ms"] = round(all_times[idx], 1)

    conn.close()

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "db_path": str(DB_PATH),
        "db_size_bytes": db_size,
        "meta": {
            "total_messages_all_time": total_all,
            "first_message": first_msg,
            "last_message": last_msg,
        },
        "daily": daily_stats(),
        "weekly": weekly_stats(),
        "commands": command_stats(),
        "voice": voice_stats(),
        "distributions": {
            "by_hour": hourly_dist,
            "by_weekday": weekday_dist,
        },
        "top_users": top_users,
        "performance": {
            **global_perf,
            "percentiles": percentiles,
        },
    }


# ---------------------------------------------------------------------------
#  Donnees de demonstration (pour tester sans bot reel)
# ---------------------------------------------------------------------------

def seed_demo_data() -> dict:
    """Insere des donnees de demonstration dans la base pour tester les stats."""
    import random

    conn = get_db()

    # Verifier si des donnees existent deja
    existing = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
    if existing > 0:
        conn.close()
        return {"status": "skipped", "reason": f"base non vide ({existing} messages)"}

    # Commandes typiques JARVIS
    commands = [
        "/start", "/help", "/status", "/trading", "/gpu",
        "/cluster", "/audit", "/voice", "/settings", "/ping",
        "/thermal", "/consensus", "/deploy", "/backup", "/logs",
    ]
    msg_types = ["text", "voice", "command", "callback", "photo"]
    usernames = ["franc", "admin_bot", "tester_1", "user_42"]

    now = datetime.now()
    inserted = 0

    # Generer 500 messages sur les 14 derniers jours
    for i in range(500):
        # Repartition temporelle realiste (plus de messages en journee)
        days_ago = random.randint(0, 13)
        hour = random.choices(
            range(24),
            weights=[1, 1, 1, 1, 1, 2, 3, 5, 8, 10, 10, 9,
                     8, 7, 7, 8, 9, 10, 8, 6, 4, 3, 2, 1],
            k=1,
        )[0]
        minute = random.randint(0, 59)
        ts = (now - timedelta(days=days_ago)).replace(
            hour=hour, minute=minute, second=random.randint(0, 59)
        )

        # Type de message pondere (plus de text et commands)
        mtype = random.choices(
            msg_types, weights=[40, 15, 35, 5, 5], k=1
        )[0]

        cmd_name = None
        text_len = 0
        voice_dur = 0.0

        if mtype == "command":
            cmd_name = random.choice(commands)
            text_len = len(cmd_name) + random.randint(0, 50)
        elif mtype == "text":
            text_len = random.randint(5, 500)
        elif mtype == "voice":
            voice_dur = round(random.uniform(1.0, 45.0), 1)

        # Temps de reponse (quelques messages sans reponse mesuree)
        resp_time = None
        if random.random() < 0.9:
            # Vocaux plus lents (transcription)
            base = 800 if mtype == "voice" else 150
            resp_time = round(random.gauss(base, base * 0.3), 1)
            resp_time = max(50.0, resp_time)  # minimum 50ms

        # Taux d'erreur ~5%
        success = random.random() > 0.05
        error_msg = None
        if not success:
            error_msg = random.choice([
                "TimeoutError: agent M1 unreachable",
                "ValueError: invalid command argument",
                "ConnectionError: Ollama offline",
                "RuntimeError: GPU memory full",
                "PermissionError: unauthorized user",
            ])

        conn.execute(
            """INSERT INTO messages
               (timestamp, chat_id, user_id, username, msg_type, command_name,
                text_length, voice_duration_s, response_time_ms, success, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ts.strftime("%Y-%m-%dT%H:%M:%S"),
                random.choice([123456789, 987654321]),
                random.randint(1000, 1003),
                random.choice(usernames),
                mtype,
                cmd_name,
                text_len,
                voice_dur,
                resp_time,
                1 if success else 0,
                error_msg,
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()

    return {"status": "ok", "inserted": inserted, "db_path": str(DB_PATH)}


# ---------------------------------------------------------------------------
#  Point d'entree CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construit le parser argparse avec toutes les options."""
    parser = argparse.ArgumentParser(
        prog="telegram_stats",
        description="Statistiques d'utilisation Telegram JARVIS — Sortie JSON",
        epilog="Base SQLite : %(default)s" % {"default": str(DB_PATH)},
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Groupe mutuellement exclusif pour le mode d'affichage
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--daily",
        action="store_true",
        help="Statistiques du jour (messages, types, erreurs, heures actives)",
    )
    group.add_argument(
        "--weekly",
        action="store_true",
        help="Statistiques des 7 derniers jours (tendance, moyennes, utilisateurs)",
    )
    group.add_argument(
        "--commands",
        action="store_true",
        help="Classement des commandes les plus utilisees (all-time + 7j)",
    )
    group.add_argument(
        "--voice-stats",
        action="store_true",
        help="Statistiques des messages vocaux (durees, performance, heures)",
    )
    group.add_argument(
        "--report",
        action="store_true",
        help="Rapport complet combinant toutes les statistiques",
    )
    group.add_argument(
        "--seed",
        action="store_true",
        help="Inserer des donnees de demonstration (500 messages)",
    )

    # Options supplementaires
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=False,
        help="Sortie JSON indentee (defaut : compact)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Chemin alternatif vers la base SQLite",
    )

    return parser


def main() -> None:
    """Point d'entree principal du script."""
    global DB_PATH, DB_DIR

    parser = build_parser()
    args = parser.parse_args()

    # Chemin alternatif si specifie
    if args.db:
        DB_PATH = Path(args.db)
        DB_DIR = DB_PATH.parent

    # Determiner l'action demandee
    indent = 2 if args.pretty else None

    if args.daily:
        result = daily_stats()
    elif args.weekly:
        result = weekly_stats()
    elif args.commands:
        result = command_stats()
    elif args.voice_stats:
        result = voice_stats()
    elif args.report:
        result = full_report()
    elif args.seed:
        result = seed_demo_data()
    else:
        # Aucun flag → afficher le rapport complet par defaut
        parser.print_help()
        sys.exit(0)

    # Sortie JSON sur stdout
    print(json.dumps(result, indent=indent, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
