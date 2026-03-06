import py_compile, sys
files = [
    "src/config.py", "src/tools.py", "src/orchestrator.py",
    "src/voice_correction.py", "src/cluster_startup.py",
    "src/voice.py", "src/executor.py", "src/brain.py",
    "src/mcp_server.py", "src/commands.py", "main.py",
]
ok = 0
for f in files:
    try:
        py_compile.compile(f"F:/BUREAU/turbo/{f}", doraise=True)
        print(f"  [OK] {f}")
        ok += 1
    except py_compile.PyCompileError as e:
        print(f"  [!!] {f}: {e}")
print(f"\n{ok}/{len(files)} fichiers OK")
sys.exit(0 if ok == len(files) else 1)
