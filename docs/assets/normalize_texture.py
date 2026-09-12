#!/usr/bin/env python3
"""AI 纹理归一：裁边/色温归一 → static/assets/textures/（通道缩放法，记录于报告）。"""
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(__file__).parent / "ai_textures"
DST = Path(__file__).parent.parent.parent / "static" / "assets" / "textures"


def normalize(img: Image.Image, target_rgb, crop=None) -> Image.Image:
    if crop:  # (left, top, right, bottom) 比例
        w, h = img.size
        img = img.crop((int(w * crop[0]), int(h * crop[1]), int(w * (1 - crop[2])), int(h * (1 - crop[3]))))
    a = np.array(img).astype(np.float64)
    mean = a.reshape(-1, 3).mean(axis=0)
    scale = np.array(target_rgb) / np.maximum(mean, 1)
    return Image.fromarray(np.clip(a * scale, 0, 255).astype(np.uint8))


def _sew_edge(a: np.ndarray, axis: int, band: int) -> np.ndarray:
    """单轴缝补：边缘 band 像素与对侧镜像渐变混合，d=0 处取纯镜像（接缝差 → 0）。"""
    n = a.shape[axis]
    shape = [1, 1]
    shape[axis] = band
    t = ((1 - np.arange(band) / band) ** 2).reshape(shape)
    main = [slice(None), slice(None)]; main[axis] = slice(0, band)
    mirror = [slice(None), slice(None)]; mirror[axis] = slice(n - 1, n - 1 - band, -1)
    out = a.copy()
    out[tuple(main)] = (1 - t[..., None]) * a[tuple(main)] + t[..., None] * a[tuple(mirror)]
    return out


def make_seamless(img: Image.Image, band: int = 100) -> Image.Image:
    """平铺化：左缘/顶缘与对侧镜像渐变混合，wrap 接缝差 → 0（Canvas repeat 要求 ≤ 8）。"""
    a = np.array(img).astype(np.float64)
    a = _sew_edge(a, 1, band)  # 先缝列（左缘 ↔ 右缘镜像）
    a = _sew_edge(a, 0, band)  # 再缝行（顶缘 ↔ 底缘镜像）
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


DST.mkdir(parents=True, exist_ok=True)
# 成品图复现 D2：paper 目标色 (245,237,214) → (225,207,168)
# （整体压黄加深对齐成品图；采样设计图面 (231,206,159) 的提亮版，冲突审计 H4，
#   与 tests/test_texture_assets.py 的 TEXTURE_TARGETS 保持同步）
paper = make_seamless(normalize(Image.open(SRC / "P1_paper.png").convert("RGB"), (225, 207, 168)))
paper.save(DST / "paper_tex.jpg", quality=85)
print("paper_tex.jpg", paper.size)
wood = normalize(Image.open(SRC / "P2_wood.png").convert("RGB"), (201, 167, 106), crop=(0.0, 0.06, 0.0, 0.06))
wood.save(DST / "wood_tex.png")
print("wood_tex.png", wood.size)
