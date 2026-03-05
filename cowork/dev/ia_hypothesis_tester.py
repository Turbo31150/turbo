#!/usr/bin/env python3
"""ia_hypothesis_tester.py — Hypothesis tester. Defines hypothesis, designs experiment, runs tests, statistical analysis.
Usage: python dev/ia_hypothesis_tester.py --test "HYPOTHESIS" --once
"""
import argparse, json, os, sqlite3, subprocess, time, hashlib, re, math, random
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "hypothesis_tester.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS hypotheses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        hypothesis TEXT,
        null_hypothesis TEXT,
        experiment_design TEXT,
        status TEXT DEFAULT 'pending',
        result TEXT,
        p_value REAL,
        significant INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        hypothesis_id INTEGER,
        trial_num INTEGER,
        input_data TEXT,
        output_data TEXT,
        success INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        hypothesis_id INTEGER,
        report_text TEXT,
        conclusion TEXT
    )""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=1024):
    """Send prompt to M1."""
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60",
             "http://127.0.0.1:1234/api/v1/chat",
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=65
        )
        data = json.loads(result.stdout)
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
        return str(data)
    except Exception as e:
        return f"ERROR: {e}"


def design_experiment(hypothesis):
    """Ask M1 to design an experiment for the hypothesis."""
    prompt = (
        f"Design a simple experiment to test this hypothesis. "
        f"Include: 1) Null hypothesis, 2) Variables, 3) Method, 4) Expected outcome.\n\n"
        f"Hypothesis: {hypothesis}\n\n"
        f"Format your response as:\n"
        f"NULL_HYPOTHESIS: ...\n"
        f"VARIABLES: ...\n"
        f"METHOD: ...\n"
        f"EXPECTED: ..."
    )
    return call_m1(prompt)


def run_statistical_test(observations, expected_rate=0.5):
    """Run a simple binomial-like statistical test."""
    n = len(observations)
    if n == 0:
        return {"p_value": 1.0, "significant": False, "test": "no_data"}

    successes = sum(1 for o in observations if o)
    observed_rate = successes / n

    # Simple z-test approximation for proportions
    if expected_rate * (1 - expected_rate) == 0:
        return {"p_value": 0.5, "significant": False, "test": "degenerate"}

    se = math.sqrt(expected_rate * (1 - expected_rate) / n)
    if se == 0:
        return {"p_value": 0.5, "significant": False, "test": "zero_se"}

    z = (observed_rate - expected_rate) / se
    # Approximate p-value using normal distribution (rough)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    return {
        "n": n,
        "successes": successes,
        "observed_rate": round(observed_rate, 4),
        "expected_rate": expected_rate,
        "z_score": round(z, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "test": "z_test_proportions"
    }


def do_test(hypothesis):
    """Test a hypothesis end-to-end."""
    db = init_db()

    # Step 1: Design experiment
    design = design_experiment(hypothesis)

    # Extract null hypothesis
    null_h = "Not specified"
    null_match = re.search(r"NULL_HYPOTHESIS:\s*(.+?)(?:\n|$)", design)
    if null_match:
        null_h = null_match.group(1).strip()

    # Step 2: Create hypothesis record
    hyp_id = db.execute(
        "INSERT INTO hypotheses (ts, hypothesis, null_hypothesis, experiment_design, status) VALUES (?,?,?,?,?)",
        (time.time(), hypothesis, null_h, design[:2000], "running")
    ).lastrowid

    # Step 3: Run trials (simulated via M1 evaluation)
    num_trials = 5
    observations = []
    for i in range(num_trials):
        trial_prompt = (
            f"Given this hypothesis: \"{hypothesis}\"\n"
            f"Trial {i+1}: Does available evidence support this hypothesis? "
            f"Answer YES or NO with brief reasoning."
        )
        response = call_m1(trial_prompt, max_tokens=256)
        success = "yes" in response.lower()[:50]
        observations.append(success)

        db.execute(
            "INSERT INTO experiments (ts, hypothesis_id, trial_num, input_data, output_data, success) VALUES (?,?,?,?,?,?)",
            (time.time(), hyp_id, i + 1, trial_prompt[:200], response[:500], int(success))
        )

    # Step 4: Statistical analysis
    stats = run_statistical_test(observations)

    # Step 5: Determine result
    if stats["significant"]:
        result_text = "SUPPORTED" if stats["observed_rate"] > 0.5 else "REJECTED"
    else:
        result_text = "INCONCLUSIVE"

    db.execute(
        "UPDATE hypotheses SET status='completed', result=?, p_value=?, significant=? WHERE id=?",
        (result_text, stats["p_value"], int(stats["significant"]), hyp_id)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "test",
        "hypothesis_id": hyp_id,
        "hypothesis": hypothesis,
        "null_hypothesis": null_h,
        "trials": num_trials,
        "observations": observations,
        "statistics": stats,
        "result": result_text,
        "experiment_preview": design[:400]
    }


