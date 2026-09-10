"""质量门自身守卫：用合成图验证 docs/assets/quality_gate.py 的判定不回退。

质量门是光栅图标入库的必要关卡（docs/plans/ui-replication-plan.md Phase 6），
本文件保证其判据本身不被意外破坏。
"""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "quality_gate", BASE / "docs" / "assets" / "quality_gate.py"
)
qg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qg)


def _save(tmp_path, arr, name):
    p = tmp_path / name
    Image.fromarray(arr).save(p)
    return p


def test_clean_icon_passes(tmp_path):
    """单一实心图形：全部判据通过。"""
    a = np.zeros((60, 60, 4), dtype=np.uint8)
    a[10:50, 10:50, :3] = (42, 34, 24)
    a[10:50, 10:50, 3] = 255
    m = qg.metrics(_save(tmp_path, a, "clean.png"))
    v, fails = qg.verdict(m)
    assert v == "PASS", fails


def test_green_background_fails_on_green_ratio(tmp_path):
    """绿幕残留（绿主导像素）：G3 绿边判据必须命中。"""
    a = np.zeros((60, 60, 4), dtype=np.uint8)
    a[:, :, 1] = 255
    a[10:50, 10:50, 3] = 255
    m = qg.metrics(_save(tmp_path, a, "green.png"))
    v, fails = qg.verdict(m)
    assert v == "FAIL" and "G3绿边" in fails


def test_fragmented_icon_fails(tmp_path):
    """散点碎片：G4 主体完整性判据必须命中。"""
    a = np.zeros((80, 80, 4), dtype=np.uint8)
    rng = np.random.default_rng(0)
    ys, xs = rng.integers(0, 80, size=(400, 2)).T
    a[ys, xs, 3] = 255
    a[ys, xs, :3] = (42, 34, 24)
    m = qg.metrics(_save(tmp_path, a, "frag.png"))
    v, fails = qg.verdict(m)
    assert v == "FAIL" and "G4碎片化" in fails


def test_two_subjects_flagged_manual(tmp_path):
    """两块大体量主体：合并切割嫌疑 → MANUAL（人工分拆复审）。"""
    a = np.zeros((120, 240, 4), dtype=np.uint8)
    a[20:100, 10:90, 3] = 255
    a[20:100, 10:90, :3] = (42, 34, 24)
    a[20:100, 150:230, 3] = 255
    a[20:100, 150:230, :3] = (120, 30, 30)
    m = qg.metrics(_save(tmp_path, a, "merged.png"))
    v, _ = qg.verdict(m)
    assert v == "MANUAL"


def test_blank_icon_fails(tmp_path):
    """全透明空图：G1 判据必须命中。"""
    a = np.zeros((60, 60, 4), dtype=np.uint8)
    m = qg.metrics(_save(tmp_path, a, "blank.png"))
    v, fails = qg.verdict(m)
    assert v == "FAIL" and "G1空白" in fails
