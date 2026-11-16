# ER＋V2：两项独立移植，Colab运行

**重要修复：旧c6d23ea新增指标错位，旧变体结果及断点无效；使用本修复版新Notebook、新结果目录。原基准及行情缓存保留。见INDEX_FIX.md。**

基准提交f8aa6a9440ce3a0b486a3b1245a1051b77b8d145。原ER完整信号、V2两根弱化／余额3%参考预算／最多一次25%减仓、2%硬止损与uncapped阶梯均保留。不是无V2的FIXED5 OHLC。

- `ER_V2_FAIL_EXIT`：成交满4小时后的首个15m收盘仅检查一次；两根各自在各自六线带内，且本笔已实现分批毛盈亏＋剩余浮动毛盈亏<0，才请求T+60秒或之后首个真实事件退出。原止损、V2排队部分退出先处理，不回填收盘价。
- `ER_V2_VOL_SIZE`：ATR96 Wilder、前2880有效值（排除当前）中位数；倍率clip(ref/current,.5,1)，只缩放挂单原名义并沿用取整；无效回退1且记录。无新增信号。
- 14个ER基准账本及分钟曲线在Git中，仅新运行14个year×asset任务，每任务两本独立账户，共28新账户。任务间是独立进程，任务内共用官方raw cache，隔离全局费用状态。
- 2020北京时间Feb16起，2021—25全年，2026至Nov1 00:00前；各年各币500。费用／资金费0、退出滑点0.02%。2025ETH只用原SHA白名单S_ALL，不扩展九情景，保留异常标签。

## 路径与数据

环境变量`BTC_REPO_ROOT`、`BTC_DATA_ROOT`、`BTC_OUTPUT_ROOT`可任意配置。portable.py仅在加载时替换历史源码绝对路径字面量；原文件字节不改，原父链manifest仍核验。原调用链：cost_engine.Book→priority_engine.Book→Dynamic(Ledger,BoundedAdaptive)。

Git包含代码、14基准账本／曲线／信号、官方来源及异常审计/白名单；**不包含全部15m/1m派生行情、每日逐笔ZIP和异常日大数组**。input_manifest.json锁定14组输入SHA和预热边界。缺失原生行情从币安UM官方月K线档案下载，校验CHECKSUM、完整时间网格，按旧格式重建后必须匹配旧输入SHA。缺失逐笔按活动日从同市场官方trades获取，仍严格校验，无OHLC兜底。

异常日ZIP须匹配原053164...SHA，重建int64 ID/时间及float64价格数组后逐一匹配旧审计SHA；才进入原S_ALL稳定排序。不是修复官方数据。

原始ZIP保留在`BTC_DATA_ROOT/archives`；不自动删除既有缓存。逐笔缓存可能占大量空间，空间不足记录失败并保留断点，需更大本地磁盘或重新配置缓存根目录；不能因此换OHLC。Drive上的原始缓存使用前先复制到本地；不在Drive直接随机读取逐笔。

## 运行

```bash
export BTC_REPO_ROOT=/your/repository
export BTC_DATA_ROOT=/your/local_data
export BTC_OUTPUT_ROOT=/your/local_results
python outputs/er_v2_colab/smoke_checks.py
python outputs/er_v2_colab/run.py 2020 ETH --hours 8
python outputs/er_v2_colab/batch.py
python outputs/er_v2_colab/report.py
```

仅Colab用户执行batch；Codex本轮没有启动年度批处理。8小时试算从首个原信号之前15分钟开始，空闲段略去但无先前订单／持仓；不是年度收益。小时参数只允许最小试算，不用于年度结果目录。

每个UTC日结束及任务末写原segment checkpoint，校验实验源码／输入／信号／任务边界指纹；不忽略不兼容断点。`BTC_DRIVE_RESULTS`指定时，日checkpoint原子写完再复制回Drive；`BTC_DRIVE_DATA`指定时保存新建原生行情。断线后同固定提交、同环境变量，从Drive复制结果和行情回本地，重跑batch。完成且指纹一致跳过；运行中从最后已保存日续跑（最多重放未保存的一日）。

30%等仓位／门槛搜索、额外费用、其他历史优化均不运行。报告七期为独立损益简单合计，不是跨年复利；匹配交易每1000初始名义差额仅作归因，不是账户收益。历史已反复查看，不称新样本外。

## 返回分析

将`results_for_review.zip`交回即可，其中包含REPORT.md、annual.csv、period_summary.csv、trade_matching.csv、failed_exit_matching.csv、sizing.csv、trade_effects.csv、concentration.csv、missing.csv、任务账本、分钟曲线、配置、日志和批处理状态。不包含庞大原行情和checkpoint。如不能下载ZIP，至少交上述CSV和runs下全部result.json/status.json/failure.json。
