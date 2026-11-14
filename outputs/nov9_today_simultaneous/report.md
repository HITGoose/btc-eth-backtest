# 11月9日至最新已发布数据：两币同时开仓

范围：2026-11-09 00:00至2026-11-13 08:00（北京时间，截止不含）。11-13 08:00至11-14当前未验证：fapi.binance.com/fapi/v1/time返回451，11-13及11-14官方BTC 15m CHECKSUM返回404。不能称已验证至今天。

仅币安USDT永续，官方daily/klines和daily/trades档案核对SHA256。原ER与V2独立账户，11月1日各币各500USDT起跑，11月9日不重置；不是全年余额续接。手续费0、3倍名义、原0.02%不利出场滑点、未计资金费。只筛选本期开仓的交易PnL，不当作期间账户收益率。

同根信号同时成交定义：两币信号收盘时间相同且两张限价单均实际触达成交，非同一毫秒成交。两版均1组：11-09 06:00做空；BTC06:00:23.603、ETH06:00:19.255，相差4.348秒。

|币种|实际开仓（北京时间）|方向|原ER盈利USDT|V2盈利USDT|
|---|---|---|---:|---:|
|ETH|11-09 06:00:19.255|空|+16.08|+9.95|
|BTC|11-09 06:00:23.603|空|+14.19|+13.68|
|BTC|11-11 22:38:02.805|空|+29.47|+20.04|

BTC 2笔、ETH 1笔；本期开仓全部在截止前平仓。原ER合计+59.73USDT，V2合计+43.67USDT。同根信号那组原ER+30.27USDT、V2+23.63USDT。

本期持仓重叠共有两段：11-09零点至05:55:17.486已同时持有BTC多与ETH空（均11-08开仓，不计本期新单）；11-09 06:00:23.603至16:24:28.046同时持有两币空单。重叠明细见overlapping_positions.csv，平仓及档位见trades.csv。

执行命令：
```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/nov9_today_simultaneous/run.py > outputs/nov9_today_simultaneous/run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/nov9_today_simultaneous/collect.py > outputs/nov9_today_simultaneous/collect.log 2>&1
```

首次下载临时502，失败日志first_network_failure.log保留；有限重试恢复后两个币任务均退出0。原入场、2%绝对距离和止损保留。限价采用全量触达成交代理，不模拟深度排队。原版不覆盖。
