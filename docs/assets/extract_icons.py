#!/usr/bin/env python3
"""
从绿幕切图素材表中自动扣出所有 Icon。
用法: python extract_icons.py input.png [output_dir]
"""

import sys
import os
from pathlib import Path
from PIL import Image
import numpy as np


def is_green(r, g, b):
    """
    判断像素是否为绿幕背景。
    简单直接：绿色通道显著高于红蓝通道。
    """
    # 绿色背景通常是纯绿 (#00FF00) 或接近纯绿
    # 判断条件：g > 100 且 g 比 r 和 b 都高出至少 40
    return g > 100 and g > r + 40 and g > b + 40


def find_icons(img_array, min_area=100):
    """
    从绿幕图中找到所有非绿像素组成的矩形区域（Icon）。
    返回 [(x, y, w, h), ...] 列表。
    """
    h, w, _ = img_array.shape

    # 创建 mask：非绿像素 = 255，绿幕 = 0
    mask = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            r, g, b = img_array[y, x, :3]
            if not is_green(r, g, b):
                mask[y, x] = 255

    # 水平投影找行
    h_proj = mask.mean(axis=1)
    in_region = False
    rows = []
    for y in range(h):
        if h_proj[y] > 0 and not in_region:
            start_y = y
            in_region = True
        elif h_proj[y] == 0 and in_region:
            rows.append((start_y, y))
            in_region = False
    if in_region:
        rows.append((start_y, h))

    # 每行内找列区间
    icons = []
    for ry1, ry2 in rows:
        row_mask = mask[ry1:ry2, :]
        v_proj = row_mask.mean(axis=0)
        in_col = False
        for x in range(w):
            if v_proj[x] > 0 and not in_col:
                start_x = x
                in_col = True
            elif v_proj[x] == 0 and in_col:
                cw = x - start_x
                ch = ry2 - ry1
                if cw * ch >= min_area:
                    icons.append((start_x, ry1, cw, ch))
                in_col = False
        if in_col:
            cw = w - start_x
            ch = ry2 - ry1
            if cw * ch >= min_area:
                icons.append((start_x, ry1, cw, ch))

    return icons


def merge_nearby(icons, gap=4):
    """合并距离太近的小块（可能是同一 Icon 被拆分了）。"""
    if not icons:
        return icons
    merged = True
    result = list(icons)
    while merged:
        merged = False
        new_result = []
        used = [False] * len(result)
        for i in range(len(result)):
            if used[i]:
                continue
            x1, y1, w1, h1 = result[i]
            for j in range(i + 1, len(result)):
                if used[j]:
                    continue
                x2, y2, w2, h2 = result[j]
                # 检查是否重叠或相邻
                if (x1 - gap <= x2 + w2 and x2 - gap <= x1 + w1 and
                    y1 - gap <= y2 + h2 and y2 - gap <= y1 + h1):
                    # 合并
                    nx = min(x1, x2)
                    ny = min(y1, y2)
                    nw = max(x1 + w1, x2 + w2) - nx
                    nh = max(y1 + h1, y2 + h2) - ny
                    x1, y1, w1, h1 = nx, ny, nw, nh
                    used[j] = True
                    merged = True
            new_result.append((x1, y1, w1, h1))
            used[i] = True
        result = new_result
    return result


def classify_icon(x, y, w, h, img_w, img_h):
    """根据位置给 Icon 分类命名。"""
    cx = x + w / 2
    cy = y + h / 2

    if cy < img_h * 0.18:
        if cx < img_w * 0.25:
            return "fleet"
        elif cx < img_w * 0.35:
            return "enemy"
        elif cx < img_w * 0.55:
            return "compass"
        else:
            return "map_tool"
    elif cy < img_h * 0.55:
        if cx < img_w * 0.5:
            return "aircraft"
        else:
            return "text_style"
    else:
        if cx < img_w * 0.25:
            return "status_bar"
        elif cx < img_w * 0.65:
            return "fleet"
        else:
            return "button"


