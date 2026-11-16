# 未成交挂单失效撤销固定实验

[中文报告](outputs/a_stale_order_cancel/CONCLUSION.md) · [年度CSV](outputs/a_stale_order_cancel/annual.csv) · [实际撤单与基准匹配](outputs/a_stale_order_cancel/cancel_matching.csv) · [所有请求与结果](outputs/a_stale_order_cancel/cancel_requests.csv) · [基准等待](outputs/a_stale_order_cancel/base_order_waiting.csv) · [新增消失](outputs/a_stale_order_cancel/trade_matching.csv) · [复跑命令](outputs/a_stale_order_cancel/RUN.md)

固定A_BASE cap5/3x、全入场信号不变。提交后闭15m失效则T+60秒撤单，原到期优先，撤单先于该分钟撮合，之前成交则请求失效。无A_FAIL_EXIT或V2。28新账户、28引用基准；15m+1m OHLC模型、ZERO及每边0.02%假设、零资金费。main与旧结果未改。
