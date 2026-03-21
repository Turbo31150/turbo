# ═══════════════════════════════════════════════════════════════
# JARVIS — Create ALL Scheduled Tasks for Cowork Automation
# Run as Admin: powershell -ExecutionPolicy Bypass -File create_all_scheduled_tasks.ps1
# ═══════════════════════════════════════════════════════════════

$TURBO = 'F:\BUREAU\turbo'
$PYTHON = 'python'

# Helper function
function Create-JarvisTask {
    param($Name, $Script, $Schedule, $Interval)

    $action = switch -Regex ($Script) {
        '\.ps1$' { New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File $Script" }
        '\.py$'  { New-ScheduledTaskAction -Execute $PYTHON -Argument $Script }
        default  { New-ScheduledTaskAction -Execute $Script }
    }

    $trigger = switch ($Schedule) {
        'OnStart'  { New-ScheduledTaskTrigger -AtStartup }
        'Daily8'   { New-ScheduledTaskTrigger -Daily -At '08:00' }
        'Daily2'   { New-ScheduledTaskTrigger -Daily -At '02:00' }
        'WeeklySun' { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '03:00' }
        'WeeklyMon' { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '09:00' }
        default    {
            # Interval-based: use repetition
            $t = New-ScheduledTaskTrigger -AtStartup
            $t.Repetition = New-Object Microsoft.Management.Infrastructure.CimInstance 'MSFT_TaskRepetitionPattern','root/Microsoft/Windows/TaskScheduler'
            $t.Repetition.Interval = "PT${Interval}M"
            $t
        }
    }

    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    try {
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force
        Write-Host "[OK] $Name"
    } catch {
        Write-Host "[FAIL] $Name : $_"
    }
}

Write-Host "=== JARVIS Scheduled Tasks Creation ==="
Write-Host ""

# CRITICAL - On Start
Create-JarvisTask -Name 'JARVIS Cowork Docker'    -Script "$TURBO\scripts\start_cowork_docker.ps1" -Schedule 'OnStart'

# HIGH - Frequent intervals
Create-JarvisTask -Name 'JARVIS Cluster Health'    -Script "$TURBO\cowork\dev\cluster_heartbeat.py" -Schedule 'Interval' -Interval 1
Create-JarvisTask -Name 'JARVIS Trading Scan'      -Script "$TURBO\cowork\dev\auto_trader.py"       -Schedule 'Interval' -Interval 5
Create-JarvisTask -Name 'JARVIS GPU Monitor'       -Script "$TURBO\cowork\dev\gpu_thermal_guard.py" -Schedule 'Interval' -Interval 5
Create-JarvisTask -Name 'JARVIS Disk Watcher'      -Script "$TURBO\cowork\dev\disk_space_watcher.py" -Schedule 'Interval' -Interval 10
Create-JarvisTask -Name 'JARVIS Service Watcher'   -Script "$TURBO\cowork\dev\service_watcher.py"   -Schedule 'Interval' -Interval 5

# MEDIUM - Daily
Create-JarvisTask -Name 'JARVIS Auto Backup'       -Script "$TURBO\cowork\dev\auto_backup.py"       -Schedule 'Interval' -Interval 360
Create-JarvisTask -Name 'JARVIS Daily Report'       -Script "$TURBO\cowork\dev\daily_health_report.py" -Schedule 'Daily8'
Create-JarvisTask -Name 'JARVIS Auto Git Commit'    -Script "$TURBO\cowork\dev\auto_git_commit.py"  -Schedule 'Daily8'

# LOW - Night/Weekly
Create-JarvisTask -Name 'JARVIS Night Ops'          -Script "$TURBO\cowork\dev\night_operator.py"   -Schedule 'Daily2'
Create-JarvisTask -Name 'JARVIS Log Rotate'          -Script "$TURBO\cowork\dev\log_rotator.py"     -Schedule 'WeeklySun'
Create-JarvisTask -Name 'JARVIS Weekly PnL'          -Script "$TURBO\cowork\dev\weekly_pnl_report.py" -Schedule 'WeeklyMon'

Write-Host ""
Write-Host "=== Done: 12 tasks created ==="
