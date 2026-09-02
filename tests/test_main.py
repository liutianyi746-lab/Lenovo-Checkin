import main as main_module
from config import load_config


def test_run_resets_adb_before_ensuring_emulator(monkeypatch, tmp_path) -> None:
    events: list[str] = []
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "ldplayer:\n  close_after_run: false\n"
        "paths:\n  logs: logs\n  screenshots: screenshots\n  dumps: dumps\n",
        encoding="utf-8",
    )

    class FakeManager:
        def __init__(self, config) -> None:
            del config

        def reset_adb_server(self) -> None:
            events.append("reset")

        def ensure_running(self) -> str:
            events.append("ensure")
            raise RuntimeError("stop after order check")

    monkeypatch.setattr(main_module, "LDPlayerManager", FakeManager)

    assert main_module.run(load_config(config_file)) == 1
    assert events == ["reset", "ensure"]


def test_main_returns_distinct_error_without_running_when_lock_is_busy(
    monkeypatch,
) -> None:
    class BusyLock:
        def __init__(self, path) -> None:
            del path

        def __enter__(self):
            raise main_module.AlreadyRunningError("busy")

        def __exit__(self, *exc_info) -> None:
            del exc_info

    monkeypatch.setattr(main_module, "RunLock", BusyLock)
    monkeypatch.setattr(
        main_module,
        "run",
        lambda config: (_ for _ in ()).throw(AssertionError("run must not start")),
    )

    assert main_module.main() == 2
