# IBD Weekly Digest — Windows Task Scheduler installer
# Run once as Administrator: powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Script   = Join-Path $RepoRoot "scripts\ibd_digest.py"
$TaskName = "IBD Weekly Digest"

# Verify Python exists
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python — activate venv first."
    exit 1
}

# Install Playwright chromium browser
Write-Host "Installing Playwright chromium..." -ForegroundColor Cyan
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Error "playwright install chromium failed"; exit 1 }

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'."
}

# Create trigger: weekly, every Monday at 06:00
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "06:00AM"

# Action: run python scripts/ibd_digest.py from repo root
# Script path is double-quoted in case it contains spaces
$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`"" `
    -WorkingDirectory $RepoRoot

# Settings: stop if runs > 2 hours, start if missed
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RunOnlyIfNetworkAvailable `
    -StartWhenAvailable

# Principal: run only when user is logged on interactively (required for headless=False fallback)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# Register task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Force

Write-Host "`nTask '$TaskName' registered successfully." -ForegroundColor Green
Write-Host "It will run every Monday at 06:00 AM when you are logged on."
Write-Host "`nTo test immediately:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
