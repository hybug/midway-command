#!/usr/bin/env python3
"""战区包校验器（CHART_SYSTEM.md §七）。

硬校验（FAIL 拒载）：schema 合法 / 视野中心在经纬度范围 / GeoJSON 几何闭合 /
坐标范围 / land 面积下限 / bases 至少 1 个且在视野内 / RING 原点在视野内 / 时区合法。
软校验（WARN 进报告，stdout 打印）：海岸线顶点数异常（>500 疑未简化）/ 岛名缺失 /
check_points 真实地理抽样比对（误差 >0.5° 报警）。

用法：.venv/bin/python tools/validate_theater.py [theaters/midway]
"""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PACK = REPO / "theaters" / "midway"

# geography.geojson 合法 class 集合（§三约定）
GEO_CLASSES = {"land", "islet", "reef", "lagoon", "depth_contour", "label", "route_hint"}

MIN_LAND_AREA_NM2 = 1.0        # land 多边形面积下限（排除退化/误标）
MAX_COASTLINE_VERTS = 500      # 软校验：超过疑未简化
MAX_CHECK_POINT_ERR_DEG = 0.5  # 软校验：真实地理抽样容差


def _nm_east_south(dlon: float, dlat: float, ref_lat: float) -> tuple[float, float]:
    """经纬差 → nm 偏移（等距圆柱 + cos(lat) 修正，与前端投影同式）。"""
    return dlon * 60.0 * math.cos(math.radians(ref_lat)), dlat * 60.0


def _in_view(lat: float, lon: float, view: dict) -> bool:
    """点是否在视野内（以 view_nm 为半径的圆域）。"""
    c = view["center"]
    e, s = _nm_east_south(lon - c["lon"], lat - c["lat"], c["lat"])
    return math.hypot(e, s) <= view["view_nm"]


def _ring_area_nm2(ring: list, ref_lat: float) -> float:
    """鞋带公式求线环面积（nm²，顶点经 cos(lat) 修正到 nm 平面）。"""
    pts = []
    for lon, lat in ring:
        e, s = _nm_east_south(lon, lat, ref_lat)
        pts.append((e, s))
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _check_geojson(geo: dict, view: dict, errors: list, warnings: list) -> None:
    if not isinstance(geo, dict) or geo.get("type") != "FeatureCollection":
        errors.append("geography.geojson 顶层须为 FeatureCollection")
        return
    features = geo.get("features")
    if not isinstance(features, list) or not features:
        errors.append("geography.geojson 无 features")
        return
    has_land = False
    for i, f in enumerate(features):
        tag = f"feature[{i}]"
        props = f.get("properties") or {}
        cls = props.get("class")
        if cls not in GEO_CLASSES:
            errors.append(f"{tag} class 非法: {cls!r}")
            continue
        geom = f.get("geometry") or {}
        gtype, coords = geom.get("type"), geom.get("coordinates")
        if gtype == "Point":
            lon, lat = coords
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                errors.append(f"{tag} Point 坐标越界: {coords}")
        elif gtype == "LineString":
            for lon, lat in coords:
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    errors.append(f"{tag} LineString 坐标越界: {coords}")
        elif gtype == "Polygon":
            for ring in coords:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    errors.append(f"{tag} Polygon 线环未闭合（首尾同点、≥4 顶点）")
                for lon, lat in ring:
                    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                        errors.append(f"{tag} Polygon 坐标越界: {(lon, lat)}")
            if cls == "land":
                has_land = True
                area = _ring_area_nm2(coords[0], view["center"]["lat"])
                if area < MIN_LAND_AREA_NM2:
                    errors.append(f"{tag} land 面积 {area:.2f}nm² < 下限 {MIN_LAND_AREA_NM2}nm²")
        else:
            errors.append(f"{tag} 几何类型非法: {gtype!r}（Point/LineString/Polygon）")
            continue
        # 软校验：海岸线顶点数 / 岛名缺失
        if cls in ("land", "islet"):
            n_verts = sum(len(r) for r in coords) if gtype == "Polygon" else len(coords)
            if n_verts > MAX_COASTLINE_VERTS:
                warnings.append(f"{tag} {props.get('name', '?')} 顶点数 {n_verts} > "
                                f"{MAX_COASTLINE_VERTS}，疑未简化")
            if not props.get("name"):
                warnings.append(f"{tag} 陆地要素缺 name（岛名缺失）")
    if not has_land:
        errors.append("geography.geojson 无 land 要素")


def _check_scenario(sc: dict, errors: list) -> None:
    tfs = sc.get("task_forces")
    if not isinstance(tfs, list) or not tfs:
        errors.append("scenario.json task_forces 须为非空数组")
        return
    for i, tf in enumerate(tfs):
        tag = f"task_forces[{i}]"
        for key in ("callsign", "lat", "lon", "course", "speed"):
            if key not in tf:
                errors.append(f"{tag} 缺字段 {key}")
        if "lat" in tf and "lon" in tf:
            if not (-90 <= tf["lat"] <= 90 and -180 <= tf["lon"] <= 180):
                errors.append(f"{tag} 坐标越界: {(tf['lat'], tf['lon'])}")
        if "course" in tf and not (0 <= tf["course"] <= 359):
            errors.append(f"{tag} course 越界: {tf['course']}")


