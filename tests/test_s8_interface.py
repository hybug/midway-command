"""S8.0 信息架构守卫（五工作台/三层结构/通知分级/数据契约对照）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "design" / "S8_INTERFACE.md"


def test_interface_spec_defines_five_workbenches():
    text = SPEC.read_text()
    for wb in ("CHART", "COMMS", "INTEL", "STAFF", "LOG"):
        assert wb in text, f"S8 规格缺少工作台 {wb}"
    assert "一级导航=五工作台" in text


def test_interface_spec_defers_to_commander_desk_layering():
    text = SPEC.read_text()
    assert "COMMANDER DESK" in text
    assert "不推进时间" in text                      # 案卷台不推进时间
    assert "ISSUE ORDER" in text                     # 全局唯一正式命令入口


def test_interface_spec_notification_taxonomy():
    text = SPEC.read_text()
    for level in ("INFO", "ROUTINE", "URGENT", "FLASH", "STAFF_VISIT", "CONFLICT"):
        assert level in text, f"通知分级缺少 {level}"
    assert "只有 FLASH 与 STAFF_VISIT 主动打断" in text


def test_interface_spec_data_contract_whitelist():
    text = SPEC.read_text()
    # S3 契约
    for token in ("confidence_band", "recommendation", "change_my_mind"):
        assert token in text
    # S4 只做前端契约与适配器（不实现引擎）
    assert "s4Adapter" in text and "StaffVisitEvent" in text
    # 权限红线
    assert "actual_enemy" in text and "不进默认海图" in text.replace(
        "未批准 PlotProposal 不进默认海图", "不进默认海图")


def test_interface_spec_whitelist_endpoint_mapping():
    text = SPEC.read_text()
    for ep in ("/intel/inbox", "/intel/briefs", "/intel/plots",
               "/intel/evidence", "/staff/roster", "/judgment/tasks",
               "/log/timeline"):
        assert ep in text, f"数据源对照缺少 {ep}"
