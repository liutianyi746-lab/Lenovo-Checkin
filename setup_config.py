from __future__ import annotations

import sys
from pathlib import Path

import yaml


class SetupConfigError(ValueError):
    """首次配置无法安全完成。"""


def _validated_executable(path: Path, names: set[str], label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.name.lower() not in names:
        raise SetupConfigError(f"{label}路径无效：{resolved}")
    return resolved


def write_local_config(
    project_dir: Path,
    ldplayer_path: Path,
    adb_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    project_dir = project_dir.expanduser().resolve()
    target = project_dir / "config.local.yaml"
    if target.exists() and not overwrite:
        raise SetupConfigError(f"本机配置已存在：{target}")

    player = _validated_executable(
        ldplayer_path, {"dnplayer.exe", "ldplayer.exe"}, "雷电模拟器"
    )
    adb = _validated_executable(adb_path, {"adb.exe"}, "ADB")
    data = {
        "app": {"package_name": "com.lenovo.club.app", "startup_timeout": 30},
        "ldplayer": {
            "auto_start": True,
            "executable_path": str(player),
            "instance_index": 0,
            "startup_timeout": 120,
            "close_after_run": True,
        },
        "adb": {
            "address": "auto",
            "connect_timeout": 30,
            "executable_path": str(adb),
        },
        "automation": {
            "element_timeout": 15,
            "max_retries": 3,
            "save_debug_on_error": True,
        },
        "paths": {"logs": "logs", "screenshots": "screenshots", "dumps": "dumps"},
    }
    target.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return target


def _input_path(prompt: str) -> Path:
    return Path(input(prompt).strip().strip('"'))


def main() -> int:
    project_dir = Path(__file__).parent
    target = project_dir / "config.local.yaml"
    try:
        overwrite = False
        if target.exists():
            answer = (
                input("config.local.yaml 已存在，是否覆盖？[y/N]：").strip().lower()
            )
            if answer not in {"y", "yes"}:
                print("已取消，原配置未改变。")
                return 1
            overwrite = True

        player = _input_path("请拖入 dnplayer.exe（或粘贴完整路径）后按回车：")
        sibling_adb = player.expanduser().resolve().parent / "adb.exe"
        adb = (
            sibling_adb
            if sibling_adb.is_file()
            else _input_path("同目录未找到 adb.exe，请拖入 adb.exe 后按回车：")
        )
        result = write_local_config(project_dir, player, adb, overwrite=overwrite)
        print(f"配置已保存：{result}")
        print("现在可以运行 python main.py 测试。")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("配置已取消。")
        return 1
    except SetupConfigError as exc:
        print(f"配置失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
