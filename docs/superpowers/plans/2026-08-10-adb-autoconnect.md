# 雷电 ADB 自动连接修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 雷电 14 启动后即使没有自动出现在 `adb devices`，程序也能连接实例 0 的本地 ADB 并继续签到。

**Architecture:** 在 `LDPlayerManager` 的设备发现边界增加本地端口连接，不改导航和签到逻辑。端口由实例索引确定，显式 ADB 地址保持原行为。

**Tech Stack:** Python 3.11+、pytest、ADB、雷电模拟器

## Global Constraints

- 只连接 `127.0.0.1`，不扫描网络或外部设备。
- 实例 0 对应端口 5555，实例索引每增加 1，端口增加 2。
- 不改变验证码、风控或签到按钮的处理。

---

### Task 1: ADB 自动连接

**Files:**
- Modify: `emulator.py`
- Modify: `tests/test_emulator.py`

**Interfaces:**
- Produces: `ldplayer_adb_address(instance_index: int) -> str`
- Updates: `LDPlayerManager.adb_devices() -> dict[str, str]`

- [ ] **Step 1: Write failing tests**

```python
def test_adb_devices_connects_local_instance_when_initial_list_is_empty():
    # runner returns empty list, successful connect, then 127.0.0.1:5555 device
    assert manager.adb_devices() == {"127.0.0.1:5555": "device"}


def test_adb_devices_does_not_autoconnect_for_explicit_address():
    assert manager.adb_devices() == {}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_emulator.py -q`

Expected: FAIL because the connect command is not issued.

- [ ] **Step 3: Implement minimal connection behavior**

Add `ldplayer_adb_address()` and retry `adb devices` once after `adb connect` only when auto address mode has no emulator candidate.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_emulator.py -q`

Expected: all emulator tests pass.

- [ ] **Step 5: Verify project and real workflow**

Run full pytest, Ruff checks, then execute `main.py`. Success requires exit code 0 plus either “签到成功” or “今日已经签到，无需重复操作”, a current result PNG/XML, and no remaining雷电 process.
