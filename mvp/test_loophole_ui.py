from pathlib import Path
import re

HTML = Path(__file__).with_name("loophole.html").read_text(encoding="utf-8")


def test_reset_restores_scene_status_and_syncs_visual_state():
    match = re.search(r'\$\("reset"\)\.onclick=\(\)=>\{(.*?)renderLog\(\)\};', HTML, re.S)
    assert match, "reset handler should remain identifiable"
    body = match.group(1)

    assert 'selected=new Set()' in body
    assert 'found=new Set()' in body
    assert 'hiddenSolved=false' in body
    assert 'roomStatus").textContent="位置：铜钥匙在右侧木箱旁；旧铜铃在滑轨边；鱼钩在左侧墙边；破洞位于墙脚。"' in body
    assert 'syncSceneObjects()' in body
    assert body.index('found=new Set()') < body.index('syncSceneObjects()')


def test_scene_sync_derives_visual_classes_from_current_state():
    match = re.search(r'function syncSceneObjects\(\)\{(.*?)\}\nfunction animateWorld', HTML, re.S)
    assert match, "scene synchronization function should remain identifiable"
    body = match.group(1)

    assert 'el.classList.toggle("selected",selected.has(id))' in body
    assert 'el.classList.toggle("inspected",found.has(id))' in body
    assert 'el.classList.toggle("active",found.has(el.dataset.map)||selected.has(el.dataset.map))' in body
