from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """配置文件内容无效。"""


@dataclass(frozen=True)
class AppConfig:
    package_name: str = "com.lenovo.club.app"
    startup_timeout: int = 30


@dataclass(frozen=True)
class LDPlayerConfig:
    auto_start: bool = True
    executable_path: str = "auto"
    instance_index: int = 0
    startup_timeout: int = 120
    close_after_run: bool = True


@dataclass(frozen=True)
class ADBConfig:
    address: str = "auto"
    connect_timeout: int = 30
    executable_path: str = "adb"


@dataclass(frozen=True)
class AutomationConfig:
    element_timeout: int = 15
    max_retries: int = 3
    save_debug_on_error: bool = True


@dataclass(frozen=True)
class PathsConfig:
    logs: Path
    screenshots: Path
    dumps: Path


@dataclass(frozen=True)
class Config:
    app: AppConfig
    ldplayer: LDPlayerConfig
    adb: ADBConfig
    automation: AutomationConfig
    paths: PathsConfig
    config_file: Path


def resolve_config_path(project_dir: Path) -> Path:
    """优先使用不入库的本机配置，否则使用公开的通用配置。"""
    local = project_dir / "config.local.yaml"
    return local if local.is_file() else project_dir / "config.yaml"


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{name} 必须是 YAML 映射")
    return value


def _positive(value: Any, name: str) -> int:
    result = int(value)
    if result <= 0:
        raise ConfigError(f"{name} 必须大于 0")
    return result


def load_config(path: str | Path = "config.yaml") -> Config:
    config_file = Path(path).expanduser().resolve()
    if not config_file.is_file():
        raise ConfigError(f"配置文件不存在：{config_file}")
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError("config.yaml 顶层必须是映射")

    app_raw, ld_raw = _section(raw, "app"), _section(raw, "ldplayer")
    adb_raw, auto_raw, paths_raw = (
        _section(raw, "adb"),
        _section(raw, "automation"),
        _section(raw, "paths"),
    )
    instance_index = int(ld_raw.get("instance_index", 0))
    if instance_index < 0:
        raise ConfigError("ldplayer.instance_index 不能小于 0")

    base = config_file.parent
    resolve_path = lambda value: (
        (base / str(value)).resolve()
        if not Path(str(value)).is_absolute()
        else Path(str(value))
    )
    paths = PathsConfig(
        logs=resolve_path(paths_raw.get("logs", "logs")),
        screenshots=resolve_path(paths_raw.get("screenshots", "screenshots")),
        dumps=resolve_path(paths_raw.get("dumps", "dumps")),
    )
    for directory in (paths.logs, paths.screenshots, paths.dumps):
        directory.mkdir(parents=True, exist_ok=True)

    return Config(
        app=AppConfig(
            str(app_raw.get("package_name", "com.lenovo.club.app")),
            _positive(app_raw.get("startup_timeout", 30), "app.startup_timeout"),
        ),
        ldplayer=LDPlayerConfig(
            bool(ld_raw.get("auto_start", True)),
            str(ld_raw.get("executable_path", "auto")),
            instance_index,
            _positive(ld_raw.get("startup_timeout", 120), "ldplayer.startup_timeout"),
            bool(ld_raw.get("close_after_run", True)),
        ),
        adb=ADBConfig(
            str(adb_raw.get("address", "auto")),
            _positive(adb_raw.get("connect_timeout", 30), "adb.connect_timeout"),
            str(adb_raw.get("executable_path", "adb")),
        ),
        automation=AutomationConfig(
            _positive(
                auto_raw.get("element_timeout", 15), "automation.element_timeout"
            ),
            _positive(auto_raw.get("max_retries", 3), "automation.max_retries"),
            bool(auto_raw.get("save_debug_on_error", True)),
        ),
        paths=paths,
        config_file=config_file,
    )
