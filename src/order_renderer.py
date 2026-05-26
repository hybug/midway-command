"""Operation Order renderer — based on CINCPAC Operation Plan 29-42 format.

Generates military-style operation orders in the real US Navy WWII format.
Uses numbered paragraph structure (1, 1.a, 1.a.(1)) with planning language.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class OperationOrder:
    """A military operation order."""
    order_type: str          # RECON, COURSE, STRIKE, DEFENSE
    order_number: str        # TF16-RECON-001
    date: str               # 1942年6月4日
    time: str               # 04:15 (Z+12)
    classification: str     # 机密
    issuer: str             # 参谋长 M.R. Browning
    recipient: str          # 指挥官 R.A. Spruance
    mission: str            # 任务描述
    execution: list[dict]   # 执行细节
    logistics: list[dict]   # 行政后勤
    command: list[dict]     # 指挥与信号


class OrderRenderer:
    """渲染作战命令为格式化文本"""

    def render(self, order: OperationOrder) -> str:
        """渲染完整命令"""
        header = self._render_header(order)
        mission = self._render_mission(order)
        execution = self._render_execution(order)
        logistics = self._render_logistics(order)
        command = self._render_command(order)
        footer = self._render_footer()

        return f"{header}\n{mission}\n{execution}\n{logistics}\n{command}\n{footer}"

    def _render_header(self, order: OperationOrder) -> str:
        """渲染命令头部"""
        return f"""═══════════════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════════════
  编号: {order.order_number:<30} {order.date}
  时间: {order.time:<30} 分类: {order.classification}
  签发: {order.issuer}
  呈报: {order.recipient}
═══════════════════════════════════════════════════════════════"""

    def _render_mission(self, order: OperationOrder) -> str:
        """渲染任务段"""
        return f"""
1. 任务 (MISSION)
{self._indent(order.mission, 2)}"""

    def _render_execution(self, order: OperationOrder) -> str:
        """渲染执行段"""
        lines = ["\n2. 执行 (EXECUTION)\n"]
        for i, item in enumerate(order.execution, 97):
            letter = chr(i)  # a, b, c...
            lines.append(f"  2.{letter}. {item['title']}")
            if 'details' in item:
                for detail in item['details']:
                    lines.append(f"    {detail}")
        return "\n".join(lines)

    def _render_logistics(self, order: OperationOrder) -> str:
        """渲染行政后勤段"""
        lines = ["\n3. 行政后勤 (LOGISTICS)\n"]
        for item in order.logistics:
            lines.append(f"  {item}")
        return "\n".join(lines)

    def _render_command(self, order: OperationOrder) -> str:
        """渲染指挥与信号段"""
        lines = ["\n4. 指挥与信号 (COMMAND & SIGNAL)\n"]
        for item in order.command:
            lines.append(f"  {item}")
        return "\n".join(lines)

    def _render_footer(self) -> str:
        """渲染底部"""
        return """
═══════════════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════════════"""

    def _indent(self, text: str, spaces: int) -> str:
        """缩进文本"""
        indent = " " * spaces
        return "\n".join(indent + line for line in text.split("\n"))


# ── 命令工厂 ──

def create_recon_order(
    aircraft_type: str,
    aircraft_count: int,
    carrier: str,
    sector_start: int,
    sector_end: int,
    range_nm: int,
    altitude_ft: int,
    launch_time: str,
    arrive_sector: str,
    search_complete: str,
    recovery_time: str,
    expected_report: str,
    notes: str = "",
) -> OperationOrder:
    """创建侦察命令"""
    direction_cn = {
        310: "西北", 0: "正北", 45: "东北",
        90: "正东", 135: "东南", 180: "正南",
        225: "西南", 270: "正西"
    }.get(sector_start, "未知")

    return OperationOrder(
        order_type="RECON",
        order_number=f"TF16-RECON-{datetime.now().strftime('%H%M')}",
        date="1942年6月4日",
        time=f"{launch_time} (Z+12)",
        classification="机密",
        issuer="参谋长 M.R. Browning",
        recipient="指挥官 R.A. Spruance",
        mission=f"派出 {aircraft_type} 侦察机搜索{direction_cn}方向，定位日军机动部队。",
        execution=[
            {
                "title": "侦察计划",
                "details": [
                    f"飞机型号: {aircraft_type} Dauntless（侦察型）",
                    f"数量: {aircraft_count} 架",
                    f"来源: {carrier}",
                ]
            },
            {
                "title": "搜索参数",
                "details": [
                    f"扇面: {sector_start}° - {sector_end}°",
                    f"航程: {range_nm} 海里",
                    f"高度: {altitude_ft} 英尺",
                ]
            },
            {
                "title": "时间表",
                "details": [
                    f"起飞: {launch_time}",
                    f"到达搜索区域: {arrive_sector}",
                    f"完成搜索: {search_complete}",
                    f"预计回报: {expected_report}",
                ]
            },
        ],
        logistics=[
            "燃油: 满载",
            "弹药: 无（侦察任务）",
            "通信: TBS 无线电报告",
        ],
        command=[
            f"指挥官: TF16 指挥官",
            f"通信频率: TBS Channel 1",
        ],
    )


def create_course_order(
    current_course: int,
    new_course: int,
    current_speed: int,
    new_speed: int,
    reason: str,
) -> OperationOrder:
    """创建航线命令"""
    return OperationOrder(
        order_type="COURSE",
        order_number=f"TF16-COURSE-{datetime.now().strftime('%H%M')}",
        date="1942年6月4日",
        time=f"{datetime.now().strftime('%H:%M')} (Z+12)",
        classification="机密",
        issuer="参谋长 M.R. Browning",
        recipient="指挥官 R.A. Spruance",
        mission=reason,
        execution=[
            {
                "title": "航向调整",
                "details": [
                    f"当前航向: {current_course}°",
                    f"新航向: {new_course}°",
                    f"调整幅度: {abs(new_course - current_course)}°",
                ]
            },
            {
                "title": "航速调整",
                "details": [
                    f"当前航速: {current_speed} 节",
                    f"新航速: {new_speed} 节",
                ]
            },
            {
                "title": "生效时间",
                "details": ["立即生效"],
            },
        ],
        logistics=[],
        command=["指挥官: TF16 指挥官"],
    )
