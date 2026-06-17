# 中途岛指挥官 · UI 设计文档

> 基于 1942 年美军航母舰桥海图桌的二战海图风格游戏界面

---

## 一、设计理念

**核心体验**：玩家作为 TF16 指挥官 Spruance，坐在舰桥海图桌前，面对泛黄的作战地图，通过电报和参谋对话下达命令。界面必须还原"1942年舰桥指挥台"的沉浸感。

**视觉关键词**：泛黄纸张、墨水线条、木桌背景、军事命令文档、打字机字体、罗盘玫瑰。

---

## 二、色彩系统

### CSS Variables（严格遵守）

```css
--color-desk: #3a2518;         /* 深色木桌背景 */
--color-desk-light: #4a3528;   /* 木桌浅色（侧面板） */
--color-paper-base: #f5edd6;   /* 主海图纸底色 */
--color-paper-dark: #e8dcc8;   /* 深米黄（顶栏/仪表带） */
--color-paper-edge: #d4c8a8;   /* 纸张边缘 */
--color-ink-main: #2a2218;     /* 深棕黑（主文本/重要线条） */
--color-ink-fade: #6b5d4a;     /* 褪色棕（次要标签/边框） */
--color-ink-faint: #a89878;    /* 极淡棕（网格线/分隔线） */
--color-enemy-red: #8b2500;    /* 深红（敌方标记） */
--color-secret-red: #c0392b;   /* 亮红（SECRET 印章） */
--color-grid-line: rgba(160,140,110,0.35); /* 半透明网格线 */
--color-lagoon: #b8d4c8;       /* 泻湖蓝绿 */
--color-reef: #8aaa98;         /* 珊瑚礁 */
--color-sand: #d4c4a0;         /* 沙岛 */
--color-eastern: #c8b890;      /* 东岛 */
```

---

## 三、字体系统

| 用途 | 字体 | 字号 |
|------|------|------|
| 手写标记/签名 | `Caveat, cursive` | 8-13px |
| 打字机/战报/仪表 | `Special Elite, monospace` | 11-16px |
| 时钟 | `Special Elite` | 40px bold |
| SECRET 印章 | `Caveat` | 16px bold |

---

## 四、布局结构

### 整体 Grid

```
┌─────────────────────────────────────────────────┐
│ 顶栏 (48px)                                      │
├──────────────────────────────────┬──────────────┤
│ 海图区 (flex:1)                   │ 通信面板     │
│                                  │ (360px 固定)  │
│                                  │              │
│                                  │              │
├──────────────────────────────────┤              │
│ 底部状态栏 (56px)                │              │
└──────────────────────────────────┴──────────────┘

整体 padding: 6px, gap: 4px（木桌缝隙）
```

### 顶栏

```
┌──────────────────────────────────────────────────┐
│ 🇺🇸 中途岛指挥官  TASK FORCE 16  │  04 JUN 1942  │ 04:00 Z │  ACTION POINTS: 3/3  │
└──────────────────────────────────────────────────┘
     左对齐                  ←── 居中 ──→          右对齐
```

- 背景：`--color-paper-base`
- 时钟：40px 粗体，2px 黑色边框，"Z" 后缀
- 居中：`position: absolute; left: 50%; transform: translateX(-50%)`

### 底部状态栏

```
┌──────┬──────┬──────────┬──────┬──────┬──────┬──────┬──────┐
│ 航向  │ 航速  │ 位置     │ 损伤  │ 甲板  │ 巡逻  │ 侦察  │ 敌情  │
│240°  │25 KTS│32°N 175°W│ OK   │ —    │0 CAP │ 无   │ 暂无  │
└──────┴──────┴──────────┴──────┴──────┴──────┴──────┴──────┘
```

- 标签：10px `--color-ink-faint`
- 数值：15px bold `--color-ink-main`
- 每项居中对齐，竖排标签+数值
- 右侧按钮：ADVANCE +15MIN / SITUATION REPORT

### 右侧通信面板

```
┌──────────────────────┐
│ COS│ADML│TF16│COMM│INTEL│  ← NPC 标签栏
├──────────────────────┤
│ INTEL                │  ← 深色区块标题
│ 情报消息...          │
├──────────────────────┤
│ PLAYER               │  ← 棕色区块标题
│ 指挥官命令...        │
├──────────────────────┤
│ SECRET —            │  ← 红色命令文档
│ INTERCEPTION PLAN    │
│ MISSION: ...         │
│ COMMANDER SIGNATURE: │
│ [EXECUTE ORDER]      │
│ [REVISE PLAN]        │
├──────────────────────┤
│ [输入指令...]  [发送] │
└──────────────────────┘
```

---

## 五、Canvas 海图渲染

### 图层顺序（从下到上）

1. **纸张背景**：泛黄底色 + 噪点颗粒 + 水渍 + 暗角
2. **海图边框**：双线（外 1px + 内 0.5px）
3. **水深等深线**：4 层同心椭圆，极淡蓝灰
4. **经纬网格**：虚线，四边标注度数
5. **距离环**：圆形虚线，标注 20/40/60/80/100nm
6. **搜索扇面**：楔形扇区，半透明填充 + hatching + 方向标注
7. **中途岛环礁**：有机贝塞尔曲线形状
   - 外环：珊瑚礁填充 + 虚线轮廓
   - 泻湖：蓝绿色椭圆
   - 沙岛：不规则椭圆 + 标注 "SAND ISLAND"
   - 东岛：三角形 + 三条交叉跑道 + 标注 "EASTERN ISLAND"
   - 沙嘴岛：小椭圆
   - Brooks Channel：虚线水道
