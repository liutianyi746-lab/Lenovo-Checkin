from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from navigation import has_security_challenge
from utils.hierarchy import parse_hierarchy

SIGN_BUTTON_ID = "com.lenovo.club.app:id/img_do_sign"
SIGN_TITLE_ID = "com.lenovo.club.app:id/tv_sign_title"


class CheckinError(RuntimeError):
    """签到状态无法确认或签到失败。"""


class CheckinStatus(Enum):
    UNSIGNED = "UNSIGNED"
    SIGNED = "SIGNED"
    UNKNOWN = "UNKNOWN"


class CheckinResult(Enum):
    SUCCESS = "SUCCESS"
    ALREADY_SIGNED = "ALREADY_SIGNED"


def detect_checkin_status_from_xml(xml: str) -> CheckinStatus:
    root = parse_hierarchy(xml)
    nodes = list(root.iter())
    on_checkin_page = any(
        node.attrib.get("resource-id") == SIGN_TITLE_ID
        or node.attrib.get("text") == "签到有礼"
        for node in nodes
    )
    if not on_checkin_page:
        return CheckinStatus.UNKNOWN
    button_exists = any(
        node.attrib.get("resource-id") == SIGN_BUTTON_ID
        and node.attrib.get("enabled", "true") == "true"
        for node in nodes
    )
    return CheckinStatus.UNSIGNED if button_exists else CheckinStatus.SIGNED


def detect_checkin_status(device: Any) -> CheckinStatus:
    xml = device.dump_hierarchy(compressed=False)
    if has_security_challenge(xml):
        raise CheckinError("检测到安全验证，需要人工处理")
    return detect_checkin_status_from_xml(xml)


def perform_checkin(
    device: Any, timeout: float = 15, poll_interval: float = 0.5
) -> CheckinResult:
    logger = logging.getLogger(__name__)
    status = detect_checkin_status(device)
    if status is CheckinStatus.SIGNED:
        logger.info("今日已经签到，不重复点击")
        return CheckinResult.ALREADY_SIGNED
    if status is not CheckinStatus.UNSIGNED:
        raise CheckinError("无法判断当前签到状态，拒绝点击")

    button = device(resourceId=SIGN_BUTTON_ID)
    if not button.exists:
        raise CheckinError("状态显示未签到，但未找到真实签到按钮")
    logger.info("点击立即签到")
    button.click()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = detect_checkin_status(device)
        if status is CheckinStatus.SIGNED:
            logger.info("签到成功：签到按钮已消失")
            return CheckinResult.SUCCESS
        time.sleep(poll_interval)
    raise CheckinError(f"点击后 {timeout:g} 秒内未确认签到成功")


def verify_checkin_result(device: Any) -> bool:
    return detect_checkin_status(device) is CheckinStatus.SIGNED
