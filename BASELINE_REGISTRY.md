# 基准登记：停止混用“原版／CONTROL／A／B”

登记日期2026-11-16；本轮独立分支从133f95967b5789b216406b30117d3703643c7d7a建立。**只整理两个候选并补必要逐笔对照，不追加优化。main、旧源码、原账本、实际部署均不改；实际部署版本未知。**

## 1. ER_V2_REFERENCE：原ER入场＋V2出场

- 锁定提交：133f95967b5789b216406b30117d3703643c7d7a。
- 权威入口：outputs/rebound_annual_zero/CONCLUSION.md中的A；单币为runs/{年}/{币}/results/CONTROL_result.json，尽管名字CONTROL，实际使用V2。
- 实际运行命令：`python outputs/rebound_annual_zero/worker.py YEAR BTC`、ETH同理；2025ETH修复续跑见该目录recover_2025_eth.py及2025_ETH_recovery.log。本轮只读复用这条原版路径，不调用反弹分支重跑。
- 调用链：worker → rebound_followdown/signals.build取core（REBOUND并集另有账户，不能混入A）→ extra_sizing_cost_stress/replay.py及cost_engine.Book → eth_core_priority/priority_engine.Book(w.Dynamic) → eth_density_experiment/worker.Dynamic(Ledger,v.BoundedAdaptive) → adaptive_risk_exit_v2/worker.BoundedAdaptive。
- V2：连续两根已闭15m弱化；每根同时六线未全同向且MACD非同向；当前本币已实现余额3%参考预算；按至当前止损的距离计算目标剩余仓位；每笔最多一次有效减仓请求、最多减初始数量25%。不是每次盈利固定减仓，也不是固定15U预算。不满足数量条件不消耗机会。余仓保留原2%硬止损与uncapped阶梯。
- 行情分类：已闭小时ER，12h阈值0.28284271247461906、120h阈值0.10。transition暂停新信号，原挂单不因分类变化取消。
- 入场：SMA20/60/120＋EMA20/60/120；每条与3根15m前严格同向；收盘在六线外侧、MACD方向一致；最近96根最小带宽≤0.25%，range当前带宽≤0.50%；趋势SMA5/20及原距离／放量／回踩确认，2%绝对距离不改。use_entry_crosses=False。
- 原挂单：信号收盘后10秒，偏移0.2%，原价格刻度与nearest_tick，60分钟有效、单币单仓；BTC步长0.0001／最低名义100，ETH0.01／5。
- 资金：各年度各币500U独立；名义=当前本币已实现余额×3，原数量向下取整及预留逻辑。
- 本轮引用口径：ZERO手续费0、资金费明确0、退出不利滑点0.02%。不包含未计成本，不能叫完整实盘净收益。
- 数据／执行：同市场币安USDT永续已闭15m信号；官方原始trades逐笔、5秒相位2轮询、触价全量模拟代理。不是排队成交。1m原生K线只是原框架索引，不代替逐笔顺序；活动分钟读取逐笔、原始逐笔最后价估值。不可被最近OHLC实验替代。
- 2020北京时间02-16 00:00起；2021—2025各Jan1到次年Jan1；2026Jan1到Nov1；UTC均减8小时。每年重置，不拼连续复利。2025ETH保留S_ALL、COMPLETED_WITH_DATA_ANOMALY，其余保留原标签，不混称全历史严格通过。
- 原报告收益：2020 +7.869266%，2021 +44.063402%，2022 +83.748%左右、2023 +73.465%左右、2024 +49.848%左右、2025 +167.862%左右、2026 +57.885%左右；**精确值以comparison.csv读实际账本为准，不用此处四舍五入数计算收益。**
- 14个既有账户的JSON／分钟NPZ／配置／源行情SHA及原基准对账证据列于outputs/baseline_registry/account_reuse_manifest.json。本地运行产物部分不在旧Git提交中逐文件跟踪，代码提交身份与本地账本证据分开登记，不能伪称每个文件都存于133快照。

## 2. MA_DIRECTION_REFERENCE：旧六线方向分类，无V2

