"""Kill all telegram-bot processes and their parents."""
import subprocess, os

result = subprocess.run(
    ['wmic', 'process', 'where', "commandline like '%telegram-bot%'", 'get', 'processid'],
    capture_output=True, text=True
)
pids = [int(p.strip()) for p in result.stdout.split() if p.strip().isdigit() and int(p.strip()) != os.getpid()]
print(f'Found {len(pids)} telegram-related processes')
for pid in pids:
    try:
        subprocess.run(['taskkill', '/PID', str(pid), '/F', '/T'], capture_output=True, timeout=5)
        print(f'  Killed {pid}')
    except Exception:
        pass

# Kill nohup processes too
result2 = subprocess.run(
    ['wmic', 'process', 'where', "name='nohup.exe'", 'get', 'processid'],
    capture_output=True, text=True
)
pids2 = [int(p.strip()) for p in result2.stdout.split() if p.strip().isdigit()]
for pid in pids2:
    try:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, timeout=5)
        print(f'  Killed nohup {pid}')
    except Exception:
        pass

# Remove lock
from pathlib import Path
lock = Path('F:/BUREAU/turbo/canvas/.telegram-bot.lock')
if lock.exists():
    lock.unlink()
    print('Lock removed')
