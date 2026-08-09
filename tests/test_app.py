from app import LenovoApp


class ShellResult:
    def __init__(self, output: str) -> None:
        self.output = output


class ColdStartDevice:
    def __init__(self) -> None:
        self.package = "com.android.launcher3"
        self.shell_calls: list[list[str]] = []

    def app_list(self) -> list[str]:
        return ["com.lenovo.club.app"]

    def app_start(self, package: str) -> None:
        assert package == "com.lenovo.club.app"

    def app_current(self) -> dict[str, str]:
        return {"package": self.package}

    def dump_hierarchy(self, compressed: bool = False) -> str:
        del compressed
        return "<hierarchy><node /></hierarchy>"

    def shell(self, command: list[str]) -> ShellResult:
        self.shell_calls.append(command)
        if command[:3] == ["cmd", "package", "resolve-activity"]:
            return ShellResult("com.lenovo.club.app/.AppStart\n")
        if command[:3] == ["am", "start", "-W"]:
            self.package = "com.lenovo.club.app"
            return ShellResult("Status: ok\n")
        raise AssertionError(command)


def test_start_falls_back_to_resolved_activity_after_cold_start() -> None:
    device = ColdStartDevice()
    LenovoApp(device, "com.lenovo.club.app", startup_timeout=1).start()
    assert [
        "am",
        "start",
        "-W",
        "-n",
        "com.lenovo.club.app/.AppStart",
    ] in device.shell_calls
