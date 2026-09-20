from pathlib import Path

import pytest

from run_lock import AlreadyRunningError, RunLock


def test_second_run_is_rejected_until_first_run_releases_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".checkin.lock"
    first = RunLock(lock_path)
    second = RunLock(lock_path)

    first.acquire()
    try:
        with pytest.raises(AlreadyRunningError):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()
