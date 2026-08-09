from utils.hierarchy import find_click_target, parse_hierarchy

XML = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node class="android.widget.FrameLayout" clickable="true" enabled="true" bounds="[0,0][200,100]">
    <node text="签到领好礼" class="android.widget.TextView" clickable="false" enabled="true" bounds="[10,10][190,90]" />
  </node>
  <node class="android.view.View" clickable="false" enabled="true" bounds="[0,100][200,200]" />
</hierarchy>"""


def test_find_click_target_returns_nearest_clickable_parent() -> None:
    root = parse_hierarchy(XML)
    target = next(
        node for node in root.iter() if node.attrib.get("text") == "签到领好礼"
    )
    assert (
        find_click_target(root, target).attrib["class"] == "android.widget.FrameLayout"
    )


def test_meaningful_nodes_filter_empty_noninteractive_nodes() -> None:
    root = parse_hierarchy(XML)
    meaningful = [node for node in root.iter() if node.is_meaningful]
    assert len(meaningful) == 2
