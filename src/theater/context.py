"""TheaterContext — 运行时战区上下文（CHART_SYSTEM.md §三/§四/§九决议6）。

游戏逻辑通过 TheaterContext 读战区配置，禁止直连具体战区常量（§五）。
`GET /theater` 下发的战区包合并 JSON 以前端 ChartEngine 为唯一消费者（§四）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tools.validate_theater import validate_theater


@dataclass
class TheaterContext:
    """战区运行时上下文：theater.json 结构化字段 + 原始 dict + scenario 摘要。

    theater_raw / geography 保留原始 dict，供 `GET /theater` 原样下发。
    """

    id: str
    name: str
    view: dict                      # 取景：center/view_nm/rotation（§三 schema）
    bases: list[dict]               # 基地/机场（起飞/降落/陆基航程）
    sectors: list[dict]             # 侦察扇区模板（generate_*_route 参数来源）
    graticule: dict                 # 经纬网步进/标注格式
    range_rings: dict               # 距离环原点/半径
    scenario: dict                  # scenario.json（战区剧本摘要：兵力/NPC 名册/胜利条件）
    theater_raw: dict               # theater.json 原样
    geography: dict                 # geography.geojson 原样
    pack_dir: Path                  # 战区包目录


def load_theater(pack_dir: Path | str) -> TheaterContext:
    """读取战区包（theater.json + geography.geojson + scenario.json）→ TheaterContext。

    先过 validate_theater（§七），失败抛 ValueError——调用方（server 启动）据此拒绝启动。
    """
    pack_dir = Path(pack_dir)
    result = validate_theater(pack_dir)
    if not result["ok"]:
        raise ValueError(f"战区包校验失败 {pack_dir}: {result['errors']}")

    theater = json.loads((pack_dir / "theater.json").read_text(encoding="utf-8"))
    geography = json.loads((pack_dir / "geography.geojson").read_text(encoding="utf-8"))
    scenario = json.loads((pack_dir / "scenario.json").read_text(encoding="utf-8"))

    return TheaterContext(
        id=theater["id"],
        name=theater["name"],
        view=theater["view"],
        bases=theater["bases"],
        sectors=theater["sectors"],
        graticule=theater["graticule"],
        range_rings=theater["range_rings"],
        scenario=scenario,
        theater_raw=theater,
        geography=geography,
        pack_dir=pack_dir,
    )
