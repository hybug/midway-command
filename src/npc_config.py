"""NPC configuration — centralized parameters and info permissions.

Each NPC has:
- Autonomy parameters (autonomy, risk_tolerance, initiative, competence)
- Info scope: what parts of GameState this NPC can see
- Allowed tools: which tool names this NPC can call
"""
from dataclasses import dataclass, field


@dataclass
class NPCConfig:
    """Configuration for a single NPC."""
    name: str
    role: str
    autonomy: int          # 0-10
    risk_tolerance: float  # 0-1
    initiative: float      # 0-1
    competence: float      # 0-1
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
        risk_tolerance=0.8,
        initiative=0.9,
        competence=0.9,
        info_scope=[
            "fleet_global", "air_groups", "known_enemy",
            "active_scouts", "pending_reports",
        ],
        allowed_tools=[
            "query_fleet_status", "execute_action", "propose_recon",
        ],
    ),
    "murray": NPCConfig(
        name="George Murray",
        role="企业号舰长",
        autonomy=5,
        risk_tolerance=0.4,
        initiative=0.5,
        competence=0.7,
        info_scope=["own_carrier", "air_groups"],
        allowed_tools=["query_fleet_status", "execute_action"],
        carrier_filter="Enterprise",
    ),
    "mitscher": NPCConfig(
        name="Marc Mitscher",
        role="大黄蜂舰长",
        autonomy=5,
        risk_tolerance=0.4,
        initiative=0.5,
        competence=0.7,
        info_scope=["own_carrier", "air_groups"],
        allowed_tools=["query_fleet_status", "execute_action"],
        carrier_filter="Hornet",
    ),
    "radio_officer": NPCConfig(
        name="通信官",
        role="通信官",
        autonomy=1,
        risk_tolerance=0.1,
        initiative=0.2,
        competence=0.6,
        info_scope=["incoming_msgs"],
        allowed_tools=[],
    ),
    "intel_officer": NPCConfig(
        name="情报官",
        role="情报参谋",
        autonomy=3,
        risk_tolerance=0.3,
        initiative=0.6,
        competence=0.7,
        info_scope=["known_enemy", "pending_reports", "active_scouts"],
        allowed_tools=["query_fleet_status"],
    ),
}
