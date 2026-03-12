"""Export the full JARVIS SQL database to JSON."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database import export_full_db

data = export_full_db()
out = Path(__file__).resolve().parent / "data" / "jarvis_export.json"
out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

stats = data["stats"]
cmds = stats["commands"]
skills = stats["skills"]
corr = stats["corrections"]
scen = stats["scenarios"]
cycles = stats["validation_cycles"]
rate = stats["validation_pass_rate"]
size = out.stat().st_size / 1024

print(f"Export: {cmds} commandes, {skills} skills, {corr} corrections")
print(f"Scenarios: {scen} | Validation cycles: {cycles}")
print(f"Pass rate: {rate}%")
print(f"Fichier: {out} ({size:.0f} KB)")
