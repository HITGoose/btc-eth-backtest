# 反弹续跌年度零费用对照

基准4fbc499370454246ee92ac110d8b590328b0719e；原signals.py规则不变。手续费0、资金费0为用户指定口径，退出不利滑点0.02%，不是完整实盘净收益。每年度每币500；近期单独保持Nov1账户路径，不与年度拼接。

本轮A=两币原版；B=仅BTC加分支；C=仅ETH加分支；D=两币加分支。与旧实验组名不同。实际只回放每币两条独立账户，四组按同一时间轴组合，不新增本金。

|区间|本轮组|收益%|最大回撤%|已平仓|总亏损USDT|最大单亏USDT|状态|
|---|---|---:|---:|---:|---:|---:|---|
|2020|A|7.869|38.395|145|1752.004|37.382|COMPLETE|
|2020|B|-1.381|40.059|159|1895.507|37.382|COMPLETE|
|2020|C|3.327|31.996|163|1835.836|36.767|COMPLETE|
|2020|D|-5.923|33.707|177|1979.338|35.721|COMPLETE|
|2021|A|44.063|24.625|66|901.385|51.590|COMPLETE|
|2021|B|24.851|23.489|91|1374.130|46.976|COMPLETE|
|2021|C|35.689|26.984|88|1313.559|51.590|COMPLETE|
|2021|D|16.476|30.811|113|1786.304|46.976|COMPLETE|
|2022|A|83.748|22.510|126|2111.318|66.077|COMPLETE|
|2022|B|61.856|29.816|159|2639.089|66.077|COMPLETE|
|2022|C|61.210|27.595|167|2859.139|57.697|COMPLETE|
|2022|D|39.317|42.687|200|3386.911|57.697|COMPLETE|
|2023|A|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2023|B|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2023|C|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2023|D|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2024|A|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2024|B|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2024|C|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2024|D|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2025|A|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2025|B|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2025|C|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2025|D|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2026|A|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2026|B|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2026|C|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|
|2026|D|未验证|未验证|未验证|未验证|未验证|UNVERIFIED_INCOMPLETE_ASSET|

2020仅2月16日至年底，2026仅1—10月，具体UTC/北京边界见每账户config。最大回撤按分钟合并权益，不是两币回撤简单平均。总亏损和最大单亏按已平仓完整交易净额；年末浮动估值计入权益，不假设年末全平。2025仅S_ALL已授权异常视图，不能称全历史严格验证，也不将旧九情景一致套用到本策略。

## 新增分支与机会挤占

|区间|币|新增已成交/已平|赢/亏|新增已平净额|完整账户权益差额|原盈利单消失笔数/金额|
|---|---|---|---|---:|---:|---|
|2020|BTC|14/14|6/8|-89.957|-92.501|0/0.000|
|2020|ETH|18/18|10/8|-53.830|-45.418|0/0.000|
|2021|BTC|25/25|12/13|-183.961|-192.125|0/0.000|
|2021|ETH|22/22|9/13|-74.359|-83.745|0/0.000|
|2022|BTC|33/33|14/19|-157.479|-218.922|0/0.000|
|2022|ETH|41/41|18/23|-209.460|-225.382|0/0.000|

新增分支净额只统计该账户已平EXTRA交易；完整账户差额含资金余额变化、原信号挤占、仓位/退出变化及年末浮动，不能把两者相加。原盈利单消失金额是原账户实际利润的事后机会归因，不是可直接相加的损失。trades.csv保留两路径逐笔，trade_matching.csv按方向+signal_close_ms匹配，不强行配对。

## 近期独立区间

真实逐笔执行截止北京2026-11-14T08:00:00.000+08:00；后续闭15m假设路径截止北京2026-11-15T10:45:00.000+08:00。原始逐笔与合成路径单列；15m内OHLC/OLHC先后与插值时间不是实际观察，也不是严格收益上下界。

|口径|本轮组|9日起收益%|期末权益|最大回撤%|
|---|---|---:|---:|---:|
|RAW|A|13.116|1125.422|7.360|
|RAW|B|13.116|1125.422|7.360|
|RAW|C|23.268|1226.429|7.360|
|RAW|D|23.268|1226.429|7.360|
|OHLC|A|13.116|1125.422|7.360|
|OHLC|B|14.800|1142.173|7.360|
|OHLC|C|27.149|1265.039|7.360|
|OHLC|D|28.833|1281.791|7.360|
|OLHC|A|13.116|1125.422|7.360|
|OLHC|B|14.800|1142.169|7.360|
|OLHC|C|25.189|1245.533|7.360|
|OLHC|D|26.872|1262.281|7.360|

recent_trades.csv记录两币每笔开空和退出时间、成交价、净额及是否依赖假设。9日前完整账户状态相同证明见recent/*/pre9_state_comparison.json；原零费基准前缀比较见baseline_comparison.json。近期新增已平利润和同一时刻完整账户差额应分开理解。

## 直接判断

年度仍有未完成或失败区间，不给伪完整结论；已完成结果保留，失败明细见failures.json。

## 未完成/失败

- 2023 BTC：NOT_COMPLETED，pending
- 2023 ETH：NOT_COMPLETED，pending
- 2024 BTC：NOT_COMPLETED，pending
- 2024 ETH：NOT_COMPLETED，pending
- 2025 BTC：NOT_COMPLETED，pending
- 2025 ETH：NOT_COMPLETED，pending
- 2026 BTC：NOT_COMPLETED，pending
- 2026 ETH：NOT_COMPLETED，pending

复跑命令（Python3.12，仓库根目录）：
```bash
python outputs/rebound_annual_zero/supervisor.py
python outputs/rebound_annual_zero/recent_prepare.py
python outputs/rebound_annual_zero/recent.py BTC
python outputs/rebound_annual_zero/recent.py ETH
python outputs/rebound_annual_zero/report.py
```

原代码及main不改；本轮不追加参数搜索、收费部署或大包。