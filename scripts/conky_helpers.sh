#!/bin/bash
# Helpers pour les widgets Conky JARVIS
# Usage: conky_helpers.sh [voice_analytics|db_status|trading_signals|macros]

JARVIS_HOME="/home/turbo/jarvis"
cd "$JARVIS_HOME" 2>/dev/null || exit 1

case "${1}" in
    voice_analytics)
        python3 -c "
from src.voice_learning import analyze_failures
a = analyze_failures(24)
if a.get('total', 0) > 0:
    print(f'  Cmds 24h: {a[\"total\"]}')
    print(f'  Success:  {a[\"success_rate\"]}%')
    print(f'  Latence:  {a[\"avg_latency_ms\"]}ms')
else:
    print('  Pas de donnees')
" 2>/dev/null
        ;;
    db_status)
        python3 -c "
from src.db_boot_validator import validate_all_databases
r = validate_all_databases(repair=False)
s = r['summary']
vc = r.get('voice_cache', {})
print(f'  {s[\"ok\"]}/{s[\"total\"]} OK ({r[\"duration_ms\"]}ms)')
print(f'  Corrections: {len(vc.get(\"corrections\", {}))}')
print(f'  Cmds SQL:    {vc.get(\"commands_count\", 0)}')
print(f'  Skills:      {vc.get(\"skills_count\", 0)}')
" 2>/dev/null
        ;;
    trading_signals)
        python3 -c "
import sqlite3
conn = sqlite3.connect('data/sniper.db')
try:
    rows = conn.execute('SELECT symbol, type FROM signals ORDER BY ts DESC LIMIT 3').fetchall()
    for r in rows: print(f'  {r[0]}: {r[1]}')
    if not rows: print('  Aucun signal')
except: print('  DB offline')
conn.close()
" 2>/dev/null
        ;;
    macros)
        python3 -c "
import sqlite3, json
try:
    conn = sqlite3.connect('data/jarvis.db')
    rows = conn.execute('SELECT name, commands, usage_count FROM voice_macros ORDER BY usage_count DESC LIMIT 5').fetchall()
    conn.close()
    if rows:
        for r in rows:
            cmds = json.loads(r[1])
            print(f'  {r[0]}: {len(cmds)}cmd ({r[2]}x)')
    else:
        print('  Aucune macro')
except: print('  Aucune macro')
" 2>/dev/null
        ;;
    *)
        echo "Usage: $0 {voice_analytics|db_status|trading_signals|macros}"
        ;;
esac
