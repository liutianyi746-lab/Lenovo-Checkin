import main as main_module


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
