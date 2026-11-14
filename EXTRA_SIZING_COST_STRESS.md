# EXTRA仓位与固定成本矩阵（独立实验）

源提交87f94d2e29b9832526e0aa35c0400c7ed7496805；分支codex/extra-sizing-cost-stress-20261114。不改main，不覆盖原策略与结果。**执行中，最终状态以交付报告和覆盖表为准，不能把断点当全年结果。**

B/G/H/I100保持原ER BASELINE（use_entry_crosses=False）与V2；I50/I25仅ETH EXTRA初始名义×50%/25%。CORE/BTC、六均线、ER、2%绝对距离、挂单、止损与V2预算不改。

[中文结果](outputs/extra_sizing_cost_stress/report.md) · [年度表](outputs/extra_sizing_cost_stress/mobile_annual.csv) · [数据及执行覆盖](outputs/extra_sizing_cost_stress/availability.csv) · [资金费数据](outputs/extra_sizing_cost_stress/FUNDING.md) · [固定协议](outputs/extra_sizing_cost_stress/EXPERIMENT.md) · [限制](outputs/extra_sizing_cost_stress/ISSUES.md)

官方www.binance.com/fapi/v1/fundingRate恢复了2024/25/26/NOV精确资金费与标记价；2020—2023缺完整标记价，对应全年含资金费场景未验证。缺失不填零，不用K线或固定8小时替代。2025始终独立COMPLETED_WITH_DATA_ANOMALY，不称全历史严格通过。

当前云端复跑：Python3.12，仓库根目录执行`python outputs/extra_sizing_cost_stress/run_all.py`。先恢复同SHA原生缓存、原始逐笔异常审计数组及可信旧参考分钟数组；Git不包含大输入和断点，不宣称新克隆无需恢复数据即可完整复现。资金费和逐笔新订单都进入实际账户路径，不按比例缩放旧收益。

F_THROUGH审查发现原型额外等待激活检查的问题，已独立纠正并全区间重跑。最终只读取through_exact_clock，不能使用旧prototype成交敏感性结果。其他F_TOUCH结果不受影响。详见ISSUES.md。
