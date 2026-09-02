# 漏跑签到自动恢复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 当电脑错过每天 00:01 的签到任务时，在用户登录 Windows 后自动检查当天结果，仅在未成功时补跑主程序。

**架构：** 新增独立的 `missed_checkin.py`，只负责解析当天成功日志并按需调用 `main.py`；签到导航仍全部由现有主程序执行。新增 PowerShell 安装脚本，以当前项目绝对路径注册 00:01 主任务和登录检查任务，并配置错过后尽快运行、失败重试和禁止并发。

**技术栈：** Python 3.11、pytest、Windows PowerShell ScheduledTasks、Windows 任务计划程序

---

## 文件结构

- 创建 `missed_checkin.py`：判断当天是否已经成功并按需启动 `main.py`。
- 创建 `tests/test_missed_checkin.py`：覆盖成功、漏跑、旧日志、缺失日志和退出码透传。
- 创建 `安装自动任务.ps1`：注册或更新两个 Windows 计划任务。
- 修改 `README.md`：说明登录补跑行为、安装命令和验证方法。

### 任务 1：当天成功日志识别

**文件：**
- 创建：`missed_checkin.py`
- 创建：`tests/test_missed_checkin.py`

- [ ] **步骤 1：编写失败的日期识别测试**

```python
from datetime import date
from pathlib import Path

from missed_checkin import has_success_for_date


def test_has_success_for_date_accepts_only_same_day_success(tmp_path: Path) -> None:
    log_path = tmp_path / "checkin.log"
    log_path.write_text(
        "2026-09-01 00:02:03 [SUCCESS] 签到成功\n",
        encoding="utf-8",
    )

    assert has_success_for_date(log_path, date(2026, 9, 1))
    assert not has_success_for_date(log_path, date(2026, 9, 2))


def test_has_success_for_date_rejects_info_and_missing_log(tmp_path: Path) -> None:
    log_path = tmp_path / "checkin.log"
    log_path.write_text(
        "2026-09-01 00:02:03 [INFO] 签到成功\n",
        encoding="utf-8",
    )

    assert not has_success_for_date(log_path, date(2026, 9, 1))
    assert not has_success_for_date(tmp_path / "missing.log", date(2026, 9, 1))
```

- [ ] **步骤 2：运行测试并确认因模块不存在而失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_missed_checkin.py -q`

预期：FAIL，提示 `ModuleNotFoundError: No module named 'missed_checkin'`。

- [ ] **步骤 3：实现严格的当天成功识别**

```python
from datetime import date
from pathlib import Path

SUCCESS_MESSAGES = (
    "[SUCCESS] 签到成功",
    "[SUCCESS] 今日已经签到，无需重复操作",
)


def has_success_for_date(log_path: Path, day: date) -> bool:
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError, UnicodeError):
        return False
    prefix = f"{day.isoformat()} "
    return any(
        line.startswith(prefix) and any(message in line for message in SUCCESS_MESSAGES)
        for line in lines
    )
```

- [ ] **步骤 4：运行测试确认通过**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_missed_checkin.py -q`

预期：2 passed。

### 任务 2：仅在漏跑时调用主程序

**文件：**
- 修改：`missed_checkin.py`
- 修改：`tests/test_missed_checkin.py`

- [ ] **步骤 1：编写失败的按需补跑测试**

```python
from subprocess import CompletedProcess

from missed_checkin import run_if_needed


def test_run_if_needed_skips_main_after_success(tmp_path: Path) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "checkin.log").write_text(
        "2026-09-01 00:02:03 [SUCCESS] 今日已经签到，无需重复操作\n",
        encoding="utf-8",
    )
    calls: list[tuple[list[str], Path]] = []

    result = run_if_needed(
        tmp_path,
        date(2026, 9, 1),
        "python.exe",
        lambda command, cwd: calls.append((command, cwd)),
    )

    assert result == 0
    assert calls == []


def test_run_if_needed_returns_main_exit_code(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path]] = []

    def runner(command: list[str], cwd: Path) -> CompletedProcess[str]:
        calls.append((command, cwd))
        return CompletedProcess(command, 7)

    result = run_if_needed(tmp_path, date(2026, 9, 1), "python.exe", runner)

    assert result == 7
    assert calls == [(["python.exe", "main.py"], tmp_path)]
```

