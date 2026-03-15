"""Seed learned_actions.db avec les dominos Linux."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from src.learned_actions import LearnedActionsEngine
from src.domino_pipelines_linux import LINUX_PIPELINES


def main():
    engine = LearnedActionsEngine()
    count = 0
    for name, pipeline in LINUX_PIPELINES.items():
        try:
            engine.save_action(
                canonical_name=name,
                category=pipeline["category"],
                platform="linux",
                trigger_phrases=pipeline["triggers"],
                pipeline_steps=pipeline["steps"],
                learned_from="seed_dominos_linux",
            )
            count += 1
            print(f"  OK: {name} ({len(pipeline['triggers'])} triggers)")
        except Exception as e:
            print(f"  FAIL: {name} — {e}")
    print(f"\n{count}/{len(LINUX_PIPELINES)} dominos seedés dans learned_actions.db")


if __name__ == "__main__":
    main()
