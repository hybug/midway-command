#!/usr/bin/env python3
"""中途岛战区包生成器（CHART_SYSTEM.md §三/§四）。

把 chartRenderer.js 的程序化环礁/双岛/跑道公式移植为坐标产出——
数据与渲染同源（同一谐波系数、同一比例结构），保证 M.3/M.4 ChartEngine
消费本包时与现状视觉等价（本阶段视觉零变化）。

产出 theaters/midway/：theater.json、geography.geojson、scenario.json、README.md。

用法：.venv/bin/python tools/gen_midway_pack.py
"""
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACK = REPO / "theaters" / "midway"

# ── 与 chartRenderer.js 同源常量（现值锚点，本阶段视觉零变化）──
CENTER_LAT = 28.2
CENTER_LON = -177.4          # CHART_CENTER
CHART_VIEW_NM = 45           # CHART_VIEW_NM
RING_NM = [20, 25, 40, 60]   # RING_NM 标签对数值
GRATICULE_MINOR = 0.25       # drawLatLonGrid 细网步进
GRATICULE_MAJOR = 1.0        # 主网步进（0.5° 绘制网以 0.25 细网+主网表达，schema 按 0.25/1.0）
SECTOR_BEARING = (30, 90)    # 侦察扇区沿用值
COS_LAT = math.cos(math.radians(CENTER_LAT))  # makeProjector 纬度修正

# 基准图面短边：1600×900 验证窗口 → 图区 (1600-320)×(900-60-56)=1280×784，
# #chart-area 10px 木框 → 画布 1260×764，短边 764。chartNmToPx 同式：
# px = (nm/45)×(min(w,h)/2+100)。仅用于把 chartRenderer 里少量绝对 px 几何
# （岛块胶囊尺寸/标注锚点偏移）换算成 nm——比例结构特征，非渲染参数。
REF_MIN_WH = 764
PX_PER_NM = (REF_MIN_WH / 2 + 100) / 45

def px_to_nm(px: float) -> float:
    return px / PX_PER_NM

# 环礁半轴（drawAtoll：rx=chartNmToPx(34), ry=chartNmToPx(25)）
ATOLL_RX_NM = 34.0
ATOLL_RY_NM = 25.0


def nm_offset_to_lonlat(nm_east: float, nm_south: float) -> list[float]:
    """环礁心的 nm 偏移（东/南为正）→ (lon, lat)（GeoJSON 顺序）。

    与 makeProjector 互逆：1° lat = 60nm；1° lon = 60/cos(lat) nm。
    """
    return [
        round(CENTER_LON + nm_east * COS_LAT / 60.0, 6),
        round(CENTER_LAT - nm_south / 60.0, 6),
    ]


def atoll_outline_nm(rx_nm: float, ry_nm: float, n: int = 120) -> list[list[float]]:
    """chartRenderer atollOutline 移植：确定性三谐波波浪 + 西南礁盘缺口。

    wob = 1 + 0.07·sin(3t+0.8) + 0.045·sin(7t+2.1) + 0.03·sin(11t+4.5)
    gap = 0.92（2.4<t<3.4 西南缺口）| 1.0
    """
    pts = []
    for i in range(n):
        t = (i / n) * math.pi * 2
        wob = 1 + 0.07 * math.sin(3 * t + 0.8) + 0.045 * math.sin(7 * t + 2.1) \
            + 0.03 * math.sin(11 * t + 4.5)
        gap = 0.92 if 2.4 < t < 3.4 else 1.0
        pts.append([rx_nm * wob * gap * math.cos(t), ry_nm * wob * gap * math.sin(t)])
    return [nm_offset_to_lonlat(e, s) for e, s in pts]


def closed_ring(pts_lonlat: list[list[float]]) -> list[list[float]]:
    """GeoJSON Polygon 线环闭合（首尾同点）。"""
    return pts_lonlat + [pts_lonlat[0]]


# ── geography.geojson ──────────────────────────────────────────

