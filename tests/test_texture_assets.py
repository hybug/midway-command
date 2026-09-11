"""AI 纹理素材质量门（docs/plans/ui-fidelity-fix-plan.md 批次 B）。

源素材到位性 + 集成产物的色温归一与平铺接缝断言。
"""
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "docs" / "assets" / "ai_textures"
DST = BASE / "static" / "assets" / "textures"

# 集成产物 → (接缝差阈值/255——None 表示非平铺用途不断言, 目标均值色, 通道容差)
TEXTURE_TARGETS = {
    "paper_tex.jpg": (8, (245, 237, 214), 10),
    "wood_tex.png": (None, (201, 167, 106), 14),
}


def test_source_images_present():
    for f in ["P1_paper.png", "P2_wood.png", "P3_compass.png"]:
        assert (SRC / f).exists(), f"缺少 AI 源素材 {f}"


def test_integrated_textures_normalized():
    for fname, (seam_max, target, tol) in TEXTURE_TARGETS.items():
        p = DST / fname
        assert p.exists(), f"缺少集成纹理 {fname}"
        a = np.array(Image.open(p).convert("RGB")).astype(int)
        mean = a.reshape(-1, 3).mean(axis=0)
        dev = max(abs(mean[0] - target[0]), abs(mean[1] - target[1]), abs(mean[2] - target[2]))
        assert dev <= tol, f"{fname} 均值色 {mean.round(1)} 偏离 {target} 超 {tol}"
        if seam_max is not None:
            h, w, _ = a.shape
            seam = max(
                np.abs(a[:, 0, :] - a[:, w - 1, :]).mean(),
                np.abs(a[0, :, :] - a[h - 1, :, :]).mean(),
            )
            assert seam <= seam_max, f"{fname} 接缝差 {seam:.1f} 超阈 {seam_max}"


def test_integrated_textures_size_floor():
    for fname in TEXTURE_TARGETS:
        im = Image.open(DST / fname)
        assert min(im.size) >= 400, f"{fname} 尺寸过小 {im.size}"
