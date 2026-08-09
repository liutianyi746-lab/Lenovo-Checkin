from pathlib import Path

import pytest

from config import load_config
from setup_config import SetupConfigError, write_local_config


def test_write_local_config_creates_loadable_config(tmp_path: Path) -> None:
    install_dir = tmp_path / "雷电 模拟器"
    install_dir.mkdir()
    player = install_dir / "dnplayer.exe"
    adb = install_dir / "adb.exe"
    player.touch()
    adb.touch()

    result = write_local_config(tmp_path, player, adb)

    config = load_config(result)
    assert result == tmp_path / "config.local.yaml"
    assert Path(config.ldplayer.executable_path) == player.resolve()
    assert Path(config.adb.executable_path) == adb.resolve()
    assert config.ldplayer.instance_index == 0
    assert config.ldplayer.close_after_run is True


def test_write_local_config_rejects_missing_player_without_creating_file(
    tmp_path: Path,
) -> None:
    adb = tmp_path / "adb.exe"
    adb.touch()

    with pytest.raises(SetupConfigError, match="雷电"):
        write_local_config(tmp_path, tmp_path / "dnplayer.exe", adb)

    assert not (tmp_path / "config.local.yaml").exists()


def test_write_local_config_does_not_overwrite_without_permission(
    tmp_path: Path,
) -> None:
    player = tmp_path / "dnplayer.exe"
    adb = tmp_path / "adb.exe"
    player.touch()
    adb.touch()
    target = tmp_path / "config.local.yaml"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(SetupConfigError, match="已存在"):
        write_local_config(tmp_path, player, adb)

    assert target.read_text(encoding="utf-8") == "original"
