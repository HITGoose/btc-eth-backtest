# 结果及入口索引

|内容|路径|
|---|---|
|2024/2025原ER、旧15预算、V2收益及回撤|outputs/adaptive_risk_exit_v2/report.md、comparison.csv、audit.json|
|2020—2023/2026扩展，2019缺失|outputs/adaptive_risk_exit_v2_extended/report.md、comparison.csv、audit.json|
|最新可用11月模拟开平仓与同时开仓|outputs/nov9_today_simultaneous/report.md、trades.csv、same_signal_pairs.csv、overlapping_positions.csv|
|ETH11月11日不开仓逐项核对|outputs/nov9_today_simultaneous/ETH_nov11_reason.md、ETH_nov11_conditions.csv|
|19—26年单币独开全量价格/条件/盈利亏损|outputs/cross_asset_entry_audit/report.md、trades.csv、conditions.csv、summary.csv|
|单币独开手机筛选与Excel|outputs/cross_asset_entry_audit/mobile.html、BTC_ETH_独立开仓全量核对.xlsx|
|原始85文件恢复校验|outputs/retry_nov9_nov12/source_restore.json|
|本次Git状态|handoff/astra_20261114/git_status.json|

CONTROL_result.json是原ER对照；V2两个目录内DYNAMIC_result.json才是当前修正版。其他目录DYNAMIC含义不同，见策略文档版本表。source/result/config/run.log都应配套读取。

2024/25的monthly.csv已打包，其他年份本轮未重新生成V2月度表。各年分钟权益.npy不在包中。历史原Gate报告仍保留，但不能与本轮币安逐笔结果混用。
