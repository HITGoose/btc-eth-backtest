# ETH CORE优先与BTC确认：审查入口

锁定源提交01937b2d4a1306ab211a9c1853bda285258c2853，独立分支codex/eth-core-priority-btc-confirm-20261114，不合并main，不覆盖旧策略或结果。

五组固定：B=.25 V2；D=.30 V2；G=仅EXTRA需同根BTC完整信号同向；H=CORE优先；I=两者。BTC保持原.25 V2，原ER BASELINE，未搜索其他带宽。

- [冻结规则、来源、时序与直接复跑命令](outputs/eth_core_priority/EXPERIMENT.md)
- [冻结配置与执行指纹](outputs/eth_core_priority/frozen_config.json)
- [实际问题记录](outputs/eth_core_priority/ISSUES.md)
- [新增边界测试](outputs/eth_core_priority/tests.json)
- [原32项测试](outputs/eth_core_priority/validation32/test_results.json)

历史回放正在执行，当前代码提交本身不表示全部区间已完成。后续结果以独立目录中的status、availability、audit及中文报告为准。2025官方逐笔冲突继续严格处理，不能用旧流水或OHLC替代新增订单路径。资金费未计，费用压力每边.05%仅为假设，模拟触价全量不代表实盘成交保证。
