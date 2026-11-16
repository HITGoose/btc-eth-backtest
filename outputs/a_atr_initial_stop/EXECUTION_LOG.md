# 实际执行记录

Python3.12环境：/workspace/.venv-btc-eth-original；工作目录/workspace/btc-eth-backtest。

1. 搜索/workspace未发现AGENTS.md，读取原CONTROL/原挂单/原秒事件执行链及基准协议。从060e12a建立独立分支codex/a-atr-initial-stop-20261116。
2. 编写并执行checks.py。正式金融回放前，非零费同事件成交/止损对账检查发现复制visit函数捕获旧全局FEE，改为读取该账户同值self.fee。修正后全部必要检查通过；没有错误费用的年度结果进入正式回放。
3. 实际命令：python outputs/a_atr_initial_stop/pipeline.py > outputs/a_atr_initial_stop/pipeline.log 2>&1。三进程上限，14个币年任务逐个运行ZERO和MAKER_002_SIDE；完整28个新账户完成。每项真实命令和期末值在logs/。execution_status.json全部returncode=0。
4. report.py只读取已完成结果。过程中修正长期持仓报告字典重复键和空样本均值格式化错误；没有修改金融执行源码、参数或重跑已完成账户。最终重新生成全部84个年度行和4148条成交记录（含期末未平），最终56份账户均对账。
5. verify.py核验：原信号一致、源文件SHA与基准不变、ATR时间对齐、止损价格、数量取整/最低名义、计划风险≤6%、阶梯不放松及账本闭合。最大现金残差5.684341886080801e-13 USDT。两费用场景按信号匹配的开平身份/时间/价格一致，数量与现金分别回放。
6. make_report.py生成中文结论与宽止损明细；不根据结果重新调参。

本轮没有下载行情，没有账户回放失败项，没有新增实验组。2020按2月16日起、2026仅1—10月；旧A_BASE复用，不将其说成本次重新回放。原数据/执行标签按基准保留；所有实际结果为15m信号＋1m OHLC假设执行。
