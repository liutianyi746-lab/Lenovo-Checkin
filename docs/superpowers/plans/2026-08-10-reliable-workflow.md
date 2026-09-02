# Reliable Lenovo Check-in Workflow Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Make the daily Lenovo check-in run reliably without Codex by preventing overlapping runs, recovering once from an unhealthy LDPlayer start, and navigating only after the real native home UI is ready.

**Architecture:** Keep `main.py` as the orchestration entry point. Add a process-scoped run lock around the existing workflow, make `EmulatorManager` own launch/recovery, and make `NavigationManager` wait for stable resource IDs before advancing. Preserve the existing idempotent check-in verification and evidence capture.

**Tech Stack:** Python 3.11+, pytest, uiautomator2, Windows `msvcrt`, LDPlayer `ldconsole.exe`, ADB.

---

### Task 1: Prevent overlapping runs

**Files:**
- Create: `run_lock.py`
- Create: `tests/test_run_lock.py`
- Modify: `main.py`
- Modify: `.gitignore`

1. Write a failing test proving a second lock acquisition is rejected while the first is held.
2. Run `python -m pytest tests/test_run_lock.py -q` and confirm it fails because the lock module is missing.
3. Implement the smallest Windows-compatible byte-range lock with context-manager cleanup.
4. Run the focused test and the full test suite.
5. Integrate the lock into `main.main()` so duplicate runs exit non-zero and always release the lock.

### Task 2: Launch LDPlayer through its console and retry one unhealthy boot

**Files:**
- Modify: `tests/test_emulator.py`
- Modify: `emulator.py`

1. Add failing behavioral tests proving `ldconsole launch --index 0` is preferred and a failed boot is cleaned up and retried exactly once.
2. Run `python -m pytest tests/test_emulator.py -q` and confirm the new tests fail for the expected missing behavior.
3. Implement console launch with `dnplayer.exe` fallback, ADB disconnect cleanup, a five-second recovery pause, and at most two boot attempts.
4. Re-run focused and full tests.

### Task 3: Stabilize Home and My navigation

**Files:**
- Modify: `tests/test_navigation.py`
- Modify: `navigation.py`

1. Add failing tests proving Home waits for `com.lenovo.club.app:id/navigator_bottom`, ignores right-pane product resources, and My is clicked only after native Home is ready.
2. Run `python -m pytest tests/test_navigation.py -q` and confirm the tests fail for the missing stable-state checks.
3. Implement the verified Home coordinate fallback `(300, 105)` at 1920x1080 using ratios, wait for `navigator_bottom`, then locate and click the real `我的` node dynamically.
4. Re-run focused and full tests.

### Task 4: Document and perform full acceptance

**Files:**
- Modify: `README.md`

1. Document single-instance behavior, one automatic emulator restart, evidence locations, and non-zero failure behavior.
2. Run the complete automated test suite.
3. Execute `main.py` with the bundled Python runtime against LDPlayer instance 0.
4. Verify exit code 0, a current log result (`签到成功` or `今日已经签到，无需重复操作`), a current screenshot and hierarchy XML, released lock, and stopped LDPlayer.
5. Inspect the final diff, commit the verified implementation, and prepare it for integration/publication.
