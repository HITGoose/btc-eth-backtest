# A/B/C/D 离线下载包

下载全部四个ZIP，并依次解压到同一个目录（不是二进制拼接）。

- [btc_eth_ABCD_part01.zip](btc_eth_ABCD_part01.zip) (65.1 MiB), SHA256: `34febf44d79b90bec76560c27df9ce7c458c1139428b84e8d8eb3038e37f4274`
- [btc_eth_ABCD_part02.zip](btc_eth_ABCD_part02.zip) (64.7 MiB), SHA256: `4c07e2a5a725910a90be637d95088e1e2081b2b272a5e64177a793ae5c308a31`
- [btc_eth_ABCD_part03.zip](btc_eth_ABCD_part03.zip) (64.1 MiB), SHA256: `b20b346d8df523013259ba48ddf081f8870d5997b17e79d0e4b1faac5575e838`
- [btc_eth_ABCD_part04.zip](btc_eth_ABCD_part04.zip) (10.8 MiB), SHA256: `4ce4c71331fd5450af7d5c87daa449071fc68a0d9a23e9b3a830a5257f6e2833`

进入解压后的 btc-eth-backtest，执行 `python offline_reproduce_trade_matching.py`。

包含源码、K线、保存的账本；可以从账本重新生成匹配表。不含约88GiB原始逐笔，不能完全离线从行情重跑金融账户。原main和策略未修改。
