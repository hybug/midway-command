# 中途岛指挥官 · 美术方向文档

> 用于图像生成 AI（Midjourney / DALL-E / Stable Diffusion）

---

## 一句话描述

1942年美军航母舰桥上的海图桌指挥界面，二战海军作战风格，纸张质感，墨水线条。

---

## 视觉风格

### 整体氛围
- 二战太平洋战场舰桥指挥室
- 海图桌上摊开的作战地图
- 昏暗的舰桥灯光下的纸张泛黄效果
- 紧张、孤独、不确定的指挥氛围

### 色调
- 主色：米黄纸张色 `#f5edd6` / `#e8dcc8`
- 墨水：深棕黑色 `#2a2218`
- 辅助墨水：褪色棕 `#6b5d4a` / `#a89878`
- 敌方标记：深红色 `#8b2500`
- 边框/网格线：`#c4b89a`

### 字体风格
- 手写体风格（Caveat 类似）
- 打字机风格（Special Elite 类似）
- 全大写标注
- 度分秒坐标格式

---

## 海图样式

### 底图
- 泛黄纸张质感，有细微颗粒噪点
- 边缘有轻微暗角（年代感）
- 偶尔有淡褐色水渍（age stains）
- 经纬线网格，细灰色虚线

### 中途岛环礁
- 真实形状：椭圆环礁轮廓（珊瑚礁虚线）
- 两座岛屿：沙岛（矩形）+ 东岛（三角形）
- 泻湖：浅蓝绿色填充
- 三条交叉跑道在东岛上（三角形布局）
- 标注：`MIDWAY ATOLL 28°12'N 177°21'W`

### 己方舰队
- 空心圆圈 + 内部十字线
- 代号标签（ENT / HOR）
- 航向矢量实线 + 虚线预测延长线
- 标注航向度数

### 敌方标记
- 红色虚线圆圈
- 问号符号（表示不确定）
- 标注 "ENEMY"

### 侦察扇面
- 斜线填充（hatching），极淡

### 距离环
- 圆形虚线，标注海里数（20nm, 40nm, 60nm...）

### 罗盘玫瑰
- 经典航海罗盘样式（八角星 + N/S/E/W 标注）
- 位于海图右上角

### 比例尺
- 底部右侧，标注 50 nm

### 分类标记
- 左上角红色边框 `SECRET` 印章

---

## UI 元素

### 顶栏
- 深米黄背景 `#e8dcc8`
- 左侧：标题 "中途岛指挥官" + 舰队番号
- 右侧：日期 "04 JUN 1942" + 大号时钟 + 行动点数

### 仪表带（海图下方）
- 单行横排，分隔线 `│`
- 数据项：航向 / 航速 / 位置 / 损伤 / 甲板 / 巡逻 / 侦察 / 敌情
- 标签褪色棕，数值深棕黑

### 通信面板（右侧）
- NPC 标签栏：5个按钮（参谋长/企业号舰长/大黄蜂舰长/通信官/情报官）
- 对话记录：纸张色背景的消息卡片
  - 玩家消息：左侧棕色边框
  - NPC 消息：左侧深棕色边框
  - 时间戳 + 发件人 + 正文
- 待确认方案：军事命令文档风格
  - 暖色纸张渐变背景
  - "SECRET" 头部标记
  - 签发/呈报信息
  - 任务/执行/时间表段落
  - 指挥官签名栏

### 按钮
- 复古纸张风格
- 边框 `#a89878`
- 按下凹陷效果
- 批准按钮：深色背景白字
- 驳回按钮：纸张背景红字

---

## 参考图像关键词

### Midjourney / DALL-E 提示词

**海图风格：**
```
WWII Pacific naval chart, 1942 battle map, aged yellow paper, ink pen markings, compass rose, coordinate grid, Midway Atoll, military operations map, vintage cartography, hand-drawn style, secret classification stamp --ar 4:3 --style raw
```

**舰桥指挥：**
```
1942 US Navy bridge plotting table, tactical map with ship markers, compass and dividers, dim yellow lighting, wartime command center, officers studying charts, Pacific theater WWII, photorealistic --ar 16:9
```

**UI 界面：**
```
WWII military command interface, vintage paper texture, ink typography, naval operations dashboard, tactical map with fleet positions, amber and brown color palette, retro war room aesthetic, UI design mockup --ar 16:9
```

**军事命令文档：**
```
WWII US Navy operation order document, typewriter text on aged paper, TOP SECRET stamp, military letterhead, signed by officer, formal naval command style, vintage document scan --ar 3:4
```

---

## 关键约束

- 不要科幻感、不要 CRT 终端感、不要像素游戏感
- 要真实感、年代感、纸张质感
- 灵感来源：真实的 1942 年太平洋舰队作战地图和 CINCPAC 作战命令
