#!/usr/bin/env python3
"""jarvis_roi_calculator.py — #209 Calculate ROI: cloud costs, time saved, trading, electricity.
Usage:
    python dev/jarvis_roi_calculator.py --calculate
    python dev/jarvis_roi_calculator.py --savings
    python dev/jarvis_roi_calculator.py --cost
    python dev/jarvis_roi_calculator.py --report
    python dev/jarvis_roi_calculator.py --once
"""
import argparse, json, sqlite3, time, os
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DATA_DIR = DEV / "data"
DB_PATH = DATA_DIR / "roi_calculator.db"

# Cost estimates
CLOUD_COST_PER_1K_TOKENS = {
    "gpt-oss": 0.003,
    "devstral": 0.002,
    "glm-4.7": 0.001,
    "minimax": 0.001,
    "qwen3-coder:480b": 0.002,
    "claude-opus": 0.015,
    "claude-sonnet": 0.003,
    "gemini-pro": 0.001,
}
LOCAL_GPU_WATTS = {
    "M1": 250,   # 6 GPU ~250W total under load
    "M2": 180,   # 3 GPU
    "M3": 70,    # 1 GPU
    "OL1": 200,  # 5 GPU
}
ELECTRICITY_COST_KWH = 0.18  # EUR/kWh France average
MANUAL_TASK_MINUTES = {
    "code_review": 30,
    "bug_fix": 45,
    "test_write": 20,
    "documentation": 25,
    "deployment": 15,
    "monitoring": 10,
    "trading_signal": 5,
}
HOURLY_RATE = 50  # EUR/h developer equivalent


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS cost_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        amount_eur REAL DEFAULT 0,
        tokens_used INTEGER DEFAULT 0,
        model TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS savings_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        time_saved_min REAL DEFAULT 0,
        value_eur REAL DEFAULT 0,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS monthly_roi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT NOT NULL UNIQUE,
        total_cost_eur REAL DEFAULT 0,
        total_savings_eur REAL DEFAULT 0,
        electricity_eur REAL DEFAULT 0,
        trading_pnl_eur REAL DEFAULT 0,
        net_roi_eur REAL DEFAULT 0,
        roi_pct REAL DEFAULT 0,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _estimate_cloud_costs(db):
    """Estimate cloud token costs from experiment/benchmark data."""
    costs = {}
    # Check if experiment_runner.db exists
    exp_db = DATA_DIR / "experiment_runner.db"
    if exp_db.exists():
        try:
            conn = sqlite3.connect(str(exp_db))
            rows = conn.execute(
                "SELECT model, COUNT(*), AVG(output_len) FROM results GROUP BY model"
            ).fetchall()
            for model, count, avg_len in rows:
                est_tokens = int(count * (avg_len or 200) * 1.3)  # ~1.3 tokens per char
                rate = CLOUD_COST_PER_1K_TOKENS.get(model, 0.002)
                cost = est_tokens / 1000 * rate
                costs[model] = {"requests": count, "est_tokens": est_tokens, "cost_eur": round(cost, 4)}
            conn.close()
        except Exception:
            pass

    # Check benchmark.db
    bench_db = DATA_DIR / "benchmark.db"
    if bench_db.exists():
        try:
            conn = sqlite3.connect(str(bench_db))
            tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for tbl in tables:
                try:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                    if cnt > 0 and "benchmark" not in costs:
                        costs["benchmarks"] = {"runs": cnt, "est_cost_eur": round(cnt * 0.005, 3)}
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass

    return costs


def _estimate_electricity(hours_per_day=8, days=30):
    """Estimate monthly GPU electricity cost."""
    total_watts = sum(LOCAL_GPU_WATTS.values())
    daily_kwh = (total_watts / 1000) * hours_per_day
    monthly_kwh = daily_kwh * days
    monthly_eur = monthly_kwh * ELECTRICITY_COST_KWH
    return {
        "total_gpu_watts": total_watts,
        "hours_per_day": hours_per_day,
        "monthly_kwh": round(monthly_kwh, 1),
        "monthly_eur": round(monthly_eur, 2),
        "per_node": {k: round(v / 1000 * hours_per_day * days * ELECTRICITY_COST_KWH, 2)
                     for k, v in LOCAL_GPU_WATTS.items()}
    }


