"""
JARVIS v3.5 Auto-Learning - CRASH TEST COGNITIF
Valide le pipeline complet: Normalisation -> Fallback -> M2 sim -> Log -> Learn -> Report
46 tests couvrant tous les composants du systeme d'auto-apprentissage.
"""
import sys
import os
import sqlite3
import time

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
DB_PATH = os.path.join(ROOT, "database", "trading.db")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "voice_system"))

# ================================================================
# TEST FRAMEWORK
# ================================================================
PASSED = 0
FAILED = 0
TOTAL = 0

def test(name, condition, detail=""):
    global PASSED, FAILED, TOTAL
    TOTAL += 1
    if condition:
        PASSED += 1
        print(f"  [{TOTAL:02d}] PASS  {name}")
    else:
        FAILED += 1
        print(f"  [{TOTAL:02d}] FAIL  {name} {f'-- {detail}' if detail else ''}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ================================================================
# PHASE 0: CLEANUP - Etat propre pour les tests
# ================================================================
section("PHASE 0: CLEANUP")

conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM command_history WHERE session_id LIKE 'TEST_%'")
conn.execute("DELETE FROM learned_patterns WHERE source LIKE 'test_%'")
conn.commit()
conn.close()
print("  Etat propre pour les tests.")


# ================================================================
# PHASE 1: LEARNING ENGINE MODULE
# ================================================================
section("PHASE 1: LEARNING ENGINE - Module")

from learning_engine import (
    init_db, log_command, get_stats, report, analyze_failures,
    auto_expand_fallback, suggest_genesis_tools, get_learned_patterns,
    increment_pattern_use, add_learned_pattern, SESSION_ID,
)
import learning_engine
original_session = learning_engine.SESSION_ID
learning_engine.SESSION_ID = "TEST_001"

# T01: init_db
ok = init_db()
test("init_db() retourne True", ok)

# T02-03: Tables existent
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
test("Table command_history existe", cur.fetchone() is not None)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'")
test("Table learned_patterns existe", cur.fetchone() is not None)

# T04: Schema command_history
cur.execute("PRAGMA table_info(command_history)")
cols = {r[1] for r in cur.fetchall()}
expected = {"id", "timestamp", "session_id", "raw_text", "intent_source", "action",
            "params", "m2_latency_ms", "exec_success", "exec_error", "exec_latency_ms"}
test("Schema command_history complet", expected.issubset(cols), f"manque: {expected - cols}")

# T05: Schema learned_patterns
cur.execute("PRAGMA table_info(learned_patterns)")
cols = {r[1] for r in cur.fetchall()}
expected = {"id", "created_at", "pattern_text", "action", "params", "source",
            "confidence", "usage_count", "last_used"}
test("Schema learned_patterns complet", expected.issubset(cols), f"manque: {expected - cols}")
conn.close()

# T06-08: log_command
log_command("ouvre chrome", "FALLBACK_LOCAL", "OPEN_APP", "chrome", 0, True, None, 45)
log_command("scan le marche", "M2", "RUN_SCAN", "", 6200, True, None, 120)
log_command("fais un truc bizarre", "UNKNOWN", "UNKNOWN", "", 8000, False, "not recognized", 0)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM command_history WHERE session_id='TEST_001'")
count = cur.fetchone()[0]
test("log_command: 3 entries inserees", count == 3, f"got {count}")

# T09: intent_source tracking
cur.execute("SELECT DISTINCT intent_source FROM command_history WHERE session_id='TEST_001' ORDER BY intent_source")
sources = sorted([r[0] for r in cur.fetchall()])
test("log_command: sources FALLBACK/M2/UNKNOWN", sources == ["FALLBACK_LOCAL", "M2", "UNKNOWN"], f"got {sources}")

# T10: exec_success = 0 pour echec
cur.execute("SELECT exec_success FROM command_history WHERE session_id='TEST_001' AND action='UNKNOWN'")
test("log_command: exec_success=0 pour echec", cur.fetchone()[0] == 0)
conn.close()


# ================================================================
# PHASE 2: STATS & REPORT
# ================================================================
section("PHASE 2: STATS & REPORT")

stats = get_stats(24)
test("get_stats() retourne un dict", isinstance(stats, dict))
test("get_stats: total >= 3", stats.get("total", 0) >= 3, f"got {stats.get('total')}")
test("get_stats: success_rate presente", "success_rate" in stats)
test("get_stats: sources dict present", isinstance(stats.get("sources"), dict))
test("get_stats: top_actions present", isinstance(stats.get("top_actions"), list))

r = report()
test("report() retourne du texte", len(r) > 50, f"got {len(r)} chars")
test("report: contient 'JARVIS Stats'", "JARVIS Stats" in r)
test("report: contient 'Succes'", "Succes" in r)


# ================================================================
# PHASE 3: LEARNED PATTERNS
# ================================================================
section("PHASE 3: LEARNED PATTERNS")

ok = add_learned_pattern("test montre cpu", "CHECK_SYSTEM", "", "test_auto", 0.8)
test("add_learned_pattern: retourne True", ok)

patterns = get_learned_patterns()
found = any(p["pattern_text"] == "test montre cpu" for p in patterns)
test("get_learned_patterns: pattern retrouve", found)

increment_pattern_use("test montre cpu")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT usage_count FROM learned_patterns WHERE pattern_text='test montre cpu'")
row = cur.fetchone()
test("increment_pattern_use: usage_count >= 1", row and row[0] >= 1, f"got {row}")

cur.execute("SELECT last_used FROM learned_patterns WHERE pattern_text='test montre cpu'")
row = cur.fetchone()
test("increment_pattern_use: last_used non null", row and row[0] is not None)
conn.close()


# ================================================================
# PHASE 4: AUTO-EXPAND FALLBACK
# ================================================================
section("PHASE 4: AUTO-EXPAND FALLBACK")

for i in range(4):
    log_command("mets le wifi", "M2", "SETTINGS", "", 5000, True, None, 80)

n = auto_expand_fallback()
test("auto_expand_fallback: >= 1 pattern ajoute", n >= 1, f"got {n}")

patterns = get_learned_patterns()
found = any(p["pattern_text"] == "mets le wifi" for p in patterns)
test("auto_expand: 'mets le wifi' dans learned_patterns", found)

n2 = auto_expand_fallback()
test("auto_expand: re-run ne duplique pas", n2 == 0, f"got {n2}")


# ================================================================
# PHASE 5: ANALYZE FAILURES
# ================================================================
section("PHASE 5: ANALYZE FAILURES")

for i in range(4):
    log_command("danse le moonwalk", "UNKNOWN", "UNKNOWN", "", 7000, False, "unknown cmd", 0)

failures = analyze_failures()
test("analyze_failures: detecte echecs repetitifs", len(failures) >= 1)

found = any("moonwalk" in f[0] for f in failures)
test("analyze_failures: 'moonwalk' detecte", found, f"got {failures}")

n = suggest_genesis_tools()
test("suggest_genesis_tools: >= 1 suggestion", n >= 1, f"got {n}")


# ================================================================
# PHASE 6: COMMANDER V2 - Code Analysis
# ================================================================
section("PHASE 6: COMMANDER V2 - Code Analysis")

commander_path = os.path.join(ROOT, "voice_system", "commander_v2.py")
with open(commander_path, "r", encoding="utf-8") as f:
    source = f.read()

test("commander_v2: version 3.5", "v3.5" in source)
test("commander_v2: import learning_engine", "from learning_engine import" in source)
test("commander_v2: execute_command_tracked()", "def execute_command_tracked" in source)
test("commander_v2: _check_learned_engine()", "def _check_learned_engine" in source)
test("commander_v2: _le_log_command dans process_input", "_le_log_command(" in source)
test("commander_v2: action JARVIS_REPORT", 'action == "JARVIS_REPORT"' in source)
test("commander_v2: action JARVIS_LEARN", 'action == "JARVIS_LEARN"' in source)
test("commander_v2: LEARNING_ENGINE_OK flag", "LEARNING_ENGINE_OK" in source)
test("commander_v2: intent_source tracking", "intent_source" in source)
test("commander_v2: m2_latency_ms tracking", "m2_latency_ms" in source)
test("commander_v2: PRIORITY 'rapport jarvis'", '"rapport jarvis"' in source)
test("commander_v2: PRIORITY 'auto-amelioration'", '"auto-amelioration"' in source)
test("commander_v2: PRIORITY 'comment tu vas'", '"comment tu vas"' in source)


# ================================================================
# PHASE 7: OS_PILOT RETURN VALUES
# ================================================================
section("PHASE 7: OS_PILOT RETURN VALUES")

pilot_path = os.path.join(ROOT, "scripts", "os_pilot.py")
with open(pilot_path, "r", encoding="utf-8") as f:
    pilot_source = f.read()

test("os_pilot: return 'OK' present", 'return "OK"' in pilot_source)
test("os_pilot: return UNKNOWN_ACTION", 'return f"UNKNOWN_ACTION' in pilot_source)
test("os_pilot: return ERROR pour exceptions", 'return f"ERROR: {e}"' in pilot_source)


# ================================================================
# PHASE 8: LIVE MODULE IMPORT (commander_v2)
# ================================================================
section("PHASE 8: LIVE MODULE IMPORT")

import importlib.util
spec = importlib.util.spec_from_file_location("commander", commander_path)
cmd = importlib.util.module_from_spec(spec)

# Patch pilot avant import pour eviter pyautogui side-effects
executed_actions = []
spec.loader.exec_module(cmd)
_orig_pilot = cmd.os_pilot.run_command
def mock_pilot(intent, params=None):
    executed_actions.append({"action": intent, "params": params})
    if intent == "CHECK_SYSTEM":
        return {"cpu_pct": 25, "ram_pct": 60, "ram_used_gb": 9.6, "ram_total_gb": 16, "disks": {}}
    if intent == "LIST_APPS":
        return [{"name": "test.exe", "pid": 1, "mem_mb": 100}]
    return "OK"
cmd.os_pilot.run_command = mock_pilot

speak_texts = []
def mock_speak(text):
    speak_texts.append(text)
cmd.speak = mock_speak

# T42: normalize_speech fonctionne
r = cmd.normalize_speech("euh est-ce que tu peux ouvrir crome s'il te plait")
test("normalize_speech: full pipeline", r == "ouvrir chrome", f"got '{r}'")

# T43: local_fallback fonctionne
r = cmd.local_fallback("nouvel onglet")
test("local_fallback: 'nouvel onglet' -> NEW_TAB", r and r["action"] == "NEW_TAB")

# T44: JARVIS_REPORT dans priority patterns
r = cmd.local_fallback("rapport jarvis")
test("local_fallback: 'rapport jarvis' -> JARVIS_REPORT", r and r["action"] == "JARVIS_REPORT")

# T45: JARVIS_LEARN dans priority patterns
r = cmd.local_fallback("auto-amelioration")
test("local_fallback: 'auto-amelioration' -> JARVIS_LEARN", r and r["action"] == "JARVIS_LEARN")

# T46: LEARNING_ENGINE_OK flag actif
test("LEARNING_ENGINE_OK = True", cmd.LEARNING_ENGINE_OK is True)


# ================================================================
# CLEANUP
# ================================================================
section("CLEANUP")

conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM command_history WHERE session_id='TEST_001'")
conn.execute("DELETE FROM learned_patterns WHERE source LIKE 'test_%'")
conn.execute("DELETE FROM learned_patterns WHERE pattern_text IN ('mets le wifi', 'test montre cpu', 'danse le moonwalk')")
conn.commit()
conn.close()
learning_engine.SESSION_ID = original_session
print("  Donnees de test nettoyees.")


# ================================================================
# RAPPORT FINAL
# ================================================================
print(f"\n{'='*60}")
print(f"  RESULTATS CRASH TEST COGNITIF - JARVIS v3.5")
print(f"{'='*60}")
print(f"  Total:  {TOTAL}")
print(f"  Pass:   {PASSED}")
print(f"  Fail:   {FAILED}")
pct = round(PASSED / TOTAL * 100, 1) if TOTAL > 0 else 0
print(f"  Score:  {pct}%")
print(f"{'='*60}")

if FAILED == 0:
    print(f"\n  >>> TOUS LES TESTS PASSENT ({TOTAL}/{TOTAL}) <<<")
    print(f"  >>> JARVIS v3.5 Auto-Learning: PRET POUR PRODUCTION <<<\n")
else:
    print(f"\n  !!! {FAILED} TEST(S) EN ECHEC !!!")
    print(f"  !!! Corriger avant deploiement !!!\n")

sys.exit(0 if FAILED == 0 else 1)
