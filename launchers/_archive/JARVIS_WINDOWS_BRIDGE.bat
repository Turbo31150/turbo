@echo off
title JARVIS Windows Bridge
cd /d F:\BUREAU\turbo

echo [JARVIS] Windows Notification + Command Bridge
echo [JARVIS] Toast notifications + command dialog

:: Start notification daemon
start "" /min cmd /c "title JARVIS Notify && uv run python scripts/jarvis_windows_notify.py --daemon"

:: Start command listener (interactive dialog loop)
echo [JARVIS] Commander: tapez vos commandes dans la popup
uv run python scripts/jarvis_windows_listener.py --loop
