# 指挥关系（command relationships）

> 机器可读：`data/units.json` + `docs/reference/CORAL_SEA_COMMAND_ROSTER.md`（S4 运行名册依据）。

## 盟军指挥链（珊瑚海当刻）

```text
CINCPAC（Nimitz，珍珠港）—— 战略指示 / 情报（JN-25 体系）
  └ CTF-17 RAdm Fletcher（旗舰 Yorktown）—— 战役战术总指挥
      ├ CTG 17.5 RAdm Fitch（旗舰 Lexington）—— 航母群；5/8 09:07-15:10 任 OTC
      │   ├ 约克城舰长 Capt Buckmaster（含副长 Kiefer、航空长 Arnold）
      │   └ 列克星敦舰长 Capt Sherman
      ├ CTG 17.2 RAdm Kinkaid（旗舰 Minneapolis）—— 支援群
      ├ CTG 17.3 RAdm Crace, RN（旗舰 Australia）—— 攻击群（RN/RAN 指挥链归英澳，战术上隶 Fletcher）
      └ CTF-17 参谋（参谋长 UNKNOWN；情报参谋/作战参谋为职务名）
```

要点（S4 直接沟通名单的史实依据）：

1. **Fitch**：不同舰（Lexington），只能经 TBS/无线电直接联系——`DIRECT_RADIO`。
2. **TF17 情报参谋 / 作战参谋**：同舰（Yorktown），可当面呈报——`DIRECT_IN_PERSON`（职务名）。
3. **Crace**：编队司令但不同舰不同群，只有 despatch 通信——`REPORT_ONLY`。
4. **舰长（Buckmaster/Sherman）**：向本群司令上呈，不直接向 CTF 越级——`CHAIN_ONLY`。
5. Fletcher 5/8 09:07 将战术指挥移交 Fitch（OTC），15:10 收回——指挥权变更在案（SRC-TF17）。

## 日军指挥链

```text
联合舰队（Yamamoto，特鲁克）
  └ 第四舰队司令长官 VAdm 井上成美（拉包尔）—— MO 作战总指挥
      ├ MO 机动部队 RAdm 高木武雄（旗舰 Myōkō）—— 海上战术指挥
      │   └ 第五航空战队 RAdm 原忠一（旗舰 Shōkaku）—— 舰载航空实际指挥
      ├ MO 掩护部队 RAdm 五藤存知（旗舰 Aoba；Shōhō 在编）
      ├ MO 主攻略部队 RAdm 梶冈定道
      ├ 图拉吉攻略部队 RAdm 志摩清英
      └ 第25航空战队（岸基，拉包尔/Deboyne）
```

要点：日方海上指挥权在机动部队（高木），航空战术在五航战（原）；第四舰队总体上
掌握攻略节奏——5/8 延期决定由井上作出（CONFIRMED）。

## 通信关系

- 盟军舰间：TBS 75.5Mc 话音（近距）+ HF despatch（远距/格式电文）。
- 旗舰战斗定向：列克星敦雷达席承担 TF17 空情引导（SRC-CV5：1410 起约克城从列克星敦接手）。
- 盟军岸舰：CINCPAC↔TF17 HF；海岸瞭望站（coastwatchers）经岸台转发。
- 日方：舰间旗语/灯语为主、HF 为辅；岸基经拉包尔-Deboyne 前进基地中继。
- 权限语义（S4 映射）：不同舰高级军官即使军衔高也只能 `DIRECT_RADIO`，不能表现为
  走进旗舰舱室——本战役期 Fletcher/Fitch 两旗舰恰好常同航速同行，但接触仍走 TBS。
