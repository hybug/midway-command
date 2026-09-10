#!/usr/bin/env python3
"""光栅图标质量门（docs/plans/ui-replication-plan.md Phase 6）。

对抠图产物做客观质量检查。所有抠图（存量复审与新增入库）必须 PASS，
或 MANUAL（合并切割嫌疑）经人工分拆复审通过后，才可进入
static/assets/ui/icons/。

用法:
    python docs/assets/quality_gate.py <file|dir>            # 逐枚判定
    python docs/assets/quality_gate.py <dir> --markdown      # 输出报告表格
    python docs/assets/quality_gate.py <dir> --sheets <dir>  # 生成目检拼图(12枚/张)

判据（全部满足才 PASS）:
  G1 非空     alpha 最大值 > 0
  G2 内容占比 0.03 <= 不透明像素占比 <= 0.98（排除空白与整块实心）
  G3 无绿边   不透明像素中「绿主导」(g>r+25 且 g>b+25) 占比 <= 2%
  G4 主体完整 最大连通域面积 / 不透明面积 >= 0.5（碎片化检测）
  G5 尺寸可用 max(w, h) >= 24px
输出 MANUAL: 存在 >=2 个面积占比 >20% 的连通域（合并切割嫌疑，需人工分拆复审）。
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def label_components(mask):
    """4-连通域标记（素材图小，BFS 足够）。返回 (labels, 组件数)。"""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    cur = 0
    for sy in range(h):
        for sx in np.nonzero(mask[sy] & (labels[sy] == 0))[0]:
            if labels[sy, sx]:
                continue
            cur += 1
            stack = [(sy, int(sx))]
            labels[sy, sx] = cur
            while stack:
                y, x = stack.pop()
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = cur
                        stack.append((ny, nx))
    return labels, cur


def metrics(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    alpha = a[:, :, 3]
    opaque = alpha > 0
    n = int(opaque.sum())
    rgb = a[:, :, :3].astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = (g > r + 25) & (g > b + 25) & opaque
    labels, ncomp = label_components(opaque)
    areas = sorted((int((labels == i).sum()) for i in range(1, ncomp + 1)), reverse=True)
    return {
        "file": Path(path).name,
        "w": im.width,
        "h": im.height,
        "alpha_max": int(alpha.max()),
        "opaque_ratio": round(n / opaque.size, 4) if n else 0.0,
        "green_ratio": round(float(green.sum()) / n, 4) if n else 0.0,
        "components": ncomp,
        "largest_ratio": round(areas[0] / n, 4) if n and areas else 0.0,
        "big_parts": sum(1 for x in areas if n and x / n > 0.2),
    }


def verdict(m):
    fails = []
    if m["alpha_max"] == 0:
        fails.append("G1空白")
    if not (0.03 <= m["opaque_ratio"] <= 0.98):
        fails.append("G2内容占比")
    if m["green_ratio"] > 0.02:
        fails.append("G3绿边")
    if m["largest_ratio"] < 0.5:
        fails.append("G4碎片化")
    if max(m["w"], m["h"]) < 24:
        fails.append("G5尺寸")
    if not fails and m["big_parts"] >= 2:
        return "MANUAL", []
    return ("FAIL", fails) if fails else ("PASS", [])


def contact_sheets(paths, out_dir, per_sheet=12, cols=4):
    """目检拼图：纸张底色（模拟使用场景），文件名标注。返回生成的文件列表。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h = 230, 215
    made = []
    for s in range((len(paths) + per_sheet - 1) // per_sheet):
        chunk = paths[s * per_sheet:(s + 1) * per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (245, 237, 214))
        d = ImageDraw.Draw(sheet)
        for i, p in enumerate(chunk):
            im = Image.open(p).convert("RGBA")
            im.thumbnail((cell_w - 30, cell_h - 42))
            cx, cy = (i % cols) * cell_w + 12, (i // cols) * cell_h + 8
            sheet.paste(im, (cx, cy), im)
            d.text((cx, cy + cell_h - 30), Path(p).name, fill=(42, 34, 24))
        out = out_dir / f"sheet_{s + 1}.png"
        sheet.save(out)
        made.append(str(out))
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--sheets", type=Path, default=None)
    args = ap.parse_args()

    paths = sorted([args.target] if args.target.is_file() else args.target.glob("*.png"))
    if not paths:
        sys.exit(f"no png under {args.target}")

    results = []
    for p in paths:
        m = metrics(p)
        v, fails = verdict(m)
        results.append((m, v, fails))

    if args.markdown:
        print("| 文件 | 尺寸 | 门判定 | 内容占比 | 绿边占比 | 连通域 | 主体占比 | 违反 |")
        print("|------|------|--------|---------|---------|--------|---------|------|")
        for m, v, fails in results:
            print(f"| {m['file']} | {m['w']}x{m['h']} | {v} | {m['opaque_ratio']:.2f} "
                  f"| {m['green_ratio']:.3f} | {m['components']} | {m['largest_ratio']:.2f} "
                  f"| {'/'.join(fails) or '—'} |")
    else:
        for m, v, fails in results:
            print(f"{v:6s} {m['file']:32s} {m['w']}x{m['h']:<4d} 占比{m['opaque_ratio']:.2f} "
                  f"绿{m['green_ratio']:.3f} 连通域{m['components']:2d} 主体{m['largest_ratio']:.2f} "
                  f"{'|'.join(fails)}")

    summary = {"PASS": 0, "MANUAL": 0, "FAIL": 0}
    for _, v, _ in results:
        summary[v] += 1
    print(f"\n汇总: PASS {summary['PASS']} / MANUAL {summary['MANUAL']} / FAIL {summary['FAIL']}，共 {len(results)}")

    if args.sheets:
        print("拼图:", *contact_sheets(paths, args.sheets), sep="\n  ")


if __name__ == "__main__":
    main()
