# 复跑

起点：060e12a18bc745a7c98e5270f2e37b0c759cc5ff。独立分支只添加本目录和入口，不合并main。

在包含本提交、原本地模块及已有币安15m/1m缓存的仓库运行。原框架使用固定路径 `/workspace/btc-eth-backtest`，Python3.12环境 `/workspace/.venv-btc-eth-original`：

```bash
cd /workspace/btc-eth-backtest
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/checks.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/pipeline.py > outputs/a_atr_initial_stop/pipeline.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/report.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/verify.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/make_report.py
```

指定币年续跑：

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/a_atr_initial_stop/runner.py 2025 ETH
```

完成且指纹一致的账户跳过；数据、代码或配置不一致拒绝续用，不强制忽略指纹。每个费用场景完成即保存完整账本与分钟权益；该币年全部完成后写status。若中途中断，保留完成场景，不需重跑其他年度。未完成场景从该年度本币起点恢复，禁止凭空构造持仓状态。

执行链：runner → adaptive_density_floors/experiment.py的Native/Cache → adaptive_density_control/signals.py原A信号及engine.py原CONTROL → 本目录atr_engine.py局部子类。没有调用V2、提前退出、挂单撤单或此前波动率减仓。

数据缓存与SHA、预热和时间范围见runs/*/*/input.json；原基准复用SHA见baseline_reuse.json。原行情缓存不在本提交重复打包，不联网下载，也不把已有结果当作新增路径的行情。

原价规则nearest_tick确定P，再冻结信号ATR、d、L。初始有效ATR止损按P*(1-side*d)精确表达；后续阶梯仍为原价格刻度及cap5。指标无效回退原2%刻度规则和3倍，计数保留。手续费预留沿用原Sizing配置（本基准fee_reserve=False），不更改数量规则。

原账本、源码、main不改；报告中阶段合计为独立区间USDT相加，没有跨年复利或跨年拼接回撤。两费用场景均完整账户回放，不能把费用加回旧账本代替。
