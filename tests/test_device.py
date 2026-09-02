from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

import pytest

from device import AndroidDevice, DeviceError


class ConnectedDevice:
    def __init__(self) -> None:
        self.info = {"productName": "LDPlayer"}


def successful_runner(
    args: list[str], **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    del kwargs
    return subprocess.CompletedProcess(args, 0, "ok", "")


def test_connect_recovers_once_when_uiautomator2_hangs() -> None:
    blocked = threading.Event()
    attempts = 0
    adb_calls: list[list[str]] = []

    def connector(address: str) -> ConnectedDevice:
        nonlocal attempts
        assert address == "emulator-5554"
        attempts += 1
        if attempts == 1:
            blocked.wait()
        return ConnectedDevice()

    def runner(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        adb_calls.append(args)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    device = AndroidDevice(
        "emulator-5554",
        "adb",
        connect_timeout=0.02,
        runner=runner,
        connector=connector,
    )

    assert device.connect().info == {"productName": "LDPlayer"}
    assert attempts == 2
    assert ["adb", "kill-server"] in adb_calls
    assert ["adb", "start-server"] in adb_calls


def test_connect_stops_after_bounded_uiautomator2_retries() -> None:
    blocked = threading.Event()

    def connector(address: str) -> ConnectedDevice:
        assert address == "emulator-5554"
        blocked.wait()
        return ConnectedDevice()

    started = time.monotonic()
    with pytest.raises(DeviceError, match="uiautomator2 连接超时"):
        AndroidDevice(
            "emulator-5554",
            "adb",
            connect_timeout=0.02,
            runner=successful_runner,
            connector=connector,
        ).connect()

    assert time.monotonic() - started < 0.5


def test_connect_translates_persistent_tcp_adb_timeout() -> None:
    def runner(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if args[1] == "connect":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        return subprocess.CompletedProcess(args, 0, "ok", "")

    with pytest.raises(DeviceError, match="ADB 连接超时"):
        AndroidDevice(
            "127.0.0.1:5555",
            "adb",
            connect_timeout=0.02,
            runner=runner,
            connector=lambda address: ConnectedDevice(),
        ).connect()


def test_connect_translates_adb_process_launch_error() -> None:
    def runner(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise PermissionError("拒绝访问")

    with pytest.raises(DeviceError, match="检查 ADB 失败.*拒绝访问"):
        AndroidDevice(
            "emulator-5554",
            "adb",
            runner=runner,
            connector=lambda address: ConnectedDevice(),
        ).connect()
