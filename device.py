from __future__ import annotations

import logging
import queue
import subprocess
import threading
from collections.abc import Callable
from typing import Any

import uiautomator2 as u2


class DeviceError(RuntimeError):
    """ADB 或 uiautomator2 连接失败。"""


class AndroidDevice:
    def __init__(
        self,
        address: str,
        adb_path: str = "adb",
        connect_timeout: float = 30,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        connector: Callable[[str], Any] = u2.connect,
    ) -> None:
        self.address = address
        self.adb_path = adb_path
        self.connect_timeout = connect_timeout
        self.runner = runner
        self.connector = connector
        self.d: Any | None = None
        self.logger = logging.getLogger(__name__)

    def _run_adb(
        self, arguments: list[str], timeout: float, operation: str
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self.runner(
                [self.adb_path, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DeviceError(f"ADB 不可用：{self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DeviceError(f"{operation}超时") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise DeviceError(f"{operation}失败：{detail or '未知错误'}")
        return result

    def _connect_uiautomator2(self) -> Any:
        results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def initialize() -> None:
            try:
                device = self.connector(self.address)
                info = device.info
                results.put((True, (device, info)))
            except Exception as exc:  # noqa: BLE001 - 第三方连接器异常类型不统一
                results.put((False, exc))

        threading.Thread(target=initialize, daemon=True).start()
        try:
            succeeded, value = results.get(timeout=self.connect_timeout)
        except queue.Empty as exc:
            raise DeviceError("uiautomator2 连接超时") from exc
        if not succeeded:
            raise DeviceError(f"uiautomator2 连接失败：{value}") from value
        device, info = value
        if not info:
            raise DeviceError("uiautomator2 未返回设备信息")
        return device

    def _reset_adb(self) -> None:
        self._run_adb(["kill-server"], 10, "停止 ADB 服务")
        self._run_adb(["start-server"], 10, "启动 ADB 服务")

    def connect(self) -> Any:
        self._run_adb(["version"], 10, "检查 ADB")
        last_error: DeviceError | None = None
        for attempt in (1, 2):
            try:
                if ":" in self.address:
                    self._run_adb(
                        ["connect", self.address],
                        self.connect_timeout,
                        "ADB 连接",
                    )
                self.d = self._connect_uiautomator2()
                break
            except DeviceError as exc:
                last_error = exc
                if attempt == 2:
                    raise
                self.logger.warning("设备连接失败，重启 ADB 后重试一次：%s", exc)
                self._reset_adb()
        if self.d is None:
            raise last_error or DeviceError("设备连接失败")
        self.logger.info("ADB device detected: %s", self.address)
        self.logger.info("uiautomator2 连接成功")
        return self.d

    def require_connection(self) -> Any:
        if self.d is None:
            raise DeviceError("设备尚未连接")
        return self.d

    def screen_size(self) -> tuple[int, int]:
        size = self.require_connection().window_size()
        return int(size[0]), int(size[1])

    def is_healthy(self) -> bool:
        try:
            return bool(self.require_connection().info)
        except Exception:  # noqa: BLE001 - uiautomator2 未提供统一连接异常基类
            return False
