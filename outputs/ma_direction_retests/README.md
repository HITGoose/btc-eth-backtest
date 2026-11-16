# 旧六线方向分类版：直接移植既有优化

不新增ER/MA基准比较，不把ER优化成绩移作MA成绩。基准使用f8aa6a9登记的MA_DIRECTION_REFERENCE：原SMA20/60/120及EMA20/60/120相对3根前的严格方向，全上up、全下down、其他range；原完整入场及2%绝对距离；无V2、2%硬止损、uncapped原阶梯。不是MA5/10/30/60/120/250版本。

直接搬同一11项固定优化及原训练网格，每项默认单独作用于该MA基准。提前退出/波动减仓也重新计算，不能导入ER＋V2的利润或断点。uncapped是MA REF别名；ETH范围、双币范围、BTC确认/CORE替换、补充单比例保持历史实验定义；CORE改为MA自身完整信号，BTC确认查同根BTC完整MA信号，不查后续成交或盈亏。反弹续跌中的down改由MA分类状态供给，原形态和其他条件不改。

所有账户的实际MRO为Book→VariantControl→CostControl→PriorityControl→Control→Ledger→AuditSleeve→ObservedSleeve→InitialStop→Sleeve；不含Dynamic、BoundedAdaptive或VariantSleeve。共享原金融循环与成本/观察方法，不依靠改profile冒充无V2。每个结果断言没有V2或部分退出事件。

## 顺序

1. MA提前退出、波动减仓；先完成2020—2022，再按成功提交目标L算术均值冻结MA自己的L_fixed，运行固定低杠杆及后段。
2. ATR初始止损+6%计划风险上限；3. 失效挂单撤销；4. cap5、uncapped别名REF、原trail_from_8pct；5. 原120h ER方向仅作1.3/.7下单权重，不改变MA入场分类；6. 仅ETH密集.25/.30/.35；7. 原三组滚动分位数；8. 原三组ATR归一化；9. MA CORE优先+自适应补充1x；10. ETH BTC确认、CORE优先、两者结合及1/.5/.25补充比例；11. 反弹续跌仅BTC/仅ETH/双币组合（只算两种单币路径）。

7/8均只用2020—2022原评分mean(组合return−年度分钟DD)，同原tie-break；各自冻结赢家后评估2023—2026，不沿用ER赢家。第9项仅在两赢家间按原评分定源。不新增指标、参数或临时组合。

## 数据及区间

2020北京时间2月16日起，2021—2025全年；2026 Jan1连续至北京时间Nov16 00:00前，包含11月15日全天，11月不重置。各年各币500、原3x、零手续费/资金费、退出滑点.02%。币安USDT永续原生15m信号与官方逐笔，5秒相位2，触价模拟代理；不换OHLC。2025仅原授权S_ALL及异常标记。

仅复用MA自身2020—2025十二个基准账本/分钟曲线，均无部分退出。2026需补自身延长区间基准。市场输入同原登记数据，SHA必须相符；已有行情缓存复用；不复用53份ER优化账本。截图2020原112.88%账本窗口仍缺，不按数字反推规则，本项目使用已找回且统一Feb16起的MA账本，不另作两基准比较。

## ZIP问题一起处理

新MA入口在本地checksum不匹配时，仅下载一份新候选、核官方前后CHECKSUM/基准已知SHA和ZIP CRC，全部通过才将异常原件改名quarantine保留并原子替换缓存。仅上述两个已知ZIP若本地精确匹配原基准SHA且CRC正常，可继续使用原冻结快照，并明确记录不匹配最新版；若原快照缺失，保持UNVERIFIED。其他文件不放宽。见ZIP_VERSION_NOTICE.md。

`cache_doctor.py`也可独立用于旧ER运行时；resume_er_cache.py可不改原源码地安装只读SHA快照适配器并恢复原⑤。它只用标准库，不修改原ER代码/参数/账本/断点；必须等原⑤结束，再在原运行时运行，先inspect，确认后repair。提供ZIP_RECOVERY.ipynb，其中的独立代码格可复制回原Notebook；单独打开一个新Colab运行时不能读取旧运行时的/content缓存。恢复前检查coordinator.lock，仍在跑就拒绝修改。修复后重跑原⑤，成功账户跳过、失败账户用兼容日断点恢复。

当前远端Colab的坏ZIP尚未实际读取/修好；这里只完成工具及最小模拟故障验证，不声称用户文件已恢复。结果ZIP导出会作CRC验证、输出大小/SHA并复制Drive；另提供REPORT.md和各CSV独立下载格。ChatGPT“连接已失效”并不等同ZIP损坏，不能由缓存工具保证解决上传服务问题。

## Colab

新Notebook和独立运行时；不要在正在跑的ER Notebook中替换源代码。市场Drive缓存目录可共享，但计算前复制到本地。结果/断点使用新的MA专属前缀，绝不复制ER结果或checkpoint进来。CPU/RAM约束并行，同币同年同任务共享逐笔，各账本独立。每UTC日保存原指纹checkpoint及Drive备份；每项显示年度表并继续。可停/续跑，无需模型持续读日志。

Codex仅做短区间和针对性机制检查，不在这里运行年度矩阵。Colab输出annual.csv、period_summary.csv、trade_matching.csv、account_reconciliation.csv、change_reason_summary.csv、training_scores.csv、freeze_*.json、incomplete.csv、REPORT.md及ma_retests_results_for_review.zip。七期是独立损益之和，非跨年复利；历史已见，不称新样本外，不按年度拼赢家，不自动部署。
