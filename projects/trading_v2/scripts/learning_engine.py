"""
JARVIS Learning Engine v1.0 - Auto-Learning & Self-Improvement
Tracks every command, analyzes failures, auto-expands fallback patterns.
DB: trading.db (tables: command_history, learned_patterns)
"""
import sqlite3
import os
import time
import uuid
from datetime import datetime

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
DB_PATH = os.path.join(ROOT, "database", "trading.db")

# Session ID unique par lancement
SESSION_ID = uuid.uuid4().hex[:8]


def init_db():
    """Cree les tables d'apprentissage si absentes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (datetime('now','localtime')),
            session_id TEXT,
            raw_text TEXT NOT NULL,
            intent_source TEXT,
            action TEXT,
            params TEXT,
            m2_latency_ms INTEGER,
            exec_success INTEGER DEFAULT 1,
            exec_error TEXT,
            exec_latency_ms INTEGER
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT (datetime('now','localtime')),
            pattern_text TEXT NOT NULL UNIQUE,
            action TEXT NOT NULL,
            params TEXT DEFAULT '',
            source TEXT DEFAULT 'auto_m2',
            confidence REAL DEFAULT 0.5,
            usage_count INTEGER DEFAULT 0,
            last_used DATETIME
        )""")

        # Migrate existing learning_patterns data if present
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learning_patterns'")
        if cur.fetchone():
            cur.execute("""SELECT trigger_phrase, action, params, source, uses
                           FROM learning_patterns
                           WHERE trigger_phrase NOT IN (SELECT pattern_text FROM learned_patterns)""")
            rows = cur.fetchall()
            for row in rows:
                try:
                    cur.execute("""INSERT OR IGNORE INTO learned_patterns
                                   (pattern_text, action, params, source, confidence, usage_count)
                                   VALUES (?, ?, ?, ?, 0.5, ?)""",
                                (row[0], row[1], row[2] or '', row[3] or 'migrated', row[4] or 0))
                except:
                    pass

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  LEARNING ENGINE init error: {e}")
        return False


def log_command(raw_text, intent_source, action, params, m2_latency_ms=0,
                exec_success=True, exec_error=None, exec_latency_ms=0):
    """Log chaque commande dans command_history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO command_history
                        (session_id, raw_text, intent_source, action, params,
                         m2_latency_ms, exec_success, exec_error, exec_latency_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (SESSION_ID, raw_text, intent_source, action, params or '',
                      m2_latency_ms, 1 if exec_success else 0, exec_error, exec_latency_ms))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  LOG error: {e}")


def get_stats(hours=24):
    """Stats: total, success_rate, avg_latency, top_actions, top_errors"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        since = f"datetime('now','localtime','-{hours} hours')"

        # Total commands
        cur.execute(f"SELECT COUNT(*) FROM command_history WHERE timestamp >= {since}")
        total = cur.fetchone()[0]

        if total == 0:
            conn.close()
            return {"total": 0, "hours": hours}

        # Success rate
        cur.execute(f"SELECT SUM(exec_success) FROM command_history WHERE timestamp >= {since}")
        successes = cur.fetchone()[0] or 0

        # Avg M2 latency (only M2 calls)
        cur.execute(f"""SELECT AVG(m2_latency_ms) FROM command_history
                        WHERE timestamp >= {since} AND intent_source = 'M2' AND m2_latency_ms > 0""")
        avg_m2 = cur.fetchone()[0] or 0

        # Avg exec latency
        cur.execute(f"""SELECT AVG(exec_latency_ms) FROM command_history
                        WHERE timestamp >= {since} AND exec_latency_ms > 0""")
        avg_exec = cur.fetchone()[0] or 0

        # Top actions
        cur.execute(f"""SELECT action, COUNT(*) as cnt FROM command_history
                        WHERE timestamp >= {since} AND action IS NOT NULL
                        GROUP BY action ORDER BY cnt DESC LIMIT 5""")
        top_actions = [(r[0], r[1]) for r in cur.fetchall()]

        # Intent source distribution
        cur.execute(f"""SELECT intent_source, COUNT(*) as cnt FROM command_history
                        WHERE timestamp >= {since}
                        GROUP BY intent_source ORDER BY cnt DESC""")
        sources = {r[0]: r[1] for r in cur.fetchall()}

        # Top errors
        cur.execute(f"""SELECT exec_error, COUNT(*) as cnt FROM command_history
                        WHERE timestamp >= {since} AND exec_success = 0 AND exec_error IS NOT NULL
                        GROUP BY exec_error ORDER BY cnt DESC LIMIT 3""")
        top_errors = [(r[0], r[1]) for r in cur.fetchall()]

        # Failures (UNKNOWN)
        cur.execute(f"""SELECT COUNT(*) FROM command_history
                        WHERE timestamp >= {since} AND (action = 'UNKNOWN' OR exec_success = 0)""")
        failures = cur.fetchone()[0]

        conn.close()
        return {
            "total": total,
            "hours": hours,
            "successes": successes,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
            "avg_m2_latency_ms": round(avg_m2),
            "avg_exec_latency_ms": round(avg_exec),
            "top_actions": top_actions,
            "sources": sources,
            "top_errors": top_errors,
            "failures": failures,
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_failures():
    """Trouver les patterns d'echec repetitifs (3+ occurrences)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""SELECT raw_text, COUNT(*) as cnt FROM command_history
                       WHERE action = 'UNKNOWN' OR exec_success = 0
                       GROUP BY raw_text HAVING cnt >= 3
                       ORDER BY cnt DESC LIMIT 10""")
        rows = cur.fetchall()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except:
        return []


