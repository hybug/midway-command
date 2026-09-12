# 中途岛指挥官 / Midway Command

二战中途岛战役背景的文字策略游戏。

玩家扮演 1942 年 6 月 4 日的 TF16 指挥官 Raymond Spruance，通过自然语言与参谋团对话，下达侦察、航向、CAP 等命令。参谋根据性格和专业判断理解、执行命令，带来不确定性。

**核心体验**：信息不对称 × 参谋性格偏差 × 时间压力

## 开发进度

| Day | 主题 | 状态 |
|-----|------|------|
| 1-4 | 核心循环（AP/侦察/信息延迟） | ✅ |
| 5-7 | 舰队实体/六边形地图/侦察方案 | ✅ |
| 8 | 多 NPC（5 个参谋可切换） | ✅ |
| 8+ | UI 重构 + Canvas 海图 | ✅ |
| 8++ | 迁移纯 Web 前端 | ✅ |
| 9 | 战斗演算 | ⬜ 待做 |
| 10 | 内测 + 迭代 | ⬜ 待做 |

## 核心玩法

### 侦察系统（已实现）
- 三种搜索模式：扇形（集中）、平行（覆盖）、方格（彻底）
- 完整生命周期：起飞 → 飞往搜索区 → 搜索 → 返航 → 着舰
- SBD Dauntless 真实燃油参数（1.2 gal/nm 巡航，25 gal/hr 搜索）
- 侦察报告有失真（方位±5°、距离±10%、数量可能少报）
- 报告延迟 20-55 分钟

### NPC 系统（已实现）
- **Browning（参谋长）**：暴躁果断，主动推荐搜索模式，分析侦察报告
- **Murray（企业号舰长）**：稳重专业，只管本舰
- **Mitscher（大黄蜂舰长）**：沉默寡言，飞行员出身
- **通信官**：公事公办，只读电报
- **情报官**：谨慎分析，评估情报可信度

### 信息不对称（已实现）
- 侦察报告有方位/距离/数量失真
- Browning 作为情报中介：分析报告可信度、指出矛盾、给出战术建议
- 玩家永远不知道完整真相

## 技术架构

```
浏览器: HTML + CSS + JavaScript (Canvas)
  ├── CSS Grid 布局
  ├── Canvas 海图（二战海图风格）
  └── DOM 渲染对话/仪表盘
    ↕ REST API
Python: FastAPI (后端)
  └── src/ (游戏逻辑)
```

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / Pydantic v2 |
| 前端 | 原生 JS / CSS / HTML5 Canvas |
| LLM | Kimi Code API (kimi-for-coding) |
| 测试 | pytest (285 tests) |

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 MOONSHOT_API_KEY

# 2. 安装依赖
source .venv/bin/activate
pip install -r requirements.txt

# 3. 启动服务
uvicorn server:app --reload

# 4. 浏览器打开 http://localhost:8000
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 主页 |
| GET | `/state` | 游戏状态 |
| GET | `/npcs` | NPC 列表 |
| GET | `/npc/{id}/history` | 对话历史 |
| POST | `/chat` | 发送消息给 NPC |
| POST | `/advance` | 推进时间 |
| POST | `/suggestion/{id}/approve` | 批准方案 |
| POST | `/suggestion/{id}/reject` | 驳回方案 |
| POST | `/plan-strike` | 制定空袭方案 |
| POST | `/confirm-strike` | 确认空袭方案 |
| POST | `/reject-strike` | 驳回空袭方案 |
| POST | `/recall` | 召回机群 |
| POST | `/confirm-contact/{index}` | 确认敌情接触 |

## 文档

- [游戏设计](docs/design/GAME_DESIGN_V2.md) — 核心玩法、NPC 性格、骰子系统
- [UI 设计](docs/design/UI_DESIGN.md) — 二战海图风格规范
- [美术方向](docs/design/ART_DIRECTION.md) — 图像生成 AI 提示词
- [技术架构](docs/design/TECH_ARCH.md) — 系统分层、模块职责
- [历史背景](docs/reference/HISTORICAL_NOTES.md) — 真实战况、人物、电文
- [NPC 档案](docs/design/NPC_PROFILES.md) — 人物设定、自主度参数
