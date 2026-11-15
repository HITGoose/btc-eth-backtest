# 复跑入口
Python3.12，沿用原requirements和既有币安USDT永续15m/1m缓存，不下载逐笔或研究资金费。
```
python outputs/a_macro_cooldown/pipeline.py
python outputs/a_macro_cooldown/checks.py
python outputs/a_macro_cooldown/report.py
python outputs/a_macro_cooldown/finalize.py
```
单个币年可用：`python outputs/a_macro_cooldown/run.py 2020 BTC`。
实际执行：pipeline三进程并行完整回放56个新账户；各年度每币500、独立起算，ZERO及ASSUMED_005_SIDE；原A经指纹/信号/数据一致核对后复用28账户。执行日志为pipeline.log及年度_币种.log，状态execution_status.json。
重跑已有结果仅在指纹正确时跳过；参数、日历或代码改变须新目录，不能误用旧账本。
report从每个完整币年的status及金融账本生成年度、合计、逐笔配对、接续交易和账户差额对账；finalize在全量结束后附中文结论及文件SHA。再次生成最终报告应先report再finalize，避免重复追加。
calendar.json包含官方URL、时区、UTC毫秒、原响应SHA和紧急会议声明头部。常规事件与前轮日历相同，仅按官方实际时间补入2020年3月两次紧急利率决议。日历已保存，不需要联网。
OHLC执行与上轮完全一致：假设每分钟0/20/40/59秒依次打印O/H/L/C，按5秒相位2轮询；不是实际逐笔或严格最坏/最好界。2025不加载冲突逐笔档案，不声称官方逐笔修复。资金费0，假设手续费不是用户真实账户费率。没有改变原挂单/止损/仓位规则。
