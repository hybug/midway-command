#!/usr/bin/env python3
"""compare_regions.py — 区域比对流水线（product-replica-plan P0.2 固化）。

把 2026-09-12 像素级比对（计划「像素级比对结论」节，存证 docs/reports/product-compare/）
执行过的临时 PIL 逻辑固化为可重复脚本：

    python docs/assets/compare_regions.py <design.png> <current.png> <outdir>

流程：两图非等比缩放统一到 1440×900（仅区域粗测）→ 4×4 区域均色差矩阵 →
关键采样 → side-by-side 存证。产物落 <outdir>/：design-scaled.png、
side-by-side.png、compare-report.md。

口径：区域均色差 = 两图该区域均色（mean RGB）的逐通道绝对差取均值（0–255）。
基准数字（2026-09-12 实测，设计 2752×1536 vs 截图 1440×900，缩放插值允许 ±2 波动）：
    整体均值色 设计 (169,153,122) vs 当前 (208,199,177)
    4×4 最大热区 右中 98.7；底行 74.9 / 70.8 / 78.7
    关键采样：图面空白 设计 (231,206,159) vs 当前 (227,220,200)；顶栏 182 vs 186
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

UNIFIED_SIZE = (1440, 900)  # 统一画幅：设计图非等比压缩到当前视口尺寸
GRID = 4  # 4×4 区域差矩阵

# 关键采样窗（统一 1440×900 坐标，(left, top, right, bottom)），对应计划采样点：
#   图面空白/顶栏数字与计划引用值一致；底栏/右栏为叙事采样（设计深 chrome vs 当前浅纸）。
SAMPLES: list[tuple[str, tuple[int, int, int, int]]] = [
    ("chart_blank 图面空白", (980, 240, 1020, 280)),
    ("top_bar 顶栏", (360, 4, 1080, 44)),
    ("bottom_bar 底栏", (0, 852, 1440, 900)),
    ("right_col 右栏", (1140, 48, 1440, 852)),
]


def load_unified(path: str) -> Image.Image:
    """载入图片并强制缩放到统一画幅（非等比，仅区域粗测）。"""
    return Image.open(path).convert("RGB").resize(UNIFIED_SIZE)


def region_diffs(design: np.ndarray, current: np.ndarray) -> list[list[float]]:
    """4×4 区域均色差矩阵：每格均色的 RGB 绝对差取均值。"""
    h, w = design.shape[:2]
    ch, cw = h // GRID, w // GRID
    matrix = []
    for r in range(GRID):
        row = []
        for c in range(GRID):
            cell = slice(r * ch, (r + 1) * ch), slice(c * cw, (c + 1) * cw)
            dm = design[cell].mean(axis=(0, 1))
            cm = current[cell].mean(axis=(0, 1))
            row.append(float(np.abs(dm - cm).mean()))
        matrix.append(row)
    return matrix


def sample_means(design: np.ndarray, current: np.ndarray) -> list[dict]:
    """关键采样窗均色（设计/当前/逐通道差）。"""
    out = []
    for name, (x0, y0, x1, y1) in SAMPLES:
        win = np.s_[y0:y1, x0:x1]
        dm = design[win].mean(axis=(0, 1))
        cm = current[win].mean(axis=(0, 1))
        out.append({
            "name": name,
            "design": dm.round().astype(int).tolist(),
            "current": cm.round().astype(int).tolist(),
            "delta": (cm - dm).round().astype(int).tolist(),
        })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="区域比对流水线（缩放→4×4 区域差→关键采样→side-by-side 存证）")
    parser.add_argument("design", help="设计基准图（如 docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png）")
    parser.add_argument("current", help="当前实拍截图（如 docs/reports/fidelity-loop/final-1440.png）")
    parser.add_argument("outdir", help="产物输出目录（如 docs/reports/product-compare/）")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    design_img = load_unified(args.design)
    current_img = load_unified(args.current)
    design_img.save(outdir / "design-scaled.png")

    side = Image.new("RGB", (UNIFIED_SIZE[0] * 2, UNIFIED_SIZE[1]))
    side.paste(design_img, (0, 0))
    side.paste(current_img, (UNIFIED_SIZE[0], 0))
    side.save(outdir / "side-by-side.png")

    design = np.asarray(design_img, dtype=np.float64)
    current = np.asarray(current_img, dtype=np.float64)

    overall_d = design.mean(axis=(0, 1))
    overall_c = current.mean(axis=(0, 1))
    matrix = region_diffs(design, current)
    samples = sample_means(design, current)

    # stdout 报告
    print(f"统一 {UNIFIED_SIZE[0]}×{UNIFIED_SIZE[1]}（设计非等比压缩，仅区域粗测）")
    print(f"整体均值色：设计 ({overall_d.round(0).astype(int)[0]},{overall_d.round(0).astype(int)[1]},{overall_d.round(0).astype(int)[2]})"
          f" vs 当前 ({overall_c.round(0).astype(int)[0]},{overall_c.round(0).astype(int)[1]},{overall_c.round(0).astype(int)[2]})")
    print(f"\n4×4 区域均色差矩阵（0–255）：")
    for r, row in enumerate(matrix):
        print("  " + "  ".join(f"{v:6.1f}" for v in row) + f"   <- 行 {r}")
    flat = [(v, r, c) for r, row in enumerate(matrix) for c, v in enumerate(row)]
    worst_v, worst_r, worst_c = max(flat)
    print(f"最大热区：r{worst_r}c{worst_c} = {worst_v:.1f}")
    print("\n关键采样：")
    for s in samples:
        print(f"  {s['name']}: 设计 {tuple(s['design'])} vs 当前 {tuple(s['current'])}（差 {tuple(s['delta'])}）")
    print(f"\n存证已写入：{outdir}/design-scaled.png, side-by-side.png, compare-report.md")

    # markdown 报告
    lines = [
        "# 区域比对报告（compare_regions.py）",
        "",
        f"- 设计：`{args.design}` → 统一 {UNIFIED_SIZE[0]}×{UNIFIED_SIZE[1]}（非等比压缩，仅区域粗测）",
        f"- 当前：`{args.current}`",
        "- 口径：区域均色差 = 两图均色 RGB 绝对差的均值（0–255）；缩放插值允许 ±2 波动。",
        "",
        "## 整体均值色",
        "",
        f"设计 ({overall_d.round(0).astype(int)[0]},{overall_d.round(0).astype(int)[1]},{overall_d.round(0).astype(int)[2]})"
        f" vs 当前 ({overall_c.round(0).astype(int)[0]},{overall_c.round(0).astype(int)[1]},{overall_c.round(0).astype(int)[2]})",
        "",
        f"## 4×4 区域均色差矩阵（最大热区 r{worst_r}c{worst_c} = {worst_v:.1f}，计划基准 98.7）",
        "",
        "| 行\\列 | " + " | ".join(str(c) for c in range(GRID)) + " |",
        "|---|" + "---|" * GRID,
    ]
    for r, row in enumerate(matrix):
        lines.append(f"| {r} | " + " | ".join(f"{v:.1f}" for v in row) + " |")
    lines += [
        "",
        "## 关键采样",
        "",
        "| 采样 | 设计 RGB | 当前 RGB | 差（当前−设计） |",
        "|------|----------|----------|------------------|",
    ]
    for s in samples:
        lines.append(f"| {s['name']} | ({','.join(map(str, s['design']))}) | ({','.join(map(str, s['current']))}) | ({','.join(map(str, s['delta']))}) |")
    lines += [
        "",
        "## 存证",
        "",
        "- `design-scaled.png`：设计图统一 1440×900 后的比对输入",
        "- `side-by-side.png`：设计（左）vs 当前（右）拼接",
        "",
    ]
    (outdir / "compare-report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
