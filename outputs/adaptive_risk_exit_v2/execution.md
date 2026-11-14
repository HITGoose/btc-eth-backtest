# 实际执行记录

环境：/workspace/btc-eth-backtest；Python /workspace/.venv-btc-eth-original/bin/python（3.12）。2026-11-14启动本实验。原GitHub源码由已认证连接恢复在此目录，当前目录没有.git，不能声称本次已提交或推送；按85个Git blob清单验证保留原文件。

## 执行命令

```sh
df -h /workspace
free -h
/workspace/.venv-btc-eth-original/bin/python -m py_compile outputs/adaptive_risk_exit_v2/worker.py outputs/adaptive_risk_exit_v2/supervisor.py
/workspace/.venv-btc-eth-original/bin/python -u outputs/adaptive_risk_exit_v2/supervisor.py > outputs/adaptive_risk_exit_v2/run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/adaptive_risk_exit_v2/tests.py
/workspace/.venv-btc-eth-original/bin/python outputs/adaptive_risk_exit_v2/collect.py
```

调度器启动4个进程：worker.py 2024 BTC、2024 ETH、2025 BTC、2025 ETH。每任务同时执行CONTROL与V2，共用该币当天官方逐笔，结果分别写CONTROL/DYNAMIC文件；DYNAMIC在本目录明确为V2，不能当作其他目录旧动态版。

## 网络恢复及已知限制

- 首次常规沙箱通过urllib访问公开币安逐笔CHECKSUM：PermissionError [Errno 1] Operation not permitted；这是沙箱套接字限制。
- 按云端环境技能的网络指引，以require_escalated恢复同一只读下载，返回HTTP 200。随后逐笔回测也在同一已授权执行模式运行；无账户密钥、无交易下单。
- 开始时磁盘可用约5.8GB，内存可用约9.1GB，4进程；每天ZIP校验、解析后删除，缓存最多2个交易日。
- git status返回not a git repository：此目录是原源码恢复快照。原文件完整性由source_restore.json的Git blob哈希核对，不冒充Git checkout/push。
- 每任务状态、进度和错误在YYYY/ASSET/status.json、progress.json、failure.json（如有）和run.log。未完成的任务不能称历史验证通过。

数据来源：https://data.binance.vision/data/futures/um/ 原生K线和daily/trades。逐笔原文件、官方SHA256、ID跳号及时间戳记录在raw_sources.json，原生K线与逐笔不符记录candle_tick_disagreements.json；不根据K线高低删改官方逐笔。

四个任务均以退出码0完成，collector以退出码0完成。统计已保存comparison.csv/json、monthly.csv（72行）、audit.json、report.md；4任务及85个原Git blob完整性检查通过。合成金融回归测试另存tests.py/test_results.json；合成测试不代表真实历史结果。

执行测试：32/32通过（16项金融行为＋16组全逐笔/优化事件对照，每组90分钟约7411笔合成成交）。覆盖多空、连续闭合K线、预算随余额增长、数量上限、反弹不追加、跳价与阶梯止损优先。初版测试读CONTROL journal缺失partial_fills字段导致8项框架错误，已仅修正测试读取方式后全部通过，未为此修改策略或参数。

收集实际命令：`/workspace/.venv-btc-eth-original/bin/python outputs/adaptive_risk_exit_v2/collect.py > outputs/adaptive_risk_exit_v2/collect.log 2>&1`，返回0；audit.errors为空。V2两年的开仓与最终止损时间/价格/档位均逐笔与原ER匹配，仅减仓执行及后续数量/余额变化。