def validate_theater(pack_dir: Path) -> dict:
    """校验战区包目录。返回 {ok, errors, warnings}；errors 非空即 FAIL。"""
    pack_dir = Path(pack_dir)
    errors: list[str] = []
    warnings: list[str] = []

    # ── theater.json schema ──
    theater_path = pack_dir / "theater.json"
    try:
        theater = json.loads(theater_path.read_text())
    except FileNotFoundError:
        errors.append("缺 theater.json")
        theater = None
    except json.JSONDecodeError as e:
        errors.append(f"theater.json JSON 解析失败: {e}")
        theater = None

    view = None
    if theater is not None:
        for key in ("id", "name", "view", "graticule", "range_rings", "bases", "sectors"):
            if key not in theater:
                errors.append(f"theater.json 缺字段 {key}")
        if "view" in theater:
            view = theater["view"]
            c = view.get("center") or {}
            if not (-90 <= c.get("lat", 999) <= 90 and -180 <= c.get("lon", 999) <= 180):
                errors.append(f"视野中心坐标越界: {c}")
            if not (0 < view.get("view_nm", 0) <= 3000):
                errors.append(f"view_nm 非法: {view.get('view_nm')}")
        gr = theater.get("graticule") or {}
        if not (0 < gr.get("minor_step", 0) < gr.get("major_step", 0) <= 30):
            errors.append("graticule 步进非法（须 0 < minor < major）")
        # 可选字段宽松校验（M.3 前端消费：存在才校验，缺省放行）
        frac = view.get("atoll_screen_frac")
        if frac is not None:
            fx, fy = frac.get("x"), frac.get("y")
            if not (isinstance(fx, (int, float)) and isinstance(fy, (int, float))
                    and 0 <= fx <= 1 and 0 <= fy <= 1):
                errors.append(f"atoll_screen_frac 非法（须 0≤x,y≤1）: {frac}")
        ext = gr.get("extent")
        if ext is not None:
            if not (ext.get("lat_min", 91) < ext.get("lat_max", -91)
                    and ext.get("lon_min", 181) < ext.get("lon_max", -181)):
                errors.append(f"graticule.extent 非法（须 min < max）: {ext}")
        atoll = theater.get("atoll")
        if atoll is not None:
            r = atoll.get("radius_nm") or {}
            if not (0 < r.get("x", 0) <= 300 and 0 < r.get("y", 0) <= 300):
                errors.append(f"atoll.radius_nm 非法（须 0 < x,y ≤ 300nm）: {r}")
        labels = theater.get("labels")
        if labels is not None and not all(isinstance(v, str) and v for v in labels.values()):
            errors.append(f"labels 须为非空字符串映射: {labels}")
        if not -12 <= theater.get("timezone_offset", 999) <= 14:
            errors.append(f"timezone_offset 非法: {theater.get('timezone_offset')}")
        bases = theater.get("bases")
        if not isinstance(bases, list) or len(bases) < 1:
            errors.append("bases 至少 1 个")
        elif view and view.get("center"):
            for b in bases:
                if not _in_view(b["lat"], b["lon"], view):
                    errors.append(f"base {b.get('id')!r} 不在视野内: "
                                  f"({b['lat']}, {b['lon']})")
        if not isinstance(theater.get("sectors"), list) or len(theater.get("sectors", [])) < 1:
            errors.append("sectors 至少 1 个")
        # 软校验：check_points 真实地理抽样比对
        for cp in theater.get("check_points", []):
            best = _min_geo_distance_deg(pack_dir / "geography.geojson", cp)
            if best is not None and best > MAX_CHECK_POINT_ERR_DEG:
                warnings.append(f"check_point {cp.get('name', '?')} 距最近地理要素 "
                                f"{best:.2f}° > {MAX_CHECK_POINT_ERR_DEG}°")

    # ── geography.geojson ──
    try:
        geo = json.loads((pack_dir / "geography.geojson").read_text())
        if view:
            _check_geojson(geo, view, errors, warnings)
    except FileNotFoundError:
        errors.append("缺 geography.geojson")
    except json.JSONDecodeError as e:
        errors.append(f"geography.geojson JSON 解析失败: {e}")

    # ── scenario.json ──
    try:
        _check_scenario(json.loads((pack_dir / "scenario.json").read_text()), errors)
    except FileNotFoundError:
        errors.append("缺 scenario.json")
    except json.JSONDecodeError as e:
        errors.append(f"scenario.json JSON 解析失败: {e}")

    # ── RING 原点在视野内 ──
    if theater and view and view.get("center") and "range_rings" in theater:
        origin = (theater["range_rings"].get("origin") or {})
        if "lat" in origin and "lon" in origin:
            if not _in_view(origin["lat"], origin["lon"], view):
                errors.append(f"距离环原点不在视野内: ({origin['lat']}, {origin['lon']})")
        else:
            errors.append("range_rings 缺 origin")

    for w in warnings:
        print(f"WARN: {w}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _min_geo_distance_deg(geo_path: Path, check_point: dict) -> float | None:
    """check_point 到地理要素全部顶点/点的最小角距（度，经度按 cos(lat) 折算）。"""
    try:
        geo = json.loads(geo_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    lat0, lon0 = check_point["lat"], check_point["lon"]
    best = None
    pts: list[tuple[float, float]] = []
    for f in geo.get("features", []):
        geom = f.get("geometry") or {}
        c = geom.get("coordinates")
        if geom.get("type") == "Point":
            pts.append(tuple(c))
        elif geom.get("type") in ("LineString", "MultiPoint"):
            pts.extend(tuple(p) for p in c)
        elif geom.get("type") == "Polygon":
            for ring in c:
                pts.extend(tuple(p) for p in ring)
    for lon, lat in pts:
        e, s = _nm_east_south(lon - lon0, lat - lat0, lat0)
        deg = math.hypot(e, s) / 60.0
        best = deg if best is None else min(best, deg)
    return best


def main() -> int:
    pack = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PACK
    result = validate_theater(pack)
    status = "PASS" if result["ok"] else "FAIL"
    print(f"[{status}] {pack}  errors={len(result['errors'])} warnings={len(result['warnings'])}")
    for e in result["errors"]:
        print(f"ERROR: {e}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
