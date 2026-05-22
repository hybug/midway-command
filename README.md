# 中途岛指挥官 / Midway Command

二战中途岛战役背景的文字角色扮演游戏。

玩家扮演 1942 年 6 月 4 日的 TF16 指挥官 Raymond Spruance,通过**自然语言**
与参谋团对话,发出意图性命令,由参谋**理解、分解、执行**。

**核心乐趣：理解偏差**——同一命令,不同性格的参谋会有不同解读和执行,
玩家通过观察结果来发现偏差,并用自然语言纠正。

## 当前阶段

**Phase 3 · 理解偏差** — 验证"NPC 直接执行 + 性格偏差"的核心玩法。

- 开局:双方都不知道对方精确位置,需要侦查索敌
- Browning(参谋长)可直接执行航向/CAP 调整,但会按性格产生偏差
- 玩家观察状态变化,用自然语言纠正偏差

## 核心机制

```
NPC 报告态势 → 玩家发意图命令 → NPC 理解并直接执行(带偏差)
    → 玩家观察结果 → 纠正/认可 → (循环)
```

**Browning 的执行风格**:直接执行,事后报告。总是比玩家预期更激进。

## 文档

- [游戏设计 GAME_DESIGN.md](docs/GAME_DESIGN.md) — 核心玩法、角色、偏差机制
- [技术架构 TECH_ARCH.md](docs/TECH_ARCH.md) — 系统分层、执行引擎、Prompt 策略
- [历史背景 HISTORICAL_NOTES.md](docs/HISTORICAL_NOTES.md) — 真实战况、人物、电文

## 技术栈

- Python 3.10+
- Streamlit (前端)
- Kimi Code API · `kimi-for-coding` (NPC, OpenAI-compatible)
- Pydantic (状态建模)
- OpenAI SDK (Kimi API 客户端)
- pytest (测试)

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env,填入 MOONSHOT_API_KEY

# 2. 启动服务
source .venv/bin/activate
streamlit run app.py

# 3. 浏览器打开 http://localhost:8501
```

## 查看决策日志

```bash
tail -f logs/decision.log
```