- [ ] **步骤 2：运行测试并确认因函数不存在而失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_missed_checkin.py -q`

预期：FAIL，提示无法导入 `run_if_needed`。

- [ ] **步骤 3：实现补跑入口和退出码透传**

```python
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path


def run_if_needed(
    project_dir: Path,
    day: date,
    python_executable: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> int:
    if has_success_for_date(project_dir / "logs" / "checkin.log", day):
        print("今日签到已完成，无需补跑")
        return 0
    result = runner([python_executable, "main.py"], cwd=project_dir)
    return result.returncode


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    return run_if_needed(project_dir, date.today(), sys.executable, subprocess.run)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 4：运行测试确认通过**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_missed_checkin.py -q`

预期：4 passed。

- [ ] **步骤 5：提交 Python 检查器**

```powershell
git add -- missed_checkin.py tests/test_missed_checkin.py
git commit -m "增加漏跑签到检查器"
```

### 任务 3：安装 Windows 自动任务

**文件：**
- 创建：`安装自动任务.ps1`

- [ ] **步骤 1：创建可移植任务安装脚本**

```powershell
$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "未找到项目 Python：$pythonExe"
}

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

$mainAction = New-ScheduledTaskAction -Execute $pythonExe -Argument "main.py" -WorkingDirectory $projectDir
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At "00:01"
Register-ScheduledTask -TaskName "联想每日自动签到" -Action $mainAction `
    -Trigger $dailyTrigger -Principal $principal -Settings $settings -Force

$checkAction = New-ScheduledTaskAction -Execute $pythonExe -Argument "missed_checkin.py" -WorkingDirectory $projectDir
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName "联想签到漏跑检查" -Action $checkAction `
    -Trigger $logonTrigger -Principal $principal -Settings $settings -Force
```

- [ ] **步骤 2：执行安装脚本**

运行：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\安装自动任务.ps1`

预期：两个任务注册成功，命令退出码为 0。

- [ ] **步骤 3：读取并验证任务配置**

运行：

```powershell
Get-ScheduledTask -TaskName "联想每日自动签到", "联想签到漏跑检查" |
    Select-Object TaskName, State, Actions, Triggers, Settings
```

预期：主任务触发时间为 00:01，检查任务为当前用户登录时触发；两者均为 `StartWhenAvailable=True`、`MultipleInstances=IgnoreNew`、`RestartCount=3`。

- [ ] **步骤 4：提交任务安装脚本**

```powershell
git add -- 安装自动任务.ps1
git commit -m "增加登录漏跑自动任务"
```

### 任务 4：文档与最终验证

**文件：**
- 修改：`README.md`

- [ ] **步骤 1：更新自动任务说明**

在 `README.md` 的“设置每天 00:01 自动运行”章节补充：运行 `安装自动任务.ps1`；主任务错过后尽快运行；登录检查任务只在当天没有成功日志时调用主程序；两个任务均不依赖 Codex；查看任务、手动运行检查和卸载任务的 PowerShell 命令。

- [ ] **步骤 2：运行完整自动化验证**

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

预期：全部测试通过，Ruff 和 diff 检查退出码均为 0。

- [ ] **步骤 3：验证已有成功时不会启动雷电**

运行：`.\.venv\Scripts\python.exe .\missed_checkin.py`

预期：输出“今日签到已完成，无需补跑”，退出码为 0，`ldconsole.exe list2` 仍显示实例 0 未运行。

- [ ] **步骤 4：提交文档**

```powershell
git add -- README.md docs/superpowers/specs/2026-09-01-missed-checkin-recovery-design.md docs/superpowers/plans/2026-09-01-missed-checkin-recovery.md
git commit -m "说明漏跑签到自动恢复"
```
