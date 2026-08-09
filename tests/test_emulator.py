import subprocess
from pathlib import Path

import pytest

from config import load_config
from emulator import EmulatorError, parse_adb_devices, select_ldplayer_device


def test_parse_adb_devices_ignores_header_and_keeps_states() -> None:
    output = (
        "List of devices attached\nemulator-5554\tdevice\n127.0.0.1:5555\toffline\n\n"
    )
    assert parse_adb_devices(output) == {
        "emulator-5554": "device",
        "127.0.0.1:5555": "offline",
    }


def test_select_ldplayer_device_prefers_emulator_candidates() -> None:
    devices = {
        "R58M123": "device",
        "127.0.0.1:5555": "device",
        "emulator-5554": "device",
    }
    assert select_ldplayer_device(devices, 0) == "emulator-5554"
    assert select_ldplayer_device(devices, 1) == "127.0.0.1:5555"


def test_select_ldplayer_device_rejects_missing_instance() -> None:
    with pytest.raises(EmulatorError, match="实例"):
        select_ldplayer_device({"emulator-5554": "device"}, 2)


def test_stop_uses_ldconsole_for_configured_instance(tmp_path: Path) -> None:
    player = tmp_path / "dnplayer.exe"
    console = tmp_path / "ldconsole.exe"
    player.touch()
    console.touch()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "ldplayer:\n"
        f"  executable_path: '{player}'\n"
        "  instance_index: 2\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    from emulator import LDPlayerManager

    LDPlayerManager(load_config(config_file), runner=runner).stop()

    assert calls == [[str(console), "quit", "--index", "2"]]
