import subprocess
from pathlib import Path

import pytest

from config import load_config
from emulator import (
    EmulatorError,
    LDPlayerManager,
    parse_adb_devices,
    select_ldplayer_device,
    stop_processes_by_executable,
)


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


def test_stop_processes_by_executable_passes_resolved_path_as_argument(
    tmp_path: Path,
) -> None:
    adb = tmp_path / "adb.exe"
    adb.touch()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "", "")

    stop_processes_by_executable(adb, runner=runner)

    assert calls[0][0][-1] == str(adb.resolve())
    assert "ExecutablePath" in calls[0][0][-2]
    assert "Stop-Process" in calls[0][0][-2]
    assert "/IM" not in " ".join(calls[0][0])


def adb_test_config(tmp_path: Path):
    adb = tmp_path / "adb.exe"
    adb.touch()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"adb:\n  executable_path: '{adb}'\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    return load_config(config_file), adb.resolve()


def test_reset_adb_server_uses_normal_restart_without_forced_cleanup(
    tmp_path: Path,
) -> None:
    config, adb = adb_test_config(tmp_path)
    calls: list[list[str]] = []
    cleaned: list[Path] = []

    def runner(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    manager = LDPlayerManager(config, runner=runner, process_cleaner=cleaned.append)

    manager.reset_adb_server()

    assert calls == [[str(adb), "kill-server"], [str(adb), "start-server"]]
    assert cleaned == []


def test_reset_adb_server_cleans_exact_path_after_kill_timeout(
    tmp_path: Path,
) -> None:
    config, adb = adb_test_config(tmp_path)
    cleaned: list[Path] = []

    def runner(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if args[-1] == "kill-server":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        return subprocess.CompletedProcess(args, 0, "", "")

    manager = LDPlayerManager(config, runner=runner, process_cleaner=cleaned.append)

    manager.reset_adb_server()

    assert cleaned == [adb]


def test_reset_adb_server_stops_when_exact_cleanup_fails(tmp_path: Path) -> None:
    config, _ = adb_test_config(tmp_path)

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    def cleaner(path: Path) -> None:
        del path
        raise EmulatorError("cleanup failed")

    manager = LDPlayerManager(config, runner=runner, process_cleaner=cleaner)

    with pytest.raises(EmulatorError, match="cleanup failed"):
        manager.reset_adb_server()


def test_reset_adb_server_stops_when_start_server_fails(tmp_path: Path) -> None:
    config, _ = adb_test_config(tmp_path)

    def runner(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args,
            0 if args[-1] == "kill-server" else 1,
            "",
            "cannot start",
        )

    manager = LDPlayerManager(config, runner=runner)

    with pytest.raises(EmulatorError, match="start-server"):
        manager.reset_adb_server()


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


def test_start_prefers_ldconsole_launch_for_configured_instance(
    tmp_path: Path, monkeypatch
) -> None:
    player = tmp_path / "dnplayer.exe"
    console = tmp_path / "ldconsole.exe"
    player.touch()
    console.touch()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "ldplayer:\n"
        f"  executable_path: '{player}'\n"
        "  instance_index: 3\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(
        "emulator.subprocess.Popen",
        lambda *args, **kwargs: calls.append(["Popen"]),
    )

    LDPlayerManager(load_config(config_file), runner=runner).start()

    assert calls == [[str(console), "launch", "--index", "3"]]


def test_ensure_running_cleans_up_and_retries_one_failed_boot(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    events: list[str] = []

    class RetryManager(LDPlayerManager):
        def is_running(self) -> bool:
            events.append("is_running")
            return False

        def start(self) -> None:
            events.append("start")

        def wait_for_boot(self) -> str:
            events.append("wait_for_boot")
            if events.count("wait_for_boot") == 1:
                raise EmulatorError("first boot timed out")
            return "127.0.0.1:5555"

        def stop(self) -> None:
            events.append("stop")

        def disconnect_adb(self) -> None:
            events.append("disconnect_adb")

    manager = RetryManager(
        load_config(config_file), sleeper=lambda seconds: events.append(f"sleep:{seconds}")
    )

    assert manager.ensure_running() == "127.0.0.1:5555"
    assert events == [
        "is_running",
        "start",
        "wait_for_boot",
        "stop",
        "disconnect_adb",
        "sleep:5",
        "is_running",
        "start",
        "wait_for_boot",
    ]


def test_ensure_running_stops_after_second_failed_boot(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )
    events: list[str] = []

    class FailingManager(LDPlayerManager):
        def is_running(self) -> bool:
            return False

        def start(self) -> None:
            events.append("start")

        def wait_for_boot(self) -> str:
            events.append("wait_for_boot")
            raise EmulatorError("boot timed out")

        def stop(self) -> None:
            events.append("stop")

        def disconnect_adb(self) -> None:
            events.append("disconnect_adb")

    manager = FailingManager(load_config(config_file), sleeper=lambda seconds: None)

    with pytest.raises(EmulatorError, match="boot timed out"):
        manager.ensure_running()

    assert events == [
        "start",
        "wait_for_boot",
        "stop",
        "disconnect_adb",
        "start",
        "wait_for_boot",
    ]
