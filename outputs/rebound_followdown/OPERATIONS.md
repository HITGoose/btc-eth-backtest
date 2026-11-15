# 独立实验复跑
Python3.12，仓库根目录；依赖沿用原仓库。先读EXPERIMENT.md，不因结果再调参。

```bash
python outputs/rebound_followdown/counts.py
python outputs/rebound_followdown/tests.py
python outputs/rebound_followdown/supervisor.py
python outputs/rebound_followdown/recent.py BTC
python outputs/rebound_followdown/recent.py ETH
python outputs/rebound_followdown/report.py
```

历史四段每币500独立起算，C1不含资金费；近期从原Nov1完整路径起步，Nov9前禁止新增分支，C2含精确资金费。原B全部交易、现金、分钟权益与独立续跑一致，新旧9日前权益路径一致。不能把四个周区间视为全年，不能把回顾性四根K线假跌破标签用于入场。原始输入按既有下载流程恢复，URL和SHA在各run/raw_sources、原仓库candle_sources和数据指纹中，未以保存交易结果替代行情。checkpoint含源码/数据指纹，不兼容时新目录重新执行，禁止忽略哈希。

续跑输出来自独立分支codex/nov15-continuation-audit-20261115；本实验分支仅增加独立规则与结果，不覆盖正式策略。全部触价为模拟代理。14/15日逐笔未发布，因此至15日完整结果仍未验证，不得靠K线补出成交。
