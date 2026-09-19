"""S4 运行名册加载（scenario roster 决定直接沟通名单，计划 §四/§九）。

- 珊瑚海：theaters/coral-sea/roster.json（由 CORAL_SEA_COMMAND_ROSTER.md 派生）。
- 其余战区（无 roster.json）：MIDWAY_PROVISIONAL 占位编制，active=False——
  S4 主动触发器不启用，仅提供 STAFF 频道静态展示。
- fail-fast：权限语义不一致（如 NO_INITIATIVE 却可主动）即抛 ValueError。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from src.staff.models import ContactPermission

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIDWAY_THEATER_ID = "midway"

# 权限语义推导表（单一事实来源，加载时校验 roster 与之一致）
_INITIATIVE_ALLOWED = {
    ContactPermission.DIRECT_IN_PERSON,
    ContactPermission.DIRECT_RADIO,
}
_SUMMON_ALLOWED = {
    ContactPermission.DIRECT_IN_PERSON,
    ContactPermission.DIRECT_RADIO,
    ContactPermission.NO_INITIATIVE,
}


@dataclass(frozen=True)
class ContactChannel:
    actor_id: str
    personnel_id: str
    display_name: str
    rank: str
    role: str
    flagship: str
    contact_permission: ContactPermission
    can_be_summoned: bool
    can_initiate: bool
    evidence_grade: str
    source_ids: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class RunRoster:
    theater_id: str
    roster_version: str
    active: bool
    commander_id: str
    contact_channels: tuple[ContactChannel, ...]
    chain_of_command: tuple[dict, ...] = ()
    role_bindings: dict[str, str] = field(default_factory=dict)
    role_of_actor: dict[str, str] = field(default_factory=dict)
    order_routing: dict[str, str] = field(default_factory=dict)
    derived_from: str = ""

    def channel(self, actor_id: str) -> ContactChannel | None:
        for ch in self.contact_channels:
            if ch.actor_id == actor_id:
                return ch
        return None

    def actor_for_role(self, role: str) -> str | None:
        return self.role_bindings.get(role)


MIDWAY_PROVISIONAL: dict = {
    "theater_id": MIDWAY_THEATER_ID,
    "roster_version": "0.1-provisional",
    "derived_from": "中途岛开局无 S4 级考证名册——游戏占位编制（职务名，ESTIMATED）",
    "active": False,
    "commander_id": "fletcher",
    "contact_channels": [
        {"actor_id": "browning", "personnel_id": "", "display_name": "Miles Browning",
         "rank": "Commander", "role": "参谋长", "flagship": "USS Enterprise",
         "contact_permission": "DIRECT_IN_PERSON", "can_be_summoned": True,
         "can_initiate": True, "evidence_grade": "UNKNOWN", "source_ids": []},
        {"actor_id": "navigator", "personnel_id": "", "display_name": "航海参谋（职务名）",
         "rank": "", "role": "航海参谋", "flagship": "USS Enterprise",
         "contact_permission": "DIRECT_IN_PERSON", "can_be_summoned": True,
         "can_initiate": False, "evidence_grade": "UNKNOWN", "source_ids": []},
        {"actor_id": "intel_officer", "personnel_id": "", "display_name": "情报参谋（职务名）",
         "rank": "", "role": "情报参谋", "flagship": "USS Enterprise",
         "contact_permission": "DIRECT_IN_PERSON", "can_be_summoned": True,
         "can_initiate": False, "evidence_grade": "UNKNOWN", "source_ids": []},
        {"actor_id": "radio_officer", "personnel_id": "", "display_name": "通信官（职务名）",
         "rank": "", "role": "通信官", "flagship": "USS Enterprise",
         "contact_permission": "NO_INITIATIVE", "can_be_summoned": True,
         "can_initiate": False, "evidence_grade": "UNKNOWN", "source_ids": []},
        {"actor_id": "murray", "personnel_id": "", "display_name": "George Murray",
         "rank": "Captain", "role": "企业号舰长", "flagship": "USS Enterprise",
         "contact_permission": "CHAIN_ONLY", "can_be_summoned": False,
         "can_initiate": False, "evidence_grade": "UNKNOWN", "source_ids": []},
        {"actor_id": "mitscher", "personnel_id": "", "display_name": "Marc Mitscher",
         "rank": "Captain", "role": "大黄蜂舰长", "flagship": "USS Hornet",
         "contact_permission": "CHAIN_ONLY", "can_be_summoned": False,
         "can_initiate": False, "evidence_grade": "UNKNOWN", "source_ids": []},
    ],
    "chain_of_command": [
        {"from_role": "CARRIER_CAPTAIN", "to_role": "CHIEF_OF_STAFF"},
        {"from_role": "CHIEF_OF_STAFF", "to_role": "COMMANDER"},
        {"from_role": "STAFF", "to_role": "COMMANDER"},
    ],
    "role_bindings": {"COMMANDER": "fletcher"},
    "role_of_actor": {},
    "order_routing": {"NAVIGATOR": "navigator", "AIR_OFFICER": "browning"},
}


def _build(raw: dict) -> RunRoster:
    channels = []
    for ch in raw.get("contact_channels", []):
        perm = ContactPermission(ch["contact_permission"])
        can_summon = bool(ch.get("can_be_summoned"))
        can_initiate = bool(ch.get("can_initiate"))
        if can_initiate and perm not in _INITIATIVE_ALLOWED:
            raise ValueError(
                f"roster 权限矛盾：{ch['actor_id']} 为 {perm.value} 却可主动联系")
        if can_summon and perm not in _SUMMON_ALLOWED:
            raise ValueError(
                f"roster 权限矛盾：{ch['actor_id']} 为 {perm.value} 却可召见")
        channels.append(ContactChannel(
            actor_id=ch["actor_id"],
            personnel_id=ch.get("personnel_id", ""),
            display_name=ch.get("display_name", ""),
            rank=ch.get("rank", ""),
            role=ch.get("role", ""),
            flagship=ch.get("flagship", ""),
            contact_permission=perm,
            can_be_summoned=can_summon,
            can_initiate=can_initiate,
            evidence_grade=ch.get("evidence_grade", "UNKNOWN"),
            source_ids=tuple(ch.get("source_ids", [])),
            note=ch.get("channel_note", ""),
        ))
    return RunRoster(
        theater_id=raw["theater_id"],
        roster_version=raw.get("roster_version", ""),
        active=bool(raw.get("active")),
        commander_id=raw.get("commander_id", "fletcher"),
        contact_channels=tuple(channels),
        chain_of_command=tuple(raw.get("chain_of_command", [])),
        role_bindings=dict(raw.get("role_bindings", {})),
        role_of_actor=dict(raw.get("role_of_actor", {})),
        order_routing=dict(raw.get("order_routing", {})),
        derived_from=raw.get("derived_from", ""),
    )


def load_run_roster(theater_id: str) -> RunRoster:
    """按战区加载运行名册；无 roster.json 的战区回退占位编制。"""
    path = REPO_ROOT / "theaters" / theater_id / "roster.json"
    if not path.is_file():
        return _build(dict(MIDWAY_PROVISIONAL, theater_id=theater_id))
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("theater_id") != theater_id:
        raise ValueError(f"roster theater_id 不匹配: {raw.get('theater_id')} != {theater_id}")
    return _build(raw)


# 当前对局的活动名册（server 启动/换战区时设置；pipeline 步骤经 get_active_roster 读取）
_ACTIVE_ROSTER: RunRoster | None = None


def set_active_roster(roster: RunRoster | None) -> None:
    global _ACTIVE_ROSTER
    _ACTIVE_ROSTER = roster


def get_active_roster() -> RunRoster | None:
    return _ACTIVE_ROSTER
