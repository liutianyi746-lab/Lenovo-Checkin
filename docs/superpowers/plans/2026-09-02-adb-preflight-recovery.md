# ADB 启动前恢复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在每次签到启动雷电前恢复雷电自带 ADB；常规停止失败时只终止可执行路径完全匹配的雷电 ADB 进程。

**架构：** `emulator.py` 提供独立的 Windows 精确路径进程清理函数，并由 `LDPlayerManager.reset_adb_server()` 协调 `kill-server`、安全兜底清理和 `start-server`。`main.py` 在 `ensure_running()` 前调用恢复方法，页面导航和签到逻辑保持不变。

**技术栈：** Python 3.11、pytest、Windows PowerShell/CIM、ADB、Ruff

---

## 文件结构

- 修改 `emulator.py`：新增精确路径进程清理和 ADB 预检恢复方法。
- 修改 `main.py`：在雷电启动前调用 ADB 预检恢复。
- 修改 `tests/test_emulator.py`：覆盖正常恢复、超时兜底、路径安全和失败停止。
- 修改 `README.md`：说明启动前 ADB 自动恢复和安全边界。

### 任务 1：精确路径进程清理边界

**文件：**
- 修改：`emulator.py`
- 修改：`tests/test_emulator.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_stop_processes_by_executable_passes_resolved_path_as_argument(tmp_path: Path) -> None:
    adb = tmp_path / "adb.exe"
    adb.touch()
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "", "")

    stop_processes_by_executable(adb, runner=runner)

    assert calls[0][0][-1] == str(adb.resolve())
    assert "ExecutablePath" in calls[0][0][-2]
    assert "Stop-Process" in calls[0][0][-2]
    assert "/IM" not in " ".join(calls[0][0])
```

