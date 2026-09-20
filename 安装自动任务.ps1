$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
$mainScript = Join-Path $projectDir "main.py"
$checkScript = Join-Path $projectDir "missed_checkin.py"

foreach ($requiredFile in @($pythonExe, $mainScript, $checkScript)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "未找到自动任务所需文件：$requiredFile"
    }
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

$mainAction = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument ('"' + $mainScript + '"') `
    -WorkingDirectory $projectDir
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At "00:01"
$mainTaskParameters = @{
    TaskName = "联想每日自动签到"
    Description = "每天 00:01 自动签到；错过后尽快运行，失败最多重试 3 次。"
    Action = $mainAction
    Trigger = $dailyTrigger
    Principal = $principal
    Settings = $settings
    Force = $true
}
Register-ScheduledTask @mainTaskParameters | Out-Null

$checkAction = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument ('"' + $checkScript + '"') `
    -WorkingDirectory $projectDir
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$checkTaskParameters = @{
    TaskName = "联想签到漏跑检查"
    Description = "用户登录 Windows 后检查当天签到结果；仅在尚未成功时补跑。"
    Action = $checkAction
    Trigger = $logonTrigger
    Principal = $principal
    Settings = $settings
    Force = $true
}
Register-ScheduledTask @checkTaskParameters | Out-Null

Write-Output "已安装：联想每日自动签到（每天 00:01）"
Write-Output "已安装：联想签到漏跑检查（用户登录时）"
