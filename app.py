from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any


class AppError(RuntimeError):
    """联想 App 生命周期操作失败。"""


ACTIONABLE_RESOURCE_IDS = {
    "com.lenovo.club.app:id/navigator_bottom",
    "com.lenovo.club.app:id/personal_container",
    "com.lenovo.club.app:id/tv_sign_title",
    "com.lenovo.club.app:id/img_do_sign",
}
AI_WEBVIEW_ID = "com.lenovo.club.app:id/fl_webview_container"
AI_READY_TEXTS = {"签到", "深度思考(自动)", "会员日领福利"}


def is_actionable_hierarchy(xml: str) -> bool:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return False
    resource_ids = {node.attrib.get("resource-id", "") for node in root.iter()}
    if resource_ids & ACTIONABLE_RESOURCE_IDS:
        return True
    texts = {node.attrib.get("text", "").strip() for node in root.iter()}
    return AI_WEBVIEW_ID in resource_ids and bool(texts & AI_READY_TEXTS)


class LenovoApp:
    def __init__(
        self, device: Any, package_name: str, startup_timeout: int = 30
    ) -> None:
        self.d = device
        self.package_name = package_name
        self.startup_timeout = startup_timeout
        self.logger = logging.getLogger(__name__)

    def is_installed(self) -> bool:
        try:
            return self.package_name in self.d.app_list()
        except Exception as exc:
            raise AppError(f"无法读取 App 列表：{exc}") from exc

    def start(self) -> None:
        if not self.is_installed():
            raise AppError(f"未检测到 {self.package_name}，请先安装联想 App")
        self.logger.info("启动联想 App")
        try:
            self.d.app_start(self.package_name)
        except Exception as exc:
            raise AppError(f"无法启动联想 App：{exc}") from exc
        try:
            self.wait_until_ready(timeout=min(5.0, max(0.5, self.startup_timeout / 3)))
            return
        except AppError:
            self.logger.warning("通用 app_start 未拉起 App，尝试解析启动 Activity")
        self._start_resolved_activity()
        self.wait_until_ready()

    @staticmethod
    def _shell_output(response: Any) -> str:
        if hasattr(response, "output"):
            return str(response.output)
        if isinstance(response, (tuple, list)) and response:
            return str(response[0])
        return str(response)

    def _start_resolved_activity(self) -> None:
        try:
            response = self.d.shell(
                ["cmd", "package", "resolve-activity", "--brief", self.package_name]
            )
            activity = next(
                (
                    line.strip()
                    for line in reversed(self._shell_output(response).splitlines())
                    if "/" in line and line.strip().startswith(self.package_name)
                ),
                "",
            )
            if not activity:
                raise AppError(f"无法解析 {self.package_name} 的启动 Activity")
            self.logger.info("显式启动 Activity：%s", activity)
            result = self.d.shell(["am", "start", "-W", "-n", activity])
            output = self._shell_output(result)
            if "Error:" in output or "Exception" in output:
                raise AppError(f"显式启动 App 失败：{output.strip()}")
        except AppError:
            raise
        except Exception as exc:
            raise AppError(f"显式启动 App 失败：{exc}") from exc

    def stop(self) -> None:
        self.d.app_stop(self.package_name)

    def restart(self) -> None:
        self.stop()
        self.start()

    def wait_until_ready(self, timeout: float | None = None) -> None:
        wait_timeout = self.startup_timeout if timeout is None else timeout
        deadline = time.monotonic() + wait_timeout
        last_package = ""
        while time.monotonic() < deadline:
            try:
                current = self.d.app_current()
                last_package = current.get("package", "")
                xml = self.d.dump_hierarchy(compressed=False)
                if last_package == self.package_name and is_actionable_hierarchy(xml):
                    return
            except Exception as exc:  # noqa: BLE001 - uiautomator2 没有统一的 SDK 异常基类
                self.logger.debug("等待 App 就绪时暂时无法读取页面：%s", exc)
            time.sleep(0.5)
        raise AppError(
            f"App 加载超过 {wait_timeout:g} 秒，当前包名：{last_package or '未知'}"
        )
