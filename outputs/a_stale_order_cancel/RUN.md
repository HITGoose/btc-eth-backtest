# 固定未成交撤单复跑
Python3.12，原requirements与币安USDT永续15m/1m缓存，无新行情下载。
```
python outputs/a_stale_order_cancel/checks.py
python outputs/a_stale_order_cancel/runner.py 2020 BTC
python outputs/a_stale_order_cancel/pipeline.py
python outputs/a_stale_order_cancel/report.py
python outputs/a_stale_order_cancel/finalize.py
```
pipeline负责其余13个币年，先行runner负责2020BTC；单个币年runner.py YEAR BTC或ETH。只28个A_CANCEL新账户；28个A_BASE经原源码、金融指纹、缓存SHA、完整信号和费用/区间一致后引用，不重跑。
原基准提交060e12a18bc745a7c98e5270f2e37b0c759cc5ff。仅ZERO、MAKER_002_SIDE，不使用A_FAIL_EXIT或V2。实际命令输出在pilot.log、pipeline.log及年度_币种.log，完成状态execution_status.json与各币年status.json。
时钟：每分钟前先原expire，再处理到时撤单，再检查当时刚闭15m；T+60原到期优先、同订单撤单先于价格事件。原价事件与轮询顺序不改。已成交/到期请求失效，按订单对象身份保护不同新单。仅会计恒等式增加独立stale_cancelled，不伪记expired。
原始六线按原warmup与函数计算，宽度与原Leg逐点核对。入场S.25/W.50、六线/ER、挂单价差/10秒延迟/60分钟TTL/取整、fixed/cap5、2%硬止损、3x全部不变，不立即重挂/补单/追价。下一原信号才可下单。
checks.py只有5项必要合成时序检查；实际年度来自完整账户回放。report.py核对入场信号一致、首次实际撤单前权益与基准一致、所有实际撤单在T+60且尚未成交、原订单会计守恒、所有账本及账户差额闭合。
撤单匹配按资产/方向/signal_close_ms，不以近似价格强配。基准未提交24单单列；基准73未成交单无实际成交名义，r1000留空。成交等待按原effective submission到opened_us，未成交不把TTL当等待。期末未平仅作估值，不判最终输赢。
2020仅02-16起、2026仅1—10月，年度每币500独立，资金费0、0.02%退出滑点。1m OHLC假设打印非真实逐笔或严格边界；MAKER费用为每边0.02%假设。合计USDT不是跨年复利，不把已看年份称全新样本外，不追加参数/费用/路径搜索。
