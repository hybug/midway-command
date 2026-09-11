#!/usr/bin/env python3
"""木纹 data-URI 内嵌进 ruler 副本（<img> 引用的 SVG 禁外部资源，必须内嵌）。
产物 ruler_wood.svg；原 ruler.svg 保留为回退。
"""
import base64
from pathlib import Path

SRC = Path("static/assets/textures/wood_tex.png")
TPL = Path("static/assets/ui/ruler.svg")
OUT = Path("static/assets/ui/ruler_wood.svg")

b64 = base64.b64encode(SRC.read_bytes()).decode()
svg = TPL.read_text()
pattern = (
    '<pattern id="woodTex" width="600" height="44" patternUnits="userSpaceOnUse">'
    f'<image href="data:image/png;base64,{b64}" width="600" height="44" preserveAspectRatio="xMidYMid slice"/>'
    '</pattern>'
)
svg = svg.replace('<linearGradient id="wood"', f'{pattern}<linearGradient id="wood"')
svg = svg.replace('fill="url(#wood)"', 'fill="url(#woodTex)"')
OUT.write_text(svg)
print(f"{OUT} written ({OUT.stat().st_size // 1024}KB)")
