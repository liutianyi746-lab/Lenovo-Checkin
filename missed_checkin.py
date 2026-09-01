import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
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
    messages = "|".join(re.escape(message) for message in SUCCESS_MESSAGES)
    success_line = re.compile(
        rf"{re.escape(day.isoformat())} \d{{2}}:\d{{2}}:\d{{2}} (?:{messages})"
    )
    return any(success_line.fullmatch(line) for line in lines)


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
    local_day = datetime.now(tz=UTC).astimezone().date()
    return run_if_needed(project_dir, local_day, sys.executable, subprocess.run)


if __name__ == "__main__":
    raise SystemExit(main())
