"""NPC configuration — centralized parameters and info permissions.

Each NPC has:
- Autonomy parameters (autonomy, risk_tolerance, initiative, competence)
- Info scope: what parts of GameState this NPC can see
- Allowed tools: which tool names this NPC can call
"""
from dataclasses import dataclass, field


@dataclass
class NPCConfig:
    """Configuration for a single NPC (§8.2.1).

    All parameters are 0-10 integers (骰子系统 §7.3).
    """
    name: str
    role: str
    autonomy: int          # 0-10: 越自主，行动越果断
    risk_tolerance: int    # 0-10: 越敢冒险，波动越大
    initiative: int        # 0-10: 越主动，越可能抓住机会
    competence: int        # 0-10: 越专业，执行质量越高
    # Which parts of state this NPC can access
    info_scope: list[str] = field(default_factory=list)
    # Which tools this NPC can call (by name)
    allowed_tools: list[str] = field(default_factory=list)
    # Carrier name this NPC is responsible for (for captains)
    carrier_filter: str = ""


# info_scope keys:
#   "fleet_global"    — full fleet positions, courses, speeds
#   "own_carrier"     — only this NPC's assigned carrier
#   "air_groups"      — air group readiness (fuel, ammo, status)
#   "known_enemy"     — confirmed enemy contacts
#   "incoming_msgs"   — raw telegrams
#   "pending_reports" — delayed scout reports in transit
#   "active_scouts"   — active scout missions

NPC_REGISTRY: dict[str, NPCConfig] = {
    "browning": NPCConfig(
        name="Miles Browning",
        role="参谋长",
        autonomy=8,
        risk_tolerance=8,
        initiative=9,
        competence=9,
        info_scope=[
            "fleet_global", "air_groups", "known_enemy",
            "active_scouts", "pending_reports",
        ],
        allowed_tools=["query_fleet_status", "propose_recon"],
    ),
    "murray": NPCConfig(
        name="George Murray",
        role="企业号舰长",
        autonomy=5,
        risk_tolerance=4,
        initiative=5,
        competence=7,
        info_scope=["own_carrier", "air_groups"],
        allowed_tools=["query_fleet_status"],
        carrier_filter="Enterprise",
    ),
    "mitscher": NPCConfig(
        name="Marc Mitscher",
        role="大黄蜂舰长",
        autonomy=5,
        risk_tolerance=4,
        initiative=5,
        competence=7,
        info_scope=["own_carrier", "air_groups"],
        allowed_tools=["query_fleet_status"],
        carrier_filter="Hornet",
    ),
    "radio_officer": NPCConfig(
        name="通信官",
        role="通信官",
        autonomy=1,
        risk_tolerance=1,
        initiative=2,
        competence=6,
        info_scope=["incoming_msgs"],
        allowed_tools=[],
    ),
    "intel_officer": NPCConfig(
        name="情报官",
        role="情报参谋",
        autonomy=3,
        risk_tolerance=3,
        initiative=4,
        competence=7,
        info_scope=["known_enemy", "pending_reports", "active_scouts"],
        allowed_tools=["query_fleet_status"],
    ),
    "navigator": NPCConfig(
        name="航海参谋",
        role="航海参谋",
        autonomy=4,
        risk_tolerance=2,
        initiative=4,
        competence=9,
        info_scope=["fleet_global"],
        allowed_tools=[
            "query_own_fleet", "query_theater",
            "query_distance_bearing", "propose_route",
        ],
    ),
}


# ── 执行单位档案（S2.1：检定用实际执行单位能力，而非固定参谋）──
# 侦察/通信等检定的执行者是具体单位（中队、电台员等），不是岸上参谋。
# competence 直接进入骰子 NPC 层（×2，封顶 +20，§7.3）。
UNIT_REGISTRY: dict[str, NPCConfig] = {
    "sbd_scout_section": NPCConfig(
        name="SBD 侦察中队",
        role="侦察机队",
        autonomy=2,
        risk_tolerance=2,
        initiative=3,
        competence=6,
    ),
}