def build_geojson() -> dict:
    rx, ry = ATOLL_RX_NM, ATOLL_RY_NM
    features: list[dict] = []

    # land = atoll rim 外环（drawAtoll outer：sand 填充 + reef 虚线描边同一轮廓）
    features.append({
        "type": "Feature",
        "properties": {"class": "land", "name": "Midway Atoll"},
        "geometry": {"type": "Polygon",
                     "coordinates": [closed_ring(atoll_outline_nm(rx, ry))]},
    })

    # lagoon 内环（drawAtoll lagoon：rx*0.80 / ry*0.74）
    features.append({
        "type": "Feature",
        "properties": {"class": "lagoon", "name": "Midway Lagoon"},
        "geometry": {"type": "Polygon",
                     "coordinates": [closed_ring(atoll_outline_nm(rx * 0.80, ry * 0.74))]},
    })

    # islet ① SAND ISLAND（drawIslands：环礁西侧圆角矩形胶囊；
    # sandW 文字度量依赖字体加载，取守卫下限 62px 为规范宽，圆角 r=3px 属描边风格不入数据）
    sx = -rx * 0.60                      # c.x - rx*0.60
    sy = ry * 0.32                       # c.y + ry*0.32（屏幕 y 向下=南）
    sand_w, sand_h = px_to_nm(62), px_to_nm(16)
    features.append({
        "type": "Feature",
        "properties": {"class": "islet", "name": "Sand Island"},
        "geometry": {"type": "Polygon", "coordinates": [closed_ring([
            nm_offset_to_lonlat(sx, sy),
            nm_offset_to_lonlat(sx + sand_w, sy),
            nm_offset_to_lonlat(sx + sand_w, sy + sand_h),
            nm_offset_to_lonlat(sx, sy + sand_h),
        ])]},
    })

    # islet ② EASTERN ISLAND（drawIslands：东南侧三角形，s = rx*0.26）
    ex, ey = rx * 0.28, ry * 0.52
    s = rx * 0.26
    features.append({
        "type": "Feature",
        "properties": {"class": "islet", "name": "Eastern Island"},
        "geometry": {"type": "Polygon", "coordinates": [closed_ring([
            nm_offset_to_lonlat(ex, ey - s * 0.55),
            nm_offset_to_lonlat(ex + s, ey + s * 0.35),
            nm_offset_to_lonlat(ex - s * 0.8, ey + s * 0.45),
        ])]},
    })

    # 跑道（rwy 三条 + 沙岛侧跑道横带中线）——schema v1 无 runway class，
    # 以 route_hint 线要素承载（name 前缀 runway_ 标识），虚线淡线渲染语义一致
    rwy = [(-s * 0.7, s * 0.3, s * 0.9, -s * 0.35),
           (-s * 0.55, -s * 0.4, s * 0.7, s * 0.5),
           (-s * 0.1, -s * 0.55, s * 0.15, s * 0.6)]
    for i, (x1, y1, x2, y2) in enumerate(rwy, 1):
        features.append({
            "type": "Feature",
            "properties": {"class": "route_hint", "name": f"runway_eastern_{i}"},
            "geometry": {"type": "LineString", "coordinates": [
                nm_offset_to_lonlat(ex + x1, ey + y1),
                nm_offset_to_lonlat(ex + x2, ey + y2),
            ]},
        })
    band_y = sy + px_to_nm(16 + 8)       # bandY = sy + sandH + 8
    features.append({
        "type": "Feature",
        "properties": {"class": "route_hint", "name": "runway_sand_centerline"},
        "geometry": {"type": "LineString", "coordinates": [
            nm_offset_to_lonlat(sx + px_to_nm(4), band_y + px_to_nm(5)),
            nm_offset_to_lonlat(sx + sand_w - px_to_nm(4), band_y + px_to_nm(5)),
        ]},
    })

    # label 四条（CHART_LABELS 同名字面量；锚点 = 屏幕绘制点经基准换算）
    # MIDWAY ATOLL（bold 13px，c.x-48, c.y-24）与坐标行（9px，c.x-48, c.y+4）
    features.append({
        "type": "Feature",
        "properties": {"class": "label", "text": "MIDWAY ATOLL", "size": 13, "role": "atoll"},
        "geometry": {"type": "Point",
                     "coordinates": nm_offset_to_lonlat(px_to_nm(-48), px_to_nm(-24))},
    })
    features.append({
        "type": "Feature",
        "properties": {"class": "label", "text": "28°12'N 177°21'W", "size": 9, "role": "coord"},
        "geometry": {"type": "Point",
                     "coordinates": nm_offset_to_lonlat(px_to_nm(-48), px_to_nm(4))},
    })
    # SAND ISLAND（10px，胶囊内居中）与 EASTERN ISLAND（7px，黄底标注块 lx+4, ly+6）
    features.append({
        "type": "Feature",
        "properties": {"class": "label", "text": "SAND ISLAND", "size": 10, "role": "island"},
        "geometry": {"type": "Point",
                     "coordinates": nm_offset_to_lonlat(sx + sand_w / 2, sy + sand_h / 2)},
    })
    features.append({
        "type": "Feature",
        "properties": {"class": "label", "text": "EASTERN ISLAND", "size": 7, "role": "island"},
        "geometry": {"type": "Point",
                     "coordinates": nm_offset_to_lonlat(ex + s * 0.35 + px_to_nm(4),
                                                        ey + s * 0.62 + px_to_nm(6))},
    })
    return {"type": "FeatureCollection", "features": features}


