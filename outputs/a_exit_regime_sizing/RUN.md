# 固定矩阵复跑
Python3.12，原requirements与既有币安USDT永续15m/1m缓存。源提交36f338e0b5bbef38b1465f18fda8ce6c8045adbc，独立分支codex/a-exit-regime-sizing-20261115。
```
python outputs/a_exit_regime_sizing/pipeline.py
python outputs/a_exit_regime_sizing/checks.py
python outputs/a_exit_regime_sizing/report.py
python outputs/a_exit_regime_sizing/finalize.py
```
单个币年：`python outputs/a_exit_regime_sizing/runner.py 2020 BTC`。
每个币年四组×三费率，合计168账户；uncapped两费用经指纹/信号/数据一致核对后复用28账户，其他140新账户实际完整回放。pipeline最多三进程并行；每个进程内部四组严格使用同一个core信号对象、相同行情及原执行器。
日志pipeline.log、年度_币种.log及execution_status.json保存实际执行结果。缓存或金融代码指纹不匹配时拒绝复用，不能拿旧手续费结果简单加减。固定A新基准是5档封顶，并非以前报告的uncapped A。
Settings和RegimeOverlay、入场信号均不修改；仅实例的exit_policy或传入原执行器的size_multipliers有变化。没有修改work原源码、LADDER_CAP常量或main，没有宏观过滤、V2或动态带宽。
120h状态仅从signal_close_ms之前或当时已闭小时获取，0.10原阈值不改。权重1.3/0.7预先固定，并未用未来全年数据归一化；实际风险是否接近由exposure.csv核算，而不是承诺。出场与数量改变实际成交/占仓，入场信号不删不加。
均为1m OHLC假设执行，非逐笔。2020仅2月16日起、2026仅1—10月。净盈亏含期末未平估值，未预扣未来平仓费，已平净额/现金/未平浮盈另外保留。各年独立重置，合计只相加USDT，回撤取最差年度。
MAKER_002_SIDE统一每边0.02%是假设，不代表已核实用户费率，也不保证止损/主动退出可获得Maker费率。资金费0，退出不利滑点0.02%。不增加真实账户或资金。
