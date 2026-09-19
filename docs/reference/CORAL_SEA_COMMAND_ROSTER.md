# 珊瑚海指挥名册（CORAL_SEA_COMMAND_ROSTER）

> 用途：**S4 参谋班子与关系系统的运行名册依据**（s4-staff-relations-system-plan §九/S4.0）。
> 生成日期：2026-09-19 · 证据等级：CONFIRMED / PROBABLE / UNKNOWN（CONFLICTED 不入运行配置）
> 数据上游：`docs/reference/coral-sea/`（personnel.json / command-relationships.md / communications.md）
> 运行配置：`theaters/coral-sea/roster.json`（由本文冻结后生成，校验器强制其纪律）

## 一、登记规则（计划原文强制）

- 一手行动报告与官方编制记录优先；单来源人物标 PROBABLE。
- 未确认姓名必须使用职务名（后缀「（职务名）」），不凭印象补人。
- 不把战后职务倒推至珊瑚海当天；职务变化按日期标注。
- 物理位置与通信能力**分别考证**：不同舰的高官即使军衔高，也只能无线电联系。

## 二、指挥官与旗舰位置（1942-05-07/08）

| 人物 | 军衔 | 职务 | 位置 | 证据等级 | 来源 |
|---|---|---|---|---|---|
| Fletcher, Frank Jack | RAdm | CTF-17（战役总指挥；5/8 09:07-15:10 间非 OTC） | USS Yorktown | CONFIRMED | SRC-TF17/SRC-CV5 |
| Fitch, Aubrey W. | RAdm | CTG 17.5 航母群司令；5/8 OTC | USS Lexington | CONFIRMED | SRC-TF17/SRC-CV5 |
| Crace, John G. | RAdm, RN | CTG 17.3 攻击群司令 | HMAS Australia | CONFIRMED | SRC-TF17 |
| Kinkaid, Thomas C. | RAdm | CTG 17.2 支援群司令 | USS Minneapolis | CONFIRMED | SRC-TF17 |

## 三、核心参谋编制（TF17 司令部）

| 职务 | 位置 | 证据等级 | 备注 |
|---|---|---|---|
| 参谋长（职务名） | 约克城 | UNKNOWN | 一手报告不载姓名 |
| 情报参谋（职务名） | 约克城 | UNKNOWN | S3 `tf17_intel` 对应；5/7 contact pad 流程相关 |
| 作战参谋（职务名） | 约克城 | UNKNOWN | S3 `tf17_ops` 对应 |

舰上要职（S4 路由岗位的史实锚点，CONFIRMED 于 SRC-CV5）：
约克城航空长 Murr E. Arnold（Air Officer 岗）、通信长 Clarence C. Ray（通信官岗）、
航海长 Ivan D. Wiltsie、损管长 Clarence E. Aldrich。

## 四、直接沟通名单（S4 v0 冻结）

contact_permission 语义：`DIRECT_IN_PERSON` 同舰可当面呈报 / `DIRECT_RADIO` 无线电直连 /
`CHAIN_ONLY` 逐级上呈 / `REPORT_ONLY` 书面报告 / `NO_INITIATIVE` 只被动应答。

| actor_id | 人物 | contact_permission | can_be_summoned | can_initiate | 依据 |
|---|---|---|---|---|---|
| fitch | Fitch | DIRECT_RADIO | 否（不同舰） | 是（TF11/航母群司令职权） | 不同舰；TBS/HF 在案 |
| tf17_intel | TF17 情报参谋（职务名） | DIRECT_IN_PERSON | 是 | 是（情报呈报职权） | 同舰参谋（UNKNOWN 姓名） |
| tf17_ops | TF17 作战参谋（职务名） | DIRECT_IN_PERSON | 是 | 是（作战参谋职权） | 同舰参谋（UNKNOWN 姓名） |
| crace | Crace | REPORT_ONLY | 否 | 否（despatch 报告制） | 编队司令但异群异舰；TF17 报告全为 despatch |
| tf17_air_officer | 约克城航空长 Arnold | NO_INITIATIVE | 是 | 否（执行岗） | 舰内岗位，S5 AIR_OFFICER 代理锚点 |
| tf17_comms | 约克城通信长 Ray | NO_INITIATIVE | 是 | 否 | 通信官只收报与路由 |

**明确不进入名单**（CHAIN_ONLY 示例）：约克城舰长 Buckmaster、列克星敦舰长 Sherman——
舰长向本群司令上呈（指挥链见 §五），不直接对 CTF 主动。

## 五、指挥链（ChainReport 上呈路径）

```text
盟军：
  舰长/下级岗位 → 本群司令 → CTF-17
    YOR/Lex 舰长 → CTG 17.5（Fitch）→ CTF-17（Fletcher）
    TG17.2 舰长 → Kinkaid → CTF-17
    TG17.3 舰长 → Crace → CTF-17（despatch）
  专业参谋 → CTF-17 参谋长 → CTF-17
日方（对照，不在 S4 运行内）：
  五航战（原）→ 机动部队（高木）→ 第四舰队（井上）
```

规则对齐（s4 计划 §六）：所有正式报告保留原始来源；上级可附加批注不可改写原文；
未送达报告不暴露给指挥官；链中每个持有人与状态变化记录时间。

## 六、未考证人物处置

以下仅以职务名存在，运行 roster 不得硬编码其姓名（校验器强制「（职务名）」后缀）：
TF17 参谋长 / 情报参谋 / 作战参谋、VF-2 中队长、VT-2 中队长、
约克城 5/7 米西马方向侦察报告飞行员、五航战航空队长级。

## 七、冻结与评审

- 本文即 S4.0 考证交付物；运行配置 `theaters/coral-sea/roster.json` 由其派生并受
  `tools/validate_coral_sea_data.py` 与 `tests/test_coral_sea_reference_data.py` 双重校验。
- 任何 roster 变更必须先改本文并附来源，再同步运行配置。