- 可恢复实现位于133f959...：outputs/retry_nov9_nov12/replay_comparison.py的ma_schedules，是复制原market_schedules后**只替换state计算**：`up if leg.up[i]==6 else down if leg.down[i]==6 else range`。
- 六线仍是SMA20/60/120、EMA20/60/120，方向对比3根15m前。**不是MA5/10/30/60/120/250，也不是30m／4h确认版本。**
- outputs/attribution_2026/paired_replay.py的prepare同时调用ER及ma_schedules，使用相同leg、原基础门槛和stacked_signals；new_book为AuditSleeve、ENTRY.exit_policy=uncapped。没有BoundedAdaptive，没有V2部分减仓。
- 入场其余门槛仍为历史0.25%、range当前0.50%、六线同向／价外／MACD、趋势原确认与2%绝对距离。由于完整入场本来要求六线同向，能开仓的候选会落入up/down分支；不应把range／原ER过渡期的含义混用。
- 原2026命令：`python outputs/attribution_2026/paired_replay.py --asset BTC`，ETH同理；更早Gate近期复用同规则但不是本年度候选数据，必须排除。
- 已找回2026的两币完整MA账本及分钟权益：outputs/attribution_2026/{BTC,ETH}_MA_result.json、*_MA_equity.npy。组合+12.1699377%，吻合截图+12.17%。BTC+27.9085093%、ETH−3.5686339%。无V2、3倍、零费、滑点0.02%。
- 旧2026执行器：paired_generator／ActualMarket／DayCache，旧活动分钟选择与aggTrades或trades校验路径。与ER_V2后来的“所有活动分钟＋严格trades”执行器不完全相同，**旧结果先作为历史证据，不能直接充当本轮统一引擎对照。**
- 未找回：截图2020—2025原MA完整账本、分钟权益及当时完整年度驱动日志；2020截图起止日期未知。prior_annual_evidence_from_conversation.csv有若干收益转录，但明确原文件未挂载，不能当作验证账本。截图2020 +112.88、2021 +92.13、2022 +70.79、2023 +13.71、2024 +156.21、2025 +158.47暂为待验证历史主张。
- 本轮只把已找到的原ma_schedules原样用于统一年度边界及ER_V2既有逐笔执行引擎。换用原无V2 Control基类，保留原策略无上限全仓出场；不添加V2来强行对齐ER。这是完整策略对照，不把差额全部归因于分类。
- 补跑入口：`python outputs/baseline_registry/compare_runner.py YEAR ASSET`。它调用既有p.prepare中的MA映射，不按截图数字写新规则；共同数据SHA必须与ER_V2对应币年完全一致。2020统一Feb16起的新结果不冒充旧未知窗口的截图复现。
- 新账户文件outputs/baseline_registry/runs/{年}/{币}/results/MA_DIRECTION_REFERENCE_result.json，分钟权益同名_equity.npz；数据不足或容量阻断保留断点，不以OHLC填补。精确执行与来源见RUN.md、各账户config及raw_sources。

## 3. ER_FIXED5_OHLC_EXPERIMENT：近期A_BASE的正确身份

- 提交060e12a18bc745a7c98e5270f2e37b0c759cc5ff；入口outputs/a_exit_regime_sizing/runner.py，命令`python outputs/a_exit_regime_sizing/runner.py YEAR ASSET`，其中A_BASE。
- 该目录入口还会运行其旧四组／三费用矩阵，**这里仅登记历史命令，本轮不执行**。
- 原ER固定入场、pause_transition=True；2%初始止损、fixed出场，LADDER_CAP=5，**无V2**。5档是止损锁利上限，不是盈利5%立即退出。
- 币安15m信号＋1m OHLC每分钟0/20/40/59秒假设路径，5秒相位2；不是实际毫秒逐笔。各年资金及边界同上。
- 已有ZERO、每边0.05%、每边0.02%假设费用等结果；本轮不重跑、不添加费用场景。
- 原代码／JSON中的A_BASE不改写，只用本登记表给其明确别名，不再叫早先正式基准；已有账本全部保留。
- 本轮不在其上追加任何优化。其2020／2023亏损与上述ER_V2并不矛盾，因为出场与执行口径不同。

## 4. 旧实验结论的适用边界

|分类|目录／组别|正确基准与处理|
|---|---|---|
|1 原ER＋V2上完成|eth_density_experiment的B/D/F；eth_core_priority的B/D/G/H/I；eth_2025_anomaly_sensitivity；extra_sizing_cost_stress／funding_early_forward；rebound_annual_zero的A对照与各反弹组；eth_rebound_confirmation|保留各自原配置、数据异常、费用、执行假设下的结论；不是重新宣布所有数据严格通过。其中纯B、C0_B_F_TOUCH等可作为ER_V2参考证据，含新增分支或不同仓位／成本的不能冒充同一基准。|
|2 无V2或其他基准|adaptive_density_control及adaptive_density_floors、a_macro_cooldown、a_exit_regime_sizing、a_base_regime_attribution|保留原结果，只适用于其各自CONTROL／OHLC／配置。动态带宽和宏观实验也不能自动等同ER_V2。|
|2 近期四项优化|a_failed_breakout_exit、a_stale_order_cancel、a_volatility_sizing、a_atr_initial_stop|对应ER_FIXED5_OHLC_EXPERIMENT。失败或未建议保留，不代表同样修改在ER_V2上也失败；**不因此自动全部重跑**。|
|2 其他早期策略|DYNAMIC10/25／固定15U风险预算、新六MA、多周期、Gate历史报告、现货替代区间|各自保留，不能互换命名、市场、仓位／出场或验证标签。|
|3 已有同口径可复用|rebound_annual_zero的14个CONTROL单币账户及分钟NPZ|本轮ER_V2_REFERENCE全部直接复用，不重跑、不加回费用。|
|3 仅历史实现证据|attribution_2026旧MA两账户|规则及截图2026能核对；执行器不同，未做统一回放前不作为公平对比结果。|
|4 缺少统一口径|MA_DIRECTION_REFERENCE各年|只补缺失或不一致的候选年度；成功／失败／断点与缺失原因列于comparison.csv及runs。无数据时保持UNVERIFIED，不填0、不换OHLC。|

## 5. 使用与结束条件

- 先以ER_V2_REFERENCE作为本项目研究对照的明确名称，理由是用户指定、七期账本及V2链完整，不是因为事后选收益高的版本；不等于部署或实盘批准。
- 在同引擎同数据两币账户都完整的区间，才计算候选收益／回撤差额；缺失时不排名。截图数字单独保留，不填入新comparison.csv冒充账户结果。
- 年度独立重置，不拼跨年复利／跨年回撤。期末未平贡献包括该未平交易已实现V2部分减仓与剩余浮盈，单列已平交易净额；不把未平浮盈称作已兑现利润。
- 本轮完成登记及可执行必要对照后结束，不追加早退／撤单／ATR止损／动态仓位／宏观／新入场规则，不搜参数。
