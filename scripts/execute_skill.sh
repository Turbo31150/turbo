#!/bin/bash
# Execute un skill JARVIS par nom
# Usage: execute_skill.sh <skill_name>
# Appele par les raccourcis clavier globaux

SKILL_NAME="$1"
JARVIS_HOME="/home/turbo/jarvis"
LOG_FILE="${JARVIS_HOME}/logs/hotkey_skills.log"

mkdir -p "${JARVIS_HOME}/logs"

if [ -z "$SKILL_NAME" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERREUR: Nom de skill manquant" >> "$LOG_FILE"
    notify-send "JARVIS Hotkey" "Erreur: nom de skill manquant" -i dialog-error -t 3000
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Execution skill: $SKILL_NAME" >> "$LOG_FILE"

# Notification de debut
notify-send "JARVIS" "Skill: ${SKILL_NAME}..." -i system-run -t 2000

# Execution du skill via le module Python JARVIS
python3 -c "
import sys, asyncio, json
sys.path.insert(0, '${JARVIS_HOME}')

from src.skills import load_skills, find_skill, record_skill_use

skill_name = '${SKILL_NAME}'
skills = load_skills()

# Chercher le skill par nom exact
target = None
for s in skills:
    if s.name == skill_name:
        target = s
        break

if target is None:
    print(f'Skill \"{skill_name}\" introuvable')
    sys.exit(1)

# Executer chaque etape du skill via subprocess (mode autonome sans MCP)
import subprocess

results = []
all_ok = True

for i, step in enumerate(target.steps):
    desc = step.description or step.tool
    print(f'[{i+1}/{len(target.steps)}] {desc}...')

    # Essayer d'executer via le serveur MCP local
    try:
        import urllib.request
        payload = json.dumps({'tool': step.tool, 'args': step.args}).encode()
        req = urllib.request.Request(
            'http://127.0.0.1:8080/api/tool',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = resp.read().decode()
        results.append(f'  OK: {result[:150]}')
    except Exception as e:
        # Fallback: executer directement si c'est un bash_run
        if step.tool in ('bash_run', 'run_script'):
            cmd = step.args.get('command', step.args.get('script', ''))
            if cmd:
                try:
                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                    results.append(f'  OK: {r.stdout[:150]}')
                except Exception as e2:
                    all_ok = False
                    results.append(f'  Erreur: {e2}')
            else:
                results.append(f'  Skip: pas de commande')
        else:
            all_ok = False
            results.append(f'  Erreur MCP: {e}')

record_skill_use(skill_name, all_ok)
status = 'termine' if all_ok else 'termine avec erreurs'
print(f'\\nSkill \"{skill_name}\" {status}')
for r in results:
    print(r)
" 2>> "$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    notify-send "JARVIS" "Skill ${SKILL_NAME} termine" -i dialog-information -t 3000
else
    notify-send "JARVIS" "Skill ${SKILL_NAME} echoue (code: ${EXIT_CODE})" -i dialog-error -t 5000
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skill $SKILL_NAME termine (code: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