def auto_expand_fallback():
    """Si M2 renvoie toujours la meme action pour un texte (3+ fois), proposer ajout fallback"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Trouver les patterns M2 stables (meme texte -> meme action, 3+ fois)
        cur.execute("""SELECT raw_text, action, params, COUNT(*) as cnt
                       FROM command_history
                       WHERE intent_source = 'M2' AND exec_success = 1
                         AND action != 'UNKNOWN'
                       GROUP BY raw_text, action
                       HAVING cnt >= 3
                       ORDER BY cnt DESC""")
        candidates = cur.fetchall()

        n_added = 0
        for raw, action, params, cnt in candidates:
            pattern = raw.lower().strip()
            # Verifier si pas deja dans learned_patterns
            cur.execute("SELECT id FROM learned_patterns WHERE pattern_text = ?", (pattern,))
            if cur.fetchone():
                continue

            confidence = min(cnt / 10.0, 1.0)
            cur.execute("""INSERT OR IGNORE INTO learned_patterns
                           (pattern_text, action, params, source, confidence, usage_count)
                           VALUES (?, ?, ?, 'auto_m2', ?, ?)""",
                        (pattern, action, params or '', confidence, cnt))
            if cur.rowcount > 0:
                n_added += 1
                print(f"  AUTO-EXPAND: '{pattern}' -> {action} (conf={confidence:.1f}, from {cnt} M2 calls)")

        conn.commit()
        conn.close()
        return n_added
    except Exception as e:
        print(f"  AUTO-EXPAND error: {e}")
        return 0


def suggest_genesis_tools():
    """Si 3+ echecs du meme type, proposer creation outil Genesis"""
    try:
        failures = analyze_failures()
        if not failures:
            return 0

        n_suggested = 0
        for text, count in failures:
            if count >= 3:
                print(f"  GENESIS SUGGEST: '{text}' (failed {count}x) - candidate for auto-tool")
                n_suggested += 1

        return n_suggested
    except:
        return 0


def get_learned_patterns():
    """Retourne les patterns appris (pour injection dans fallback)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""SELECT pattern_text, action, params, confidence
                       FROM learned_patterns
                       WHERE confidence >= 0.3
                       ORDER BY usage_count DESC, confidence DESC""")
        rows = cur.fetchall()
        conn.close()
        return [{"pattern_text": r[0], "action": r[1], "params": r[2] or "", "confidence": r[3]}
                for r in rows]
    except:
        return []


def increment_pattern_use(pattern_text):
    """Incremente le compteur d'utilisation + update last_used"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""UPDATE learned_patterns
                        SET usage_count = usage_count + 1, last_used = datetime('now','localtime')
                        WHERE pattern_text = ?""", (pattern_text,))
        conn.commit()
        conn.close()
    except:
        pass


def add_learned_pattern(pattern_text, action, params="", source="auto_m2", confidence=0.5):
    """Ajoute un pattern appris dans la DB"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT OR REPLACE INTO learned_patterns
                        (pattern_text, action, params, source, confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))""",
                     (pattern_text.lower().strip(), action, params, source, confidence))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  LEARN error: {e}")
        return False


def report():
    """Rapport texte complet (pour TTS ou affichage)"""
    stats = get_stats(24)

    if "error" in stats:
        return f"Erreur lors de la collecte des stats: {stats['error']}"

    if stats["total"] == 0:
        return "Aucune commande enregistree dans les dernieres 24 heures."

    lines = [f"JARVIS Stats ({stats['hours']}h):"]
    lines.append(f"  {stats['total']} commandes executees")
    lines.append(f"  Succes: {stats['success_rate']}% ({stats['successes']}/{stats['total']})")

    # Sources
    sources = stats.get("sources", {})
    if sources:
        parts = []
        for src, cnt in sources.items():
            pct = round(cnt / stats["total"] * 100)
            parts.append(f"{src} {pct}%")
        lines.append(f"  Route: {', '.join(parts)}")

    # Latences
    if stats["avg_m2_latency_ms"] > 0:
        lines.append(f"  Latence M2 moy: {stats['avg_m2_latency_ms']}ms")
    if stats["avg_exec_latency_ms"] > 0:
        lines.append(f"  Latence exec moy: {stats['avg_exec_latency_ms']}ms")

    # Top actions
    if stats["top_actions"]:
        top = ", ".join(f"{a}({c})" for a, c in stats["top_actions"])
        lines.append(f"  Top actions: {top}")

    # Failures
    if stats["failures"]:
        lines.append(f"  Echecs: {stats['failures']}")

    # Top errors
    if stats["top_errors"]:
        errs = ", ".join(f"{e[:40]}({c})" for e, c in stats["top_errors"])
        lines.append(f"  Top erreurs: {errs}")

    # Learned patterns count
    patterns = get_learned_patterns()
    lines.append(f"  Patterns appris: {len(patterns)}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=== LEARNING ENGINE - TEST ===")
    ok = init_db()
    print(f"DB init: {'OK' if ok else 'FAIL'}")

    # Test log
    log_command("test ouvre chrome", "FALLBACK", "OPEN_APP", "chrome",
                m2_latency_ms=0, exec_success=True, exec_latency_ms=50)
    print("Log test: OK")

    # Test stats
    print("\n" + report())

    # Test patterns
    patterns = get_learned_patterns()
    print(f"\nPatterns appris: {len(patterns)}")
    for p in patterns[:5]:
        print(f"  '{p['pattern_text']}' -> {p['action']} (conf={p['confidence']})")