def _estimate_time_saved():
    """Estimate time saved by automation."""
    # Count automated scripts
    scripts = list(DEV.glob("*.py"))
    cron_count = 0
    for s in scripts:
        try:
            content = s.read_text(encoding="utf-8", errors="ignore")
            if "schedule" in content or "cron" in content or "loop" in content:
                cron_count += 1
        except Exception:
            pass

    # Estimate savings
    auto_tasks_per_day = max(5, cron_count // 3)
    avg_manual_min = sum(MANUAL_TASK_MINUTES.values()) / len(MANUAL_TASK_MINUTES)
    daily_saved_min = auto_tasks_per_day * avg_manual_min
    monthly_saved_hours = (daily_saved_min * 30) / 60
    monthly_value = monthly_saved_hours * HOURLY_RATE

    return {
        "total_scripts": len(scripts),
        "automated_scripts": cron_count,
        "auto_tasks_per_day": auto_tasks_per_day,
        "daily_saved_min": round(daily_saved_min),
        "monthly_saved_hours": round(monthly_saved_hours, 1),
        "monthly_value_eur": round(monthly_value, 2),
        "hourly_rate": HOURLY_RATE
    }


def calculate_roi(db):
    """Full ROI calculation."""
    month = datetime.now().strftime("%Y-%m")
    cloud_costs = _estimate_cloud_costs(db)
    electricity = _estimate_electricity()
    time_saved = _estimate_time_saved()

    total_cloud = sum(c.get("cost_eur", 0) for c in cloud_costs.values() if isinstance(c, dict) and "cost_eur" in c)
    total_cost = total_cloud + electricity["monthly_eur"]
    total_savings = time_saved["monthly_value_eur"]
    net_roi = total_savings - total_cost
    roi_pct = round((net_roi / total_cost) * 100, 1) if total_cost > 0 else 0

    db.execute("""INSERT OR REPLACE INTO monthly_roi
        (month, total_cost_eur, total_savings_eur, electricity_eur, net_roi_eur, roi_pct)
        VALUES (?,?,?,?,?,?)""",
        (month, round(total_cost, 2), round(total_savings, 2), electricity["monthly_eur"], round(net_roi, 2), roi_pct)
    )
    db.commit()

    return {
        "month": month,
        "costs": {
            "cloud_tokens": round(total_cloud, 2),
            "electricity": electricity["monthly_eur"],
            "total": round(total_cost, 2),
            "cloud_detail": cloud_costs,
            "electricity_detail": electricity
        },
        "savings": {
            "time_automation": time_saved["monthly_value_eur"],
            "total": round(total_savings, 2),
            "detail": time_saved
        },
        "roi": {
            "net_eur": round(net_roi, 2),
            "roi_pct": roi_pct,
            "verdict": "PROFITABLE" if net_roi > 0 else "COST CENTER"
        }
    }


def get_savings(db):
    """Show savings breakdown."""
    return _estimate_time_saved()


def get_costs(db):
    """Show cost breakdown."""
    cloud = _estimate_cloud_costs(db)
    elec = _estimate_electricity()
    total_cloud = sum(c.get("cost_eur", 0) for c in cloud.values() if isinstance(c, dict) and "cost_eur" in c)
    return {
        "cloud_costs": cloud,
        "electricity": elec,
        "total_monthly_eur": round(total_cloud + elec["monthly_eur"], 2)
    }


def full_report(db):
    """Historical ROI report."""
    roi = calculate_roi(db)
    history = db.execute(
        "SELECT month, total_cost_eur, total_savings_eur, net_roi_eur, roi_pct FROM monthly_roi ORDER BY month DESC LIMIT 6"
    ).fetchall()
    roi["history"] = [
        {"month": h[0], "cost": h[1], "savings": h[2], "net": h[3], "pct": h[4]} for h in history
    ]
    return roi


def do_status(db):
    months = db.execute("SELECT COUNT(*) FROM monthly_roi").fetchone()[0]
    latest = db.execute(
        "SELECT month, net_roi_eur, roi_pct FROM monthly_roi ORDER BY month DESC LIMIT 1"
    ).fetchone()
    return {
        "script": "jarvis_roi_calculator.py",
        "id": 209,
        "db": str(DB_PATH),
        "months_tracked": months,
        "latest_roi": {"month": latest[0], "net_eur": latest[1], "pct": latest[2]} if latest else None,
        "gpu_nodes": list(LOCAL_GPU_WATTS.keys()),
        "hourly_rate_eur": HOURLY_RATE,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS ROI Calculator — costs vs savings analysis")
    parser.add_argument("--calculate", action="store_true", help="Calculate monthly ROI")
    parser.add_argument("--savings", action="store_true", help="Show savings breakdown")
    parser.add_argument("--cost", action="store_true", help="Show cost breakdown")
    parser.add_argument("--report", action="store_true", help="Full report with history")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.calculate:
        result = calculate_roi(db)
    elif args.savings:
        result = get_savings(db)
    elif args.cost:
        result = get_costs(db)
    elif args.report:
        result = full_report(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
