from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from utils.hierarchy import UINode, find_click_target, parse_hierarchy


class NavigationError(RuntimeError):
    """无法识别页面或完成导航。"""


class SecurityChallengeError(NavigationError):
    """检测到必须人工处理的安全验证。"""


class PageState(Enum):
    LEXIANG_AI = "LEXIANG_AI"
    HOME = "HOME"
    MINE = "MINE"
    CHECKIN = "CHECKIN"
    UNKNOWN = "UNKNOWN"


SECURITY_WORDS = (
    "验证码",
    "滑块",
    "短信验证",
    "设备验证",
    "安全验证",
    "账号验证",
    "风险验证",
    "风控",
)
MARKETING_POPUP_CLOSE_ID = "com.lenovo.club.app:id/iv_advertise_cancel"
NATIVE_HOME_NAVIGATION_ID = "com.lenovo.club.app:id/navigator_bottom"


def _texts(xml: str) -> set[str]:
    return {
        node.attrib.get("text", "").strip()
        for node in parse_hierarchy(xml).iter()
        if node.attrib.get("text", "").strip()
    }


def has_security_challenge(xml: str) -> bool:
    content = " ".join(_texts(xml))
    return any(word in content for word in SECURITY_WORDS)


def has_known_marketing_popup(xml: str) -> bool:
    return any(
        node.attrib.get("resource-id") == MARKETING_POPUP_CLOSE_ID
        and node.attrib.get("clickable") == "true"
        for node in parse_hierarchy(xml).iter()
    )


def has_resource_id(xml: str, resource_id: str) -> bool:
    return any(
        node.attrib.get("resource-id") == resource_id
        for node in parse_hierarchy(xml).iter()
    )


def detect_page_from_xml(xml: str) -> PageState:
    root = parse_hierarchy(xml)
    texts = {
        node.attrib.get("text", "").strip()
        for node in root.iter()
        if node.attrib.get("text", "").strip()
    }
    if "签到有礼" in texts or any(
        node.attrib.get("resource-id") == "com.lenovo.club.app:id/tv_sign_title"
        for node in root.iter()
    ):
        return PageState.CHECKIN
    resource_ids = {node.attrib.get("resource-id", "") for node in root.iter()}
    if {"我的订单", "签到领好礼"}.issubset(texts):
        return PageState.MINE
    if "com.lenovo.club.app:id/personal_container" in resource_ids:
        return PageState.MINE
    if {"首页", "分类", "购物车", "我的"}.issubset(texts):
        return PageState.HOME
    if NATIVE_HOME_NAVIGATION_ID in resource_ids:
        return PageState.HOME
    if {"乐享AI", "首页"}.issubset(texts):
        return PageState.LEXIANG_AI
    if "com.lenovo.club.app:id/fl_webview_container" in resource_ids:
        return PageState.LEXIANG_AI
    # 签到页结构尚未知。只有离开已知 MINE 页面后，运行时才能将其确认成 CHECKIN。
    return PageState.UNKNOWN


def _bounds_center(bounds: str) -> tuple[int, int]:
    import re

    values = [int(value) for value in re.findall(r"\d+", bounds)]
    if len(values) != 4:
        raise NavigationError(f"控件 bounds 无效：{bounds}")
    return (values[0] + values[2]) // 2, (values[1] + values[3]) // 2


def _best_text_node(root: UINode, text: str, prefer: str) -> UINode | None:
    matches = [node for node in root.iter() if node.attrib.get("text") == text]
    if not matches:
        return None

    def score(node: UINode) -> tuple[int, int]:
        bounds = node.attrib.get("bounds", "")
        try:
            _, y = _bounds_center(bounds)
        except NavigationError:
            y = 0
        return (
            1
            if (find_click_target(root, node).attrib.get("clickable") == "true")
            else 0,
            -y if prefer == "top" else y,
        )

    return max(matches, key=score)


def click_element_or_clickable_parent(device: Any, root: UINode, node: UINode) -> None:
    target = find_click_target(root, node)
    node_resource_id = node.attrib.get("resource-id", "")
    node_text = node.attrib.get("text", "")
    if (
        node_resource_id
        and node_text
        and device(resourceId=node_resource_id, text=node_text).exists
    ):
        # 同一底部导航的父节点可能复用 resource-id；组合文字唯一定位子节点中心。
        device(resourceId=node_resource_id, text=node_text).click()
        return
    resource_id = target.attrib.get("resource-id", "")
    text = target.attrib.get("text", "")
    description = target.attrib.get("content-desc", "")
    if resource_id and device(resourceId=resource_id).exists:
        device(resourceId=resource_id).click()
    elif text and device(text=text).exists:
        device(text=text).click()
    elif description and device(description=description).exists:
        device(description=description).click()
    elif (
        node.attrib.get("resource-id")
        and device(resourceId=node.attrib["resource-id"]).exists
    ):
        device(resourceId=node.attrib["resource-id"]).click()
    elif node.attrib.get("text") and device(text=node.attrib["text"]).exists:
        # 部分底部导航父容器虽标记 clickable，但只有文字节点中心响应点击。
        device(text=node.attrib["text"]).click()
    elif (
        node.attrib.get("content-desc")
        and device(description=node.attrib["content-desc"]).exists
    ):
        device(description=node.attrib["content-desc"]).click()
    else:
        # hierarchy 已确认目标或其父节点可点击；坐标只取动态 bounds 中心，不写死像素。
        device.click(*_bounds_center(target.attrib.get("bounds", "")))