- [ ] **步骤 2：运行并确认失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_emulator.py::test_stop_processes_by_executable_passes_resolved_path_as_argument -q`

预期：FAIL，无法导入 `stop_processes_by_executable`。

- [ ] **步骤 3：实现精确路径清理函数**

```python
def stop_processes_by_executable(
    executable: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    if os.name != "nt":
        raise EmulatorError("ADB 强制恢复仅支持 Windows")
    target = executable.expanduser().resolve()
    script = (
        "$target=[IO.Path]::GetFullPath($args[0]);"
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.ExecutablePath -and "
        "[StringComparer]::OrdinalIgnoreCase.Equals("
        "[IO.Path]::GetFullPath($_.ExecutablePath),$target)};"
        "$items | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }"
    )
    try:
        result = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise EmulatorError("无法精确清理雷电 ADB 进程") from exc
    if result.returncode != 0:
        raise EmulatorError(f"精确清理雷电 ADB 失败：{result.stderr.strip()}")
```

- [ ] **步骤 4：运行测试确认通过**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_emulator.py::test_stop_processes_by_executable_passes_resolved_path_as_argument -q`

预期：1 passed。

### 任务 2：ADB 预检恢复

**文件：**
- 修改：`emulator.py`
- 修改：`tests/test_emulator.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_reset_adb_server_uses_normal_restart_without_forced_cleanup(tmp_path: Path) -> None:
    calls = []
    cleaned = []
    adb = tmp_path / "adb.exe"
    adb.touch()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"adb:\n  executable_path: '{adb}'\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )

    def runner(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    manager = LDPlayerManager(
        load_config(config_file),
        runner=runner,
        process_cleaner=cleaned.append,
    )

    manager.reset_adb_server()

    assert [call[-1] for call in calls] == ["kill-server", "start-server"]
    assert cleaned == []


def test_reset_adb_server_cleans_exact_path_after_kill_timeout(tmp_path: Path) -> None:
    cleaned = []
    adb = tmp_path / "adb.exe"
    adb.touch()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"adb:\n  executable_path: '{adb}'\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )

    def runner(args, **kwargs):
        if args[-1] == "kill-server":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        return subprocess.CompletedProcess(args, 0, "", "")

    manager = LDPlayerManager(
        load_config(config_file),
        runner=runner,
        process_cleaner=cleaned.append,
    )

    manager.reset_adb_server()

    assert cleaned == [(tmp_path / "adb.exe").resolve()]
```

- [ ] **步骤 2：运行并确认失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_emulator.py -k "reset_adb_server" -q`

预期：FAIL，构造函数不接受 `process_cleaner` 或方法不存在。

- [ ] **步骤 3：实现恢复方法**

```python
class LDPlayerManager:
    def __init__(
        self,
        config: Config,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        sleeper: Callable[[float], None] = time.sleep,
        process_cleaner: Callable[[Path], None] = stop_processes_by_executable,
    ) -> None:
        self.process_cleaner = process_cleaner

    def reset_adb_server(self) -> None:
        adb = Path(self.find_adb_executable()).expanduser().resolve()
        try:
            stopped = self._run([str(adb), "kill-server"])
            if stopped.returncode != 0:
                raise EmulatorError(f"adb kill-server 失败：{stopped.stderr.strip()}")
        except EmulatorError as exc:
            self.logger.warning("常规停止 ADB 失败，执行精确路径清理：%s", exc)
            self.process_cleaner(adb)
        started = self._run([str(adb), "start-server"])
        if started.returncode != 0:
            raise EmulatorError(f"adb start-server 失败：{started.stderr.strip()}")
```

- [ ] **步骤 4：补充失败停止测试**

测试 `process_cleaner` 抛出 `EmulatorError` 和 `start-server` 返回非零时，`reset_adb_server()` 都抛出 `EmulatorError`。

- [ ] **步骤 5：运行测试确认通过**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_emulator.py -q`

预期：所有模拟器测试通过。

- [ ] **步骤 6：提交恢复实现**

```powershell
git add -- emulator.py tests/test_emulator.py
git commit -m "增加 ADB 启动前安全恢复"
```

### 任务 3：接入主流程并验证

**文件：**
- 修改：`main.py`
- 修改：`tests/test_main.py`
- 修改：`README.md`

- [ ] **步骤 1：编写失败的调用顺序测试**

```python
def test_run_resets_adb_before_ensuring_emulator(monkeypatch, tmp_path) -> None:
    events = []
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )

    class FakeManager:
        def __init__(self, config) -> None:
            del config

        def reset_adb_server(self) -> None:
            events.append("reset")

        def ensure_running(self) -> str:
            events.append("ensure")
            raise RuntimeError("stop after order check")

    monkeypatch.setattr(main_module, "LDPlayerManager", FakeManager)

    assert main_module.run(load_config(config_file)) == 1
    assert events == ["reset", "ensure"]
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests\test_main.py -q`

预期：FAIL，事件中缺少 `reset_adb_server`。

- [ ] **步骤 3：接入主流程**

```python
manager = LDPlayerManager(config)
manager.reset_adb_server()
address = manager.ensure_running()
```

- [ ] **步骤 4：更新 README**

在故障恢复说明中写明：任务启动前自动重启雷电 ADB；常规停止卡死时只清理配置路径完全匹配的 ADB，不影响其他目录的 Android 工具。

- [ ] **步骤 5：运行完整验证**

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

预期：全部测试、Ruff 和 diff 检查通过。

- [ ] **步骤 6：真实补跑验证**

运行 `.\.venv\Scripts\python.exe .\missed_checkin.py`。由于今天已有成功记录，预期输出“今日签到已完成，无需补跑”且不启动雷电。随后直接运行 `main.py`，预期识别“今日已经签到，无需重复操作”、退出码 0，并关闭雷电；保存结果截图/XML。

- [ ] **步骤 7：提交接入和文档**

```powershell
git add -- main.py tests/test_main.py README.md docs/superpowers/specs/2026-09-02-adb-preflight-recovery-design.md docs/superpowers/plans/2026-09-02-adb-preflight-recovery.md
git commit -m "接入 ADB 启动前恢复"
```
