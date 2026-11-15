# 只读统计复跑
源提交060e12a18bc745a7c98e5270f2e37b0c759cc5ff，源分支codex/a-exit-regime-sizing-20261115。只读28个ZERO/MAKER_002_SIDE的A_BASE账本与14份15m缓存，不导入金融回放执行器、不重新下载数据、不创建或续跑账户。
Python3.12 + numpy：
```
python outputs/a_base_regime_attribution/analyze.py
python outputs/a_base_regime_attribution/robustness.py
python outputs/a_base_regime_attribution/report.py
python outputs/a_base_regime_attribution/verify.py
```
实际执行stdout保留execution.log、verification.log。
小时标签原样提取work/backtest_squeeze_short.py的hourly_regimes()，24h/120h阈值0.20/0.10；原策略实际入场是12h/120h阈值约0.28284271247461906/0.10，报告明确不同，不修改入场。
每笔存signal_close_ms与opened_us的当时标签及已闭小时，并另存真实模型提交时间+10秒及其标签。主锚点按signal_close_ms冻结；成交标签只做事后归因。
闭仓用账本net；未平用原期末mark估值减已付入场费记账户贡献，不假设平仓。原始浮盈与费用分别保留，未平不计已平胜率。逐笔r1000算术均值与中位数从各交易实际初始名义计算，不用总盈亏除总名义。
两个费用场景记录具有相同的交易键和开平时间，不能当成1800个独立交易样本；SIGNAL_CLOSE/FILL两个锚点也不能相加。原A_BASE每费用895笔已平、5笔独立期末未平。
2020仅02-16起、2026仅1—10月，年度独立500/币重置；数据为15m+1m OHLC模型的既有账本，不是实际逐笔或实盘成交。Maker费用是假设，资金费0。
只输出描述性阶段对比，不调阈值、不测试杠杆或加仓、不将事后剔除观察值当成完整账户重放，不合并main。
