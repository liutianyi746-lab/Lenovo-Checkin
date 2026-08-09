from __future__ import annotations

import logging
import subprocess
from typing import Any

import uiautomator2 as u2


class DeviceError(RuntimeError):
    """ADB 或 uiautomator2 连接失败。"""


class AndroidDevice:
    def __init__(
        self, address: str, adb_path: str = "adb", connect_timeout: int = 30
    ) -> None:
        self.address = address
        self.adb_path = adb_path
        self.connect_timeout = connect_timeout
        self.d: Any | None = None
        self.logger = logging.getLogger(__name__)

    def connect(self) -> Any:
        try:
            version = subprocess.run(
                [self.adb_path, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DeviceError(f"ADB 不可用：{self.adb_path}") from exc
        if version.returncode != 0:
            raise DeviceError(f"ADB 不可用：{version.stderr.strip()}")
        if ":" in self.address:
            subprocess.run(
                [self.adb_path, "connect", self.address],
                capture_output=True,
                text=True,
                timeout=self.connect_timeout,
                check=False,
            )
        try:
            self.d = u2.connect(self.address)
            info = self.d.info
            if not info:
                raise DeviceError("uiautomator2 未返回设备信息")
        except Exception as exc:
            raise DeviceError(f"uiautomator2 连接失败：{exc}") from exc
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
