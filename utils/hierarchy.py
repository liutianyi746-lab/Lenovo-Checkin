from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET


class HierarchyError(RuntimeError):
    """UI hierarchy 无法解析。"""


@dataclass
class UINode:
    element: ET.Element
    parent: UINode | None = None

    @property
    def attrib(self) -> dict[str, str]:
        return self.element.attrib

    @property
    def is_meaningful(self) -> bool:
        a = self.attrib
        return bool(
            a.get("text")
            or a.get("resource-id")
            or a.get("content-desc")
            or a.get("clickable") == "true"
        )

    def iter(self):
        yield self
        for child in self.element:
            yield from UINode(child, self).iter()


def parse_hierarchy(xml: str) -> UINode:
    try:
        return UINode(ET.fromstring(xml))
    except ET.ParseError as exc:
        raise HierarchyError(f"hierarchy XML 无效：{exc}") from exc


def find_click_target(root: UINode, target: UINode) -> UINode:
    del root
    node: UINode | None = target
    while node is not None:
        if (
            node.attrib.get("clickable") == "true"
            and node.attrib.get("enabled", "true") == "true"
        ):
            return node
        node = node.parent
    return target


def node_summary(node: UINode) -> str:
    a = node.attrib
    lines = [
        f"text: {a.get('text', '')}",
        f"resourceId: {a.get('resource-id', '')}",
        f"description: {a.get('content-desc', '')}",
        f"class: {a.get('class', '')}",
        f"clickable: {a.get('clickable', 'false')}",
        f"enabled: {a.get('enabled', 'true')}",
        f"selected: {a.get('selected', 'false')}",
        f"bounds: {a.get('bounds', '')}",
    ]
    if node.parent is not None:
        lines.extend(
            [
                "",
                "Parent:",
                f"class: {node.parent.attrib.get('class', '')}",
                f"clickable: {node.parent.attrib.get('clickable', 'false')}",
            ]
        )
    return "\n".join(lines)


def print_ui_elements(xml: str) -> int:
    root = parse_hierarchy(xml)
    nodes = [node for node in root.iter() if node.is_meaningful]
    for index, node in enumerate(nodes, 1):
        print("-" * 50)
        print(f"[Element {index}]\n")
        print(node_summary(node))
    if nodes:
        print("-" * 50)
    return len(nodes)
