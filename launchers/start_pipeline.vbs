Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """F:\BUREAU\turbo\.venv\Scripts\python.exe"" -u ""F:\BUREAU\turbo\cowork\dev\autonomous_cluster_pipeline.py"" --cycles 1000 --batch 5 --pause 3 --log", 7, False