class Navigator:
    def __init__(
        self, device: Any, element_timeout: int = 15, max_retries: int = 3
    ) -> None:
        self.d = device
        self.element_timeout = element_timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def hierarchy(self) -> str:
        try:
            xml = self.d.dump_hierarchy(compressed=False)
        except Exception as exc:
            raise NavigationError(f"无法读取 UI hierarchy：{exc}") from exc
        if has_security_challenge(xml):
            raise SecurityChallengeError("检测到安全验证，需要人工处理")
        return xml

    def detect_page(self) -> PageState:
        xml = self.hierarchy()
        if has_known_marketing_popup(xml):
            self.logger.info("关闭已确认的商城广告弹窗")
            close_button = self.d(resourceId=MARKETING_POPUP_CLOSE_ID)
            if close_button.exists:
                close_button.click()
                time.sleep(0.5)
                xml = self.hierarchy()
        state = detect_page_from_xml(xml)
        self.logger.info("当前页面：%s", state.value)
        return state

    def _wait_for(self, predicate: Callable[[str], bool], description: str) -> str:
        deadline = time.monotonic() + self.element_timeout
        while time.monotonic() < deadline:
            xml = self.hierarchy()
            if has_known_marketing_popup(xml):
                self.logger.info("关闭已确认的商城广告弹窗")
                close_button = self.d(resourceId=MARKETING_POPUP_CLOSE_ID)
                if close_button.exists:
                    close_button.click()
                    time.sleep(0.5)
                    continue
            if predicate(xml):
                return xml
            time.sleep(0.5)
        raise NavigationError(f"等待{description}超过 {self.element_timeout} 秒")

    def _click_text(
        self, text: str, prefer: str = "top", contains: bool = False
    ) -> None:
        for _ in range(self.max_retries):
            xml = self.hierarchy()
            root = parse_hierarchy(xml)
            node = _best_text_node(root, text, prefer)
            if node is None and contains:
                node = next(
                    (
                        item
                        for item in root.iter()
                        if text in item.attrib.get("text", "")
                    ),
                    None,
                )
            if node is not None:
                click_element_or_clickable_parent(self.d, root, node)
                return
            time.sleep(0.5)
        raise NavigationError(f"找不到控件：{text}")

    def go_to_home(self) -> None:
        self.logger.info("点击顶部：首页")
        try:
            self._click_text("首页", prefer="top")
        except NavigationError:
            self.logger.warning("首页未暴露可访问节点，使用已验证的比例坐标")
            width, height = self.d.window_size()
            self.d.click(width * 5 // 32, height * 7 // 72)
        self._wait_for(
            lambda xml: has_resource_id(xml, NATIVE_HOME_NAVIGATION_ID),
            "原生首页底部导航",
        )

    def go_to_mine(self) -> None:
        self._wait_for(
            lambda xml: has_resource_id(xml, NATIVE_HOME_NAVIGATION_ID),
            "原生首页底部导航",
        )
        self.logger.info("点击底部：我的")
        self._click_text("我的", prefer="bottom")
        self._wait_for(
            lambda xml: detect_page_from_xml(xml) is PageState.MINE, "我的页面"
        )

    def open_checkin_page(self) -> None:
        self.logger.info("找到：签到领好礼")
        before = self.hierarchy()
        try:
            self._click_text("签到领好礼", prefer="top", contains=True)
        except NavigationError:
            self.logger.warning("签到入口未暴露可访问节点，使用已验证的比例坐标")
            width, height = self.d.window_size()
            self.d.click(int(width * 0.446), int(height * 0.148))
        self.logger.info("点击签到入口")
        self._wait_for(
            lambda xml: (
                xml != before and detect_page_from_xml(xml) is not PageState.MINE
            ),
            "签到页面",
        )

    def navigate_to_checkin(self) -> None:
        for _ in range(self.max_retries + 2):
            state = self.detect_page()
            if state is PageState.LEXIANG_AI:
                self.go_to_home()
            elif state is PageState.HOME:
                self.go_to_mine()
            elif state is PageState.MINE:
                self.open_checkin_page()
                return
            elif state is PageState.CHECKIN:
                self.logger.info("当前已经位于签到页面")
                return
            else:
                # 启动时可能仍在过渡页，短暂等待后重新识别，不猜测页面。
                time.sleep(1)
        raise NavigationError("无法从当前页面导航到签到入口")
