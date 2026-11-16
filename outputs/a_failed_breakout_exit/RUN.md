# 固定两组复现
Python3.12与原requirements，复用既有币安永续15m/1m缓存，不下载完整行情。
```
python outputs/a_failed_breakout_exit/checks.py
python outputs/a_failed_breakout_exit/runner.py 2020 BTC
python outputs/a_failed_breakout_exit/pipeline.py
python outputs/a_failed_breakout_exit/report.py
python outputs/a_failed_breakout_exit/finalize.py
```
pipeline负责其余13个币年，2020BTC先行命令负责。单个币年为runner.py YEAR BTC或ETH。金融指纹不匹配拒绝复用；已完整且指纹一致的结果跳过，不强行忽略指纹。
仅28个A_FAIL_EXIT账户新回放，28个A_BASE经源码、输入SHA、信号及金融指纹一致后引用。日志pilot.log、pipeline.log及年度_币种.log保存实际执行。
唯一改动为每个实际持仓的一次检查和退出请求；在每分钟原事件循环前检查已闭15m，T+60秒开盘原止损先执行、仍持有才早退。待执行时取消原优化跳过，强制看到该分钟开盘打印，不改变事件价格与顺序。所有退出仍由原close应用费用和0.02%滑点。
六线为SMA20/60/120、EMA20/60/120，按原模型同样预热重新计算，宽度逐点与原Leg核对；两根各自使用其本根带界。入场、挂单、数量、原2%硬止损、fixed上限5锁利不变。没有V2、分批、额外时间止损或新入场。
checks.py仅6项必要合成事件检查；全年回放不是合成单元测试结果。report.py验证实际账本现金/权益闭合、入场信号一致、首次实际早退前权益与基准相同、一次性时点及已闭数据、T+60执行与原止损优先。没有重跑基准或做大规模测试。
净盈亏包含期末未平估值，另外列已平净额、浮盈及已付未平入场费。基准期末未平单单独归因，不判最终输赢。早退同名义差额按A_BASE每笔实际初始名义归一化；存在入场/成交时点差异时会标flag，不冒充纯退出效果。
2020仅2月16日起，2021—2025全年，2026仅1—10月；年度独立重置，不拼接复利。T+60解释、4小时和连续2根均在结果前固定，不追加参数或路径搜索。
