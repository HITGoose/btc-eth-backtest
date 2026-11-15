# 运行、恢复与限制

Python3.12；当前实际环境3.12.14，沿用原项目依赖。代码根目录固定`/workspace/btc-eth-backtest`；外部机器需同路径或等价映射、原配置JSON及相同依赖。未部署收费服务，未启用系统服务。交易所行情无密钥；Git授权仅用于仓库提交，不进入交易程序。

## 当前冻结

最新运行清单FREEZE_WS_V3.json（UTC2026-11-14 23:30，北京2026-11-15 07:30）。前两份清单和失败采集不覆盖。每版本每币500空仓无挂单；主触价与越一tick独立账；不是增加同一策略本金。所有规则/比例/成本固定。第一根可生成信号的15m收盘在T0+15分钟，之前仅预热。

本次所有启动/错误/停止时刻，以forward_timeline.json、各run/status.json、原始压缩事件为准。源码已写好不代表长期常驻；对话结束后不承诺继续运行。

## 首次启动与外部常驻

已过去的T0不能在另一机器上新建空账户并自称从当时前瞻运行。若另开观察，先用同一固定策略创建新的只读采样清单：

```bash
cd /workspace/btc-eth-backtest
python3.12 outputs/funding_freeze_forward/new_external_freeze.py
```

命令打印新的清单路径和其后的15分钟T0；不改阈值/比例/成本。须在新T0之前启动（将下方路径换成打印值）：

```bash
mkdir -p outputs/funding_freeze_forward/forward
python3.12 -u outputs/funding_freeze_forward/ws_live_v3.py --manifest outputs/funding_freeze_forward/freezes/PRINTED_FILE.json --seconds 86400
```

可由已有机器的tmux/systemd/容器执行上述命令，不在此处授权创建付费云服务。需允许www.binance.com及经环境代理的fstream.binance.com WSS；程序支持已配置https_proxy/HTTPS_PROXY，不记录代理凭据。每天原始日志会增长，需预留磁盘/保存，不可删未封存日志；低于256MiB剩余会停止并留记录。当前版本遇到未解释零价NA、缺口、迟到价格可能影响止损或缺精确资金费，会暂停财务但继续采集；不能称其已经能够无人值守地产生90天完整净收益。

## 有序停止与恢复

向该清单run_id对应目录创建STOP_REQUESTED文件即可有序停止；目录内status.json和OBSERVATION_STOPPED事件记录实际截止。例：

```bash
touch outputs/funding_freeze_forward/forward/ws_closed_fix_1794699000000/STOP_REQUESTED
```

移走停止请求后使用同命令恢复原checkpoint。重启间隔在T0之后，默认保留OFFLINE_GAP_REQUIRES_REPLAY，不猜价、不假设无交易；即使空仓快照仍显示500，也不能写整段收益0%。代码/清单指纹不同拒绝复用。旧T0应检出对应implementation_commit，不能用新代码强行忽略哈希。

对已经封存的最新运行日志做确定性重放（不会补造缺失行情，也不会修改原账）：

```bash
python3.12 outputs/funding_freeze_forward/replay_capture.py outputs/funding_freeze_forward/forward/ws_closed_fix_1794699000000
```

输出为REPLAY_OF_OBSERVED_TAPE，不计作新增前瞻样本。若以后通过官方历史补齐断线区间，必须另存REPLAYED_AFTER_GAP并保留原缺口；本次/historicalTrades无密钥实测401，尚不能自行恢复被遮蔽的价格。不能用聚合成交或OHLC假装逐笔补齐。

## 报告与固定检查点

```bash
python3.12 outputs/funding_freeze_forward/forward_report.py
python3.12 outputs/funding_freeze_forward/report_stage.py
```

按清单的30、60、90天运行描述性检查，检查数据连续性、有效交易样本、成本、尾部风险及账本对账；不自动认定统计显著。不因几笔盈亏改策略。报表必须分清实时原始观察、回放、估算成本和未验证金融路径。I25的V2预算始终本币当前余额3%，没有为了小仓也减仓改公式。

## 历史复跑

先保留/恢复同SHA原生15m/1m和官方逐笔缓存，再运行：

```bash
python3.12 outputs/funding_freeze_forward/recover_marks.py
python3.12 outputs/funding_freeze_forward/history_supervisor.py
python3.12 outputs/funding_freeze_forward/report_stage.py
```

标记价ZIP/CHECKSUM及API补查保存mark_archives，已有有效文件复用。严格精确C2仍UNVERIFIED，OPEN/HIGH/LOW估算完整现金路径单列；不把一分钟开盘当精确结算价。旧C1及2024—2026引用结果不重命名本轮新跑；2025原数据异常标签不变。

## 封存包恢复

先解压artifacts/source_logs_configs.zip、funding_evidence.zip和forward_checkpoints.zip至仓库根目录（ZIP保留相对路径）。完整逐笔历史缓存按reference_proof及来源SHA另恢复。

```bash
python3.12 outputs/funding_freeze_forward/portable_capture.py restore outputs/funding_freeze_forward/artifacts/ws_closed_fix_1794699000000.capture_manifest.json outputs/funding_freeze_forward/forward/ws_closed_fix_1794699000000/events.jsonl.gz
```

便携日志恢复测试已通过415896行原始明文及哈希链核对。恢复后的gzip容器字节不同不代表事件改变；应对照manifest的明文SHA。零价消息、ID缺口和原生闭K线缺失尚未解决，财务仍UNVERIFIED。两币2026-11-14日档在最后查询均404，公开historicalTrades要求密钥（401）；以后可先复跑probe_daily_recovery.py检查日档发布状态，历史补齐必须另存REPLAYED_AFTER_GAP。
