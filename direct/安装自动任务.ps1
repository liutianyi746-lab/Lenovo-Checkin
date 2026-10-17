$ErrorActionPreference = "Stop"

Get-Command node.exe -ErrorAction Stop | Out-Null
foreach ($file in @("checkin.mjs", "credentials.dpapi", "定时签到.cmd")) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $file) -PathType Leaf)) {
        throw "缺少 $file，请先完成直连版配置。"
    }
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $env:ComSpec `
    -Argument ('/d /c ""' + (Join-Path $PSScriptRoot "定时签到.cmd") + '""') `
    -WorkingDirectory $PSScriptRoot
$triggers = @(
    New-ScheduledTaskTrigger -Daily -At "00:01"
    New-ScheduledTaskTrigger -AtLogOn -User $currentUser
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "联想每日自动签到" `
    -Description "直连签到：每天 00:01 及用户登录后执行；未签到才提交并确认，日志为直连目录 checkin.log。" `
    -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force | Out-Null

if (Get-ScheduledTask -TaskName "联想签到漏跑检查" -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName "联想签到漏跑检查" | Out-Null
}

Write-Output "已安装直连任务：每天 00:01、登录后检查；无需 Codex 或模拟器。"
