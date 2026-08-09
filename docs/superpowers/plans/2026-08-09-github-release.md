# 联想签到器 GitHub 发布实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Windows 联想 App 自动签到项目安全地发布为名为“联想签到器”的公开 GitHub 仓库，并提供可独立照做的中文使用指南。

**Architecture:** 保留现有 Python、ADB、uiautomator2 和雷电模拟器自动化结构。新增本机私有配置优先级，让公开的 `config.yaml` 使用通用自动发现值，而本机计划任务继续通过被 Git 忽略的 `config.local.yaml` 使用实际安装路径；运行产物和账号现场始终排除在仓库之外。

**Tech Stack:** Python 3.11+、PyYAML、uiautomator2、pytest、Ruff、Git、GitHub CLI、Windows 任务计划程序

## Global Constraints

- GitHub 仓库名必须为“联想签到器”，可见性为公开。
- README 只提供用户指定的第三方 APK 链接 `https://www.downxia.com/downinfo/143337.html`，不提供联想官方 Android 页面。
- 仓库不上传 APK 文件，不上传账号信息、日志、截图、hierarchy XML、缓存或本机绝对路径。
- 自动化遇到验证码、滑块、短信、设备验证、账号安全验证或风控时必须保存现场并停止，不得绕过。
- 本机现有每日 14:00 计划任务必须继续能读取真实的雷电和 ADB 路径，并在运行后关闭模拟器。

---

### Task 1: 配置隔离

**Files:**
- Modify: `main.py`
- Modify: `tests/test_config.py`
- Modify: `.gitignore`
- Modify: `config.yaml`
- Create locally but ignore: `config.local.yaml`

**Interfaces:**
- Consumes: `load_config(path: str | Path) -> Config`
- Produces: `resolve_config_path(project_dir: Path) -> Path`，优先返回存在的 `config.local.yaml`，否则返回 `config.yaml`

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_config_path_prefers_local_file(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "config.local.yaml").write_text("{}", encoding="utf-8")
    assert resolve_config_path(tmp_path) == tmp_path / "config.local.yaml"


def test_resolve_config_path_falls_back_to_public_file(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("{}", encoding="utf-8")
    assert resolve_config_path(tmp_path) == tmp_path / "config.yaml"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`

Expected: FAIL because `resolve_config_path` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def resolve_config_path(project_dir: Path) -> Path:
    local = project_dir / "config.local.yaml"
    return local if local.is_file() else project_dir / "config.yaml"
```

Update `main()` to call `load_config(resolve_config_path(Path(__file__).parent))`. Add `config.local.yaml` to `.gitignore`, copy the existing absolute-path settings into that local file, and replace tracked `config.yaml` executable paths with `auto` and `adb`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`

Expected: all config tests PASS.

### Task 2: Windows 首次配置和日志查看入口

**Files:**
- Create: `setup_config.py`
- Create: `view_log.py`
- Create: `首次配置.bat`
- Create: `查看日志.bat`
- Create: `tests/test_setup_config.py`
- Create: `tests/test_view_log.py`

**Interfaces:**
- Produces: `write_local_config(project_dir: Path, ldplayer_path: Path, adb_path: Path, overwrite: bool = False) -> Path`
- Produces: `open_checkin_log(project_dir: Path, opener: Callable[[Path], object]) -> Path`

- [ ] **Step 1: Write failing tests for configuration generation**

Test that valid player and ADB files generate loadable `config.local.yaml`, missing executables raise a clear error without creating a file, and overwrite requires explicit permission.

- [ ] **Step 2: Run configuration tests and verify failure**

Run: `python -m pytest tests/test_setup_config.py -q`

Expected: FAIL because `setup_config` does not exist.

- [ ] **Step 3: Implement configuration helper and batch launcher**

Write YAML with quoted Windows paths, preserve instance 0 and `close_after_run: true`, auto-detect an `adb.exe` beside the selected player, and let `首次配置.bat` invoke the interactive Python entrypoint.

- [ ] **Step 4: Write and verify failing log-viewer tests**

Test that an existing `logs/checkin.log` is passed to the opener and a missing log raises a user-facing error.

Run: `python -m pytest tests/test_view_log.py -q`

Expected: FAIL because `view_log` does not exist.

- [ ] **Step 5: Implement log viewer and batch launcher**

Open the resolved log path with Notepad, return zero on success, and print a clear Chinese message with a non-zero exit code when no log exists.

- [ ] **Step 6: Run both test modules**

Run: `python -m pytest tests/test_setup_config.py tests/test_view_log.py -q`

Expected: all helper tests PASS.

### Task 3: 中文使用指南与发布元数据

**Files:**
- Rewrite: `README.md`
- Create: `LICENSE`
- Create: `logs/.gitkeep`
- Create: `screenshots/.gitkeep`
- Create: `dumps/.gitkeep`

**Interfaces:**
- Consumes: repository files and `config.yaml`
- Produces: end-user installation, first-run, daily-run, result-checking, scheduling, troubleshooting, privacy and risk instructions

- [ ] **Step 1: Rewrite README with exact user workflow**

Document Python 3.11+, 雷电模拟器, ADB, dependency installation, the user-selected APK link, login preparation, `python main.py`, the two success log messages, output paths, Task Scheduler setup at 14:00, emulator shutdown, security challenge behavior, and troubleshooting. Clearly label the APK page as a third-party source and state that this repository does not distribute the APK.

- [ ] **Step 2: Add MIT license and retained output directories**

Create the MIT license and empty `.gitkeep` files while keeping generated artifacts ignored.

- [ ] **Step 3: Scan documentation and tracked candidates**

Run: `rg -n -i "32916|C:\\\\Users|D:\\\\|codex|lenovo147|token|password|secret" -g "!config.local.yaml" -g "!logs/**" -g "!screenshots/**" -g "!dumps/**" .`

Expected: no personal path, account identifier, token, password, or secret in publishable files.

Document `首次配置.bat` and `查看日志.bat`, including direct and real-time PowerShell log viewing.

### Task 4: 验证并创建公开 GitHub 仓库

**Files:**
- Create: `.git/` repository metadata
- Publish: all explicitly reviewed source, tests, docs and safe configuration files

**Interfaces:**
- Consumes: clean local release tree and authenticated GitHub CLI
- Produces: public GitHub repository `联想签到器` on the authenticated account

- [ ] **Step 1: Run complete verification**

Run: `python -m pytest -q`

Expected: all tests PASS with exit code 0.

Run: `python -m ruff check .`

Expected: no lint errors, exit code 0.

- [ ] **Step 2: Verify GitHub prerequisites**

Run: `gh --version` and `gh auth status`.

Expected: GitHub CLI is installed and the intended account is authenticated.

- [ ] **Step 3: Initialize and inspect repository scope**

Run: `git init -b main`, then explicitly stage source, tests, documentation, dependency files, safe configuration and `.gitkeep` files. Inspect `git status --short` and `git diff --cached --stat`; confirm no APK, logs, screenshots, XML, caches or `config.local.yaml` is staged.

- [ ] **Step 4: Commit and publish**

Run: `git commit -m "发布联想签到器"`, then `gh repo create "联想签到器" --public --source . --remote origin --push --description "Windows 下基于 Python、ADB 和雷电模拟器的联想 App 自动签到工具"`.

Expected: repository creation and push exit with code 0.

- [ ] **Step 5: Verify remote repository**

Run: `gh repo view --json nameWithOwner,url,visibility,defaultBranchRef` and inspect remote tracked files.

Expected: repository is PUBLIC, name is `联想签到器`, default branch is `main`, and the returned URL is ready to share.
