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
        resource_id = (
            "com.lenovo.club.app:id/navigator_bottom" if self.package == "com.lenovo.club.app" else ""
        )
        return f'<hierarchy><node resource-id="{resource_id}" /></hierarchy>'

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


def test_wait_until_ready_ignores_splash_and_empty_webview_until_ui_is_actionable() -> None:
    class LoadingDevice:
        def __init__(self) -> None:
            self.dump_count = 0

        def app_current(self) -> dict[str, str]:
            return {"package": "com.lenovo.club.app"}

        def dump_hierarchy(self, compressed: bool = False) -> str:
            del compressed
            self.dump_count += 1
            if self.dump_count == 1:
                return '<hierarchy><node resource-id="android:id/content" /></hierarchy>'
            if self.dump_count == 2:
                return (
                    '<hierarchy><node resource-id="com.lenovo.club.app:id/'
                    'fl_webview_container" /></hierarchy>'
                )
            return (
                '<hierarchy><node resource-id="com.lenovo.club.app:id/'
                'fl_webview_container"><node text="会员日领福利" /></node></hierarchy>'
            )

    device = LoadingDevice()

    LenovoApp(device, "com.lenovo.club.app", startup_timeout=2).wait_until_ready()

    assert device.dump_count == 3
