@echo off
:: JARVIS LinkedIn Scheduler — Auto-publish daemon
:: Checks every 5min, publishes due posts, auto-refills queue
::
:: Usage:
::   JARVIS_LINKEDIN.bat           : Daemon mode (continuous)
::   JARVIS_LINKEDIN.bat once      : Single check (for Task Scheduler)
::   JARVIS_LINKEDIN.bat routine   : Full daily routine
::   JARVIS_LINKEDIN.bat generate  : Generate 5 posts in advance

set PYTHONIOENCODING=utf-8
cd /d F:\BUREAU\turbo\cowork\dev

if "%1"=="once" (
    python linkedin_scheduler.py --once --method all
    goto :eof
)

if "%1"=="routine" (
    python linkedin_auto_routine.py --once
    goto :eof
)

if "%1"=="generate" (
    python linkedin_scheduler.py --generate 5
    goto :eof
)

:: Default: daemon mode — singleton guard
cd /d F:\BUREAU\turbo
python scripts/singleton_guard.py --name linkedin --kill
cd /d F:\BUREAU\turbo\cowork\dev

echo JARVIS LinkedIn Scheduler - Daemon Mode
echo Press Ctrl+C to stop
python linkedin_scheduler.py --run --method all
