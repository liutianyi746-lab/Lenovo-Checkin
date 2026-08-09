from pathlib import Path

import pytest

from checkin import (
    CheckinError,
    CheckinResult,
    CheckinStatus,
    detect_checkin_status_from_xml,
    perform_checkin,
)


def hierarchy(*nodes: str) -> str:
    return "<hierarchy>" + "".join(nodes) + "</hierarchy>"


TITLE = '<node text="签到有礼" resource-id="com.lenovo.club.app:id/tv_sign_title" />'
BUTTON = (
    '<node resource-id="com.lenovo.club.app:id/img_do_sign" '
    'class="android.widget.ImageView" clickable="true" enabled="true" />'
)


class FakeSelector:
    def __init__(self, device: "FakeDevice") -> None:
        self.device = device

    @property
    def exists(self) -> bool:
        return self.device.index == 0

    def click(self) -> None:
        self.device.clicks += 1
        self.device.index = 1


class FakeDevice:
    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self.index = 0
        self.clicks = 0

    def dump_hierarchy(self, compressed: bool = False) -> str:
        del compressed
        return self.pages[self.index]

    def __call__(self, **selector: str) -> FakeSelector:
        assert selector == {"resourceId": "com.lenovo.club.app:id/img_do_sign"}
        return FakeSelector(self)


def test_detects_unsigned_when_real_button_exists() -> None:
    assert (
        detect_checkin_status_from_xml(hierarchy(TITLE, BUTTON))
        is CheckinStatus.UNSIGNED
    )


def test_detects_signed_when_title_exists_and_button_is_absent() -> None:
    assert detect_checkin_status_from_xml(hierarchy(TITLE)) is CheckinStatus.SIGNED


def test_does_not_guess_status_outside_checkin_page() -> None:
    assert (
        detect_checkin_status_from_xml(hierarchy('<node text="首页" />'))
        is CheckinStatus.UNKNOWN
    )


def test_perform_checkin_clicks_once_and_verifies_button_disappears() -> None:
    device = FakeDevice([hierarchy(TITLE, BUTTON), hierarchy(TITLE)])
    result = perform_checkin(device, timeout=1, poll_interval=0)
    assert result is CheckinResult.SUCCESS
    assert device.clicks == 1


def test_perform_checkin_never_clicks_when_already_signed() -> None:
    device = FakeDevice([hierarchy(TITLE)])
    result = perform_checkin(device, timeout=1, poll_interval=0)
    assert result is CheckinResult.ALREADY_SIGNED
    assert device.clicks == 0


def test_perform_checkin_refuses_unknown_page() -> None:
    device = FakeDevice([hierarchy('<node text="首页" />')])
    with pytest.raises(CheckinError, match="无法判断"):
        perform_checkin(device, timeout=1, poll_interval=0)


def test_saved_real_xml_matches_expected_states() -> None:
    samples = list(Path("dumps").glob("checkin*.xml"))
    if not samples:
        pytest.skip("本机尚未采集真实签到 XML")
    statuses = {
        path: detect_checkin_status_from_xml(path.read_text(encoding="utf-8"))
        for path in samples
    }
    assert CheckinStatus.SIGNED in statuses.values()
    for path, status in statuses.items():
        xml = path.read_text(encoding="utf-8")
        if "com.lenovo.club.app:id/img_do_sign" in xml:
            assert status is CheckinStatus.UNSIGNED
