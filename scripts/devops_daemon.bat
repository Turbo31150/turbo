@echo off
REM JARVIS DevOps Orchestrator — Persistent Daemon
REM Runs in background via pythonw.exe (no console window)
REM Usage: devops_daemon.bat [start|stop|status]

set TURBO=/home/turbo/jarvis-m1-ops
set PYTHON=pythonw.exe
set SCRIPT=%TURBO%\scripts\devops_orchestrator.py
set PIDFILE=%TURBO%\data\devops_daemon.pid
set LOGFILE=%TURBO%\data\devops_daemon.log

if "%1"=="stop" goto :stop
if "%1"=="status" goto :status

:start
echo [JARVIS] Starting DevOps Orchestrator daemon...
REM Kill existing if running
if exist "%PIDFILE%" (
    for /f %%p in (%PIDFILE%) do taskkill /PID %%p /F >nul 2>&1
    del "%PIDFILE%"
)
REM Launch with pythonw (no console)
start /B %PYTHON% "%SCRIPT%" --daemon --interval 300 >> "%LOGFILE%" 2>&1
REM Save PID (approximate — get last pythonw)
timeout /t 2 /nobreak >nul
for /f "tokens=2" %%p in ('tasklist /FI "IMAGENAME eq pythonw.exe" /FO LIST ^| find "PID"') do set DPID=%%p
echo %DPID% > "%PIDFILE%"
echo [JARVIS] Daemon started (PID=%DPID%)
echo [JARVIS] Log: %LOGFILE%
goto :eof

:stop
if not exist "%PIDFILE%" (
    echo [JARVIS] No daemon running
    goto :eof
)
for /f %%p in (%PIDFILE%) do (
    taskkill /PID %%p /F >nul 2>&1
    echo [JARVIS] Daemon stopped (PID=%%p)
)
del "%PIDFILE%"
goto :eof

:status
if not exist "%PIDFILE%" (
    echo [JARVIS] Daemon not running
    goto :eof
)
for /f %%p in (%PIDFILE%) do (
    tasklist /FI "PID eq %%p" /FO TABLE /NH 2>nul | find "%%p" >nul
    if errorlevel 1 (
        echo [JARVIS] Daemon dead (stale PID=%%p)
        del "%PIDFILE%"
    ) else (
        echo [JARVIS] Daemon running (PID=%%p)
    )
)
goto :eof