def extract_icons(input_path, output_dir):
    """主函数：从绿幕图中提取所有 Icon。"""
    img = Image.open(input_path).convert("RGBA")
    img_array = np.array(img)
    img_w, img_h = img.size

    print(f"输入图片: {input_path} ({img_w}x{img_h})")

    # 先在原图上生成全局背景 mask（flood fill 从四角）
    print("生成全局背景 mask...")
    bg_mask_full = flood_fill_background(img_array)

    # 找到所有 icon 区域（基于非背景像素）
    icons = find_icons_from_mask(bg_mask_full, min_area=80)
    print(f"检测到 {len(icons)} 个原始区域")

    # 合并邻近区域
    icons = merge_nearby(icons, gap=5)
    icons.sort(key=lambda r: (r[1], r[0]))
    print(f"合并后 {len(icons)} 个 Icon")

    # 过滤
    filtered = []
    for x, y, w, h in icons:
        if w < 15 or h < 15 or w > 500 or h > 500:
            continue
        if w > h * 10 or h > w * 10:
            continue
        filtered.append((x, y, w, h))
    print(f"过滤后 {len(filtered)} 个 Icon")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted = []
    for i, (x, y, w, h) in enumerate(filtered):
        category = classify_icon(x, y, w, h, img_w, img_h)

        # 用全局 bg mask 来扣图
        padding = 2
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img_w, x + w + padding)
        y2 = min(img_h, y + h + padding)

        crop = img_array[y1:y2, x1:x2].copy()
        crop_bg = bg_mask_full[y1:y2, x1:x2]

        # 背景 → 透明
        crop[:, :, 3][crop_bg] = 0

        # 绿色溢出抑制
        r_ch = crop[:, :, 0].astype(float)
        g_ch = crop[:, :, 1].astype(float)
        b_ch = crop[:, :, 2].astype(float)
        green_higher = (g_ch > r_ch + 10) & (g_ch > b_ch + 10) & (crop[:, :, 3] > 0)
        crop[:, :, 1] = np.where(green_higher, np.clip((r_ch + b_ch) / 2, 0, 255).astype(np.uint8), crop[:, :, 1])

        # 裁剪到内容边界
        opaque = crop[:, :, 3] > 0
        rows = np.any(opaque, axis=1)
        cols = np.any(opaque, axis=0)
        if rows.any() and cols.any():
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]
            rmin = max(0, rmin - 1)
            rmax = min(crop.shape[0] - 1, rmax + 1)
            cmin = max(0, cmin - 1)
            cmax = min(crop.shape[1] - 1, cmax + 1)
            crop = crop[rmin:rmax+1, cmin:cmax+1]

        result = Image.fromarray(crop.astype(np.uint8))
        fw, fh = result.size

        filename = f"{category}_{i:02d}_{fw}x{fh}.png"
        filepath = output_dir / filename
        result.save(str(filepath))
        extracted.append((filename, fw, fh, category))
        print(f"  [{i+1:2d}] {category:12s} {fw:3d}x{fh:<3d} → {filename}")

    print(f"\n✅ 提取完成！共 {len(extracted)} 个 Icon，保存到: {output_dir}")
    return extracted


def flood_fill_background(img_array):
    """
    纯颜色匹配生成背景 mask（不做 flood fill）。
    从四角采样背景色，所有与背景色距离 < 阈值的像素都标记为背景。
    """
    h, w = img_array.shape[:2]

    # 从四角采样背景色
    corners = [(5,5), (5,w-6), (h-6,5), (h-6,w-6)]
    bg_samples = [img_array[y, x, :3].astype(float) for y, x in corners]
    bg_color = np.mean(bg_samples, axis=0)

    print(f"  采样背景色: RGB({bg_color[0]:.0f},{bg_color[1]:.0f},{bg_color[2]:.0f})")

    # 计算每个像素与背景色的欧氏距离
    r = img_array[:, :, 0].astype(float)
    g = img_array[:, :, 1].astype(float)
    b = img_array[:, :, 2].astype(float)

    dist = np.sqrt((r - bg_color[0])**2 + (g - bg_color[1])**2 + (b - bg_color[2])**2)

    # 距离 < 阈值 → 背景
    bg_mask = dist < 80

    bg_count = bg_mask.sum()
    total = h * w
    print(f"  背景像素: {bg_count}/{total} ({bg_count/total*100:.1f}%)")

    return bg_mask


def find_icons_from_mask(bg_mask, min_area=80):
    """从背景 mask 的反面（内容区域）找 icon 矩形。"""
    content = ~bg_mask
    h, w = content.shape

    h_proj = content.mean(axis=1)
    in_region = False
    rows = []
    for y in range(h):
        if h_proj[y] > 0 and not in_region:
            start_y = y
            in_region = True
        elif h_proj[y] == 0 and in_region:
            rows.append((start_y, y))
            in_region = False
    if in_region:
        rows.append((start_y, h))

    icons = []
    for ry1, ry2 in rows:
        row_content = content[ry1:ry2, :]
        v_proj = row_content.mean(axis=0)
        in_col = False
        for x in range(w):
            if v_proj[x] > 0 and not in_col:
                start_x = x
                in_col = True
            elif v_proj[x] == 0 and in_col:
                cw = x - start_x
                ch = ry2 - ry1
                if cw * ch >= min_area:
                    icons.append((start_x, ry1, cw, ch))
                in_col = False
        if in_col:
            cw = w - start_x
            ch = ry2 - ry1
            if cw * ch >= min_area:
                icons.append((start_x, ry1, cw, ch))
    return icons


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract_icons.py input.png [output_dir]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "icons_extracted"
    extract_icons(input_path, output_dir)
