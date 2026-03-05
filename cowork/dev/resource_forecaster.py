#!/usr/bin/env python3
"""resource_forecaster.py

Predicts CPU, RAM, Disk, and GPU usage trends using a simple linear regression.

CLI flags:
  --predict   Run the prediction pipeline (generates dummy data).
  --trends    Print the calculated trend (slope & intercept) for each resource.
  --report    Print a concise human‑readable report.

The script uses only the Python standard library.
"""

import argparse
import random
import statistics
import sys


def _dummy_data(days: int = 30):
    """Generate dummy usage data for *days* days.
    Returns a list of tuples: (day_index, cpu, ram, disk, gpu).
    Values are random but deterministic per run.
    """
    random.seed(0)  # deterministic for reproducibility
    data = []
    for day in range(1, days + 1):
        cpu = random.uniform(20, 80)      # percent
        ram = random.uniform(4, 16)       # GB
        disk = random.uniform(100, 500)   # GB used
        gpu = random.uniform(0, 100)      # percent
        data.append((day, cpu, ram, disk, gpu))
    return data


def _linear_regression(x, y):
    """Return slope and intercept for simple linear regression.
    x and y are sequences of numbers of the same length.
    """
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var = sum((xi - mean_x) ** 2 for xi in x)
    slope = cov / var if var != 0 else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept


def predict_trends(data):
    """Compute linear‑regression trends for each resource.
    Returns a dict keyed by resource name with slope, intercept and the
    prediction for the next day.
    """
    days = [row[0] for row in data]
    resources = {
        "CPU": [row[1] for row in data],
        "RAM": [row[2] for row in data],
        "Disk": [row[3] for row in data],
        "GPU": [row[4] for row in data],
    }
    result = {}
    for name, values in resources.items():
        slope, intercept = _linear_regression(days, values)
        next_day = days[-1] + 1
        pred = slope * next_day + intercept
        result[name] = {
            "slope": slope,
            "intercept": intercept,
            "next_day_prediction": pred,
        }
    return result


def format_report(trends):
    lines = ["Resource usage trend predictions (linear regression):"]
    for name, info in trends.items():
        lines.append(
            f"{name}: slope={info['slope']:.4f}, next day ≈ {info['next_day_prediction']:.2f}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Predict CPU/RAM/Disk/GPU usage trends using linear regression.")
    parser.add_argument("--predict", action="store_true", help="Run the prediction pipeline.")
    parser.add_argument("--trends", action="store_true", help="Show raw trend values (slope & intercept).")
    parser.add_argument("--report", action="store_true", help="Print a short human‑readable report.")
    args = parser.parse_args()

    if not args.predict:
        parser.print_help()
        sys.exit(0)

    # 1. generate dummy historical data
    data = _dummy_data()
    # 2. compute trends
    trends = predict_trends(data)
    # 3. output according to flags
    if args.trends:
        for name, info in trends.items():
            print(f"{name} trend: slope={info['slope']:.6f}, intercept={info['intercept']:.2f}")
    if args.report:
        print(format_report(trends))


if __name__ == "__main__":
    main()
