from navigation import (
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
