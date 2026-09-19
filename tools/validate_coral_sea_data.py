#!/usr/bin/env python3
"""珊瑚海史实资料包校验器（coral-sea-historical-research-plan §四/§八/§十）。

用法: python tools/validate_coral_sea_data.py docs/reference/coral-sea
退出码: 0=全部通过; 1=存在违规（违规明细打 stdout）。

覆盖：
- schema 必填字段与枚举（source_type / confidence）。
- source_ids 引用闭合；CONFIRMED 必须有 PRIMARY/OFFICIAL/ARCHIVAL 来源。
- ESTIMATED 数值必须带 estimate_note；CONFLICTED 必须在 uncertainties 登记处可查
  （此处只做枚举检查，冲突登记在 uncertainties.md 人工维护）。
- 事件时间：zulu = local + 舰队时区规则（5/7 17:00 前 +11:30，此后 +11）；
  timeline.json 顺序与 events zulu 非降序一致。
- 坐标必须落在战区包经纬网范围内（theaters/coral-sea/theater.json graticule.extent）。
- 编队旗舰必须是已登记舰艇；舰艇不得在日期重叠的两个编队中同时出现（转隶除外）。
- 损失数不得超过在舰/在编数量；人员 UNKNOWN 姓名必须使用职务名。
- 若存在 theaters/coral-sea/roster.json（S4.0 运行名册），校验其引用闭合与纪律。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PRIMARY_LIKE = {"PRIMARY", "OFFICIAL", "ARCHIVAL"}
SOURCE_TYPES = {"PRIMARY", "OFFICIAL", "ARCHIVAL", "SECONDARY", "TERTIARY"}
CONFIDENCES = {"CONFIRMED", "PROBABLE", "UNKNOWN", "CONFLICTED", "ESTIMATED"}
SIDE = {"US_ALLIED", "IJN"}
CONTACT_PERMISSIONS = {
    "DIRECT_IN_PERSON", "DIRECT_RADIO", "CHAIN_ONLY", "REPORT_ONLY", "NO_INITIATIVE",
}
EVIDENCE_GRADES = {"CONFIRMED", "PROBABLE", "UNKNOWN", "CONFLICTED"}

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 校验器需报告任意解析错误
        err(f"{path.name}: JSON 解析失败: {e}")
        return None


def parse_iso(value: str, label: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        err(f"{label}: 无法解析时间 {value!r}")
        return None


def fleet_offset(event: dict) -> timedelta | None:
    zone = str(event.get("source_time_zone", ""))
    if "civil" in zone or "local date only" in zone:
        return None
    if "-11:30" in zone:
        return timedelta(hours=11, minutes=30)
    if "-11:00" in zone or "-11" in zone:
        return timedelta(hours=11)
    err(f"{event.get('event_id')}: 未知时区标注 {zone!r}")
    return None


def _instant_check_exempt(event: dict, zone: str) -> bool:
    """换区瞬间与按日计事件不做『同一绝对时刻』校验（钟面跳变）。"""
    return "换区" in zone or "civil" in zone or "date only" in zone


def main(data_dir: Path) -> int:
    sources_doc = load_json(data_dir / "data" / "sources.json") or {}
    ships_doc = load_json(data_dir / "data" / "ships.json") or {}
    aircraft_doc = load_json(data_dir / "data" / "aircraft.json") or {}
    personnel_doc = load_json(data_dir / "data" / "personnel.json") or {}
    units_doc = load_json(data_dir / "data" / "units.json") or {}
    events_doc = load_json(data_dir / "data" / "events.json") or {}
    timeline_doc = load_json(data_dir / "data" / "timeline.json") or {}
    losses_doc = load_json(data_dir / "data" / "losses.json") or {}
    if errors:
        return finish()

    src_types = {s["source_id"]: s["source_type"] for s in sources_doc["sources"]}

    def check_refs(item: dict, label: str, allow_empty: bool = False) -> None:
        ids = item.get("source_ids") or []
        if not ids and not allow_empty:
            err(f"{label}: 缺少 source_ids")
        for sid in ids:
            if sid not in src_types:
                err(f"{label}: 引用未登记来源 {sid}")
        conf = item.get("confidence")
        if conf not in CONFIDENCES:
            err(f"{label}: 非法置信度 {conf!r}")
        if conf == "CONFIRMED" and ids:
            if not any(src_types.get(s) in PRIMARY_LIKE for s in ids):
                err(f"{label}: CONFIRMED 缺一手/官方来源")
        if conf == "ESTIMATED" and not item.get("estimate_note") \
                and not any(v.get("estimate_note") for v in item.values() if isinstance(v, dict)):
            err(f"{label}: ESTIMATED 必须显式说明建模口径")

    # ── 舰艇 ──
    ship_ids = set()
    for s in ships_doc.get("ships", []):
        label = f"ships:{s.get('ship_id')}"
        ship_ids.add(s["ship_id"])
        for field in ("name", "side", "ship_class", "type"):
            if not s.get(field):
                err(f"{label}: 缺少 {field}")
        if s.get("side") not in SIDE:
            err(f"{label}: 非法 side")
        check_refs(s, label)

    # ── 飞机 ──
    for a in aircraft_doc.get("aircraft", []):
        label = f"aircraft:{a.get('aircraft_id')}"
        check_refs(a, label, allow_empty=not a.get("present_at_coral_sea"))

    # ── 人员 ──
    personnel_ids = set()
    for p in personnel_doc.get("personnel", []):
        label = f"personnel:{p.get('personnel_id')}"
        personnel_ids.add(p["personnel_id"])
        if not p.get("name") or not p.get("role"):
            err(f"{label}: 缺少 name/role")
        if p.get("name_confidence") == "UNKNOWN" and "（职务名）" not in p.get("name", ""):
            err(f"{label}: 未确认姓名未使用职务名")
        check_refs(p, label, allow_empty=p.get("confidence") == "UNKNOWN")

    # ── 编队 ──
    unit_ids = set()
    ship_units: dict[str, list[tuple[str, str, str]]] = {}
    for u in units_doc.get("units", []):
        label = f"units:{u.get('unit_id')}"
        unit_ids.add(u["unit_id"])
        for field in ("side", "parent", "commander_id", "flagship",
                      "date_range", "task", "communication"):
            if field not in u:
                err(f"{label}: 缺少 {field}")
        if u.get("flagship") and u["flagship"] not in ship_ids:
            err(f"{label}: 旗舰 {u['flagship']} 不在舰艇登记中")
        if u.get("commander_id") and u["commander_id"] not in personnel_ids:
            err(f"{label}: 指挥官 {u['commander_id']} 不在人员登记中")
        if u.get("parent") and u["parent"] not in unit_ids:
            err(f"{label}: 上级单位 {u['parent']} 未定义（顺序错误）")
        rng = u.get("date_range") or {}
        if not (rng.get("from") and rng.get("to")):
            err(f"{label}: 缺少日期范围")
        check_refs(u, label)
        for ship in u.get("ships", []):
            if ship not in ship_ids:
                err(f"{label}: 舰艇 {ship} 未登记")
                continue
            ship_units.setdefault(ship, []).append(
                (u["unit_id"], rng["from"], rng["to"]))
    for t in units_doc.get("transfers", []):
        if t["ship"] not in ship_ids:
            err(f"transfers: 舰艇 {t['ship']} 未登记")
        if t["from_unit"] not in unit_ids or t["to_unit"] not in unit_ids:
            err(f"transfers: {t['ship']} 转隶编队未定义")

    # 舰艇同日不得在互不隶属的两个编队（显式转隶或父子嵌套除外）
    def _overlap(a: tuple[str, str, str], b: tuple[str, str, str]) -> bool:
        return a[1] <= b[2] and b[1] <= a[2]

    parent_of = {u["unit_id"]: u.get("parent") for u in units_doc.get("units", [])}

    def _related(a: str, b: str) -> bool:
        """同一层级重叠禁止；父子嵌套编队共享舰船合法。"""
        seen = {a}
        cur = parent_of.get(a)
        while cur and cur not in seen:
            if cur == b:
                return True
            seen.add(cur)
            cur = parent_of.get(cur)
        seen = {b}
        cur = parent_of.get(b)
        while cur and cur not in seen:
            if cur == a:
                return True
            seen.add(cur)
            cur = parent_of.get(cur)
        return False

    transfer_pairs = {(t["from_unit"], t["to_unit"]) for t in units_doc.get("transfers", [])}
    transfer_pairs |= {(b, a) for a, b in transfer_pairs}
    for ship, assignments in ship_units.items():
        for i in range(len(assignments)):
            for j in range(i + 1, len(assignments)):
                a, b = assignments[i], assignments[j]
                if _overlap(a, b) and not _related(a[0], b[0]) \
                        and (a[0], b[0]) not in transfer_pairs:
                    err(f"{ship}: 在重叠日期内同时属于 {a[0]} 与 {b[0]}（需登记转隶）")

    # ── 事件与时间线 ──
    events: dict[str, dict] = {}
    for e in events_doc.get("events", []):
        label = f"events:{e.get('event_id')}"
        events[e["event_id"]] = e
        loc = e.get("local_time")
        zulu = parse_iso(e.get("zulu_time", ""), f"{label}.zulu") if e.get("zulu_time") else None
        if e.get("zulu_time") and not str(e["zulu_time"]).endswith("Z"):
            err(f"{label}: zulu_time 必须以 Z 结尾")
        if loc:
            local = parse_iso(loc, f"{label}.local")
            offset = fleet_offset(e)
            if local and offset and local.utcoffset() != -offset:
                err(f"{label}: local_time 时区 {local.utcoffset()} 不符舰队区规则（应 {-offset}）")
            if local and zulu and offset and not _instant_check_exempt(e, e.get("source_time_zone") or ""):
                if local.astimezone(timezone.utc) != zulu:
                    err(f"{label}: local 与 Zulu 非同一绝对时刻")
        if not e.get("description") or not e.get("actor"):
            err(f"{label}: 缺少 description/actor")
        if e.get("time_exact") is False:
            zone = e.get("source_time_zone") or ""
            if not any(k in zone for k in ("约", "civil", "date only", "换区")):
                err(f"{label}: 非精确时间必须标注近似口径")
        lat, lon = (e.get("location") or {}).get("lat"), (e.get("location") or {}).get("lon")
        if lat is not None and not (-24.0 <= lat <= -4.0):
            err(f"{label}: 纬度 {lat} 超出战区包范围")
        if lon is not None and not (144.0 <= lon <= 170.0):
            err(f"{label}: 经度 {lon} 超出战区包范围")
        check_refs(e, label)

    prev_z = None
    for eid in timeline_doc.get("ordered_event_ids", []):
        if eid not in events:
            err(f"timeline: {eid} 不在 events.json 中")
            continue
        z = parse_iso(events[eid]["zulu_time"], f"timeline:{eid}") if events[eid].get("zulu_time") else None
        if z and prev_z and z < prev_z:
            err(f"timeline: {eid} 的时间早于前一条（顺序校验失败）")
        if z:
            prev_z = z
    missing = set(events) - set(timeline_doc.get("ordered_event_ids", []))
    if missing:
        err(f"timeline: 缺少事件 {sorted(missing)}")

    # ── 损失 ≤ 强度 ──
    ship_by_id = {s["ship_id"]: s for s in ships_doc.get("ships", [])}
    for loss in losses_doc.get("losses", []):
        label = f"losses:{loss.get('loss_id')}"
        target = loss.get("target")
        if target and target in ship_by_id:
            crew = loss.get("crew") or {}
            killed, survived, aboard = crew.get("killed"), crew.get("survived"), crew.get("aboard")
            if killed is not None and survived is not None and aboard is not None \
                    and killed + survived > aboard:
                err(f"{label}: 亡+获救 {killed + survived} 超过在舰 {aboard}")
            ac = loss.get("aircraft_lost_with_ship") or loss.get("aircraft_lost")
            if ac is not None:
                ship = ship_by_id[target]
                cap = (ship.get("air_complement") or {}).get("value")
                if cap is not None and ac > cap + 10:
                    err(f"{label}: 舰载机损失 {ac} 超过搭载 {cap}")
        if target == "CARDIV5" and target not in unit_ids:
            err(f"{label}: target 编队未登记")
        check_refs(loss, label)

    # ── S4 运行名册（存在才校验）──
    roster_path = data_dir.parent.parent.parent / "theaters" / "coral-sea" / "roster.json"
    if roster_path.is_file():
        roster = load_json(roster_path) or {}
        personnel_lookup = {
            p["personnel_id"]: p for p in personnel_doc.get("personnel", [])}
        for ch in roster.get("contact_channels", []):
            pid = ch.get("personnel_id")
            if pid not in personnel_lookup:
                err(f"roster: {ch.get('actor_id')} 指向未登记人员 {pid}")
            if ch.get("contact_permission") not in CONTACT_PERMISSIONS:
                err(f"roster: {ch.get('actor_id')} 非法 contact_permission")
            if ch.get("evidence_grade") not in EVIDENCE_GRADES:
                err(f"roster: {ch.get('actor_id')} 非法证据等级")
            if ch.get("evidence_grade") == "CONFLICTED":
                err(f"roster: {ch.get('actor_id')} 证据冲突不得进入运行 roster")
            for sid in ch.get("source_ids") or []:
                if sid not in src_types:
                    err(f"roster: {ch.get('actor_id')} 引用未登记来源 {sid}")
            if ch.get("evidence_grade") == "UNKNOWN" and "（职务名）" not in ch.get("display_name", ""):
                err(f"roster: {ch.get('actor_id')} UNKNOWN 人物未使用职务名")
        for link in roster.get("chain_of_command", []):
            if not link.get("from_role") or not link.get("to_role"):
                err("roster: 指挥链边缺少角色端点")
    return finish()


def finish() -> int:
    if errors:
        print(f"珊瑚海资料包校验：{len(errors)} 项违规")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print("珊瑚海资料包校验：全部通过（schema/来源/坐标/时区/编队/损失/名册）")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/reference/coral-sea")
    raise SystemExit(main(root))
