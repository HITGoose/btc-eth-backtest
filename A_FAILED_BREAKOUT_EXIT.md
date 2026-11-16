# 突破失败一次性提前退出

[中文结论与年度表](outputs/a_failed_breakout_exit/CONCLUSION.md) · [年度CSV](outputs/a_failed_breakout_exit/annual.csv) · [早退与基准身份匹配](outputs/a_failed_breakout_exit/early_exit_matching.csv) · [逐笔新增/消失/变化](outputs/a_failed_breakout_exit/trade_matching.csv) · [阶段合计](outputs/a_failed_breakout_exit/totals_and_stages.csv) · [复现命令](outputs/a_failed_breakout_exit/RUN.md)

固定A_BASE入场、fixed/cap5、3x。满成交4小时首个闭15m仅检查一次；负毛浮盈+连续两闭K各在六线内才请求；T+60秒下一分钟开盘执行、原止损优先。仅28新账户；28基准引用。15m+1m OHLC模型，ZERO/每边0.02%假设，零资金费。main及原结果未改。
