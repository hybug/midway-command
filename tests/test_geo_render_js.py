"""O.3 GeoJSON 地理层渲染一致性冒烟（Node 桩环境）——珊瑚海战区切换。

同 test_route_display_js.py 手法：subprocess 驱动 tests/ui/geo_render.test.mjs，
断言地理层消费真实 geography.geojson（多边形/标注/样式全走数据）、双舰队上图、
midway 近景包不回归。
"""
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def test_geo_render_node_suite():
    r = subprocess.run(["node", str(BASE / "tests" / "ui" / "geo_render.test.mjs")],
                       capture_output=True, text=True, cwd=BASE, timeout=60)
    assert r.returncode == 0, f"Node 地理层渲染测试失败:\n{r.stdout}\n{r.stderr}"
    assert "GEO-RENDER PASS" in r.stdout
