# 复跑命令与执行口径
Python3.12，原仓库requirements及已缓存官方15m/1m文件。不需要逐笔档案或交易密钥，不访问真实账户。

```
python outputs/adaptive_density_floors/checks.py
python outputs/adaptive_density_floors/experiment.py 2020 BTC
python outputs/adaptive_density_floors/pipeline.py
python outputs/adaptive_density_floors/report.py
```

pipeline处理剩余13个币年，2020BTC先行命令处理；已完成且指纹正确的账户跳过，不改已有结果。priority_tail.py仅利用空余计算槽提前跑2026BTC及2025ETH，策略组不增加。
每个币年16账户（8组×2费用），合计224账户。每个账户完整重走自身现金与占仓路径；同币共用指标、K线和假设事件缓存。
日志pilot.log、年度_币种.log、2026_ETH_priority.log、priority_tail.log及pipeline.log保留实际输出。遇失败记录exit_code，继续其他币年；不以旧逐笔结果填补。
calendar.json已经保存官方来源、缓存原字节SHA、纽约时区与UTC毫秒，无需再次网络获取。calendar子命令仅用于从现有官方原响应缓存重新提取，不会下载交易数据。

OHLC映射明确为每分钟0秒open、20秒high、40秒low、59秒close，期间轮询读取前一假设事件价格；这是假设路径，不能称真实秒级/逐笔价格。真实行情可能先低后高或有更多跳价。沿用原止损及挂单引擎，但所有年度A/B/D也必须同口径重新回放，不引用旧逐笔收益充当本轮对照。
窗口沿用旧回测北京时间年度边界；2020仅2月16日起、2026仅1—10月，详见每账本window毫秒字段。2025使用官方K线，本次未加载有冲突ID的逐笔档案，不能说已修复官方逐笔或严格通过S_ALL。
