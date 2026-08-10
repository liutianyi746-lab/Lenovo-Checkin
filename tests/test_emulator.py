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


def test_adb_devices_connects_local_instance_when_initial_list_is_empty(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "ldplayer:\n  instance_index: 0\n"
        "adb:\n  address: auto\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    device_reads = 0

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal device_reads
        del kwargs
        calls.append(args)
        if args[-1] == "devices":
            device_reads += 1
            output = (
                "List of devices attached\n"
                if device_reads == 1
                else "List of devices attached\n127.0.0.1:5555\tdevice\n"
            )
            return subprocess.CompletedProcess(args, 0, output, "")
        return subprocess.CompletedProcess(args, 0, "connected to 127.0.0.1:5555\n", "")

    from emulator import LDPlayerManager

    manager = LDPlayerManager(load_config(config_file), runner=runner)

    assert manager.adb_devices() == {"127.0.0.1:5555": "device"}
    assert calls == [
        ["adb", "devices"],
        ["adb", "connect", "127.0.0.1:5555"],
        ["adb", "devices"],
    ]


def test_adb_devices_does_not_autoconnect_for_explicit_address(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "adb:\n  address: 127.0.0.1:6000\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "List of devices attached\n", "")

    from emulator import LDPlayerManager

    manager = LDPlayerManager(load_config(config_file), runner=runner)

    assert manager.adb_devices() == {}
    assert calls == [["adb", "devices"]]


def test_adb_devices_reconnects_local_instance_when_it_is_offline(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "ldplayer:\n  instance_index: 0\n"
        "adb:\n  address: auto\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    device_reads = 0

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal device_reads
        del kwargs
        calls.append(args)
        if args[-1] == "devices":
            device_reads += 1
            state = "offline" if device_reads == 1 else "device"
            return subprocess.CompletedProcess(
                args,
                0,
                f"List of devices attached\n127.0.0.1:5555\t{state}\n",
                "",
            )
        return subprocess.CompletedProcess(args, 0, "connected to 127.0.0.1:5555\n", "")

    from emulator import LDPlayerManager

    manager = LDPlayerManager(load_config(config_file), runner=runner)

    assert manager.adb_devices() == {"127.0.0.1:5555": "device"}
    assert ["adb", "connect", "127.0.0.1:5555"] in calls


def test_is_running_rejects_stale_offline_device(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    from emulator import LDPlayerManager

    manager = LDPlayerManager(load_config(config_file))
    manager.adb_devices = lambda: {"127.0.0.1:5555": "offline"}

    assert manager.is_running() is False
