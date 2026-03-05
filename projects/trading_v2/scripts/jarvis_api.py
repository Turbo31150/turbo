"""
J.A.R.V.I.S. API Server v1.0 - Bridge Flask pour Electron
Expose commander_v2 + workflow_engine + DB via REST API.
Port: 5050 (evite les conflits avec n8n:5678, LM Studio:1234)
"""
import sys
import os
import io
import json
import sqlite3
import time
from datetime import datetime

ROOT = r"F:\BUREAU\TRADING_V2_PRODUCTION"
sys.path.insert(0, os.path.join(ROOT, "voice_system"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Flask
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    FLASK_OK = True
except ImportError:
    FLASK_OK = False
    print("Flask non installe. Run: pip install flask flask-cors")

# Commander V2
try:
    import commander_v2
    COMMANDER_OK = True
except Exception as e:
    print(f"Commander import error: {e}")
    COMMANDER_OK = False

DB_PATH = os.path.join(ROOT, "database", "trading.db")

if FLASK_OK:
    app = Flask(__name__)
    CORS(app)

    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "ok",
            "commander": COMMANDER_OK,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })

    @app.route('/api/command', methods=['POST'])
    def execute_command():
        """Execute une commande via commander_v2.process_input"""
        data = request.json
        text = data.get('text', '')
        if not text:
            return jsonify({"error": "text required"}), 400

        if not COMMANDER_OK:
            return jsonify({"error": "commander not loaded"}), 503

        # Capturer stdout
        old_stdout = sys.stdout
        capture = io.StringIO()
        sys.stdout = capture

        t0 = time.time()
        try:
            commander_v2.process_input(text)
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
        finally:
            sys.stdout = old_stdout

        output = capture.getvalue().strip()
        latency_ms = int((time.time() - t0) * 1000)

        return jsonify({
            "success": success,
            "text": text,
            "output": output,
            "error": error,
            "latency_ms": latency_ms
        })

    @app.route('/api/patterns', methods=['GET'])
    def get_patterns():
        """Liste les patterns appris (learned_patterns + learning_patterns)"""
        patterns = []
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            # learned_patterns (primary)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'")
            if cur.fetchone():
                cur.execute("""SELECT pattern_text, action, params, source, usage_count
                               FROM learned_patterns ORDER BY usage_count DESC""")
                for row in cur.fetchall():
                    patterns.append({
                        "phrase": row[0], "action": row[1], "params": row[2],
                        "source": row[3], "usage": row[4], "table": "learned_patterns"
                    })

            # learning_patterns (legacy)
            seen = {p["phrase"] for p in patterns}
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learning_patterns'")
            if cur.fetchone():
                cur.execute("""SELECT trigger_phrase, action, params, source, uses
                               FROM learning_patterns ORDER BY uses DESC""")
                for row in cur.fetchall():
                    if row[0] not in seen:
                        patterns.append({
                            "phrase": row[0], "action": row[1], "params": row[2],
                            "source": row[3], "usage": row[4], "table": "learning_patterns"
                        })

            conn.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(patterns)

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        """Stats du systeme"""
        stats = {}
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM command_history")
            stats["total_commands"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM command_history WHERE exec_success = 1")
            stats["success_count"] = cur.fetchone()[0]

            stats["success_rate"] = round(
                stats["success_count"] / max(stats["total_commands"], 1) * 100, 1
            )

            # Sources
            cur.execute("""SELECT intent_source, COUNT(*) FROM command_history
                           GROUP BY intent_source ORDER BY COUNT(*) DESC""")
            stats["sources"] = {row[0]: row[1] for row in cur.fetchall()}

            # Top actions
            cur.execute("""SELECT action, COUNT(*) FROM command_history
                           WHERE action IS NOT NULL
                           GROUP BY action ORDER BY COUNT(*) DESC LIMIT 10""")
            stats["top_actions"] = {row[0]: row[1] for row in cur.fetchall()}

            # Patterns count
            try:
                cur.execute("SELECT COUNT(*) FROM learned_patterns")
                stats["learned_patterns"] = cur.fetchone()[0]
            except:
                stats["learned_patterns"] = 0

            # Workflows
            try:
                cur.execute("SELECT COUNT(*) FROM macro_workflows")
                stats["workflows"] = cur.fetchone()[0]
            except:
                stats["workflows"] = 0

            # Avg M2 latency
            cur.execute("""SELECT AVG(m2_latency_ms) FROM command_history
                           WHERE intent_source = 'M2' AND m2_latency_ms > 0""")
            avg = cur.fetchone()[0]
            stats["avg_m2_latency_ms"] = int(avg) if avg else 0

            # Recent failures
            cur.execute("""SELECT raw_text, COUNT(*) FROM command_history
                           WHERE action = 'UNKNOWN' OR exec_success = 0
                           GROUP BY raw_text HAVING COUNT(*) >= 2
                           ORDER BY COUNT(*) DESC LIMIT 5""")
            stats["top_failures"] = [{"text": row[0], "count": row[1]}
                                     for row in cur.fetchall()]

            conn.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(stats)

    @app.route('/api/workflows', methods=['GET'])
    def get_workflows():
        """Liste les workflows memorises"""
        workflows = []
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""SELECT trigger, steps_json, usage_count, last_used
                           FROM macro_workflows ORDER BY usage_count DESC""")
            for row in cur.fetchall():
                workflows.append({
                    "trigger": row[0],
                    "steps": json.loads(row[1]) if row[1] else [],
                    "usage_count": row[2],
                    "last_used": row[3]
                })
            conn.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(workflows)

    if __name__ == '__main__':
        print(f"JARVIS API Server v1.0 - Port 5050")
        print(f"Commander: {'OK' if COMMANDER_OK else 'OFFLINE'}")
        print(f"DB: {DB_PATH}")
        app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)
