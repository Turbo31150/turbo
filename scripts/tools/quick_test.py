"""Quick 1-cycle validation test."""
import sys
import os
sys.path.insert(0, os.path.join("F:\\BUREAU\\turbo", "src"))

from scenarios import (
    SCENARIO_TEMPLATES, _simulate_match, init_db,
    import_commands_from_code, import_skills_from_code, import_corrections_from_code,
)

init_db()
import_commands_from_code()
import_skills_from_code()
import_corrections_from_code()

total = len(SCENARIO_TEMPLATES)
passed = 0
failures = []

for sc in SCENARIO_TEMPLATES:
    name, score, mtype = _simulate_match(sc["voice_input"])
    if name and name in sc["expected"]:
        passed += 1
    else:
        failures.append(
            f"  {sc['name']}: got={name}({score:.2f}) expected={sc['expected']}"
        )

print(f"{passed}/{total} — {round(passed / total * 100, 1)}%")
for f in failures:
    print(f)
