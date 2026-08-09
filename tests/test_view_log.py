from pathlib import Path

import pytest

from view_log import LogNotFoundError, open_checkin_log


def test_open_checkin_log_passes_resolved_log_to_opener(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "checkin.log"
    log.parent.mkdir()
    log.write_text("签到成功", encoding="utf-8")
    opened: list[Path] = []

    result = open_checkin_log(tmp_path, opened.append)

    assert result == log.resolve()
    assert opened == [log.resolve()]


def test_open_checkin_log_reports_missing_log(tmp_path: Path) -> None:
    with pytest.raises(LogNotFoundError, match="尚未生成日志"):
        open_checkin_log(tmp_path, lambda path: None)