def do_experiment():
    """Show experiment details for latest hypothesis."""
    db = init_db()
    row = db.execute(
        "SELECT id, hypothesis, experiment_design FROM hypotheses ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if not row:
        db.close()
        return {"ts": datetime.now().isoformat(), "status": "no_hypotheses"}

    hyp_id = row[0]
    trials = db.execute(
        "SELECT trial_num, output_data, success FROM experiments WHERE hypothesis_id=? ORDER BY trial_num",
        (hyp_id,)
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "hypothesis_id": hyp_id,
        "hypothesis": row[1][:100],
        "experiment_design": row[2][:500],
        "trials": [
            {"trial": t[0], "response": t[1][:200], "success": bool(t[2])}
            for t in trials
        ]
    }


def do_results():
    """Show results summary."""
    db = init_db()
    rows = db.execute(
        "SELECT id, hypothesis, result, p_value, significant FROM hypotheses WHERE status='completed' ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "results": [
            {
                "id": r[0], "hypothesis": r[1][:80], "result": r[2],
                "p_value": r[3], "significant": bool(r[4])
            }
            for r in rows
        ]
    }


def do_report():
    """Generate a report for the latest hypothesis."""
    db = init_db()
    row = db.execute(
        "SELECT id, hypothesis, null_hypothesis, result, p_value, significant, experiment_design "
        "FROM hypotheses WHERE status='completed' ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if not row:
        db.close()
        return {"ts": datetime.now().isoformat(), "status": "no_completed_hypotheses"}

    hyp_id = row[0]
    trials = db.execute(
        "SELECT trial_num, success FROM experiments WHERE hypothesis_id=? ORDER BY trial_num",
        (hyp_id,)
    ).fetchall()

    success_count = sum(1 for t in trials if t[1])
    total = len(trials)

    report = (
        f"Hypothesis Test Report\n"
        f"======================\n"
        f"Hypothesis: {row[1]}\n"
        f"Null Hypothesis: {row[2]}\n"
        f"Trials: {total}\n"
        f"Successes: {success_count}/{total}\n"
        f"P-value: {row[4]}\n"
        f"Significant: {'Yes' if row[5] else 'No'}\n"
        f"Result: {row[3]}\n"
    )

    conclusion = f"The hypothesis is {row[3].lower()} (p={row[4]}, alpha=0.05)."

    db.execute(
        "INSERT INTO reports (ts, hypothesis_id, report_text, conclusion) VALUES (?,?,?,?)",
        (time.time(), hyp_id, report, conclusion)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "hypothesis_id": hyp_id,
        "report": report,
        "conclusion": conclusion
    }


def main():
    parser = argparse.ArgumentParser(description="Hypothesis tester — Design experiments, run tests, statistical analysis")
    parser.add_argument("--test", metavar="HYPOTHESIS", help="Test a hypothesis")
    parser.add_argument("--experiment", action="store_true", help="Show experiment details")
    parser.add_argument("--results", action="store_true", help="Show results summary")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.test:
        result = do_test(args.test)
    elif args.experiment:
        result = do_experiment()
    elif args.results:
        result = do_results()
    elif args.report:
        result = do_report()
    else:
        result = {
            "ts": datetime.now().isoformat(),
            "status": "ok",
            "db": str(DB_PATH),
            "help": "Use --test HYPOTHESIS / --experiment / --results / --report"
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
