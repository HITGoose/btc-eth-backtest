# ETH历史密集阈值固定对照实验

源提交0ad7902161b91e7cf5538c5c06195c4a39086c24；独立分支codex/eth-density-025-030-035-20261114。锁定提交无AGENTS.md（API404、完整树搜索为空）。已读取ASTRA_REVIEW.md和策略文档，443个本地文件Git blob与锁定远端一致。

预先固定六组：A=.25原出场，B=.25V2，C=.30原出场，D=.30V2，E=.35原出场，F=.35V2。阈值单位百分数，仅ETH历史96根最小带宽改变；BTC固定.25。底层候选ENTRY和stacked range密集门槛均用隔离参数，原模块全局值未改。其他策略、2%绝对距离、撮合代理和轮询模型保持锁定代码。

只读诊断在独立状态副本生成完整gate，不受实际baseline候选是否存在限制，不消费真实回踩状态。诊断候选定义：移除历史带宽约束后，底层>=5条同向、收盘在六线外、MACD同向的全部方向；最终6条过滤及所有趋势条件仍记录。没有水平或原逻辑不计算的分支标NOT_EVALUATED，不当通过。账户占用由真实执行事件在提交时点重建；只用于诊断，不反馈交易。

先在新目录复跑32项合成测试，再复现2024/25四币年度基准交易与权益。一旦不一致，supervisor禁止启动实验。新增入口测试包括.25回归、BTC隔离、底层参数生效、趋势拒绝、未来后缀截断及诊断不消费状态。8个费用/账本/序列化用例亦通过。

费用：主实验0费率；独立压力场景每边0.05%（明确假设，不是核实用户账户费率），逐笔重跑余额路径。未计资金费，因此不称真实账户净收益验证。发现原部分减仓报表非零费率时只分摊剩余数量开仓费，压力场景仅纠正journal分摊为完整初始数量，实际cash扣费和交易行为不变。期末cash、完整已平仓净收益、未平仓费用/部分退出以及MTM强制核对。

所有年份每币500独立起算。2020仅02-16至年底；2021—2025全年；2026仅1—10月；NOV为11-01至11-13 08:00北京时间，独立500起算。2019未验证。年度已多次查看，不是全新样本外。各组都跑全部可验证年份，不依据早期收益筛选。

原生15m/1m先读本地缓存，检查时间网格/预热和当前SHA；ZIP官方校验和沿用获取时已保存证据，不虚称本轮重新下载所有K线。新增订单按新生成全部信号遍历官方原始逐笔，不用旧交易结果代替行情；原始逐笔下载仍核对官方SHA。不混用现货/Gate。

只保存月末断点（账本及分钟权益前缀），代码指纹变化拒绝复用。官方临时网络失败最多3次进程重试，断点后恢复；保留失败日志和各月进度。严禁用不利/有利先到OHLC替代逐笔。

运行：
```sh
/workspace/.venv-btc-eth-original/bin/python outputs/eth_density_experiment/validation32/tests.py
/workspace/.venv-btc-eth-original/bin/python -u outputs/eth_density_experiment/baseline_driver.py > outputs/eth_density_experiment/baseline/run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/eth_density_experiment/tests.py
/workspace/.venv-btc-eth-original/bin/python outputs/eth_density_experiment/financial_tests.py
/workspace/.venv-btc-eth-original/bin/python -u outputs/eth_density_experiment/launch_after_baseline.py > outputs/eth_density_experiment/run.log 2>&1
```

现金路径是实际逐笔价格上的模拟全量触价成交，非实盘可成交保证。归一化按相同1000USDT初始名义作归因，不视为可执行账户。不得用BTC未来盈利或成交事实决定ETH当前信号。
