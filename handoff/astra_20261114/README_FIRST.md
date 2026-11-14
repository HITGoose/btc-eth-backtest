# 给Astra：先读这里

交接对象：BTC/ETH自动交易规则复刻项目，当前原ER入场与自适应减仓V2。目标是拟合参考机器人规则，不是历史收益寻优。用户已要求停止自动迭代，发现问题先指出；不得擅自改ER、均线或2%绝对距离。

1. 先读本目录STRATEGY_CURRENT.md，明确源码实际规则与目标机器人未验证规则的区别。
2. 修正版Git状态：本次已发布在独立分支codex/adaptive-v2-astra-20261114，main保留。此前同步前状态如下：已通过授权GitHub连接确认Private仓库HITGoose/btc-eth-backtest可读、仅main分支；main的outputs/adaptive_risk_exit_v2/worker.py返回404。本地没有.git，只是已恢复源码快照。详情git_status.json。本分支包含修正版及依赖；Git网页查看指引见仓库根ASTRA_REVIEW.md。
3. 历史结果：本目录ANNUAL_RESULTS.csv与RESULT_INDEX.md；2020/2026不是全年，2019未验证。不要强制补齐全年或用现货替换永续。
4. 当前代码不是独立单文件包，跨outputs多个历史模块动态导入且ROOT写死。完整依赖源码已打包，目录须保留；Git克隆先运行verify_github.py校验；离线ZIP用verify_bundle.py校验，不要直接重跑原main实验入口。
5. 现有测试：outputs/adaptive_risk_exit_v2/test_results.json（32项）、audit.json；扩展audit.json；独开审计audit.json。合成测试不是历史数据真实性证明。
6. 单币独开931个案例/版，原ER和V2分别各518盈利、413亏损；两版不能相加当作独立交易样本。手机筛选页与Excel在outputs/cross_asset_entry_audit。
7. 11月13日08:00之后至14日尚未验证，不能说没有开仓。11月独立500起跑，与年度余额不连续。

## 搬迁及运行

代码要求Python3.12。原requirements.txt保持不动；导出Excel额外用openpyxl，环境版本见environment.json。

当前驱动ROOT多处为/workspace/btc-eth-backtest，data位置也分散。建议在同一路径解压，或由Astra先明确规划根路径配置化并用旧交易/32项测试回归。不要只修改一个ROOT后认为全部可用。

```sh
cd /workspace/btc-eth-backtest
python handoff/astra_20261114/verify_github.py
python -m pip install -r requirements.txt
python outputs/adaptive_risk_exit_v2/tests.py
```

上述pip/测试命令是接手后可执行命令，本次交接没有重跑回测；验证脚本本次实际执行。

大体量分钟权益npy、分钟原始输入、原始逐笔ZIP和下载缓存未打包，源档案URL/SHA256清单保留。直接运行收益collector可能因缺npy失败，不能把缺文件当收益0。重新获取数据后必须检查完整时间网格、时区和预热。

Git后续同步可保留原main，在独立分支提交V2及必要依赖和交接文档；不要把原始行情/全部npy随意提交Git。本次用户已明确要求同步，修正版推送到独立分支，不覆盖main，不自动通知任何人。
