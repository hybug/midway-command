"""中途岛指挥官 — 指挥官视角 · 海图桌 + 电报机"""
import logging
import sys
import streamlit as st
import streamlit.components.v1 as components
from src.llm import ChatResult
from src.config import DEV_MODE
from src.initial_state import build_initial_state
from src.agents.browning import BrowningNPC
from src.agents.murray import MurrayNPC
from src.agents.mitscher import MitscherNPC
from src.agents.radio_officer import RadioOfficerNPC
from src.agents.intel_officer import IntelOfficerNPC
from src.npc_config import NPC_REGISTRY
from src.tools import set_course
from src.events import create_midway_events
from src.ap import consume_ap, has_ap, reset_ap, get_ap_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler("/Users/doqinvera/Desktop/hanyu/workspace/midway-command/logs/decision.log", mode="a")])
logger = logging.getLogger("midway")

st.set_page_config(page_title="中途岛指挥官", page_icon="⚓", layout="wide", initial_sidebar_state="collapsed")

# ═══════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&family=Special+Elite&display=swap');

    /* ── 二战海图主题 ── */
    .stApp {
        background: #f5edd6;
        color: #2a2218;
    }

    section[data-testid="stSidebar"] { display: none !important; }
    #MainMenu, footer, header { display: none !important; }
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"] { display: none !important; }

    /* 全局字体 */
    * {
        font-family: 'Special Elite', 'Courier New', monospace !important;
    }

    h1, h2, h3 {
        font-family: 'Special Elite', monospace !important;
        color: #2a2218 !important;
        font-size: 14px !important;
        letter-spacing: 1px;
    }

    /* 纸张纹理 */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(42,34,24,0.02) 3px, rgba(42,34,24,0.02) 4px),
            repeating-linear-gradient(90deg, transparent, transparent 3px, rgba(42,34,24,0.015) 3px, rgba(42,34,24,0.015) 4px);
        pointer-events: none;
        z-index: 9999;
    }

    /* 按钮：复古纸质风格 */
    .stButton button {
        background: #e8dcc8 !important;
        color: #2a2218 !important;
        border: 1px solid #a89878 !important;
        border-radius: 2px;
        box-shadow: 1px 1px 2px rgba(42,34,24,0.2);
        font-family: 'Special Elite', monospace !important;
        font-size: 12px !important;
        letter-spacing: 1px;
        transition: all 0.1s;
    }

    .stButton button:hover {
        background: #d4c8b0 !important;
        border-color: #2a2218 !important;
    }

    .stButton button:active {
        box-shadow: inset 1px 1px 3px rgba(42,34,24,0.3);
        transform: translateY(1px);
    }

    /* 主按钮 */
    .stButton button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: #2a2218 !important;
        color: #f5edd6 !important;
        border-color: #2a2218 !important;
    }

    /* 输入框 */
    .stTextInput input, .stChatInput input {
        background: #e8dcc8 !important;
        color: #2a2218 !important;
        border: 1px solid #a89878 !important;
        border-radius: 2px;
        caret-color: #2a2218;
    }

    .stTextInput input:focus, .stChatInput input:focus {
        border-color: #2a2218 !important;
        box-shadow: 0 0 4px rgba(42,34,24,0.15);
    }

    /* 容器 */
    .block-container {
        padding-top: 0.3rem !important;
        padding-bottom: 0.3rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div { gap: 0.15rem !important; }
    div[data-testid="stHorizontalBlock"] > div { gap: 0.3rem !important; }

    /* 滚动条 */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #e8dcc8; }
    ::-webkit-scrollbar-thumb { background: #a89878; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #8a7e5a; }

    /* Expander 样式 */
    .streamlit-expanderHeader {
        background: #e8dcc8 !important;
        border: 1px solid #a89878 !important;
        color: #2a2218 !important;
    }

    /* 分割线 */
    hr {
        border-color: #a89878 !important;
    }

    /* 警告/成功/错误消息 */
    .stAlert {
        background: #e8dcc8 !important;
        border-radius: 2px;
    }

    /* 对话框标题 */
    [data-testid="stDialog"] {
        background: #f5edd6 !important;
        border: 1px solid #a89878 !important;
    }

    /* 消息淡入动画 */
    @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .msg-in { animation: fadeSlideIn 0.3s ease-out; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 会话状态
# ═══════════════════════════════════════════════════════════
if "game_state" not in st.session_state:
    st.session_state.game_state = build_initial_state()
if "npcs" not in st.session_state:
    st.session_state.npcs = {
        "browning": BrowningNPC(),
        "murray": MurrayNPC(),
        "mitscher": MitscherNPC(),
        "radio_officer": RadioOfficerNPC(),
        "intel_officer": IntelOfficerNPC(),
    }
if "active_npc" not in st.session_state:
    st.session_state.active_npc = "browning"
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "state_snapshot" not in st.session_state:
    st.session_state.state_snapshot = None
if "event_scheduler" not in st.session_state:
    st.session_state.event_scheduler = create_midway_events()
if "event_notifications" not in st.session_state:
    st.session_state.event_notifications = []
if "msg_counter" not in st.session_state:
    st.session_state.msg_counter = 0

state = st.session_state.game_state
npcs = st.session_state.npcs
active_npc_id = st.session_state.active_npc
active_npc = npcs[active_npc_id]
scheduler = st.session_state.event_scheduler
tf = state.task_forces[0]
ap = get_ap_status(state)

# NPC display config: id -> (label, sender_label)
NPC_DISPLAY = {
    "browning": ("参谋长", "布朗宁（BROWNING）· 参谋长"),
    "murray": ("企业号舰长", "默里（MURRAY）· 企业号舰长"),
    "mitscher": ("大黄蜂舰长", "米切尔（MITSCHER）· 大黄蜂舰长"),
    "radio_officer": ("通信官", "通信官 · TBS"),
    "intel_officer": ("情报官", "情报官 · 情报参谋"),
}


def get_state_digest(s):
    tf = s.task_forces[0]
    return (tf.course, tf.speed, tuple(c.cap_strength for c in tf.carriers),
            tuple((ag.status.value, ag.fuel_pct, ag.ammo_pct) for c in tf.carriers for ag in c.air_groups))


def detect_changes(old_digest, new_state):
    if old_digest is None:
        return []
    tf = new_state.task_forces[0]
    new_digest = get_state_digest(new_state)
    changes = []
    if old_digest[0] != new_digest[0]:
        changes.append(f"航向 {old_digest[0]}°→{new_digest[0]}°")
    if old_digest[1] != new_digest[1]:
        changes.append(f"航速 {old_digest[1]}→{new_digest[1]}节")
    for i, (oc, nc) in enumerate(zip(old_digest[2], new_digest[2])):
        if oc != nc:
            changes.append(f"CAP {oc}→{nc}")
    return changes


def render_telegram_msg(msg_id, time_str, sender, sender_role, text, priority="普通"):
    """渲染一条 CRT 终端风格的消息"""
    import html as html_mod
    is_player = "指挥官" in sender
    border_color = "#6b5d4a" if is_player else "#2a2218"
    safe_text = html_mod.escape(text).replace("\n", "<br>")
    return f"""<div class="msg-in" style="background:#e8dcc8;border:1px solid #a89878;border-left:3px solid {border_color};padding:5px 10px;margin:2px 0;"><div style="display:flex;justify-content:space-between;color:#6b5d4a;font-size:10px;letter-spacing:2px;margin-bottom:3px;border-bottom:1px dashed #c4b89a;padding-bottom:2px;text-transform:uppercase;"><span>#{msg_id:03d}</span><span>{time_str}</span><span>{priority}</span></div><div style="color:{border_color};font-size:10px;letter-spacing:2px;margin-bottom:2px;text-transform:uppercase;">{sender}</div><div style="color:#2a2218;font-size:14px;line-height:1.5;">{safe_text}</div></div>"""


# ═══════════════════════════════════════════════════════════
# 会话状态（补充）
# ═══════════════════════════════════════════════════════════
if "drawer_open" not in st.session_state:
    st.session_state.drawer_open = True

drawer_open = st.session_state.drawer_open


# ═══════════════════════════════════════════════════════════
# 顶部 — 电报头部
# ═══════════════════════════════════════════════════════════
drawer_btn_label = "■ 收起通信（COMM OFF）" if drawer_open else "□ 通信（COMM ON）"
st.markdown(f"""
<div style="
    background: #e8dcc8;
    border: 1px solid #a89878;
    border-bottom: 2px solid #a89878;
    padding: 6px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
">
    <div>
        <span style="color: #2a2218; font-family: 'Special Elite', monospace; font-size: 14px; letter-spacing:3px;">
            中途岛指挥官
        </span>
        <span style="color: #6b5d4a; font-size: 12px; margin-left: 16px; letter-spacing:1px;">
            USN · TF-16 · USS ENTERPRISE (CV-6) FLAGSHIP
        </span>
    </div>
    <div style="text-align: right;">
        <span style="color: #6b5d4a; font-size: 12px; letter-spacing:1px;">04 JUN 1942 · Z+12</span>
        <span style="color: #2a2218; font-size: 28px; margin-left: 12px; font-weight:bold;">
            {state.clock.game_time.strftime('%H:%M')}
        </span>
        <span style="color: #6b5d4a; font-size: 12px; margin-left: 12px;">
            AP <span style="color:#2a2218;">{ap['current']}</span>/{ap['max']}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 主布局：海图为主 + 可收起通信抽屉
# ═══════════════════════════════════════════════════════════
if drawer_open:
    col_main, col_drawer = st.columns([2, 1])
else:
    col_main = st.container()

# ─────────────────────────────────────────────────────────
# 主区域：海图 + 战术面板
# ─────────────────────────────────────────────────────────
with col_main:
    # 通信按钮
    if st.button(drawer_btn_label, key="toggle_drawer"):
        st.session_state.drawer_open = not drawer_open
        st.rerun()
    # ═══════════════════════════════════════════════════════
    # 战术仪表盘（4 条紧凑信息条 + 弹窗详情）
    # ═══════════════════════════════════════════════════════
    c1, c2 = tf.carriers[0], tf.carriers[1]
    dmg_map = {0: "OK", 1: "LGT", 2: "MOD", 3: "HVY"}
    dmg_color = {0: "#2a2218", 1: "#6b5d4a", 2: "#8b5a2b", 3: "#8b2500"}

    # ── Dialog 函数 ──
    @st.dialog("态势详情（SITUATION）")
    def _dlg_fleet():
        for carrier in tf.carriers:
            short = carrier.name.split("(")[0].strip()
            st.markdown(f"**{short}** — {carrier.position.lat:.1f}°N {abs(carrier.position.lon):.1f}°W · "
                        f"航向 {carrier.course}° · 航速 {carrier.speed} kn · "
                        f"损伤: {dmg_map.get(carrier.damage_level, '?')}")

    @st.dialog("机库·甲板详情")
    def _dlg_deck():
        for carrier in tf.carriers:
            short = carrier.name.split("(")[0].strip()
            st.markdown(f"**{short}**")
            for ag in carrier.air_groups:
                t = {"fighter": "VF", "dive": "VB", "torpedo": "VT"}.get(ag.type.value, "?")
                status_cn = {"ready": "就绪", "loading": "装弹中", "launched": "已起飞",
                             "in_flight": "飞行中", "returning": "返航中", "landing": "着舰中"
                            }.get(ag.status.value, ag.status.value)
                st.markdown(f"  {t} {ag.squadron_name or ''} × {ag.count} · {status_cn}")

    @st.dialog("舰载机详情")
    def _dlg_aircraft():
        for carrier in tf.carriers:
            short = carrier.name.split("(")[0].strip()
            st.markdown(f"**{short}**")
            for ag in carrier.air_groups:
                t = {"fighter": "VF", "dive": "VB", "torpedo": "VT"}.get(ag.type.value, "?")
                st.markdown(f"  {t} {ag.squadron_name or ''} × {ag.count} · "
                            f"燃油 {ag.fuel_pct}% · 弹药 {ag.ammo_pct}% · {ag.status.value}")

    @st.dialog("飞行任务详情")
    def _dlg_missions():
        cap_total = sum(c.cap_strength for c in tf.carriers)
        st.markdown(f"**CAP**: 共 {cap_total} 架")
        for carrier in tf.carriers:
            short = "ENT" if "Enterprise" in carrier.name else "HOR"
            st.markdown(f"  {short}: {carrier.cap_strength} 架")
        active_scouts = [s for s in state.active_scouts if s.status == "in_flight"]
        if active_scouts:
            st.markdown("**在途侦察:**")
            for s in active_scouts:
                elapsed = (state.clock.game_time - s.launched_at).total_seconds() / 60
                remaining = max(0, s.eta_minutes - elapsed)
                st.markdown(f"  {s.id}: {s.aircraft_count} 架 · {s.direction} · ETA {int(remaining)} 分钟")
        else:
            st.markdown("**在途侦察:** 无")
        if state.pending_reports:
            st.markdown("**在途报告:**")
            for pr in state.pending_reports:
                elapsed = (state.clock.game_time - pr.detected_at).total_seconds() / 60
                total_delay = (pr.arrive_at - pr.detected_at).total_seconds() / 60
                remaining = max(0, total_delay - elapsed)
                st.markdown(f"  {pr.scout_id}: {int(remaining)} 分钟后到达")
        if state.known_enemy:
            st.markdown("**已知敌情:**")
            for e in state.known_enemy:
                st.markdown(f"  {e.description}（置信度: {e.confidence}, 来源: {e.source}）")

    # ── 单行仪表带 ──
    cap_total = sum(c.cap_strength for c in tf.carriers)
    active_scouts = [s for s in state.active_scouts if s.status == "in_flight"]
    scout_count = len(active_scouts)
    scout_txt = ""
    if active_scouts:
        s = active_scouts[0]
        elapsed = (state.clock.game_time - s.launched_at).total_seconds() / 60
        remaining = max(0, s.eta_minutes - elapsed)
        d_cn = {"northwest":"西北","north":"正北","northeast":"东北","east":"正东",
                "southeast":"东南","south":"正南","southwest":"西南","west":"正西"
               }.get(s.direction, s.direction)
        scout_txt = f'{d_cn} ETA:{int(remaining)}分'
    pr_count = len(state.pending_reports)
    pr_txt = ""
    if state.pending_reports:
        pr = state.pending_reports[0]
        elapsed = (state.clock.game_time - pr.detected_at).total_seconds() / 60
        total_delay = (pr.arrive_at - pr.detected_at).total_seconds() / 60
        remaining = max(0, total_delay - elapsed)
        pr_txt = f'{int(remaining)}分'
    enemy_text = "暂无" if not state.known_enemy else state.known_enemy[0].description[:10]
    deck_parts = []
    for carrier in tf.carriers:
        short = "企业" if "Enterprise" in carrier.name else "大黄蜂"
        total = sum(ag.count for ag in carrier.air_groups)
        ready = sum(ag.count for ag in carrier.air_groups if ag.status.value == "ready")
        airborne = sum(ag.count for ag in carrier.air_groups if ag.status.value in ("launched", "in_flight", "returning"))
        deck_parts.append(f'{short} <span style="color:#2a2218;">{total}</span>/{ready}备/{airborne}飞')

    st.markdown(f"""
    <div style="background:#e8dcc8; border:1px solid #a89878; border-top:2px solid #a89878; padding:4px 14px; display:flex; justify-content:space-between; align-items:center; gap:4px; flex-wrap:nowrap; overflow:hidden;">
        <span style="color:#6b5d4a; font-size:11px;">航向<span style="color:#2a2218; font-size:13px; margin-left:2px;">{tf.course:03d}°</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">航速<span style="color:#2a2218; font-size:13px; margin-left:2px;">{tf.speed}</span>节</span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">位置<span style="color:#2a2218; font-size:11px; margin-left:2px;">{c1.position.lat:.1f}°N {abs(c1.position.lon):.1f}°W</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">损伤<span style="color:{dmg_color.get(c1.damage_level,'#2a2218')}; font-size:11px; margin-left:2px;">企业:{dmg_map.get(c1.damage_level,'?')}</span> <span style="color:{dmg_color.get(c2.damage_level,'#2a2218')};">大黄蜂:{dmg_map.get(c2.damage_level,'?')}</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">甲板 <span style="font-size:11px;">{' '.join(deck_parts)}</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">巡逻<span style="color:#2a2218; font-size:12px; margin-left:2px;">{cap_total}</span>架</span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">侦察<span style="color:#2a2218; font-size:11px; margin-left:2px;">{scout_count}</span> <span style="color:#6b5d4a; font-size:10px;">{scout_txt}</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">报告<span style="color:#2a2218; font-size:11px; margin-left:2px;">{pr_count}</span> <span style="color:#6b5d4a; font-size:10px;">{pr_txt}</span></span>
        <span style="color:#c4b89a;">│</span>
        <span style="color:#6b5d4a; font-size:11px;">敌情<span style="color:#8b2500; font-size:11px; margin-left:2px;">{enemy_text}</span></span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("详细态势", key="btn_info", use_container_width=False):
        _dlg_fleet()

    # 六边形地图（Canvas 渲染）
    from src.render.html_map import render_html_map
    from src.render.coordinate import world_to_hex
    fleet_lat = state.task_forces[0].carriers[0].position.lat
    fleet_lon = state.task_forces[0].carriers[0].position.lon
    fleet_q, fleet_r = world_to_hex(fleet_lat, fleet_lon)
    map_html = render_html_map(state, center_q=fleet_q, center_r=fleet_r, radius=8, course=tf.course)
    st.markdown('<div style="color:#6b5d4a; font-size:10px; letter-spacing:3px; margin-bottom:4px;">海图（CHART）</div>',
                unsafe_allow_html=True)
    components.html(map_html, height=600)


    # 操作按钮（一行）
    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("推进 15 分钟（ADVANCE）", use_container_width=True):
            notifications = scheduler.tick(state, 15)
            reset_ap(state)
            st.session_state.event_notifications = notifications
            st.rerun()
    with bc2:
        if st.button("态势简报（REPORT）", use_container_width=True):
            st.session_state._briefing_requested = True
            st.rerun()


# ─────────────────────────────────────────────────────────
# 通信抽屉（仅在 drawer_open 时显示）
# ─────────────────────────────────────────────────────────
if drawer_open:
  with col_drawer:
    # 通知
    if st.session_state.event_notifications:
        for n in st.session_state.event_notifications:
            st.markdown(f"""
            <div style="background:#e8dcc8; border:1px solid #8b2500; border-left:3px solid #8b2500;
                        padding:5px 10px; margin-bottom:3px;">
                <span style="color:#8b2500; font-size:13px;">! {n}</span>
            </div>
            """, unsafe_allow_html=True)
        st.session_state.event_notifications = []

    if st.session_state.state_snapshot is not None:
        changes = detect_changes(st.session_state.state_snapshot, state)
        if changes:
            npc_name = NPC_DISPLAY[active_npc_id][0]
            st.markdown(f"""
            <div style="background:#e8dcc8; border:1px solid #2a2218; border-left:3px solid #2a2218;
                        padding:5px 10px; margin-bottom:3px;">
                <span style="color:#2a2218; font-size:13px;">已执行（EXEC）{npc_name}: {', '.join(changes)}</span>
            </div>
            """, unsafe_allow_html=True)
            st.session_state.state_snapshot = None

    # NPC 频道选择
    npc_tabs = st.columns(len(NPC_DISPLAY))
    for col, (npc_id, (label, _)) in zip(npc_tabs, NPC_DISPLAY.items()):
        with col:
            is_active = npc_id == active_npc_id
            btn_label = f"▶ {label}" if is_active else label
            if st.button(btn_label, key=f"npc_{npc_id}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.active_npc = npc_id
                st.rerun()

    # 通信记录（当前 NPC 的对话）
    chat_html = ""
    for i, msg in enumerate(active_npc.messages[-12:]):
        role = msg["role"]
        msg_id = i + 1
        time_str = state.clock.game_time.strftime('%H:%M')
        if role == "user":
            chat_html += render_telegram_msg(msg_id, time_str, "指挥官（SPRUANCE）", "指挥官", msg['content'])
        elif role == "assistant":
            text_lower = msg['content'].lower()
            priority = "紧急" if any(w in text_lower for w in ["立即", "马上", "快", "紧急", "刻不容缓"]) else "普通"
            _, sender_label = NPC_DISPLAY[active_npc_id]
            chat_html += render_telegram_msg(msg_id, time_str, sender_label, active_npc.role, msg['content'], priority)

    st.markdown(f"""
    <div style="
        background: #f5edd6;
        border: 1px solid #a89878;
        padding: 6px 10px;
    ">
        <div style="color:#6b5d4a; font-size:10px; letter-spacing:3px; margin-bottom:4px; border-bottom:1px dashed #c4b89a; padding-bottom:3px;">
            通信记录（COMM）· {NPC_DISPLAY[active_npc_id][0]}
        </div>
        <div style="height:360px; overflow-y:auto; padding-right:4px;">
            {chat_html if chat_html else '<div style="color:#a89878; font-style:italic; text-align:center; padding:60px; letter-spacing:2px;">等待指令（AWAITING ORDERS）...</div>'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 待确认方案显示 — 纸质文档风格
    if state.pending_suggestions:
        for i, sug in enumerate(state.pending_suggestions):
            details = sug.details
            action_type = sug.action_type

            if action_type == "launch_scout":
                from src.recon_plan import ReconPlan
                plan = ReconPlan(
                    aircraft_count=details.get("aircraft_count", 4),
                    source_carrier=details.get("source_carrier", "Enterprise"),
                    sector_start=details.get("sector_start", 280),
                    sector_end=details.get("sector_end", 340),
                    range_nm=details.get("range_nm", 200),
                    altitude_ft=details.get("altitude_ft", 1500),
                )
                plan.calculate_timeline(state.clock.game_time)
                dir_cn = {"northwest":"西北","north":"正北","northeast":"东北","east":"正东",
                          "southeast":"东南","south":"正南","southwest":"西南","west":"正西"
                         }.get(details.get("direction",""), details.get("direction",""))
                time_str = state.clock.game_time.strftime('%H:%M')
                st.markdown(f"""
<div style="background:linear-gradient(135deg,#f5f0e1,#ede5d0); border:1px solid #b8a88a; box-shadow:4px 4px 12px rgba(0,0,0,0.4); padding:0; margin:10px 0 6px; position:relative;">
  <!-- 顶部印章 -->
  <div style="background:#2c2418; padding:6px 16px; display:flex; justify-content:space-between; align-items:center;">
    <span style="color:#c4a265; font-size:11px; letter-spacing:3px; font-weight:bold;">美 国 海 军 · 作 战 命 令</span>
    <span style="color:#8a7e6a; font-size:11px;">机密 · TOP SECRET</span>
  </div>
  <!-- 命令编号栏 -->
  <div style="padding:8px 20px 4px; display:flex; justify-content:space-between; border-bottom:1px dashed #c4b89a;">
    <span style="color:#4a3f2f; font-size:12px;">编号: TF16-RECON-{time_str.replace(':','')}</span>
    <span style="color:#4a3f2f; font-size:12px;">1942年6月4日 · {time_str} (Z+12)</span>
  </div>
  <!-- 正文 -->
  <div style="padding:14px 20px;">
    <!-- 签发信息 -->
    <div style="display:flex; gap:40px; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #d4c8a8;">
      <div><span style="color:#7a6e5a; font-size:11px;">签发</span><br><span style="color:#2c2418; font-size:14px; font-weight:bold;">参谋长 M.R. Browning</span></div>
      <div><span style="color:#7a6e5a; font-size:11px;">呈报</span><br><span style="color:#2c2418; font-size:14px;">指挥官 R.A. Spruance</span></div>
    </div>
    <!-- 任务 -->
    <div style="margin-bottom:12px;">
      <div style="color:#7a6e5a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">1. 任务 MISSION</div>
      <div style="color:#2c2418; font-size:15px; line-height:1.6;">派出 {plan.aircraft_type} 侦察机搜索<strong>{dir_cn}</strong>方向，定位日军机动部队。</div>
    </div>
    <!-- 执行 -->
    <div style="margin-bottom:12px;">
      <div style="color:#7a6e5a; font-size:10px; letter-spacing:2px; margin-bottom:6px;">2. 执行 EXECUTION</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
        <div style="background:rgba(255,255,255,0.5); padding:8px 10px; border-left:3px solid #8a7e5a;">
          <div style="color:#7a6e5a; font-size:10px; letter-spacing:1px;">2.a 侦察编队</div>
          <div style="color:#2c2418; font-size:14px; line-height:1.6;">
            {plan.aircraft_type} Dauntless × <strong>{plan.aircraft_count}</strong><br>
            来源: {plan.source_carrier}
          </div>
        </div>
        <div style="background:rgba(255,255,255,0.5); padding:8px 10px; border-left:3px solid #8a7e5a;">
          <div style="color:#7a6e5a; font-size:10px; letter-spacing:1px;">2.b 搜索参数</div>
          <div style="color:#2c2418; font-size:14px; line-height:1.6;">
            扇面: <strong>{plan.sector_start}° – {plan.sector_end}°</strong><br>
            航程: {plan.range_nm} 海里 · 高度: {plan.altitude_ft} ft
          </div>
        </div>
      </div>
    </div>
    <!-- 时间表 -->
    <div style="margin-bottom:14px;">
      <div style="color:#7a6e5a; font-size:10px; letter-spacing:2px; margin-bottom:6px;">2.c 时间表 TIMELINE</div>
      <div style="display:flex; gap:0; background:rgba(255,255,255,0.4); border:1px solid #d4c8a8;">
        <div style="flex:1; padding:6px 10px; border-right:1px solid #d4c8a8; text-align:center;">
          <div style="color:#7a6e5a; font-size:9px;">起飞</div>
          <div style="color:#2c2418; font-size:15px; font-weight:bold;">{plan.launch_time}</div>
        </div>
        <div style="flex:1; padding:6px 10px; border-right:1px solid #d4c8a8; text-align:center;">
          <div style="color:#7a6e5a; font-size:9px;">进入扇面</div>
          <div style="color:#2c2418; font-size:15px; font-weight:bold;">{plan.arrive_sector}</div>
        </div>
        <div style="flex:1; padding:6px 10px; border-right:1px solid #d4c8a8; text-align:center;">
          <div style="color:#7a6e5a; font-size:9px;">搜索完成</div>
          <div style="color:#2c2418; font-size:15px; font-weight:bold;">{plan.search_complete}</div>
        </div>
        <div style="flex:1; padding:6px 10px; text-align:center;">
          <div style="color:#7a6e5a; font-size:9px;">预计回收</div>
          <div style="color:#2c2418; font-size:15px; font-weight:bold;">{plan.recovery_time}</div>
        </div>
      </div>
    </div>
    <!-- 行政后勤 -->
    <div style="margin-bottom:12px;">
      <div style="color:#7a6e5a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">3. 行政后勤 LOGISTICS</div>
      <div style="color:#4a3f2f; font-size:13px; line-height:1.5;">燃油: 满载 · 弹药: 无（侦察任务）· 通信: TBS 无线电报告</div>
    </div>
    <!-- 签名栏 -->
    <div style="border-top:2px solid #2c2418; padding-top:10px; margin-top:6px; display:flex; justify-content:space-between; align-items:flex-end;">
      <div>
        <div style="color:#7a6e5a; font-size:10px;">指挥官签署</div>
        <div style="width:180px; border-bottom:1px solid #2c2418; height:30px;"></div>
        <div style="color:#7a6e5a; font-size:10px; margin-top:2px;">R.A. Spruance, 少将</div>
      </div>
      <div style="text-align:right;">
        <div style="color:#7a6e5a; font-size:10px;">签发</div>
        <div style="color:#2c2418; font-size:13px; font-style:italic;">M.R. Browning</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            elif action_type == "set_course":
                from src.order_renderer import create_course_order
                order = create_course_order(
                    current_course=tf.course,
                    new_course=details.get("course", tf.course),
                    current_speed=tf.speed,
                    new_speed=details.get("speed", tf.speed),
                    reason=f"按{sug.npc}建议调整航向",
                )
                time_str = state.clock.game_time.strftime('%H:%M')
                st.markdown(f"""
<div style="background:linear-gradient(135deg,#f5f0e1,#ede5d0); border:1px solid #b8a88a; box-shadow:4px 4px 12px rgba(0,0,0,0.4); padding:0; margin:10px 0 6px;">
  <div style="background:#2c2418; padding:6px 16px; display:flex; justify-content:space-between; align-items:center;">
    <span style="color:#c4a265; font-size:11px; letter-spacing:3px; font-weight:bold;">美 国 海 军 · 航 向 命 令</span>
    <span style="color:#8a7e6a; font-size:11px;">机密</span>
  </div>
  <div style="padding:8px 20px 4px; display:flex; justify-content:space-between; border-bottom:1px dashed #c4b89a;">
    <span style="color:#4a3f2f; font-size:12px;">编号: TF16-COURSE-{time_str.replace(':','')}</span>
    <span style="color:#4a3f2f; font-size:12px;">1942年6月4日 · {time_str}</span>
  </div>
  <div style="padding:14px 20px;">
    <div style="display:flex; gap:40px; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #d4c8a8;">
      <div><span style="color:#7a6e5a; font-size:11px;">签发</span><br><span style="color:#2c2418; font-size:14px; font-weight:bold;">参谋长 M.R. Browning</span></div>
      <div><span style="color:#7a6e5a; font-size:11px;">呈报</span><br><span style="color:#2c2418; font-size:14px;">指挥官 R.A. Spruance</span></div>
    </div>
    <div style="margin-bottom:10px;">
      <div style="color:#7a6e5a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">1. 任务</div>
      <div style="color:#2c2418; font-size:15px;">{order.mission}</div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px;">
      <div style="background:rgba(255,255,255,0.5); padding:8px 10px; border-left:3px solid #8a7e5a;">
        <div style="color:#7a6e5a; font-size:10px;">航向调整</div>
        <div style="color:#2c2418; font-size:15px;">{tf.course}° → <strong>{details.get('course','?')}°</strong></div>
      </div>
      <div style="background:rgba(255,255,255,0.5); padding:8px 10px; border-left:3px solid #8a7e5a;">
        <div style="color:#7a6e5a; font-size:10px;">航速</div>
        <div style="color:#2c2418; font-size:15px;">{tf.speed} 节 → <strong>{details.get('speed', tf.speed)} 节</strong></div>
      </div>
    </div>
    <div style="border-top:2px solid #2c2418; padding-top:10px; display:flex; justify-content:space-between; align-items:flex-end;">
      <div>
        <div style="color:#7a6e5a; font-size:10px;">指挥官签署</div>
        <div style="width:180px; border-bottom:1px solid #2c2418; height:30px;"></div>
        <div style="color:#7a6e5a; font-size:10px; margin-top:2px;">R.A. Spruance, 少将</div>
      </div>
      <div style="text-align:right;">
        <div style="color:#7a6e5a; font-size:10px;">签发</div>
        <div style="color:#2c2418; font-size:13px; font-style:italic;">M.R. Browning</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            else:
                detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
                st.markdown(f"""
                <div style="background:#e8dcc8; border:1px solid #a89878; padding:10px; margin:6px 0; border-radius:2px;">
                    <div style="color:#6b5d4a; font-size:11px; letter-spacing:3px; margin-bottom:6px;">PENDING ORDER</div>
                    <div style="color:#2a2218; font-size:13px;">
                        {sug.npc}: {action_type}<br>
                        <span style="color:#6b5d4a;">{detail_str}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("批准执行", key=f"confirm_{i}", use_container_width=True):
                    if action_type == "launch_scout":
                        from src.tools import handle_execute_action
                        result = handle_execute_action(state, "launch_scout", details)
                        state.pending_suggestions.remove(sug)
                        st.success(f"✅ {result}")
                        st.rerun()
                    elif action_type == "set_course":
                        from src.tools import handle_execute_action
                        result = handle_execute_action(state, "set_course", details)
                        state.pending_suggestions.remove(sug)
                        st.success(f"✅ {result}")
                        st.rerun()
            with col2:
                if st.button("驳回修改", key=f"reject_{i}", use_container_width=True):
                    state.pending_suggestions.remove(sug)
                    st.info("方案已驳回")
                    st.rerun()

    # 输入框
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    user_input = st.chat_input("输入指令...", key="chat_input_main")

    if getattr(st.session_state, '_briefing_requested', False):
        st.session_state._briefing_requested = False
        user_input = "报告当前态势。"

    if user_input:
        if not has_ap(state):
            st.error("通信带宽已满，请推进时间。")
            st.stop()

        consume_ap(state, "message")
        st.session_state.msg_counter += 1
        logger.info(f"[PLAYER_INPUT:{active_npc_id}] {user_input}")

        npc_label = NPC_DISPLAY[active_npc_id][0]
        with st.spinner(f"接通中（CONNECTING）{npc_label}..."):
            try:
                pre_digest = get_state_digest(state)
                st.session_state.state_snapshot = pre_digest

                def wrap_handler(handler):
                    def wrapped(**kwargs):
                        return handler(state, **kwargs)
                    return wrapped

                response = active_npc.chat(
                    player_input=user_input, state=state,
                    tools=active_npc.tools,
                    tool_handlers={n: wrap_handler(h) for n, h in active_npc.tool_handlers.items()},
                )
                st.session_state.last_result = response
                st.rerun()
            except Exception as e:
                logger.error(f"[ERROR] {e}", exc_info=True)
                st.error(f"通信错误：{e}")

    # Handle recon confirmation/rejection
    if getattr(st.session_state, '_recon_confirmed', False):
        st.session_state._recon_confirmed = False
        st.success("✅ 侦察方案已确认执行")

    if getattr(st.session_state, '_recon_rejected', False):
        st.session_state._recon_rejected = False
        st.info("❌ 侦察方案已拒绝")