# ── theater.json（CHART_SYSTEM §三 schema v1，数值=chartRenderer 现值）──

def build_theater() -> dict:
    return {
        "id": "midway",
        "name": "中途岛",
        "name_en": "Midway",
        "date": "1942-06-04",
        "timezone_offset": 12,
        "view": {"center": {"lat": CENTER_LAT, "lon": CENTER_LON},
                 "view_nm": CHART_VIEW_NM, "rotation": 0},
        "graticule": {"minor_step": GRATICULE_MINOR, "major_step": GRATICULE_MAJOR,
                      "label_format": "dms"},
        "range_rings": {"origin": {"lat": CENTER_LAT, "lon": CENTER_LON},
                        "rings_nm": RING_NM, "labels": True},
        "bases": [{"id": "midway", "name": "中途岛机场", "lat": 28.2072, "lon": -177.3735,
                   "type": "airfield", "capacity": 113}],
        "sectors": [{"id": "east-quad", "name": "东侧扇区", "origin_ref": "ENT",
                     "bearing_min": SECTOR_BEARING[0], "bearing_max": SECTOR_BEARING[1]}],
        "units": "nm",
        "scenario": "scenario.json",
    }


# ── scenario.json（双舰队骨架值，成品图量取规则：环礁正西 ENT 45nm / HOR 28nm）──

def nm_west_lon(nm: float) -> float:
    """环礁心正西 nm 处的经度（cos(lat) 修正，与 makeProjector 同式）。"""
    return round(CENTER_LON - nm / 60.0 / COS_LAT, 6)


