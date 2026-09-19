"""珊瑚海史实资料包校验（coral-sea-historical-research-plan §八/§十）。

红线：
- 每条关键事实必须关联 sources.json 内存在的 source_id。
- CONFIRMED 必须有 PRIMARY/OFFICIAL/ARCHIVAL 来源；ESTIMATED 必须显式标记。
- 时间线同时保留当地时间与 Zulu 时间，且服从 TF17 报告的时区规则
  （1942-05-07 17:00 前舰队时区 Z−11:30，之后 Z−11）。
- 坐标必须落在战区包经纬网范围内（lat −24..−4, lon 144..170）。
- 编队旗舰必须是已登记舰艇；损失数不得超过参战编制数。
- S4 运行 roster：每人有来源与证据等级；未确认人物使用职务名。
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "reference" / "coral-sea" / "data"
VALIDATOR = ROOT / "tools" / "validate_coral_sea_data.py"
ROSTER_DOC = ROOT / "docs" / "reference" / "CORAL_SEA_COMMAND_ROSTER.md"

REQUIRED_DOCS = [
    "README.md", "sources.md", "timeline.md", "order-of-battle.md",
    "command-relationships.md", "personnel.md", "communications.md",
    "geography.md", "environment.md", "aircraft.md", "ships.md",
    "losses.md", "decisions.md", "uncertainties.md",
]
REQUIRED_DATA = [
    "sources.json", "timeline.json", "ships.json", "aircraft.json",
    "personnel.json", "units.json", "events.json",
]


def test_reference_docs_present():
    for name in REQUIRED_DOCS:
        assert (DATA.parent / name).is_file(), f"缺少资料文档 {name}"
    assert ROSTER_DOC.is_file(), "缺少 S4 指挥名册 CORAL_SEA_COMMAND_ROSTER.md"


def test_machine_readable_data_present():
    for name in REQUIRED_DATA:
        assert (DATA / name).is_file(), f"缺少机器可读数据 {name}"
        json.loads((DATA / name).read_text(encoding="utf-8"))


def test_validator_passes():
    """schema、来源引用、坐标、日期与交叉一致性全量校验。"""
    assert VALIDATOR.is_file(), "缺少校验器 tools/validate_coral_sea_data.py"
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(DATA.parent)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"校验器未通过:\n{proc.stdout}\n{proc.stderr}"


def test_command_roster_discipline():
    """S4.0 名册纪律：来源 + 证据等级；未确认人物必须用职务名。"""
    roster_path = ROOT / "theaters" / "coral-sea" / "roster.json"
    if not roster_path.is_file():
        pytest.skip("运行 roster 尚未生成（S4.0 交付物）")
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    sources = {s["source_id"] for s in
               json.loads((DATA / "sources.json").read_text(encoding="utf-8"))["sources"]}
    assert roster.get("theater_id") == "coral-sea"
    assert roster.get("roster_version"), "运行 roster 必须带版本号"
    assert roster.get("chain_of_command"), "必须定义指挥链"
    channels = roster["contact_channels"]
    assert channels, "直接沟通名单不能为空"
    for ch in channels:
        assert ch["contact_permission"] in {
            "DIRECT_IN_PERSON", "DIRECT_RADIO", "CHAIN_ONLY",
            "REPORT_ONLY", "NO_INITIATIVE"}
        assert ch["source_ids"], f"{ch['actor_id']} 缺少史料来源"
        assert set(ch["source_ids"]) <= sources, \
            f"{ch['actor_id']} 引用了未登记来源"
        assert ch["evidence_grade"] in {
            "CONFIRMED", "PROBABLE", "UNKNOWN", "CONFLICTED"}
        assert ch["evidence_grade"] != "CONFLICTED", \
            f"{ch['actor_id']} 证据冲突不得进入运行 roster"
        if ch["evidence_grade"] == "UNKNOWN":
            # 未确认姓名必须使用职务名（display_name 不得像人名）
            assert "（职务名）" in ch["display_name"], \
                f"UNKNOWN 人物 {ch['actor_id']} 未使用职务名"
    for link in roster["chain_of_command"]:
        assert link["from_role"] and link["to_role"], "指挥链边必须按角色定义"


def test_confirmed_facts_have_primary_source():
    data = {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in DATA.glob("*.json")}
    src_types = {s["source_id"]: s["source_type"]
                 for s in data["sources"]["sources"]}
    primary_like = {"PRIMARY", "OFFICIAL", "ARCHIVAL"}
    for coll in ("ships", "aircraft", "personnel", "events"):
        for item in data[coll][coll]:
            conf = item.get("confidence")
            if conf != "CONFIRMED":
                continue
            ids = item.get("source_ids") or []
            assert ids, f"{coll}:{item.get('id')} CONFIRMED 无来源"
            assert any(src_types.get(i) in primary_like for i in ids), \
                f"{coll}:{item.get('id')} CONFIRMED 缺一手/官方来源"


def test_estimated_values_flagged():
    data = {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in DATA.glob("*.json")}
    for coll in ("ships", "aircraft"):
        for item in data[coll][coll]:
            if item.get("confidence") == "ESTIMATED":
                assert item.get("estimate_note"), \
                    f"{coll}:{item.get('id')} ESTIMATED 必须显式说明建模口径"
