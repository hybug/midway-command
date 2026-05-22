# 历史背景 · HISTORICAL_NOTES.md

> 用于 MVP 阶段 State 初始化和 NPC prompt 设计的事实参考。
> 所有数字尽量基于 Walter Lord《Incredible Victory》、Symonds《The Battle of Midway》
> 等学术研究,避免戏剧化的二手记述。

---

## 1. 关键时间线(1942/6/4 - 美方视角)

> 时间为 Zone +12(中途岛时区,西经 12 时区)。注意美军当时电报常用 GMT。

| 时间 | 事件 |
|------|------|
| 04:00 | Spruance 已起床,旗舰企业号位于约 32°N 175°W。CAP 已升空 |
| 04:30 | PBY 4V58 报告:**"Enemy carriers"**,方位 320°,距中途岛 180 海里 |
| 05:00 | 中途岛收到日机来袭报告,起飞拦截 |
| 05:34 | 又一份 PBY 报告:**"Many planes heading Midway, bearing 320"** |
| 06:07 | 第三份 PBY 报告:**"Two carriers and main body"**,方位 320°,距 180 海里 |
| 06:30-07:00 | **关键决策窗口**:Spruance 接受 Browning 建议,提前起飞 |
| 07:02 | 企业号开始起飞(SBD、TBD、F4F) |
| 09:25 | TBD 鱼雷机抵达日舰,几乎全部被击落(VT-8 仅一人生还) |
| 10:20 | McClusky 的 SBD 找到日舰(他靠跟踪日驱逐舰"岚号"找到的) |
| 10:22-10:28 | **"5 分钟改变历史"**:SBD 俯冲轰炸,赤城、加贺、苍龙起火 |
| 14:00 | 飞龙的 D3A 找到约克城,首波攻击 |
| 17:00 | 飞龙第二波攻击约克城,后被 SBD 找到击沉 |
| 夜间 | Spruance 决定向东撤,避免日方夜战 |

---

## 2. 各舰艇与机群

### 2.1 美军 TF16 (Spruance 指挥,旗舰企业号 CV-6)

**航母**:
- USS Enterprise (CV-6) — 旗舰
- USS Hornet (CV-8)

**护航**(MVP 阶段简化处理,不细分):
- 重巡:Northampton, Pensacola, Vincennes, Minneapolis, New Orleans
- 防空巡洋:Atlanta(在 TF17,这里只列示意)
- 驱逐舰若干

**艦载机** (每艘航母约 80 架):
- **VF**:F4F-3/4 Wildcat 战斗机 ~27 架
- **VS / VB**:SBD-3 Dauntless 俯冲轰炸机 ~38 架
- **VT**:TBD-1 Devastator 鱼雷机 ~15 架(老旧,飞机本身是问题)

### 2.2 美军 TF17 (Fletcher 指挥,约克城)

> MVP 不直接控制 TF17,但 NPC 知道其存在。

- USS Yorktown (CV-5) — 总指挥旗舰
- 约克城前几天刚修好(珊瑚海战役后)

### 2.3 日军 Kido Butai(机动部队,Nagumo 指挥)

> MVP 阶段玩家**完全看不到**这些实际状态,但 `_hidden_actual_enemy` 字段要记录。

- **航母 4 艘**:Akagi(赤城), Kaga(加贺), Soryu(苍龙), Hiryu(飞龙)
- 总舰载机约 250 架(零式、99 舰爆、97 舰攻)
- 位置:6/4 04:00 时约 30°N 178°W
- 状态:正在为攻击中途岛准备(挂炸弹,不是反舰)

---

## 3. PBY 报告的真实电文

(给通信官 prompt 和事件 handler 用)

### 04:30 第一份 PBY 报告
```
ENEMY CARRIERS
```
极短,只是确认存在。

### 05:34
```
MANY PLANES HEADING MIDWAY BEARING 320 DISTANCE 150
```

### 06:07 完整版
```
SIGHTED 2 CARRIERS AND MAIN BODY OF SHIPS - BEARING 320 - 
DISTANCE 180 - COURSE 135 - SPEED 25
```

