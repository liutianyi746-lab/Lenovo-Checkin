from pathlib import Path

import pytest

from config import ConfigError, load_config, resolve_config_path


def test_load_config_resolves_output_paths_from_config_directory(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "app:\n  package_name: com.lenovo.club.app\n"
        "ldplayer:\n  startup_timeout: 120\n  instance_index: 0\n"
        "adb:\n  connect_timeout: 30\n"
        "automation:\n  element_timeout: 15\n  max_retries: 3\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.paths.logs == tmp_path / "logs"
    assert config.app.package_name == "com.lenovo.club.app"
    assert config.ldplayer.close_after_run is True
    assert config.paths.dumps.is_dir()


def test_load_config_rejects_negative_instance_index(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ldplayer:\n  instance_index: -1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="instance_index"):
        load_config(config_file)


def test_resolve_config_path_prefers_local_file(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "config.local.yaml").write_text("{}", encoding="utf-8")

    assert resolve_config_path(tmp_path) == tmp_path / "config.local.yaml"


def test_resolve_config_path_falls_back_to_public_file(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("{}", encoding="utf-8")

    assert resolve_config_path(tmp_path) == tmp_path / "config.yaml"