def build_scenario() -> dict:
    def carrier(name: str, squadrons: list[dict]) -> dict:
        return {"name": name, "damage_level": 0, "deck_status": "ready", "cap_strength": 12,
                "air_groups": squadrons}

    return {
        "id": "midway",
        "date": "1942-06-04",
        "clock_start": "1942-06-04T04:00:00Z",
        "task_forces": [
            {
                "callsign": "ENT",
                "name": "Task Force 16",
                "lat": CENTER_LAT, "lon": nm_west_lon(45),
                "course": 270, "speed": 25,
                "damage_level": 0, "deck_status": "ready",
                "patrol": {"cap_strength": 12, "pattern": "sector",
                           "bearing_min": SECTOR_BEARING[0], "bearing_max": SECTOR_BEARING[1],
                           "radius_nm": 60},
                "carriers": [carrier("USS Enterprise (CV-6)", [
                    {"type": "fighter", "squadron": "VF-6", "count": 27},
                    {"type": "dive_bomber", "squadron": "VB-6/VS-6", "count": 38},
                    {"type": "torpedo", "squadron": "VT-6", "count": 15},
                ])],
            },
            {
                "callsign": "HOR",
                "name": "Task Force 17",
                "lat": CENTER_LAT, "lon": nm_west_lon(28),
                "course": 270, "speed": 25,
                "damage_level": 0, "deck_status": "ready",
                "patrol": {"cap_strength": 12, "pattern": "sector",
                           "bearing_min": SECTOR_BEARING[0], "bearing_max": SECTOR_BEARING[1],
                           "radius_nm": 60},
                "carriers": [carrier("USS Hornet (CV-8)", [
                    {"type": "fighter", "squadron": "VF-8", "count": 27},
                    {"type": "dive_bomber", "squadron": "VB-8/VS-8", "count": 38},
                    {"type": "torpedo", "squadron": "VT-8", "count": 15},
                ])],
            },
        ],
        "enemy_fleet": {"name": "Kido Butai", "lat": 31.0, "lon": -180.0,
                        "course": 135, "speed": 25,
                        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"]},
        "npc_roster": {"co_staff": "Spruance 参谋团", "intel": "Nimitz 情报组（Pearl）",
                       "air_officer": "Halsey 航空参谋（代理）"},
        "victory": {"primary": "重创日军航母编队", "secondary": "保住中途岛机场"},
        "event_seeds": ["鹦鹉螺号潜艇接敌报告", "日军对中途岛第一波空袭"],
    }


README = """# Midway Theater Pack（中途岛战区包）

## 数据来源

- **AI 生成（仓库自有公式移植，无第三方数据）**：`tools/gen_midway_pack.py` 把
  `static/js/chartRenderer.js` 的程序化环礁（atollOutline 三谐波系数）、双岛、跑道、
  标注公式移植为 GeoJSON 坐标产出——数据与渲染同源，视觉等价由 M.3/M.4 回归验收。
- theater.json 数值锚点 = chartRenderer 现值：center 28.2/-177.4、view_nm 45、
  graticule 0.25/1.0、rings [20,25,40,60]、扇区 30°-90° 沿用。
- 基地坐标 28.2072/-177.3735 = 沙岛机场史实位（美军中途岛陆基航空兵约 113 架，
  docs/reference/HISTORICAL_NOTES.md 口径）。
- scenario 双舰队初始位 = 成品图量取规则：环礁正西 ENT 45nm / HOR 28nm
  （cos(lat) 修正，与 makeProjector 投影同式），course 270、speed 25。

## 许可证

无第三方素材——全部由本仓库代码程序化生成（AI 生成声明），无外部许可证义务。

## 生成方式

```bash
.venv/bin/python tools/gen_midway_pack.py   # 重新产出本目录四文件
.venv/bin/python tools/validate_theater.py  # 校验（硬校验 FAIL / 软校验 WARN）
```

## 备注

- 跑道以 `route_hint` 线要素承载（`name` 前缀 `runway_`）：schema v1 无 runway class，
  虚线淡线渲染语义一致；M.3 ChartEngine 若需专属跑道样式，属 schema 扩展决策。
- 沙岛胶囊宽取 chartRenderer 文字度量守卫下限 62px（基准图面短边 764 换算，见生成器注释）。
"""


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    outputs = {
        "theater.json": build_theater(),
        "geography.geojson": build_geojson(),
        "scenario.json": build_scenario(),
        "README.md": README,
    }
    for fname, data in outputs.items():
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n" \
            if not fname.endswith(".md") else data
        (PACK / fname).write_text(text)
        print(f"wrote {PACK / fname}")


if __name__ == "__main__":
    main()
