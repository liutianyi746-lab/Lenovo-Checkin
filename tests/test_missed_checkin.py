from datetime import date
from pathlib import Path
from subprocess import CompletedProcess

from missed_checkin import has_success_for_date, run_if_needed


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
