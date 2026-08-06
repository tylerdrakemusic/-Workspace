# register-skill-sync-task.ps1 — registers nightly skill-sync as a Windows Scheduled Task
# Run once as Administrator, or with Developer Mode if elevation is unavailable.

$taskName = "SkillSyncNightly"
$scriptPath = "f:\⊕Workspace\tools\sync-skills.ps1"
$logPath = "f:\⊕Workspace\logs\skill-sync-task.log"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy RemoteSigned -File `"$scriptPath`" >> `"$logPath`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Daily -At "3:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Nightly git pull + SKILL.md sync for Copilot Chat skill repos" `
    -Force

Write-Host "Registered scheduled task: $taskName (daily 3am)"
