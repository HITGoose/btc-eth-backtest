# 基准整理与必要对照复跑
Python3.12；工作目录/workspace/btc-eth-backtest，现有框架使用此绝对路径。

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/audit.py
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/dispatch.py > outputs/baseline_registry/dispatch.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/audit.py
```

指定断点：
```bash
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/compare_runner.py 2026 BTC
```

audit只读原14账户，不回放、不修改原文件，核对源码与133提交、实际V2事件、源行情SHA、现金与分钟估值；compare_runner只补缺失MA账户。新MA规则直接取原p.prepare的MA映射，原无V2控制基类，不按截图反推。

统一使用ER_V2的原raw Market、polled quotes和financial event generator；MA不启用V2，以保留候选各自出场。零手续费、零资金费、退出滑点0.02%，无新情景。

每天checkpoint以原segment机制保存策略／数据／账户指纹，恢复时严格核对，不忽略指纹。2025ETH只用已授权S_ALL，原白名单／原文件／原审计数组均验证，不全局关闭strict。

优先复用有效本地逐笔档案，缺失时查询同源官方HEAD与CHECKSUM、按原下载流程获取日档；日志data_queries.jsonl记录实际URL、大小、磁盘和时间。官方文件存在不等于本机缓存存在；旧RawCache会在读取后删除本地日ZIP，所以旧账本不代表磁盘仍有原始逐笔。

磁盘需容纳日ZIP、解析和checkpoint结果，下载前按实际Content-Length检查，另留32MiB checkpoint／结果余量。现已改为单进程顺序读档，已发生的磁盘失败会从原断点串行重试；不足则保留断点。**不删除用户原缓存／原账本，不换K线，不跳过异常日。** 原始逐笔读取遇到非白名单冲突照常拦截。新增下载仅限本候选账户需要的日档。

comparison.csv只列完整同引擎账户；没完成的不填收益。historical_ma_2026.csv仅历史证据，不能填入统一结果。account_reuse_manifest.json记录复用路径及SHA。无V2旧优化的代码及结果留在原分支，不在本分支重放。

## 已发生容量／进度日志故障的定向恢复

```bash
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/recover_remaining.py
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/recover_transport.py 2025 ETH
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/audit.py
/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/report.py
```

恢复适配器只将下载余量从32MiB降为16MiB（串行），并增加只读sources进度日志委托。原Strict RawCache及ScenarioCache.load源代码SHA、代码／数据指纹与checkpoint严格核对，金融执行不变。独立适配器指纹与原失败、原checkpoint SHA保存在各账户transport_recovery.json；已完成账户直接跳过。仅删除经Git blob SHA验证且仍可从现有Git对象恢复的冗余临时base64上传副本，保留原数据和账本。
