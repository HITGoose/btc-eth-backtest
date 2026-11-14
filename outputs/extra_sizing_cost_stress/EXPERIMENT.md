# 固定EXTRA仓位与成本压力实验
源提交87f94d2e29b9832526e0aa35c0400c7ed7496805；独立分支codex/extra-sizing-cost-stress-20261114。完整源树无AGENTS.md。B/G/H/I100原策略不变，I50/I25仅ETH EXTRA下单时×.5/.25，CORE及BTC不变。0.25/0.30及全部信号/V2/止损/单账户/资金管理不变，不搜索阈值。

先逐区间重放C0/C1的B/G/H/I100，对照完整原交易、现金、期末权益与分钟回撤；通过后才执行小仓和附加压力。C0零费滑点.0002；C1费.0005滑点.0002。C2/C3/C4必须有完整官方结算费率、实际时点及计价价格才运行并标包含资金费；当前archive仅calc_time/funding_interval_hours/last_funding_rate，无mark_price，官方主API451，备用返回非JSON。不得近似结算时点/计价价格，不补零。单列C3_NO_FUNDING(.0005/.0005)、C4_NO_FUNDING(.00075/.001)；B/I100/I50/I25追加C1 F_THROUGH作为明确获准的资金费缺失退路。初次探测时C2—C4本身UNVERIFIED；后续恢复范围与最终状态见本文件“后续官方来源恢复”及availability.csv。

原S_ALL及8组合白名单适配器只读复用，全日原始ZIP及数组先核SHA。2025每个新配置重新分叉窗口；之后比较完整Book及最新实际价及配置，只有全等共享后缀，自己的全年权益前缀独立保留。其余年严格原始逐笔，不能用OHLC兜底。BTC不随ETH版本变化，但成本/成交模型改变需重新执行对应BTC路径。

资金费若取得完整数据，约定结算事件先于同毫秒真实成交，按事件前存续数量计现金，再允许该时刻止损/减仓/替换；缺精确记录不能启用。当前不含资金费实际运行不触发该约定，不宣称资金费场景完成。F_THROUGH只允许提交后新事件越过一tick并按原限价模拟全额，非真实排队概率。

独立区间2020-02-16至年底，2021—2025全年，2026-01至10，NOV2026-11-01至11-13 08:00北京。2019未验证。各币每段500余额×3，资金费进现金才会改变后续定量，绝不事后扣费。所有实际退出共享本账本成本上下文，不修改原文件常量。

命令：
```
python outputs/extra_sizing_cost_stress/tests.py
python outputs/extra_sizing_cost_stress/supervisor.py
python outputs/extra_sizing_cost_stress/report.py
```
每任务日末保存含源码/输入/配置指纹断点；原始数据校验失败保留文件，其他配置/区间仍尝试。资金费不足与下载失败单独列示，不填收益零。原结果、main及旧严格标签不变；本轮2025完成只COMPLETED_WITH_DATA_ANOMALY。

## 后续官方来源恢复（不改固定矩阵）
继续尝试后官方www.binance.com/fapi/v1/fundingRate可用，取得精确fundingTime/费率/markPrice。2024/25/26/NOV数据完整，C2—C4及C2 F_THROUGH进入独立funded_replay完整账户；2020—2023缺markPrice仍未验证。数据、时序与边界见FUNDING.md及funding_coverage.csv。运行funding_fetch.py、funding_tests.py、funded_supervisor.py；不在原不含资金费引擎上改指纹。最初探测失败日志保留。

## 仅排程优化
资金费完整的2024/25/26不再额外运行非必需的NO_FUNDING/C1越价重复矩阵，全部必需C0—C4及C2越价保留。NOV已完成的附加结果保留；早年资金费缺失仍完整运行NO_FUNDING及C1越价退路。sizing_only_replay只执行已固定的四个I50/I25 C0/C1账户，金融循环/现金/输出与原replay字节级相同（指纹函数名称除外），其单独代码指纹及差异明确保存。2024四账户从本轮已实际执行至8月1日的同源20账户断点提取，逐账户完整状态/权益SHA、费用/比例/信号/输入哈希/旧代码指纹与新兼容性清单验证，不丢历史、不按收益缩放、不忽略代码指纹。不跨资产/费用/策略共享现金。见sizing_subset_compatibility_2024.json、subset_tests.json。

## 最终F_THROUGH入口
早期prototype的F_THROUGH激活时钟偏保守，不能当最终结果。只读取through_exact_clock；新入口：
```
python outputs/extra_sizing_cost_stress/through_tests.py
python outputs/extra_sizing_cost_stress/through_supervisor.py
python outputs/extra_sizing_cost_stress/through_replay.py 2024 ETH through
```
2024/25/26/NOV自动C2实际资金费，早年缺价自动明确C1退路；不是给C2缺失补零。全部四版本和BTC独立路径重放。2025 ETH在资金费主矩阵结束后执行，避免同时创建三份大异常视图。6项新边界覆盖原提交时钟与观测时钟区别、首笔越价、同毫秒事件、CORE替换及缺价模式。

## 8GiB恢复与以后重跑
实际OOM后恢复入口：`python outputs/extra_sizing_cost_stress/recover_2025_memory.py`，同源码及输入指纹串行恢复原两账户集合。后续run_all的三个supervisor统一task_guard.memory_guard，对2025ETH整任务互斥，其他年份/资产仍按原调度；操作系统文件锁不改变模拟历史时钟、事件顺序、数据或参数。每个情景仍全部执行，旧失败日志保留，不把资源失败当数据失败。
