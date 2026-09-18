"""珊瑚海 v0 班子名册与角色证据权限（Phase S3.0，计划 §九）。

历史边界（M3.1 验收：人物档案不携带未经史料确认的虚构事实）：
- Fletcher / Fitch 为实名历史人物；TF17 情报参谋与作战参谋 v0 用职务名
  （一手行动报告未给出可靠到可入档的个人姓名）。
- attributes 是游戏设计参数（0-10，骰子系统 §7.3 口径），不是历史断言；
  每人参数理由登记在 docs/design/S3_COGNITION_SYSTEM.md §三。
- source_refs 只允许引用 HISTORICAL_SOURCES 已登记的一手史料。

权限（D6/D7）：情报参谋读权限内原始证据；Fitch 读已呈报简报引用的证据与
已批准标图；作战参谋读已批准标图与简报；任何角色禁止 actual_enemy。
NPC 默认不能读取其他 NPC 的私有判断（判断记忆按 actor 隔离）。
"""
from pydantic import Field

from src.cognition.models import ActorProfile
from src.intel.contracts import ActorRole


class StaffActor(ActorProfile):
    """名册条目：S3 ActorProfile + 名册装配字段。"""
    is_player: bool = False
    display_name: str = ""
    judgment_focus: str = ""
    duty_boundary: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


# ── 一手史料登记（计划 §十；M3.1.4 prompt 素材只允许引用此处）──

HISTORICAL_SOURCES: dict[str, dict] = {
    "TF17_REPORT": {
        "title": "Commander Task Force 17 — Battle of the Coral Sea, May 4–8",
        "url": "https://www.ibiblio.org/hyperwar/USN/rep/Coral/TF17.html",
        "note": "TF17 行动报告：5/7 米西马方向接触、contact pad 错误、祥凤击沉；5/8 黎明 360° 搜索、006°→028° 修正、Fitch 任 OTC",
    },
    "YORKTOWN_ACTION_REPORT": {
        "title": "USS Yorktown — Coral Sea Action Report",
        "url": "https://www.ibiblio.org/hyperwar/USN/ships/logs/CV/cv5-Coral.html",
        "note": "约克城号行动报告：放飞时序、舰载机作业与损失",
    },
}


CORAL_SEA_ACTORS: list[StaffActor] = [
    StaffActor(
        actor_id="fletcher",
        role="player",
        domain="command",
        display_name="Frank Jack Fletcher（CTF-17）",
        attributes={
            "competence": 6, "risk_tolerance": 5, "imagination": 4,
            "initiative": 6, "autonomy": 8,
        },
        profile_version="coral-sea-v1",
        is_player=True,
        judgment_focus="最终决心、授权、资源取舍",
        duty_boundary=["玩家本人；不作为判断引擎对象"],
        source_refs=["TF17_REPORT", "YORKTOWN_ACTION_REPORT"],
    ),
    StaffActor(
        actor_id="fitch",
        role="TF11 司令 · 航空作战",
        domain="air",
        display_name="Aubrey W. Fitch",
        attributes={
            "competence": 7, "risk_tolerance": 5, "imagination": 4,
            "initiative": 6, "autonomy": 5,
        },
        profile_version="coral-sea-v1",
        judgment_focus="航空作战、攻击窗口、航空兵协调",
        duty_boundary=["不给航空判断之外的敌情结论", "不冒充情报来源"],
        source_refs=["TF17_REPORT"],
    ),
    StaffActor(
        actor_id="tf17_intel",
        role="TF17 情报参谋（职务名）",
        domain="intelligence",
        display_name="TF17 情报参谋",
        attributes={
            "competence": 6, "risk_tolerance": 3, "imagination": 3,
            "initiative": 4, "autonomy": 3,
        },
        profile_version="coral-sea-v1",
        judgment_focus="证据可靠性、敌人身份和位置",
        duty_boundary=["不制定航空攻击细节", "不越权调度舰队"],
        source_refs=["TF17_REPORT"],
    ),
    StaffActor(
        actor_id="tf17_ops",
        role="TF17 作战参谋（职务名）",
        domain="operations",
        display_name="TF17 作战参谋",
        attributes={
            "competence": 6, "risk_tolerance": 4, "imagination": 3,
            "initiative": 5, "autonomy": 4,
        },
        profile_version="coral-sea-v1",
        judgment_focus="舰队风险、机动、CAP 和执行可行性",
        duty_boundary=["不修改敌情判断", "不代替指挥官下决心"],
        source_refs=["TF17_REPORT"],
    ),
]


def get_actor(actor_id: str) -> StaffActor:
    for a in CORAL_SEA_ACTORS:
        if a.actor_id == actor_id:
            return a
    raise KeyError(f"名册中无此角色: {actor_id}")


# ── 角色证据权限矩阵（§九 可见信息；玩家面见 PLAYER_VISIBLE_SCOPES）──
# raw_evidence_roles: 直接读取的原始证据 access 角色（S2 账本权限）
# evidence_via: 间接读取通道——briefed=已呈报简报引用的证据；
#               approved_plots=已批准标图提案引用的证据
_PERMISSIONS: dict[str, dict] = {
    "fletcher": {
        "raw_evidence_roles": [],
        "evidence_via": ["inbox", "briefs_submitted", "approved_plots"],
        "sees_other_npc_private_memory": False,
    },
    "tf17_intel": {
        "raw_evidence_roles": [ActorRole.INTEL_OFFICER.value],
        "evidence_via": [],
        "sees_other_npc_private_memory": False,
    },
    "fitch": {
        "raw_evidence_roles": [],
        "evidence_via": ["briefed", "approved_plots"],
        "sees_other_npc_private_memory": False,
    },
    "tf17_ops": {
        "raw_evidence_roles": [],
        "evidence_via": ["approved_plots", "briefed"],
        "sees_other_npc_private_memory": False,
    },
}


def get_permission(actor_id: str) -> dict:
    return dict(_PERMISSIONS[actor_id])


def permission_matrix() -> dict:
    return {k: dict(v) for k, v in _PERMISSIONS.items()}
