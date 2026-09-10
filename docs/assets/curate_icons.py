#!/usr/bin/env python3
"""光栅图标治理：预裁剪 → 裁边 → 呼吸边距 → 限尺寸 → 入库 static/assets/ui/icons/。

源池与分档见 docs/reports/raster-icon-review.md；repair 分拆产物的
裁剪框记录在同报告 3.2.1。弃用档不在此列，由 SVG 资产顶替。

- PRE_CROPS：源抠图底部带入的 "32x32px" 规格文字（铭牌本体之下的字母碎屑，
  见评审报告 3.1「微小杂点」实为文字）在入库前裁除。
- 呼吸边距：trim 后内容若铺满画布会触发质量门 G2「整块实心」判定
  （不透明占比 ≤0.98），且图标本身需要透明边距防裁切，故统一留 3% 边距。

用法: .venv/bin/python docs/assets/curate_icons.py
"""
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parents[2]  # docs/assets/curate_icons.py → 仓库根
SRC = BASE / "docs" / "assets" / "icons_extracted"
DST = BASE / "static" / "assets" / "ui" / "icons"

PAD_RATIO = 0.03  # 呼吸边距（占最大边比例），最小 2px

# (源文件, 输出名, 最大边长 px)。与 tests/test_raster_assets.py 的 RASTER_ICONS 保持一致。
TARGETS = [
    ("fleet_tag_ent.png", "fleet_tag_ent.png", 64),        # repair 分拆产物（aircraft_14 左牌）
    ("aircraft_topdown.png", "aircraft_topdown.png", 72),  # repair 分拆产物（aircraft_14 右牌）
    ("aircraft_15_105x106.png", "fleet_tag_hor.png", 64),  # usable 直取
    ("aircraft_16_122x161.png", "fleet_tag_cv.png", 64),   # usable 直取（预裁底部文字）
    ("aircraft_17_104x106.png", "fleet_tag_bb.png", 64),   # usable 直取
    ("aircraft_18_123x162.png", "enemy_tag_q.png", 72),    # usable 直取（预裁底部文字）
    ("text_style_20_220x216.png", "compass_raster.png", 96),  # usable 直取
]

# 源级预裁剪 (x1, y1, x2, y2)：裁除铭牌本体之下的规格文字（rows 121+），只留牌区。
# 实测：aircraft_16 牌区 rows 1–104 / 文字 rows 121–151；aircraft_18 牌区 rows 1–106 / 文字 rows 122–152。
PRE_CROPS = {
    "aircraft_16_122x161.png": (0, 0, 122, 112),
    "aircraft_18_123x162.png": (0, 0, 123, 114),
}


def trim(im):
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im


def pad(im):
    """四周加透明呼吸边距，避免 G2「整块实心」并为渲染留防裁切余量。"""
    p = max(2, round(max(im.size) * PAD_RATIO))
    out = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    out.paste(im, (p, p))
    return out


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for src_name, out_name, max_edge in TARGETS:
        im = Image.open(SRC / src_name).convert("RGBA")
        if src_name in PRE_CROPS:
            im = im.crop(PRE_CROPS[src_name])
        im = pad(trim(im))
        scale = max_edge / max(im.size)
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        im.save(DST / out_name)
        print(f"{out_name}: {im.size}")


if __name__ == "__main__":
    main()
