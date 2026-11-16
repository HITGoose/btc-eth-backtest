# 复跑入口

锁定起点：060e12a18bc745a7c98e5270f2e37b0c759cc5ff。策略和入场源码不修改，只新增本目录。

在已包含本实验提交、原依赖模块和行情缓存的仓库运行（现有驱动使用 `/workspace/btc-eth-backtest` 路径）：

```bash
cd /workspace/btc-eth-backtest
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/checks.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/pipeline.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/report.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/verify.py
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/make_conclusion.py
```

`pipeline.py`先运行六个训练账户，再验证/写入不可变 `FREEZE.json`，然后运行剩余新账户，并硬链接经核验的A_BASE。兼容结果直接复用；代码/数据指纹不一致时拒绝续跑。每项命令与结果保存在 `logs/` 和 `pipeline.log`。

指定断点例：

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/a_volatility_sizing/runner.py 2024 BTC final
```

不要手改FREEZE或忽略指纹。原账本来源 `outputs/a_exit_regime_sizing/runs/`；每个账户的 `input.json`记录缓存路径、SHA、分钟起点和区间，`baseline_reuse.json`记录原账本SHA。新提交不重复打包原行情。

执行链：本目录runner → adaptive_density_floors/experiment.py 的Native/Cache → adaptive_density_control/signals.py的A完整信号、engine.py的原CONTROL出场 → 原work交易模块。所有组无V2、无提前退出、无撤单实验；退出fixed且cap=5。5档为锁利上限，不是盈利5%直接平仓。

统计：report.py只读取完成的账本，不重跑账户；annual.csv含分币种和同分钟合并组合，exposure.csv含空仓分钟；period_summary.csv是独立年度合计、最差年度回撤，不拼接跨年回撤。trade_matching.csv按币种、方向、signal_close_ms精确匹配，包含期末未平仓贡献；downweighted_trade_matching.csv供减仓归因。

本轮资金费明确设0，不是未知资金费已补齐。ZERO与每边0.02%假设费率分别完整回放，费用不通过事后加回。执行为1分钟OHLC既有合成路径，不是原始逐笔或实盘排队。2025也使用该K线口径，不沿用其他RAW实验的异常敏感性验证结论。
