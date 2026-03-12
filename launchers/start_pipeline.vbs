Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """/home/turbo/jarvis-m1-ops\.venv\Scripts\python.exe"" -u ""/home/turbo/jarvis-m1-ops\cowork\dev\autonomous_cluster_pipeline.py"" --cycles 1000 --batch 5 --pause 3 --log", 7, False
