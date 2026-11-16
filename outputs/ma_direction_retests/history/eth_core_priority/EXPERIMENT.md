# 固定五组：ETH新增信号BTC确认及CORE优先

锁定源提交01937b2d4a1306ab211a9c1853bda285258c2853。独立分支codex/eth-core-priority-btc-confirm-20261114。从ETH_DENSITY_EXPERIMENT.md读取旧报告、ISSUES、STRATEGY_CURRENT。完整远端树无AGENTS.md；本地无AGENTS。执行Python及文档与锁定源一致，10个旧CSV仅换行不同；62个无关历史输出本地未获取，见source_check.json，不宣称完整checkout或改变原历史结果。新代码只写本目录，不合并main。

B：.25 V2；D：.30 V2；G：.30 V2，仅EXTRA需同根BTC完整.25信号同向；H：.30 V2，CORE优先；I：同时启用。BTC所有版本都是.25 V2独立500。BASELINE use_entry_crosses=False，原六SMA/EMA20/60/120、ER、过渡期暂停、当前宽度.50、2%绝对距离、挂单与止损参数保持。没有.35或其他阈值搜索。

CORE/EXTRA由同一闭15m上两套隔离完整策略信号生成，包含底层候选和stacked过滤；两次独立构造回踩状态，不从旧交易结果分类。BTC过滤只查同timestamp指标信号，不查账户、成交或未来盈亏。CORE不受过滤。

CORE优先在+10秒明确时钟事件处理。该时刻真实print先处理，随后处理CORE请求；沿用真实print先于poll的约定。EXTRA订单撤单后立即按CORE原ref提交；已有EXTRA持仓创建单次锁定请求，下一笔时间严格大于请求的真实print先查原止损，否则按真实价加0.02%不利滑点全退。主动退出先于同一print上的可选V2减仓；已经触发的原硬/阶梯止损始终优先。确认退出才提交CORE，原信号close定限价，有效期从实际提交起60分钟。新单不能消费退出print，下一个成交事件可成交，包括同微秒但不同真实trade ID的新事件。未触发优先分支时沿用原严格stamp>submit_at普通信号边界。

已有CORE单/仓不替换；等待中的CORE请求锁定第一信号，后续信号不覆盖。单币只有一张挂单或一个持仓，替换请求没有额外敞口。位置来源标签随原入场保持；提前退出不把EXTRA改成CORE。同向与反向相同流程。

先复跑32项原测试＋新增边界测试，2024 B/D及2025 B逐笔、每分钟权益路径和期末权益与旧实验精确比较。2025 D另试，已知数据冲突不能用它阻止其他组尝试。随后运行其余所有区间/五组/两费用。新增主动单必须读真实逐笔，旧流水仅用于B/D对照及归因。BTC同策略同独立账本只执行一份B，各组重用相同BTC结果，不作为独立样本相加。

数据仅币安USDT永续原生15m/1m及daily/trades，下载核对官方CHECKSUM，严格ID递增、时间戳规则、无OHLC兜底。先检查缓存。每区间各币500，余额×3，步长和minimum不变。ZERO零费；ASSUMED_005_SIDE每边.05%明确假设，非已核实用户费率。开仓、V2减仓、主动平仓和再开仓全部计费，journal和cash逐笔对账；资金费未计。模拟触价全量成交不是实盘成交保证，回撤是分钟末权益口径。

2020从02-16，2021—2025全年，2026仅1—10月，NOV独立11-01至11-13 08:00北京时间。2019未验证；NOV不拼接全年。2025严格保持8月29日冲突档案，各组单独尝试，失败保留断点和原档案，不能删行换平台。指纹不同拒绝复用账本，开发试跑另存development_run_before_shadow_snapshot，不计正式结果。

## 命令

在仓库根目录Python3.12安装原requirements.txt。缺原生缓存：
```sh
python outputs/eth_density_experiment/prepare_inputs.py --period ALL
```
执行：
```sh
python outputs/eth_core_priority/validation32/tests.py
python outputs/eth_core_priority/tests.py
python -u outputs/eth_core_priority/supervisor.py
python outputs/eth_core_priority/collect.py
python outputs/eth_core_priority/shadows.py
python outputs/eth_core_priority/audit.py
python outputs/eth_core_priority/package.py
```
断点恢复：同命令supervisor跳过已完成，网络失败最多重试3次；月末自有pickle+权益前缀是执行断点，只读取本项目自产可信pickle。2025每组独立：
```sh
python outputs/eth_core_priority/worker.py 2025 ETH --groups D
python outputs/eth_core_priority/worker.py 2025 ETH --groups G
python outputs/eth_core_priority/worker.py 2025 ETH --groups H
python outputs/eth_core_priority/worker.py 2025 ETH --groups I
```
真实数据冲突未修复前这些命令可能再次失败，不能把重试叫完成验证。

其余2020—23/2026/NOV的BTC完整信号和原生缓存SHA逐一匹配后，只复用不变的上轮BTC逐笔独立对照及权益路径（reuse_btc.py/reuse_manifest），不宣称是本轮重新播放。2024/25 BTC本轮新播放。ETH所有新路径从新账本真实逐笔执行，绝不以旧ETH成交路径替代。

2025若共享两费率任务遇到冲突，两种费用再分别尝试。isolate_cost.py只从同一冻结财务代码指纹的月末断点选出该独立子账户及完整分钟权益前缀，保留来源SHA、费率和subset manifest；没有从旧版本或不同代码指纹恢复，也未重算/拼接单笔收益。两账户没有共享资金或持仓，每次generator.step前恢复该账户费率。每个费率仍由自己的新逐笔路径决定是否再次受阻，不用一个费率的结果填另一个。

## 新Git克隆与当前云端差别

本次当前云端的B/D已逐笔及完整每分钟权益数组与旧实验比较。Git交付不含原始行情、equity.npy或可信pickle执行断点，只含报告、逐笔账本及来源；不能把带status的交付ZIP直接解压成可跳过的运行缓存。新克隆先按prepare_inputs恢复官方原生缓存，supervisor通过replay.py调用同一冻结worker，从旧period_*_ledgers.zip只读取对照JSON验证完整交易、期末现金/权益/状态；若旧参考NPY未提供，明确记为REFERENCE_NPY_NOT_PUBLISHED，不冒充逐分钟数组对齐。档案JSON从不供给新增订单价格。当前云端仍可直接运行原worker.py并享有全数组回归。新的直接单任务入口：
```sh
python outputs/eth_core_priority/replay.py 2024 ETH --groups BDGHI
```
执行引擎/规则未改；wrapper只补充缺少旧NPY时的独立对照验证。所有可验证年度必须有旧JSON对照，缺失则报错；2025 D旧全年本身UNVERIFIED，不能制造对照。BTC复用只用于当前有效缓存；新克隆无旧NPY时应由supervisor重新播放BTC，不运行reuse_btc.py强行跳过。

完整校验入口（不重新下载历史）：
```sh
python outputs/eth_core_priority/analysis_tests.py
python outputs/eth_core_priority/shadow_tests.py
python outputs/eth_core_priority/boundary_tests.py
python outputs/eth_core_priority/checkpoint_tests.py
python outputs/eth_core_priority/archive_reference_tests.py
```
原32＋入场/执行39＋归因8＋影子12＋完整循环边界8＋断点8共107项；另46项交付存档引用检查。合成/边界测试不是历史收益验证。当前云端全部可验证B/D闭仓交易、期末权益与每分钟数组精确对齐；Git新克隆缺参考数组时不冒充数组回归。