8. **己方舰队**：2px 圆圈 + 十字线 + 代号（ENT/HOR）+ 独立航向箭头 + 虚线预测
9. **敌军标记**：1.5px 红色虚线圆圈 + "?" + "ENEMY" + 置信度
10. **罗盘玫瑰**：右上角，双圈 + 8 方位星 + N/S/E/W + NE/SE/SW/NW
11. **比例尺**：右下角，0-25nm-50nm 三刻度
12. **SECRET 印章**：左上角，红色 2px 边框 + 16px 大字

### 中途岛绘制参数

| 元素 | 形状 | 填充色 | 标注 |
|------|------|--------|------|
| 环礁外环 | 贝塞尔曲线椭圆 | `rgba(180,210,195,0.3)` | — |
| 泻湖 | 椭圆 | `#b8d4c8` | — |
| 沙岛 | 不规则贝塞尔 | `#d4c4a0` | SAND ISLAND |
| 东岛 | 三角贝塞尔 | `#c8b890` | EASTERN ISLAND |
| 跑道 | 3 条交叉线 | — | Henderson Field |
| 沙嘴岛 | 小椭圆 | `#d4c4a0` | — |
| 水道 | 虚线 | — | — |

### 颜色编码

| 类型 | 颜色 | 说明 |
|------|------|------|
| 己方舰队 | `#2a2218` 圆圈 + 十字 | 深棕黑 |
| 敌军 | `#8b2500` 虚线圈 + ? | 深红 |
| 搜索扇面 | `rgba(160,140,110,0.08)` | 极淡棕 hatching |
| 距离环 | `rgba(42,34,24,0.12)` | 淡棕虚线 |
| 水深线 | `rgba(100,140,180,0.15)` | 淡蓝灰 |

---

## 六、组件规范

### 按钮

```css
.btn {
  background: var(--color-paper-dark);
  color: var(--color-ink-main);
  border: 1px solid var(--color-ink-faint);
  padding: 5px 12px;
  font-family: var(--font-typewriter);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
}
.btn:hover { background: var(--color-paper-edge); border-color: var(--color-ink-main); }
.btn:active { transform: translate(1px, 1px); }  /* 物理凹陷感 */
.btn-approve { background: var(--color-ink-main); color: var(--color-paper-base); }
.btn-reject { color: var(--color-secret-red); border-color: var(--color-secret-red); }
```

### 消息卡片

```css
.msg {
  background: var(--color-paper-dark);
  border: 1px solid var(--color-ink-faint);
  border-left: 3px solid var(--color-ink-fade);   /* 玩家消息 */
  padding: 6px 10px;
  margin: 4px 8px;
}
.msg-sender-npc { border-left-color: var(--color-ink-main); }  /* NPC 消息 */
```

### 军事命令文档

- 标题栏：`--color-secret-red` 背景 + 白色文字
- 正文：纸张渐变背景 + 棕色文字
- 签名栏：底部实线 + "COMMANDER SIGNATURE:"
- 按钮：EXECUTE ORDER（深色）/ REVISE PLAN（红色边框）

### 区块标题

```css
.section-intel { background: var(--color-ink-main); }   /* INTEL 深色 */
.section-player { background: var(--color-ink-fade); }   /* PLAYER 棕色 */
```

---

## 七、交互逻辑

### API 调用

| 操作 | API | 方法 |
|------|-----|------|
| 加载状态 | `GET /state` | fetch |
| 加载 NPC | `GET /npcs` | fetch |
| 对话历史 | `GET /npc/{id}/history` | fetch |
| 发送消息 | `POST /chat` | `{npc_id, message}` |
| 推进时间 | `POST /advance` | `{minutes: 15}` |
| 批准方案 | `POST /suggestion/{id}/approve` | — |
| 驳回方案 | `POST /suggestion/{id}/reject` | — |

### 模块化架构

```
static/
├── index.html          # 页面结构
├── css/style.css       # 设计系统（CSS Variables + 组件样式）
└── js/
    ├── main.js         # 入口：初始化 + API 调用 + 事件绑定
    ├── mapRenderer.js  # Canvas 海图渲染（纯绘图，无业务逻辑）
    └── uiController.js # DOM UI：标签/消息/仪表盘/命令文档
```

---

## 八、禁止项

- ❌ 圆角 > 2px
- ❌ 发光/投影效果（除纸张投影外）
- ❌ 现代渐变色
- ❌ 科幻感元素
- ❌ 外部图片资源（印章/岛屿全部 Canvas/CSS 绘制）
- ❌ 框架依赖（React/Vue 等）

---

## 九、参考图像关键词

### Midjourney / DALL-E 提示词

```
WWII Pacific naval chart, 1942 battle map, aged yellow paper on dark wood desk,
ink pen markings, compass rose, coordinate grid, Midway Atoll with reef and lagoon,
military operations map, vintage cartography, hand-drawn style, SECRET classification stamp,
fleet markers with course arrows, enemy contacts in red dashed circles,
dark brown wood texture background, paper shadow effect --ar 16:10 --style raw
```
