from __future__ import annotations

import logging
import sys
from pathlib import Path

from app import LenovoApp
from checkin import CheckinResult, perform_checkin
from config import Config, load_config, resolve_config_path
from device import AndroidDevice
from emulator import LDPlayerManager
from navigation import Navigator, SecurityChallengeError
from utils.hierarchy import print_ui_elements
from utils.logger import setup_logger, success
from utils.screenshot import capture_error, capture_page, timestamp


def run(config: Config) -> int:
    logger = setup_logger(config.paths.logs)
    logger.info("开始联想自动签到任务")
    android: AndroidDevice | None = None
    manager: LDPlayerManager | None = None
    exit_code = 1
    try:
        manager = LDPlayerManager(config)
        address = manager.ensure_running()
        android = AndroidDevice(
            address, manager.find_adb_executable(), config.adb.connect_timeout
        )
        d = android.connect()
        LenovoApp(d, config.app.package_name, config.app.startup_timeout).start()
        Navigator(
            d, config.automation.element_timeout, config.automation.max_retries
        ).navigate_to_checkin()

        screenshot_path = config.paths.screenshots / "checkin_page.png"
        dump_path = config.paths.dumps / "checkin_page.xml"
        xml = capture_page(d, screenshot_path, dump_path)
        print_ui_elements(xml)
        logger.info("已成功进入签到页面")
        logger.info("Screenshot: %s", screenshot_path)
        logger.info("Hierarchy: %s", dump_path)

        result = perform_checkin(d, timeout=config.automation.element_timeout)
        result_suffix = timestamp()
        result_image = config.paths.screenshots / f"checkin_result_{result_suffix}.png"
        result_xml = config.paths.dumps / f"checkin_result_{result_suffix}.xml"
        capture_page(d, result_image, result_xml)
        if result is CheckinResult.ALREADY_SIGNED:
            success(logger, "今日已经签到，无需重复操作")
        else:
            success(logger, "签到成功")
        logger.info("Result screenshot: %s", result_image)
        logger.info("Result hierarchy: %s", result_xml)
        exit_code = 0
    except SecurityChallengeError as exc:
        logger.warning("%s", exc)
    except Exception:
        logger.exception("任务失败")
    if exit_code != 0 and (
        android is not None
        and android.d is not None
        and config.automation.save_debug_on_error
    ):
        try:
            image, xml = capture_error(
                android.d, config.paths.screenshots, config.paths.dumps
            )
            logger.info("错误截图：%s", image)
            logger.info("错误 hierarchy：%s", xml)
        except Exception as capture_exc:  # noqa: BLE001 - 错误现场保存不能遮蔽原始失败
            logger.error("保存错误现场失败：%s", capture_exc)
    if manager is not None and config.ldplayer.close_after_run:
        try:
            manager.stop()
            logger.info("雷电模拟器已关闭")
        except Exception:
            logger.exception("关闭雷电模拟器失败")
            exit_code = 1
    return exit_code


def main() -> int:
    try:
        project_dir = Path(__file__).parent
        return run(load_config(resolve_config_path(project_dir)))
    except Exception as exc:  # noqa: BLE001 - 配置入口需要转为稳定退出码
        logging.basicConfig(
            level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s"
        )
        logging.getLogger(__name__).error("初始化失败：%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
