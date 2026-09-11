"""JS 航线显示一致性冒烟（Node 桩环境）——批次 C3。"""
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def test_route_display_node_suite():
    r = subprocess.run(["node", str(BASE / "tests" / "ui" / "route_display.test.mjs")],
                       capture_output=True, text=True, cwd=BASE, timeout=60)
    assert r.returncode == 0, f"Node 航线显示测试失败:\n{r.stdout}\n{r.stderr}"
    assert "ROUTE-DISPLAY PASS" in r.stdout
