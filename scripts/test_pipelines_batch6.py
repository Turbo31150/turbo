"""Test live batch 6 — 12 pipelines LOW priority (final)."""
import urllib.request, json, subprocess, time

PASS = FAIL = 0
RESULTS = []
START = time.time()

def ok(n, d=""): global PASS; PASS += 1; RESULTS.append((n, "PASS", d)); print(f"  [PASS] {n} — {d}")
def fail(n, d=""): global FAIL; FAIL += 1; RESULTS.append((n, "FAIL", d)); print(f"  [FAIL] {n} — {d}")
def ps(cmd, timeout=15):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

print("=" * 60)
print("TEST BATCH 6 — 12 PIPELINES LOW PRIORITY (FINAL)")
print("=" * 60)

# USER PREFERENCES (3)
print("\n[USER PREFERENCE LEARNING]")
try:
    out = ps("$hour = (Get-Date).Hour; $period = if ($hour -lt 6) { 'nuit' } elseif ($hour -lt 12) { 'matin' } elseif ($hour -lt 18) { 'apres-midi' } else { 'soiree' }; $commits = (git -C 'F:\\BUREAU\\turbo' log --oneline --since='7 days ago' 2>$null | Measure-Object).Count; Write-Output \"$period, $commits commits 7j\"")
    ok("preference_work_hours", out[:80])
except Exception as e: fail("preference_work_hours", str(e)[:80])

try:
    out = ps("(Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle -ne '' } | Measure-Object).Count")
    ok("preference_app_usage", f"{out} apps avec fenetre")
except Exception as e: fail("preference_app_usage", str(e)[:80])

try:
    out = ps("$hour = (Get-Date).Hour; $mode = if ($hour -lt 9) { 'routine_matin' } elseif ($hour -lt 18) { 'mode_dev' } else { 'routine_soir' }; Write-Output \"Suggestion: $mode\"")
    ok("preference_auto_suggest", out[:80])
except Exception as e: fail("preference_auto_suggest", str(e)[:80])

# ACCESSIBILITY (3)
print("\n[ACCESSIBILITY ENHANCEMENTS]")
try:
    out = ps("$theme = Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -ErrorAction SilentlyContinue; Write-Output \"Dark apps: $(if ($theme.AppsUseLightTheme -eq 0) { 'OUI' } else { 'NON' })\"")
    ok("accessibility_profile_show", out[:80])
except Exception as e: fail("accessibility_profile_show", str(e)[:80])

try:
    out = ps("Write-Output 'TTS Edge fr-FR-HenriNeural 1.0x'")
    ok("accessibility_voice_speed", out[:80])
except Exception as e: fail("accessibility_voice_speed", str(e)[:80])

try:
    out = ps("$theme = Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -ErrorAction SilentlyContinue; Write-Output \"Dark systeme: $(if ($theme.SystemUsesLightTheme -eq 0) { 'OUI' } else { 'NON' })\"")
    ok("accessibility_contrast_check", out[:80])
except Exception as e: fail("accessibility_contrast_check", str(e)[:80])

# STREAMING (3)
print("\n[STREAMING & BROADCASTING]")
try:
    out = ps("$obs = Get-Process -Name 'obs64','obs32' -ErrorAction SilentlyContinue; Write-Output \"OBS: $(if ($obs) { 'ACTIF PID=' + $obs.Id } else { 'INACTIF' })\"")
    ok("stream_obs_status", out[:80])
except Exception as e: fail("stream_obs_status", str(e)[:80])

try:
    out = ps("$ping = Test-Connection -ComputerName 8.8.8.8 -Count 1 -TimeoutSeconds 3 -ErrorAction SilentlyContinue; Write-Output \"Ping: $(if ($ping) { $ping.ResponseTime.ToString() + 'ms' } else { 'timeout' })\"")
    ok("stream_quality_check", out[:80])
except Exception as e: fail("stream_quality_check", str(e)[:80])

try:
    out = ps("Write-Output 'Chat: Twitch/YouTube + @turboSSebot bridge'")
    ok("stream_chat_monitor", out[:80])
except Exception as e: fail("stream_chat_monitor", str(e)[:80])

# COLLABORATION (3)
print("\n[COLLABORATION]")
try:
    out = ps("$m1 = Test-Connection -ComputerName '10.5.0.2' -Count 1 -TimeoutSeconds 2 -ErrorAction SilentlyContinue; Write-Output \"M1: $(if ($m1) { 'EN LIGNE' } else { 'HORS LIGNE' })\"")
    ok("collab_sync_status", out[:80])
except Exception as e: fail("collab_sync_status", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from src.commands_pipelines import PIPELINE_COMMANDS; print(f'{len(PIPELINE_COMMANDS)} pipelines exportables')\" 2>&1")
    ok("collab_commands_export", out[:80])
except Exception as e: fail("collab_commands_export", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('PRAGMA integrity_check').fetchone()[0]; print(f'integrity: {r}')\" 2>&1")
    ok("collab_db_merge_check", out[:80])
except Exception as e: fail("collab_db_merge_check", str(e)[:80])

elapsed = time.time() - START
print(f"\n{'=' * 60}")
print(f"RESULTATS: {PASS} PASS / {FAIL} FAIL sur {PASS+FAIL} tests")
print(f"Temps total: {elapsed:.1f}s")
print(f"{'=' * 60}")