注意:报告说**两艘**航母,实际有四艘(另两艘在云层下/未被发现)。这是
游戏迷雾的核心:玩家依据不完整信息决策。

---

## 4. 关键人物(给 NPC prompt 用)

### Raymond A. Spruance (玩家扮演)
- 1886 年生,海军中将
- 中途岛前主要指挥过巡洋舰编队,从未指挥过航母战斗群
- 性格冷静、寡言、思考慎密,被部下认为"难以读懂"
- Halsey 临阵生病推荐他接替 TF16
- 历史评价:从"运气好"逐渐被认为是太平洋战争最优秀的舰队指挥官之一

### Miles R. Browning (Browning NPC)
- 1897-1954,海军少将
- Halsey 的常任参谋长,中途岛战役借调给 Spruance
- 性格暴躁、好酒、对下属严苛,但战术嗅觉极佳
- 历史关键贡献:**坚决建议提前起飞**,押对了"日舰加油换弹"窗口
- 后来因酗酒和性格被免职(1944),晚年悲惨

### Wade McClusky (CAG, 不出场但被提及)
- 企业号航空指挥官
- 历史上**找不到日舰**,凭借跟踪一艘日驱逐舰找到机动部队
- 这是太平洋战争最幸运的决断之一

### Chester W. Nimitz (太平洋舰队司令, 不出场)
- 中途岛战役总策划
- 派出 TF16 和 TF17 的人

### Frank Jack Fletcher (TF17 指挥, 不出场)
- 总战术指挥
- 旗舰约克城被重创后,把指挥权转给 Spruance

---

## 5. 玩家"已知"和"未知"的边界(MVP 开局 04:00)

### 已知(NPC 可以引用)
- 我方位置、机群状态、燃油弹药
- 日方有 4 艘航母在西边某处(战前情报判断)
- 日方目标是中途岛
- PBY 正在搜索扇面
- 中途岛守军可以独立作战

### 未知(NPC 不能假设)
- 日方机动部队精确位置
- 日方何时发动攻击
- 日方机群当前状态(挂炸弹还是鱼雷?)
- 山本主力部队(超出 MVP 范围)的部署
- 约克城的精确状态

### "未来才知道的事"(NPC 绝对不能说)
- "我们知道日舰会在那个时刻换弹" — **NPC 不知道这一点**
- "TBD 鱼雷机会全损" — **NPC 不知道**
- "Yorktown 后来沉了" — **NPC 不可能预知**

---

## 6. 用于 prompt 的电文样式

二战美军舰队电报特点:
- 全大写
- 极简短
- 用"-"(dash)代替逗号和句号(节省发报时间)
- 数字写明单位(KNOTS, DISTANCE, BEARING)
- 不用客套话

例:
```
ENEMY CARRIERS BEARING 320 DISTANCE 180 NM COURSE 135 SPEED 25 KNOTS
```

NPC(尤其通信官)应该模仿这种电报体。Browning 说话则更口语化,引用电报内容时
转述,不直接读全文。

---

## 7. 推荐阅读(给后续 Alpha 阶段)

- Walter Lord, *Incredible Victory* (1967) — 文学性强,人物描写
- Craig L. Symonds, *The Battle of Midway* (2011) — 现代学术综合
- Jonathan Parshall & Anthony Tully, *Shattered Sword* (2005) — **日方视角**,
  Alpha 阶段如果做日方剧本必读
- Gordon Prange, *Miracle at Midway* (1982) — 经典

---

## 8. 一些值得 NPC "信手拈来"的细节

(注入到 Browning prompt 增强真实感)

- "Halsey 在病床上写信交代给 Spruance"
- "Layton 情报组解码 JN-25 的方位"
- 飞行员行话:"angels 15" = 15000 英尺、"bandits" = 敌机、"vector" = 方位
- 当时还没有"radar fighter direction"成熟战术,CAP 拦截全靠目视和雷达粗略指引
- 企业号当时还在用 TBS(Talk Between Ships)短距离无线电
