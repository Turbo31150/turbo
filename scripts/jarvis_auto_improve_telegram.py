#!/usr/bin/env python3
"""JARVIS Auto-Improve Report — Reads etoile.db + auto_heal.db and outputs
a human-readable self-improvement / health report to stdout.

Usage:  python scripts/jarvis_auto_improve_telegram.py
"""
import json, sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("F:/BUREAU/turbo/data")
ETOILE_DB = DATA_DIR / "etoile.db"
HEAL_DB = DATA_DIR / "auto_heal.db"


def _ts(ts) -> str:
    if ts is None: return "?"
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        return str(ts)[:16]
    except Exception:
        return str(ts)[:16]


def _q(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def _trend(vals):
    if len(vals) < 2: return "unknown"
    mid = len(vals) // 2
    a = sum(vals[:mid]) / max(mid, 1)
    b = sum(vals[mid:]) / max(len(vals) - mid, 1)
    d = b - a
    if d > 0.05: return "IMPROVING  ^"
    if d < -0.05: return "DEGRADING  v"
    return "STABLE     ="


def sect_self_improve(conn):
    rows = _q(conn,
        "SELECT action_type, target, description, confidence, timestamp "
        "FROM self_improve_log ORDER BY id DESC LIMIT 10")
    if not rows: return "[Self-Improve]  No entries found."
    lines = ["[Self-Improve -- last 10 actions]"]
    for act, tgt, desc, conf, ts in rows:
        lines.append(f"  {_ts(ts)}  {act:<16} {tgt:<6}  {desc}  (conf={conf:.0%})")
    return "\n".join(lines)


def sect_heal_log():
    if not HEAL_DB.exists(): return "[Auto-Heal]  Database not found."
    conn = sqlite3.connect(str(HEAL_DB))
    rows = _q(conn,
        "SELECT ts, cycle, issues_found, issues_fixed, issues_failed, "
        "duration_ms, details FROM heal_log ORDER BY id DESC LIMIT 5")
    conn.close()
    if not rows: return "[Auto-Heal]  No entries found."
    lines = ["[Auto-Heal -- last 5 cycles]"]
    for ts, cyc, found, fixed, failed, dur_ms, details in rows:
        comps = []
        try:
            for i in (json.loads(details) if details else []):
                comps.append(f"{i.get('component','?')}({i.get('severity','?')})")
        except Exception: pass
        lines.append(
            f"  {_ts(ts)}  cycle={cyc:<4} found={found} fixed={fixed} "
            f"failed={failed}  {(dur_ms or 0)/1000:.1f}s  [{', '.join(comps) or '-'}]")
    return "\n".join(lines)


def sect_node_weights(conn):
    baselines = {}
    for key, val in _q(conn,
            "SELECT key, value FROM config_snapshots WHERE category='cluster_node'"):
        try: baselines[key] = json.loads(val).get("weight", "?")
        except Exception: pass
    latest = {}
    for tgt, bv, av, desc, ts in _q(conn,
            "SELECT target, before_val, after_val, description, timestamp "
            "FROM self_improve_log WHERE action_type='weight_adjust' "
            "ORDER BY id DESC LIMIT 20"):
        if tgt not in latest:
            latest[tgt] = av
    disabled = {t for (t,) in _q(conn,
        "SELECT DISTINCT target FROM self_improve_log "
        "WHERE action_type='node_disable' ORDER BY id DESC LIMIT 10")}
    lines = ["[Node Weights]"]
    nodes = sorted(set(list(baselines) + list(latest)))
    for n in nodes:
        base, cur = baselines.get(n, "?"), latest.get(n, baselines.get(n, "?"))
        st = "DISABLED" if n in disabled else "active"
        lines.append(f"  {n:<5}  baseline={base}  current={cur}  [{st}]")
    return "\n".join(lines) if nodes else "[Node Weights]  No data."


def sect_dispatch_rates(conn):
    rows = _q(conn,
        "SELECT node, COUNT(*), SUM(CASE WHEN success=1 THEN 1 ELSE 0 END), "
        "AVG(quality), AVG(latency_ms) "
        "FROM dispatch_pipeline_log GROUP BY node ORDER BY COUNT(*) DESC")
    if not rows: return "[Dispatch Rates]  No dispatch data."
    lines = ["[Dispatch Success Rates]"]
    for node, total, ok, avg_q, avg_lat in rows:
        sr = (ok / total * 100) if total else 0
        lines.append(f"  {node:<5}  {ok}/{total} ({sr:.0f}%)  "
                     f"quality={avg_q or 0:.2f}  latency={avg_lat or 0:.0f}ms")
    return "\n".join(lines)


def sect_health_trend(conn):
    rows = _q(conn,
        "SELECT node, quality FROM dispatch_pipeline_log ORDER BY id ASC")
    if not rows: return "[Health Trend]  Not enough data."
    per_node = {}
    for node, quality in rows:
        per_node.setdefault(node, []).append(float(quality or 0))
    lines = ["[Health Trend]"]
    for node in sorted(per_node):
        v = per_node[node]
        lines.append(f"  {node:<5}  {_trend(v)}  ({len(v)} samples)")
    return "\n".join(lines)


def sect_recommendations(conn):
    recs = []
    # From improvement reports
    rep = _q(conn,
        "SELECT recommendations FROM agent_improvement_reports ORDER BY id DESC LIMIT 1")
    if rep and rep[0][0]:
        for line in rep[0][0].split("\n"):
            if line.strip(): recs.append(line.strip())
    # Degraded patterns
    seen = set()
    for tgt, desc in _q(conn,
            "SELECT target, description FROM self_improve_log "
            "WHERE action_type='pattern_evolve' ORDER BY id DESC LIMIT 5"):
        if tgt not in seen:
            recs.append(f"Pattern '{tgt}' flagged: {desc[:80]}")
            seen.add(tgt)
    # Persistent heal issues
    if HEAL_DB.exists():
        hc = sqlite3.connect(str(HEAL_DB))
        for comp, sev, msg, retries in _q(hc,
                "SELECT component, severity, message, retries "
                "FROM persistent_issues ORDER BY id DESC LIMIT 3"):
            recs.append(f"Persistent: {comp} [{sev}] -- {msg} (retries={retries})")
        hc.close()
    lines = ["[Recommendations]"]
    if recs:
        for i, r in enumerate(recs[:8], 1):
            lines.append(f"  {i}. {r}")
    else:
        lines.append("  No actionable recommendations at this time.")
    return "\n".join(lines)


def main():
    sep = "=" * 64
    print(sep)
    print("  JARVIS Auto-Improve Report")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep, "")
    if not ETOILE_DB.exists():
        print(f"ERROR: etoile.db not found at {ETOILE_DB}"); return
    conn = sqlite3.connect(str(ETOILE_DB))
    for sect in [sect_self_improve(conn), sect_heal_log(), sect_node_weights(conn),
                 sect_dispatch_rates(conn), sect_health_trend(conn),
                 sect_recommendations(conn)]:
        print(sect, "")
    conn.close()
    print(sep); print("  End of report"); print(sep)


if __name__ == "__main__":
    main()
