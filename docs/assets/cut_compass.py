#!/usr/bin/env python3
"""P3 雕刻罗盘白底→透明（亮度反转法，保留细阴线）。"""
from pathlib import Path

import numpy as np
from PIL import Image

im = Image.open(Path(__file__).parent / "ai_textures" / "P3_compass.png").convert("RGB")
a = np.array(im).astype(float)
lum = a.mean(axis=2)
alpha = np.clip((255 - lum) * 1.2, 0, 255).astype(np.uint8)
out = Image.fromarray(np.dstack([np.array(im).astype(np.uint8), alpha]), "RGBA")
out = out.crop(out.getchannel("A").getbbox())
out.save(Path(__file__).resolve().parent.parent.parent / "static" / "assets" / "ui" / "icons" / "compass_engraved.png")
print("compass_engraved.png", out.size)
