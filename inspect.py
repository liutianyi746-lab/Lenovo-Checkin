"""页面检查入口。

文件名由项目需求固定为 inspect.py。Python 标准库也有同名模块，因此当本文件被
第三方库以 ``import inspect`` 导入时，透明加载标准库实现，避免遮蔽标准库。
"""

if __name__ != "__main__":
    import os as _os

    _stdlib_inspect = _os.path.join(_os.path.dirname(_os.__file__), "inspect.py")
    with open(_stdlib_inspect, "rb") as _source:
        exec(compile(_source.read(), _stdlib_inspect, "exec"), globals(), globals())  # noqa: S102 - 标准库同名代理
else:
    import sys
    from pathlib import Path

    from config import load_config
    from device import AndroidDevice
    from emulator import LDPlayerManager
    from utils.hierarchy import print_ui_elements
    from utils.logger import setup_logger
    from utils.screenshot import capture_page, timestamp

    def main() -> int:
        config = load_config(Path(__file__).with_name("config.yaml"))
        logger = setup_logger(config.paths.logs)
        try:
            manager = LDPlayerManager(config)
            address = manager.ensure_running()
            d = AndroidDevice(
                address, manager.find_adb_executable(), config.adb.connect_timeout
            ).connect()
            suffix = timestamp()
            image_path = config.paths.screenshots / f"inspect_{suffix}.png"
            xml_path = config.paths.dumps / f"inspect_{suffix}.xml"
            xml = capture_page(d, image_path, xml_path)
            count = print_ui_elements(xml)
            logger.info("已输出 %d 个重要控件", count)
            logger.info("Screenshot: %s", image_path)
            logger.info("Hierarchy: %s", xml_path)
            return 0
        except Exception:
            logger.exception("页面检查失败")
            return 1

    sys.exit(main())
