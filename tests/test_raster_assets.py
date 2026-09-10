"""光栅图标素材守卫（docs/plans/ui-replication-plan.md Phase 6）。"""
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
DST = BASE / "static" / "assets" / "ui" / "icons"

# 输出名 → 最大边长 px。与 docs/assets/curate_icons.py 的 TARGETS 保持一致。
RASTER_ICONS = {
    "fleet_tag_ent.png": 64,
    "aircraft_topdown.png": 72,
    "fleet_tag_hor.png": 64,
    "fleet_tag_cv.png": 64,
    "fleet_tag_bb.png": 64,
    "enemy_tag_q.png": 72,
    "compass_raster.png": 96,
}


def test_raster_icons_exist():
    missing = [f for f in RASTER_ICONS if not (DST / f).exists()]
    assert missing == [], f"缺少光栅图标: {missing}"


def test_raster_icons_rgba_nonempty_within_size():
    for fname, max_edge in RASTER_ICONS.items():
        p = DST / fname
        if not p.exists():
            continue
        im = Image.open(p)
        assert im.mode == "RGBA", f"{fname} 必须为 RGBA"
        assert im.getchannel("A").getextrema()[1] > 0, f"{fname} 全透明（抠图失败）"
        assert max(im.size) <= max_edge + 2, f"{fname} 超出目标尺寸 {max_edge}"
