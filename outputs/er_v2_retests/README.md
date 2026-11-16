# ER＋V2历史优化逐项复测：Colab计算，Codex不跑年度

先看EXPERIMENT_INVENTORY.md/CSV。26份历史源码已从认证GitHub精确提交读取，SHA和来源见source_manifest.json，不从A/B/C/D变量名推断规则。

本套固定所有费用0、资金费0、退出滑点.02%、BTC/ETH各年度500。保留原ER与BoundedAdaptive V2。2026按用户追加范围从Jan1连续至北京时间Nov16 00:00前（包含Nov15全天）；年度和11月不再拆分。缺逐笔不换OHLC，2025仅原授权S_ALL。

## 去重、复用和导入

- 原基准2020—2025共12个账户直接加载。2026旧Jan-Oct不是全段，默认只有旧结果JSON，没有可证明兼容的完整V2状态，因此新区间2账户需重新从Jan1回放；本实现不拼接估值、不清空Nov1状态、不忽略旧断点指纹。
- 53个已有同口径非基准账户保存在reused/，逐账户原SHA、参数/现金/权益检验和底层基准逐笔/分钟一致证据见reuse_manifest.json、reuse_baseline_checks.json。ETH各版本BTC引用基准，不重复计算。UNCAPPED/ETH025/旧B是REF别名。反弹三组合只用两种单币路径。
- 用户已完成FAIL_EXIT和VOL_SIZE：只从正确ef0b074实现结果导入，必须匹配指纹34e03cf...、原生数据SHA、完整区间、零费、逐笔、现金及末分钟权益。旧c6d23ea错位输出拒收。这里没有新的已完成用户附件，不能谎称已导入。Colab先恢复Drive旧ef0b074结果，或在第三格上传正确results_for_review.zip。缺失早年导入保持WAITING，不重算。2026若仍是Jan-Oct则只保留旧结果，不视为完成Nov15新范围；这一区间变更是必要计算例外。
- 固定低杠杆必须从上述正确V2 VOL_SIZE 2020—2022六账户的成功提交目标L冻结，不用旧无V2值。没有导入则阻塞该项，继续其他独立项。

## 顺序与训练

运行pipeline.py自动按11项顺序完成可运行部分，每阶段输出简短组合年度表、保存统一CSV/REPORT和Drive备份，再进入下一项。每个训练项只用原3候选，训练2020—2022组合年度mean(return−DD)，按原tie-break固定顺序冻结B/C，之后才评估2023—2026；D只在B/C两赢家中按相同训练评分选源。没有扩展网格。非选中候选后续年份显示NOT_SELECTED_FROZEN_TRAINING，训练未完成为AWAITING_TRAINING_FREEZE，不捏造结果、不把训练最优称样本外。

所有互相独立的账户在同year/asset进程内共享加载的原生行情及逐笔cache；不同任务进程隔离全局费用/数据变量。自动按CPU/RAM决定并行（预留每任务约6GB、最多4进程，可调低），不使用GPU改写。两策略同时同币持仓仅属于不同实验账户，绝不在单一策略叠仓或加本金。

每个完整UTC日保存带策略源码、输入和信号/冻结参数指纹的原财务checkpoint，原子写完复制Drive。已完成匹配结果跳过；不兼容指纹直接拒绝。用户中断Notebook第五格会终止其进程组；恢复同提交同结果目录继续。不会自动删除原缓存。

## 最小验证

Codex只执行短区间、多独立书8小时与小型边界检查，不运行本pipeline或任一年度。短REF分钟曲线必须与原ER_V2_REFERENCE同时间片完全一致；ATR初始风险/stop不放松、CAP5/TRAIL8保留V2、撤单时序及现金、双币EXTRA1x为定向机制检查。原策略源码不修改。

## 运行环境变量及入口

```
BTC_REPO_ROOT=/local/repository
BTC_DATA_ROOT=/local/native_and_raw_cache
BTC_OUTPUT_ROOT=/local/new_results
BTC_DRIVE_DATA=/mounted/drive/market_cache
BTC_DRIVE_RESULTS=/mounted/drive/retests_results/CODE_PREFIX
BTC_IMPORT_ROOT=/local/corrected_prior_results
# 可选BTC_IMPORT_ZIP=/local/results_for_review.zip
python outputs/er_v2_retests/pipeline.py
```

计算只用本地磁盘，Drive仅恢复/备份。公开档案CHECKSUM有效缓存不会重复下载；缺失才下载。2026扩展只获取缺失官方daily klines，并逐日获取实际活动逐笔。取不到会记录具体失败并继续其他年份，收益不填0。

## 输出

- EXPERIMENT_INVENTORY.md/CSV、source_manifest.json：来源、准确规则、原基准、移植位置、别名去重。
- annual.csv：各版本×年×币及组合，含净收益、分钟DD、已平数、已平净额/未平贡献、亏损、最大单亏及账户差额。
- period_summary.csv：训练/后段/七期独立合计、跑赢/回撤增减年数、年度及匹配交易集中度、四类描述标签。未齐不排名。
- trade_matching.csv、account_reconciliation.csv：按side/signal_close_ms配对，实际USDT及每1000实际初始名义；信号删除与有持仓证据的占用区分；无法确定订单/资金原因不猜。已平差额加未平贡献差额必须与账户差额对账。
- training_scores.csv、freeze_*.json：所有原网格训练分数及冻结证据。
- incomplete.csv、import_status.json、stage_logs/：哪些待导入/待跑/失败；失败继续其他项。
- REPORT.md、retests_results_for_review.zip：手机报告与返回分析包，不含巨大原行情/执行pickle。所有年度历史已反复看过，不称全新样本外，不按年份挑不同策略拼曲线，不自动混搭赢家。
