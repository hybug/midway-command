"""中途岛指挥官 — 指挥官视角 · 海图桌 + 电报机"""
import logging
import sys
import streamlit as st
from src.llm import ChatResult
from src.config import DEV_MODE
from src.initial_state import build_initial_state
from src.agents.browning import BrowningNPC
from src.tools import set_course
from src.events import create_midway_events
from src.ap import consume_ap, has_ap, reset_ap, get_ap_status
from src.render.hex_grid import HexGrid

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
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap');

    .stApp {
        background: #1a1612;
        color: #d4c5a9;
    }

    section[data-testid="stSidebar"] { display: none !important; }
    #MainMenu, footer, header { display: none !important; }
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"] { display: none !important; }

    h1, h2, h3 {
        font-family: 'Press Start 2P', monospace !important;
        color: #c4a265 !important;
        text-shadow: 2px 2px 0 #000;
        font-size: 12px !important;
    }

    * {
        font-family: 'VT323', 'Courier New', monospace !important;
        font-size: 16px !important;
    }

    .stButton button {
        background: #2a2520 !important;
        color: #c4a265 !important;
        border: 2px solid #c4a265 !important;
        box-shadow: 3px 3px 0 #000;
        font-family: 'Press Start 2P', monospace !important;
        font-size: 10px !important;
    }

    .stButton button:hover {
        background: #c4a265 !important;
        color: #1a1612 !important;
        box-shadow: 1px 1px 0 #000;
        transform: translate(2px, 2px);
    }

    .stButton button:active {
        box-shadow: 0 0 0 #000;
        transform: translate(3px, 3px);
    }

    .stTextInput input, .stChatInput input {
        background: #2a2520 !important;
        color: #d4c5a9 !important;
        border: 2px solid #5a5040 !important;
    }

    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div { gap: 0.2rem !important; }
    div[data-testid="stHorizontalBlock"] > div { gap: 0.4rem !important; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #1a1612; }
    ::-webkit-scrollbar-thumb { background: #5a5040; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 会话状态
# ═══════════════════════════════════════════════════════════
if "game_state" not in st.session_state:
    st.session_state.game_state = build_initial_state()
if "browning" not in st.session_state:
    st.session_state.browning = BrowningNPC()
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
browning = st.session_state.browning
scheduler = st.session_state.event_scheduler
tf = state.task_forces[0]
ap = get_ap_status(state)


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
    """渲染一条电报纸格式的消息"""
    import html as html_mod
    border_color = "#8a7e6a" if "指挥官" in sender else "#c4a265"
    safe_text = html_mod.escape(text).replace("\n", "<br>")
    return f"""<div style="background:#22201a;border:1px solid #3a3530;border-left:3px solid {border_color};padding:6px 12px;margin:3px 0;"><div style="display:flex;justify-content:space-between;color:#8a7e6a;font-size:11px;letter-spacing:1px;margin-bottom:4px;border-bottom:1px dashed #3a3530;padding-bottom:3px;"><span>编号:{msg_id:03d}</span><span>{time_str}</span><span>优先:{priority}</span></div><div style="color:{border_color};font-size:11px;letter-spacing:1px;margin-bottom:3px;">发自：{sender}</div><div style="color:#d4c5a9;font-size:15px;line-height:1.5;">{safe_text}</div></div>"""


# ═══════════════════════════════════════════════════════════
# 顶部 — 电报头部
# ═══════════════════════════════════════════════════════════
st.markdown(f"""
<div style="
    background: #2a2520;
    border: 2px solid #5a5040;
    border-bottom: 3px double #5a5040;
    padding: 8px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
">
    <div>
        <span style="color: #c4a265; font-family: 'Press Start 2P', monospace; font-size: 13px; text-shadow: 2px 2px 0 #000;">
            ■ 中途岛指挥官 ■
        </span>
        <span style="color: #8a7e6a; font-size: 13px; margin-left: 16px;">
            美国海军 · 第16特混舰队（TF-16）· 企业号（CV-6）旗舰
        </span>
    </div>
    <div style="text-align: right;">
        <span style="color: #8a7e6a; font-size: 13px;">1942年6月4日 · 时区+12</span>
        <span style="color: #c4a265; font-size: 26px; margin-left: 12px; text-shadow: 0 0 10px rgba(196,162,101,0.5);">
            {state.clock.game_time.strftime('%H:%M')}
        </span>
        <span style="color: #8a7e6a; font-size: 13px; margin-left: 12px;">
            行动点:<span style="color:#c4a265;">{ap['current']}</span>/{ap['max']}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 主布局：左栏海图桌 + 右栏电报机
# ═══════════════════════════════════════════════════════════
col_left, col_right = st.columns([1, 2])

# ─────────────────────────────────────────────────────────
# 左栏：海图桌
# ─────────────────────────────────────────────────────────
with col_left:
    # 航向航速
    st.markdown(f"""
    <div style="background:#22201a; border:1px solid #3a3530; padding:8px 12px; margin-bottom:4px;">
        <div style="color:#8a7e6a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">航向与航速</div>
        <div style="display:flex; justify-content:space-between; align-items:baseline;">
            <div>
                <span style="color:#8a7e6a;">HDG</span>
                <span style="color:#c4a265; font-size:22px; margin-left:6px;">{tf.course:03d}°</span>
            </div>
            <div>
                <span style="color:#8a7e6a;">SPD</span>
                <span style="color:#c4a265; font-size:22px; margin-left:6px;">{tf.speed}</span>
                <span style="color:#8a7e6a; font-size:12px;">节</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 航空队状态
    for carrier in tf.carriers:
        short = carrier.name.split("(")[0].strip()
        lines = []
        for ag in carrier.air_groups:
            dot = "●" if ag.status.value == "ready" else "○"
            t = {"fighter": "VF", "dive": "VB", "torpedo": "VT"}.get(ag.type.value, "?")
            lines.append(f'<span style="color:#8a7e6a;">{dot}</span> <span style="color:#8a7e6a;">{t}</span> <span style="color:#d4c5a9;">{ag.count}</span> <span style="color:#8a7e6a;">F{ag.fuel_pct}% A{ag.ammo_pct}%</span>')

        st.markdown(f"""
        <div style="background:#22201a; border:1px solid #3a3530; padding:8px 12px; margin-bottom:4px;">
            <div style="color:#8a7e6a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">{short} · CAP:{carrier.cap_strength}</div>
            <div style="font-size:13px; line-height:1.6;">
                {'<br>'.join(lines)}
            </div>
            <div style="color:#8a7e6a; font-size:11px; margin-top:4px; padding-top:4px; border-top:1px dashed #3a3530;">
                位置 {carrier.position.lat:.1f}°N {abs(carrier.position.lon):.1f}°W
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 敌情
    enemy_text = "暂无确认接触"
    if state.known_enemy:
        enemy_text = state.known_enemy[0].description

    st.markdown(f"""
    <div style="background:#22201a; border:1px solid #3a3530; padding:8px 12px; margin-bottom:4px;">
        <div style="color:#8a7e6a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">已知敌情</div>
        <div style="color:#d4c5a9; font-size:13px;">{enemy_text}</div>
    </div>
    """, unsafe_allow_html=True)

    # 六边形地图
    grid = HexGrid()
    # Center on fleet position
    from src.render.coordinate import world_to_hex
    fleet_lat = state.task_forces[0].carriers[0].position.lat
    fleet_lon = state.task_forces[0].carriers[0].position.lon
    fleet_q, fleet_r = world_to_hex(fleet_lat, fleet_lon)
    map_ascii = grid.render_for_player(state, center_q=fleet_q, center_r=fleet_r, radius=8)
    st.markdown(f"""
    <div style="background:#22201a; border:1px solid #3a3530; padding:8px 12px; margin-bottom:4px;">
        <div style="color:#8a7e6a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">海图</div>
        <pre style="color:#d4c5a9; font-size:11px; line-height:1.2; margin:0; white-space:pre;">{map_ascii}</pre>
    </div>
    """, unsafe_allow_html=True)

    # 侦察
    scout_text = "无在途侦察"
    active_scouts = [s for s in state.active_scouts if s.status == "in_flight"]
    if active_scouts:
        s = active_scouts[0]
        elapsed = (state.clock.game_time - s.launched_at).total_seconds() / 60
        remaining = max(0, s.eta_minutes - elapsed)
        d_cn = {"northwest":"西北","north":"正北","northeast":"东北","east":"正东",
                "southeast":"东南","south":"正南","southwest":"西南","west":"正西"}.get(s.direction, s.direction)
        scout_text = f"{s.id} PBY×{s.aircraft_count} {d_cn}扇面 ETA:{int(remaining)}分"

    st.markdown(f"""
    <div style="background:#22201a; border:1px solid #3a3530; padding:8px 12px; margin-bottom:4px;">
        <div style="color:#8a7e6a; font-size:10px; letter-spacing:2px; margin-bottom:4px;">侦察状态</div>
        <div style="color:#d4c5a9; font-size:13px;">{scout_text}</div>
    </div>
    """, unsafe_allow_html=True)

    # 报告传输中
    if state.pending_reports:
        pending_text = ""
        for pr in state.pending_reports:
            elapsed = (state.clock.game_time - pr.detected_at).total_seconds() / 60
            total_delay = (pr.arrive_at - pr.detected_at).total_seconds() / 60
            remaining = max(0, total_delay - elapsed)
            pending_text += f"{pr.scout_id}: {int(remaining)}分后到达<br>"
        st.markdown(f"""
        <div style="background:#2a2520; border:1px solid #c4a265; padding:8px 12px; margin-bottom:4px;">
            <div style="color:#c4a265; font-size:10px; letter-spacing:2px; margin-bottom:4px;">📡 报告传输中</div>
            <div style="color:#d4c5a9; font-size:13px;">{pending_text}</div>
        </div>
        """, unsafe_allow_html=True)

    # 操作按钮
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("⏳ 推进 15 分钟", use_container_width=True):
        notifications = scheduler.tick(state, 15)
        reset_ap(state)
        st.session_state.event_notifications = notifications
        st.rerun()

    if st.button("📋 态势简报", use_container_width=True):
        st.session_state._briefing_requested = True
        st.rerun()


# ─────────────────────────────────────────────────────────
# 右栏：电报机
# ─────────────────────────────────────────────────────────
with col_right:
    # 通知
    if st.session_state.event_notifications:
        for n in st.session_state.event_notifications:
            st.markdown(f"""
            <div style="background:#2a2520; border:2px solid #c4a265; border-left:4px solid #c4a265;
                        padding:6px 12px; margin-bottom:4px;">
                <span style="color:#c4a265; font-size:14px;">⚡ {n}</span>
            </div>
            """, unsafe_allow_html=True)
        st.session_state.event_notifications = []

    if st.session_state.state_snapshot is not None:
        changes = detect_changes(st.session_state.state_snapshot, state)
        if changes:
            st.markdown(f"""
            <div style="background:#2a2520; border:2px solid #7ab648; border-left:4px solid #7ab648;
                        padding:6px 12px; margin-bottom:4px;">
                <span style="color:#7ab648; font-size:14px;">⚡ 布朗宁已执行：{', '.join(changes)}</span>
            </div>
            """, unsafe_allow_html=True)
            st.session_state.state_snapshot = None

    # 通信记录
    chat_html = ""
    for i, msg in enumerate(browning.messages[-12:]):
        role = msg["role"]
        msg_id = i + 1
        time_str = state.clock.game_time.strftime('%H:%M')
        if role == "user":
            chat_html += render_telegram_msg(msg_id, time_str, "指挥官（SPRUANCE）", "指挥官", msg['content'])
        elif role == "assistant":
            # 检测是否紧急
            text_lower = msg['content'].lower()
            priority = "紧急" if any(w in text_lower for w in ["立即", "马上", "快", "紧急", "刻不容缓"]) else "普通"
            chat_html += render_telegram_msg(msg_id, time_str, "布朗宁（BROWNING）· 参谋长", "参谋长", msg['content'], priority)

    st.markdown(f"""
    <div style="
        background: #22201a;
        border: 2px solid #3a3530;
        padding: 8px 12px;
    ">
        <div style="color:#8a7e6a; font-size:10px; letter-spacing:3px; margin-bottom:6px; border-bottom:1px dashed #3a3530; padding-bottom:4px;">
            ◆ 通信记录
        </div>
        <div style="height:360px; overflow-y:auto; padding-right:4px;">
            {chat_html if chat_html else '<div style="color:#8a7e6a; font-style:italic; text-align:center; padding:60px;">等待指令...</div>'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 待确认方案显示
    if state.pending_suggestions:
        for i, sug in enumerate(state.pending_suggestions):
            details = sug.details
            action_type = sug.action_type

            if action_type == "launch_scout":
                direction_cn = {
                    "northwest": "西北", "north": "正北", "northeast": "东北",
                    "east": "正东", "southeast": "东南", "south": "正南",
                    "southwest": "西南", "west": "正西"
                }.get(details.get("direction", ""), details.get("direction", ""))

                st.markdown(f"""
                <div style="background:#1a2332; border:2px solid #c4a265; padding:12px; margin:8px 0; border-radius:4px;">
                    <div style="color:#c4a265; font-size:12px; letter-spacing:2px; margin-bottom:8px;">◆ 侦察方案</div>
                    <div style="color:#d4c5a9; font-size:13px; line-height:1.8;">
                        <b>飞机</b>: PBY × {details.get('aircraft_count', 4)}<br>
                        <b>搜索扇面</b>: {details.get('sector_start', 0)}° - {details.get('sector_end', 0)}°（{direction_cn}）<br>
                        <b>航程</b>: {details.get('range_nm', 200)} 海里<br>
                        <b>预计回报</b>: 1 小时后
                    </div>
                </div>
                """, unsafe_allow_html=True)
            elif action_type == "set_course":
                st.markdown(f"""
                <div style="background:#1a2332; border:2px solid #c4a265; padding:12px; margin:8px 0; border-radius:4px;">
                    <div style="color:#c4a265; font-size:12px; letter-spacing:2px; margin-bottom:8px;">◆ 航向调整方案</div>
                    <div style="color:#d4c5a9; font-size:13px; line-height:1.8;">
                        <b>新航向</b>: {details.get('course', '?')}°
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
                st.markdown(f"""
                <div style="background:#1a2332; border:2px solid #c4a265; padding:12px; margin:8px 0; border-radius:4px;">
                    <div style="color:#c4a265; font-size:12px; letter-spacing:2px; margin-bottom:8px;">◆ 待确认方案</div>
                    <div style="color:#d4c5a9; font-size:13px;">
                        {sug.npc} 建议：{action_type}<br>
                        参数：{detail_str}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 确认执行", key=f"confirm_{i}", use_container_width=True):
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
                if st.button("❌ 拒绝", key=f"reject_{i}", use_container_width=True):
                    state.pending_suggestions.remove(sug)
                    st.info("方案已拒绝")
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
        logger.info(f"[PLAYER_INPUT] {user_input}")

        with st.spinner("布朗宁回复中..."):
            try:
                pre_digest = get_state_digest(state)
                st.session_state.state_snapshot = pre_digest

                def wrap_handler(handler):
                    def wrapped(**kwargs):
                        return handler(state, **kwargs)
                    return wrapped

                response = browning.chat(
                    player_input=user_input, state=state,
                    tools=browning.tools,
                    tool_handlers={n: wrap_handler(h) for n, h in browning.tool_handlers.items()},
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
