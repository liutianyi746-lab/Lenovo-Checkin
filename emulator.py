from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from config import Config


class EmulatorError(RuntimeError):
    """雷电模拟器发现、启动或连接失败。"""


def stop_processes_by_executable(
    executable: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    if os.name != "nt":
        raise EmulatorError("ADB 强制恢复仅支持 Windows")
    target = executable.expanduser().resolve()
    child_env = os.environ.copy()
    child_env["LENOVO_CHECKIN_ADB_TARGET"] = str(target)
    script = (
        "$ErrorActionPreference='Stop';"
        "$raw=[Environment]::GetEnvironmentVariable('LENOVO_CHECKIN_ADB_TARGET');"
        "if ([String]::IsNullOrWhiteSpace($raw)) {throw 'missing ADB target'};"
        "$target=[IO.Path]::GetFullPath($raw);"
        "$items=Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {"
        "$_.ExecutablePath -and "
        "[StringComparer]::OrdinalIgnoreCase.Equals("
        "[IO.Path]::GetFullPath($_.ExecutablePath),$target)};"
        "$items | ForEach-Object {"
        "$pidToStop=$_.ProcessId;"
        "$current=Get-CimInstance Win32_Process -Filter "
        "\"ProcessId = $pidToStop\" -ErrorAction Stop;"
        "if ($current -and $current.ExecutablePath -and "
        "[StringComparer]::OrdinalIgnoreCase.Equals("
        "[IO.Path]::GetFullPath($current.ExecutablePath),$target)) {"
        "Stop-Process -Id $pidToStop -Force -ErrorAction Stop}};"
        "$remaining=Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {"
        "$_.ExecutablePath -and "
        "[StringComparer]::OrdinalIgnoreCase.Equals("
        "[IO.Path]::GetFullPath($_.ExecutablePath),$target)};"
        "if ($remaining) {throw 'remaining ADB processes after cleanup'}"
    )
    try:
        result = runner(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            env=child_env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise EmulatorError("无法精确清理雷电 ADB 进程") from exc
    if result.returncode != 0:
        raise EmulatorError(f"精确清理雷电 ADB 失败：{result.stderr.strip()}")


def parse_adb_devices(output: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] != "List" and not parts[0].startswith("*"):
            devices[parts[0]] = parts[1]
    return devices


def _is_emulator_address(address: str) -> bool:
    return address.startswith(("emulator-", "127.0.0.1:", "localhost:"))


def ldplayer_adb_address(instance_index: int) -> str:
    return f"127.0.0.1:{5555 + instance_index * 2}"


def select_ldplayer_device(devices: dict[str, str], instance_index: int) -> str:
    candidates = [
        address
        for address, state in devices.items()
        if state == "device" and _is_emulator_address(address)
    ]
    candidates.sort(key=lambda value: (not value.startswith("emulator-"), value))
    if instance_index >= len(candidates):
        raise EmulatorError(
            f"未找到雷电模拟器实例 {instance_index}，当前可用候选：{candidates or '无'}"
        )
    return candidates[instance_index]


class LDPlayerManager:
    def __init__(
        self,
        config: Config,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        sleeper: Callable[[float], None] = time.sleep,
        process_cleaner: Callable[[Path], None] = stop_processes_by_executable,
    ) -> None:
        self.config = config
        self.runner = runner
        self.sleeper = sleeper
        self.process_cleaner = process_cleaner
        self.logger = logging.getLogger(__name__)

    def _run(
        self, args: list[str], timeout: int = 10
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise EmulatorError(
                f"未找到 ADB：{self.config.adb.executable_path}，请配置 PATH 或 adb.executable_path"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise EmulatorError(f"命令执行超时：{' '.join(args)}") from exc

    def adb_devices(self) -> dict[str, str]:
        adb = self.find_adb_executable()
        result = self._run([adb, "devices"])
        if result.returncode != 0:
            raise EmulatorError(f"adb devices 失败：{result.stderr.strip()}")
        devices = parse_adb_devices(result.stdout)
        address = ldplayer_adb_address(self.config.ldplayer.instance_index)
        if (
            self.config.adb.address.lower() == "auto"
            and devices.get(address) != "device"
        ):
            self._run([adb, "connect", address])
            result = self._run([adb, "devices"])
            if result.returncode != 0:
                raise EmulatorError(f"adb devices 失败：{result.stderr.strip()}")
            devices = parse_adb_devices(result.stdout)
        return devices

    def reset_adb_server(self) -> None:
        adb_command = self.find_adb_executable()
        adb = Path(shutil.which(adb_command) or adb_command).expanduser().resolve()
        try:
            stopped = self._run([str(adb), "kill-server"])
            if stopped.returncode != 0:
                raise EmulatorError(
                    f"adb kill-server 失败：{stopped.stderr.strip()}"
                )
        except EmulatorError as exc:
            self.logger.warning("常规停止 ADB 失败，执行精确路径清理：%s", exc)
            self.process_cleaner(adb)
        started = self._run([str(adb), "start-server"])
        if started.returncode != 0:
            raise EmulatorError(f"adb start-server 失败：{started.stderr.strip()}")

    def is_running(self) -> bool:
        try:
            return any(
                _is_emulator_address(address) and state == "device"
                for address, state in self.adb_devices().items()
            )
        except EmulatorError:
            return False

    def find_executable(self) -> Path | None:
        configured = self.config.ldplayer.executable_path
        if configured.lower() != "auto":
            path = Path(configured).expanduser()
            return path if path.is_file() else None
        candidates: list[Path] = []
        for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if base:
                candidates.extend(
                    [
                        Path(base) / "LDPlayer" / "LDPlayer9" / "dnplayer.exe",
                        Path(base) / "LDPlayer" / "LDPlayer4.0" / "dnplayer.exe",
                    ]
                )
        candidates.extend(
            [
                Path("C:/LDPlayer/LDPlayer9/dnplayer.exe"),
                Path("D:/LDPlayer/LDPlayer9/dnplayer.exe"),
            ]
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return self._find_from_processes() or self._find_from_registry()

    def _find_from_registry(self) -> Path | None:
        if os.name != "nt":
            return None
        try:
            import winreg

            keys = (
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                ),
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ),
                (
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                ),
            )
            for hive, key_name in keys:
                try:
                    with winreg.OpenKey(hive, key_name) as root:
                        for index in range(winreg.QueryInfoKey(root)[0]):
                            try:
                                with winreg.OpenKey(
                                    root, winreg.EnumKey(root, index)
                                ) as entry:
                                    name = str(
                                        winreg.QueryValueEx(entry, "DisplayName")[0]
                                    )
                                    if (
                                        "LDPlayer" not in name
                                        and "雷电模拟器" not in name
                                    ):
                                        continue
                                    install = Path(
                                        str(
                                            winreg.QueryValueEx(
                                                entry, "InstallLocation"
                                            )[0]
                                        )
                                    )
                                    for filename in ("dnplayer.exe", "LDPlayer.exe"):
                                        candidate = install / filename
                                        if candidate.is_file():
                                            return candidate
                            except OSError:
                                continue
                except OSError:
                    continue
        except (ImportError, OSError):
            return None
        return None

    def find_adb_executable(self) -> str:
        configured = self.config.adb.executable_path
        if configured.lower() != "adb" or shutil.which(configured):
            return configured
        emulator = self.find_executable()
        if emulator is not None:
            for candidate in (
                emulator.parent / "adb.exe",
                emulator.parent / "adb" / "adb.exe",
            ):
                if candidate.is_file():
                    return str(candidate)
        return configured

    def _find_from_processes(self) -> Path | None:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='dnplayer.exe'\" | Select-Object -Expand ExecutablePath",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in result.stdout.splitlines():
            path = Path(line.strip())
            if path.is_file():
                return path
        return None

    def start(self) -> None:
        executable = self.find_executable()
        if executable is None:
            raise EmulatorError(
                "未找到雷电模拟器，请在 config.yaml 中填写 executable_path"
            )
        console = executable.parent / "ldconsole.exe"
        self.logger.info("正在启动雷电模拟器实例 %d", self.config.ldplayer.instance_index)
        if console.is_file():
            result = self._run(
                [
                    str(console),
                    "launch",
                    "--index",
                    str(self.config.ldplayer.instance_index),
                ]
            )
            if result.returncode != 0:
                raise EmulatorError(f"启动雷电模拟器失败：{result.stderr.strip()}")
            return
        subprocess.Popen(
            [str(executable), f"index={self.config.ldplayer.instance_index}"],
            cwd=str(executable.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def disconnect_adb(self) -> None:
        address = ldplayer_adb_address(self.config.ldplayer.instance_index)
        result = self._run([self.find_adb_executable(), "disconnect", address])
        if result.returncode != 0:
            self.logger.warning("断开旧 ADB 连接失败：%s", result.stderr.strip())

    def stop(self) -> None:
        executable = self.find_executable()
        if executable is None:
            raise EmulatorError("无法定位雷电目录，不能关闭模拟器")
        console = executable.parent / "ldconsole.exe"
        if not console.is_file():
            raise EmulatorError(f"未找到雷电命令行工具：{console}")
        self.logger.info(
            "正在关闭雷电模拟器实例 %d", self.config.ldplayer.instance_index
        )
        result = self._run(
            [
                str(console),
                "quit",
                "--index",
                str(self.config.ldplayer.instance_index),
            ]
        )
        if result.returncode != 0:
            raise EmulatorError(f"关闭雷电模拟器失败：{result.stderr.strip()}")

    def find_adb_device(self) -> str:
        if self.config.adb.address.lower() != "auto":
            return self.config.adb.address
        return select_ldplayer_device(
            self.adb_devices(), self.config.ldplayer.instance_index
        )

    def wait_for_boot(self) -> str:
        deadline = time.monotonic() + self.config.ldplayer.startup_timeout
        last_error = ""
        while time.monotonic() < deadline:
            try:
                address = self.find_adb_device()
                result = self._run(
                    [
                        self.find_adb_executable(),
                        "-s",
                        address,
                        "shell",
                        "getprop",
                        "sys.boot_completed",
                    ]
                )
                if result.returncode == 0 and result.stdout.strip() == "1":
                    self.logger.info("Android boot completed: %s", address)
                    return address
                last_error = result.stderr.strip() or result.stdout.strip()
            except EmulatorError as exc:
                last_error = str(exc)
            self.sleeper(2)
        raise EmulatorError(
            f"等待 Android 启动超过 {self.config.ldplayer.startup_timeout} 秒。最后状态：{last_error or '未发现设备'}"
        )

    def ensure_running(self) -> str:
        self.logger.info("检查雷电模拟器")
        for attempt in (1, 2):
            running = self.is_running()
            if not running and not self.config.ldplayer.auto_start:
                raise EmulatorError("雷电模拟器未运行，且 ldplayer.auto_start=false")
            try:
                if running:
                    self.logger.info("雷电模拟器已经运行，跳过启动")
                else:
                    self.logger.info("雷电模拟器未运行")
                    self.start()
                return self.wait_for_boot()
            except EmulatorError:
                if attempt == 2:
                    raise
                self.logger.warning("首次启动未就绪，清理后自动重试一次", exc_info=True)
                try:
                    self.stop()
                except EmulatorError as exc:
                    self.logger.warning("重试前关闭模拟器失败：%s", exc)
                try:
                    self.disconnect_adb()
                except EmulatorError as exc:
                    self.logger.warning("重试前断开 ADB 失败：%s", exc)
                self.sleeper(5)
        raise EmulatorError("雷电模拟器启动失败")
