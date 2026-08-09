from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def capture_page(device: Any, screenshot_path: Path, dump_path: Path) -> str:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    device.screenshot(str(screenshot_path))
    xml = device.dump_hierarchy(compressed=False)
    dump_path.write_text(xml, encoding="utf-8")
    return xml


def capture_error(device: Any, screenshots: Path, dumps: Path) -> tuple[Path, Path]:
    suffix = timestamp()
    image_path, xml_path = (
        screenshots / f"error_{suffix}.png",
        dumps / f"error_{suffix}.xml",
    )
    capture_page(device, image_path, xml_path)
    return image_path, xml_path
