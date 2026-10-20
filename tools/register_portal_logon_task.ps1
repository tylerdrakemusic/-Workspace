[CmdletBinding()]
param(
    [ValidateSet("Register", "Unregister")]
    [string]$Action = "Register"
)

$ErrorActionPreference = "Stop"

$supervisorPath = Join-Path $PSScriptRoot "portal_supervisor.py"
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$currentUserSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$pythonPath = "C:\G\python.exe"

$planJson = & $pythonPath $supervisorPath `
    "--logon-task-plan" `
    "--user-sid" $currentUserSid `
    "--workspace-root" $workspaceRoot
if ($LASTEXITCODE -ne 0) {
    throw "The supervisor could not build the logon task plan."
}
$plan = $planJson | ConvertFrom-Json

$scheduler = New-Object -ComObject Schedule.Service
$scheduler.Connect()
$folder = $scheduler.GetFolder([string]$plan.task_path)
$existingTaskXml = $null
try {
    $existingTaskXml = [string]$folder.GetTask([string]$plan.task_name).Xml
}
catch {
    $exception = $_.Exception
    while ($null -ne $exception.InnerException) {
        $exception = $exception.InnerException
    }
    if (
        $exception -isnot [System.Runtime.InteropServices.COMException] -or
        $exception.HResult.ToString("X8") -ne "80070002"
    ) {
        throw
    }
}

function Resolve-TaskOperation {
    param([AllowNull()][object]$ExistingXml = $null)

    $arguments = @(
        $supervisorPath,
        "--logon-task-operation",
        $Action.ToLowerInvariant(),
        "--user-sid",
        $currentUserSid,
        "--workspace-root",
        $workspaceRoot
    )
    if ($null -ne $ExistingXml) {
        $encodedXml = [Convert]::ToBase64String(
            [Text.Encoding]::UTF8.GetBytes($ExistingXml)
        )
        $arguments += @("--task-xml-base64", $encodedXml)
    }
    $decisionOutput = & $pythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "The existing task identity is invalid; no task state was changed."
    }
    return ($decisionOutput -join "").Trim()
}

$decision = Resolve-TaskOperation -ExistingXml $existingTaskXml
switch ($decision) {
    "noop" {
        Write-Output "The current-user portal logon task already matches the intended contract."
        return
    }
    "register" {
        $null = $folder.RegisterTask(
            [string]$plan.task_name,
            [string]$plan.task_xml,
            2,
            $currentUserSid,
            $null,
            3,
            $null
        )
        Write-Output "Registered the current-user portal logon task."
        return
    }
    "unregister" {
        $freshTaskXml = [string]$folder.GetTask([string]$plan.task_name).Xml
        $freshDecision = Resolve-TaskOperation -ExistingXml $freshTaskXml
        if ($freshDecision -ne "unregister") {
            throw "The task identity changed during rollback; it was not removed."
        }
        $folder.DeleteTask([string]$plan.task_name, 0)
        Write-Output "Unregistered the matching current-user portal logon task."
        return
    }
    default {
        throw "Unexpected task operation '$decision'; no task state was changed."
    }
}