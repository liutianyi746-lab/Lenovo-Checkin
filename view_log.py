from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


class LogNotFoundError(FileNotFoundError):
    """签到日志尚未生成。"""


def open_checkin_log(project_dir: Path, opener: Callable[[Path], object]) -> Path:
    log_path = (project_dir / "logs" / "checkin.log").resolve()
    if not log_path.is_file():
        raise LogNotFoundError("尚未生成日志，请先运行一次签到程序。")
    opener(log_path)
    return log_path


def main() -> int:
    try:
        path = open_checkin_log(
            Path(__file__).parent,
            lambda log: subprocess.Popen(["notepad.exe", str(log)]),
        )
        print(f"已打开日志：{path}")
        return 0
    except LogNotFoundError as exc:
        print(exc)
        return 1
    except OSError as exc:
        print(f"无法打开记事本：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
