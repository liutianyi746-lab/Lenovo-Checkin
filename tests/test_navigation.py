from navigation import (
    NavigationError,
    Navigator,
    PageState,
    detect_page_from_xml,
    has_known_marketing_popup,
    has_security_challenge,
)


def xml_with(*texts: str) -> str:
    nodes = "".join(
        f'<node text="{text}" class="android.widget.TextView" />' for text in texts
    )
    return f"<hierarchy>{nodes}</hierarchy>"


def test_detects_confirmed_page_states() -> None:
    assert detect_page_from_xml(xml_with("乐享AI", "首页")) is PageState.LEXIANG_AI
    assert (
        detect_page_from_xml(xml_with("首页", "分类", "购物车", "我的"))
        is PageState.HOME
    )
    assert detect_page_from_xml(xml_with("我的订单", "签到领好礼")) is PageState.MINE
    assert detect_page_from_xml(xml_with("签到有礼")) is PageState.CHECKIN


def test_detects_webview_ai_and_native_home_by_real_resource_ids() -> None:
    ai = (
        '<hierarchy><node resource-id="com.lenovo.club.app:id/fl_webview_container" />'
        "</hierarchy>"
    )
    home = (
        '<hierarchy><node resource-id="com.lenovo.club.app:id/navigator_bottom" />'
        "</hierarchy>"
    )
    assert detect_page_from_xml(ai) is PageState.LEXIANG_AI
    assert detect_page_from_xml(home) is PageState.HOME


def test_unknown_page_is_not_guessed_as_checkin() -> None:
    assert detect_page_from_xml(xml_with("每日好礼")) is PageState.UNKNOWN


def test_security_challenge_is_detected_without_bypass() -> None:
    assert has_security_challenge(xml_with("请完成滑块验证"))


def test_detects_only_confirmed_marketing_popup_close_button() -> None:
    known = (
        '<hierarchy><node resource-id="com.lenovo.club.app:id/iv_advertise_cancel" '
        'clickable="true" /></hierarchy>'
    )
    unknown = '<hierarchy><node text="稍后再说" clickable="true" /></hierarchy>'
    assert has_known_marketing_popup(known)
    assert not has_known_marketing_popup(unknown)


def test_go_to_home_uses_verified_fallback_and_waits_for_native_bottom_navigation(
    monkeypatch,
) -> None:
    class Device:
        def __init__(self) -> None:
            self.clicks: list[tuple[int, int]] = []

        def window_size(self) -> tuple[int, int]:
            return 1920, 1080

        def click(self, x: int, y: int) -> None:
            self.clicks.append((x, y))

    device = Device()
    navigator = Navigator(device)
    checked: list[tuple[bool, bool, str]] = []
    right_products = '<hierarchy><node resource-id="rv_recommend" /></hierarchy>'
    native_home = (
        '<hierarchy><node resource-id="com.lenovo.club.app:id/navigator_bottom" />'
        "</hierarchy>"
    )

    monkeypatch.setattr(
        navigator,
        "_click_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(NavigationError("missing")),
    )

    def wait_for(predicate, description: str) -> str:
        checked.append((predicate(right_products), predicate(native_home), description))
        return native_home

    monkeypatch.setattr(navigator, "_wait_for", wait_for)

    navigator.go_to_home()

    assert device.clicks == [(300, 105)]
    assert checked == [(False, True, "原生首页底部导航")]


def test_go_to_mine_waits_for_native_home_before_clicking_mine(monkeypatch) -> None:
    navigator = Navigator(object())
    events: list[str] = []
    native_home = (
        '<hierarchy><node resource-id="com.lenovo.club.app:id/navigator_bottom" />'
        "</hierarchy>"
    )

    def wait_for(predicate, description: str) -> str:
        events.append(f"wait:{description}")
        if description == "原生首页底部导航":
            assert predicate(native_home)
        return native_home

    def click_text(text: str, prefer: str = "top", contains: bool = False) -> None:
        del prefer, contains
        events.append(f"click:{text}")

    monkeypatch.setattr(navigator, "_wait_for", wait_for)
    monkeypatch.setattr(navigator, "_click_text", click_text)

    navigator.go_to_mine()

    assert events == [
        "wait:原生首页底部导航",
        "click:我的",
        "wait:我的页面",
    ]
