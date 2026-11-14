# 原云端复跑与恢复

锁定源提交87f94d2e29b9832526e0aa35c0400c7ed7496805；只使用本独立分支，不合并main。运行目录固定为`/workspace/btc-eth-backtest`，冻结shared.py也采用该路径；Python3.12。资金费及逐笔官方网络访问需要运行环境允许公开币安域名。没有账户或API密钥。

本轮实际解释器：`/workspace/.venv-btc-eth-original/bin/python`（3.12.14）。在仓库根目录：

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/run_all.py
```

入口先校验缓存、执行原107项及新增合成/异常/资金费/边界测试、恢复官方资金费响应，再执行三组调度器；2025 ETH共用内存锁。完成的同指纹任务复用，未完成从同源码/数据/配置日末断点恢复。代码指纹或输入改变必须另建输出，不得忽略校验。资金费缺价场景仍未验证，仅运行明确标注的退路。

单个资金费或越价成交任务：

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/funded_replay.py 2025 ETH funded
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/through_replay.py 2025 ETH through
```

8GiB OOM的原两项任务恢复使用`recover_2025_memory.py`；不要与其他2025 ETH重任务并行运行此恢复脚本。正式run_all已统一互斥调度。旧失败日志保留，resource_recovery.json记录恢复返回码。

只重建只读报告与核算（已经完成金融回放后）：

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/report.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/audit_finances.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/fill_sensitivity.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/scenario_audit.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/cost_decomposition.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/conclude.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/coverage_audit.py
/workspace/.venv-btc-eth-original/bin/python outputs/extra_sizing_cost_stress/package.py
```

## 新克隆的数据前提

Git交付不含GB级原生数组、逐笔ZIP和可信历史分钟参考数组。native_input_manifest.json记录32个原生文件的路径/大小/SHA；原始官方逐笔来源、校验和与每任务input_provenance/raw_sources保存在audit_source_logs.zip。2025必须恢复原SHA异常ZIP及旧whitelist_manifest.json指定的解析数组，不能替换为交易结果JSON。原C0/C1回归还需要原实验的可信参考分钟数组；BTC_reuse_proof.json给出复用来源及SHA。原策略各级数据恢复入口保留在锁定源代码中。

因此这里只承诺已有云端同SHA输入可按命令复跑/恢复；不宣称下载本报告ZIP或新克隆仓库就已具备全部输入。缺文件应停止相应任务并恢复原来源，不能补零或跳日。大型分钟权益数组留在云端，equity_array_manifest.json记录SHA，单凭交易流水无法重建完整分钟回撤。
