# 来源清单（sources）

> 机器可读：`data/sources.json`（本文件为人类阅读版，两者以 `source_id` 对齐）。
> 版权纪律：一手官方报告为美国政府公有领域作品（经 HyperWar 公益转录访问）；
> 受版权保护书籍只做事实性引用，不复制原文段落。

## 等级定义（计划 §3.1）

```text
PRIMARY    行动报告、官方命令、原始电报、航海日志、官方照片
OFFICIAL   海军历史机构、国家档案、官方战役史
ARCHIVAL   战争日记、编制表、厂商资料、技术手册
SECONDARY  学术专著、经过引注的研究
TERTIARY   百科、网站摘要、数据库索引
EXCLUDED   小说、影视、游戏、无来源自媒体（本包零使用）
```

## 来源登记表

| source_id | 名称 | 等级 | 可靠性 | 访问方式（2026-09-19） |
|---|---|---|---|---|
| SRC-TF17 | CTF-17 珊瑚海行动报告（1942-05-27，Serial 0010N） | PRIMARY | 高 | 逐句核对（HyperWar 转录全文抓取） |
| SRC-CV5 | USS Yorktown (CV-5) 行动报告（1942-05-25，含航空队/副长/损管/医疗附录） | PRIMARY | 高 | 逐句核对（同上） |
| SRC-MORISON | Morison《US Naval Operations in WWII》Vol. IV | OFFICIAL | 高 | 知识引用 + 交叉印证 |
| SRC-NHHC | 美海军历史与遗产司令部珊瑚海概述 | OFFICIAL | 高 | 本次抓取失败；仅采多源一致事实 |
| SRC-DANFS | 美国军舰辞典（舰艇条目） | OFFICIAL | 高 | 知识引用 |
| SRC-GILLISON | 澳大利亚官方空军史 Vol. I（RAAF 1939-42） | OFFICIAL | 高 | 知识引用（岸基航空） |
| SRC-SENSHI | 戦史叢書（日方官方战史）MO 作战段（经英文转引） | OFFICIAL | 中高 | 间接转引；凡单独依赖处一律 PROBABLE |
| SRC-LUNDSTROM | Lundstrom《The First Team》(1984) | SECONDARY | 高 | 知识引用（航空作战逐中队细节） |
| SRC-DULL | Dull《A Battle History of the IJN》(1978) | SECONDARY | 高 | 知识引用（日方编制） |
| SRC-TULLY | CombinedFleet.com（Tully/Hackett）IJN 舰艇数据 | TERTIARY | 中 | 仅交叉印证 |
| SRC-WIKI-CS | Wikipedia 珊瑚海条目 | TERTIARY | 中 | 仅缺口定位与交叉印证 |

## 使用规则

1. 关键事实（人员、参数、时间、损失）**不得单独依赖 TERTIARY**。
2. CONFIRMED 必须至少有一个 PRIMARY/OFFICIAL/ARCHIVAL 来源（校验器强制）。
3. SRC-NHHC 与 SRC-SENSHI 在本会话未逐句核对原文，因此凡仅由其支撑的结论一律降为 PROBABLE。
4. 影视/小说/游戏来源：**EXCLUDED，本包零引用**。
