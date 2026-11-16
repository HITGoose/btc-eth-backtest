# 实际执行记录

工作目录 `/workspace/btc-eth-backtest`，Python3.12：`/workspace/.venv-btc-eth-original/bin/python`。

1. 编译runner/features，单独实际运行 `python outputs/a_volatility_sizing/runner.py 2020 BTC train`，成功后由pipeline兼容指纹复用。
2. `python outputs/a_volatility_sizing/checks.py`，ATR初始化、递推、排除当前的2880根历史、未来数据不影响前缀、clip及回退检查通过，保存feature_checks.json。
3. `python outputs/a_volatility_sizing/pipeline.py > outputs/a_volatility_sizing/pipeline.log 2>&1`；三进程上限，六个训练账户完成后自动freeze，最终14个币年任务完成。逐任务真实命令和输出在logs。已完成且指纹兼容的训练ZERO不重复回放。
4. `python outputs/a_volatility_sizing/report.py`，仅读取完成账本；最终126个分币/组合年度行、5400条成交记录（含六个策略/费用组合）、84份账户对账。
5. `python outputs/a_volatility_sizing/verify.py` → VERIFIED84；`python outputs/a_volatility_sizing/make_conclusion.py`生成RESULTS.md。
6. 独立Git分支从060e12a建立；只加入新目录与入口，不合并main，不改旧数据和源码。

本轮没有下载行情、没有新增回测失败项。原缓存文件和复用账本SHA逐项核实；现有行情不随新提交重复打包。report在执行途中生成过部分进度表，最终交付均由全部完成账本重新生成，没有把进度表当全期结果。
