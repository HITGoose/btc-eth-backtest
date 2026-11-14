"""Render the measured attribution for phone reading; package audit evidence."""
import csv
import json
from pathlib import Path
import zipfile

OUT=Path(__file__).resolve().parent
r=json.loads((OUT/'attribution.json').read_text())


def csvrows(name):
    with (OUT/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
            ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def signed(v,n=2):return f'{float(v):+.{n}f}'


def short(t):return t.replace('2026-','').replace('T',' ')[:11]


annual={(a['asset'],a['profile']):a for a in r['annual']}
account={a['asset']:a for a in r['attribution']}
unique={p:csvrows(p+'_only_trades.csv') for p in ['ER','MA']}
specific=[]
for asset,prefix in [('BTC','2026-03-30T06:45'),('ETH','2026-06-22T02:30'),('ETH','2026-06-22T21:45'),('ETH','2026-07-07T22:00')]:
    t=next(t for t in unique['MA'] if t['asset']==asset and t['signal_beijing'].startswith(prefix));specific.append(t)
blocker=next(t for t in unique['MA'] if t['asset']=='ETH' and t['signal_beijing'].startswith('2026-10-04T16:00'))
blocked=next(t for t in unique['ER'] if t['asset']=='ETH' and t['signal_beijing'].startswith('2026-10-06T01:00'))
assert blocker['other_reason']=='ER_TRANSITION_PAUSED'
assert blocked['other_reason']=='OCCUPIED_POSITION'
assert blocked['blocker_signal_beijing']==blocker['signal_beijing']
assert not r['common_execution_differences']
assert all(v['matches_within_1e_6'] for a in r['regression_against_prior_returns'].values() for v in a.values())

phone='''# 2026年1—10月：差额主要出在ETH

已重新用同源币安官方逐笔档案实际回放。两版均为基础版、零手续费、3倍名义仓位、原滑点，未调参。四个分币收益与此前结果完全一致。

'''
phone+=table(['币种','原ER版收益','均线版收益'],[[a,signed(annual[a,'ER']['return_pct'])+'%',signed(annual[a,'MA']['return_pct'])+'%'] for a in ['BTC','ETH','COMBINED']]).replace('COMBINED','合计')
phone+='''

原ER版138笔，均线版213笔，仅69笔共同交易。共同交易的成交时间、价格、离场时间、价格和档位全部相同。

ETH从67笔增加到111笔。均线版独有74笔合计亏312.87 USDT；ER版独有30笔合计赚373.58 USDT；共同37笔因余额路径与下单数量不同，均线版合计少赚102.40 USDT。三项合起来，ETH少788.85 USDT；BTC多80.55 USDT，合计少708.30 USDT。

ETH均线版独有交易中，51笔开在原ER会暂停的过渡期，合计亏451.29 USDT。分类改变后会更早开仓，随后又因一币最多一仓/挂单挡住别的信号。

具体新增亏损单如下，时间为北京时间的信号收盘时间，损益按各自账户实际数量计算：

'''
phone+=table(['信号时间','币种/方向','均线版损益USDT','ER处理'],[[short(t['signal_beijing']),t['asset']+('多' if t['side']=='LONG' else '空'),signed(t['net_usdt']),'过渡期暂停'] for t in specific])
phone+='''

一个明确的占仓案例：均线版10月4日16:00信号做多ETH，10月7日硬止损亏23.44 USDT。10月6日01:00，ER版发出空单信号，随后成交并第8档退出，赚241.33 USDT；均线版当时仍持多，所以不能开这笔空单。

这些是两版规则与交易路径的差异，不能直接称为违反策略的程序错误。没有对方机器人1—10月完整流水，仍不能判定哪笔偏离它的模型。

近期11月9—12日只有5/6笔开仓相同，而且是Gate数据、重新从每币500和空仓开始，不接续前10个月的余额持仓。
'''
(OUT/'phone_report.md').write_text(phone,encoding='utf-8')

report=phone+'\n\n## 账面差额完整核对\n\n'
report+=table(['币种','共同单','均线独有/净损益','ER独有/净损益','共同单数量差额','总差额USDT'],[
    [a,c['common_filled_signals'],f"{c['MA_only_count']} / {signed(c['MA_only_pnl_usdt'])}",
     f"{c['ER_only_count']} / {signed(c['ER_only_pnl_usdt'])}",signed(c['same_execution_quantity_path_delta_usdt']),signed(c['equity_delta_usdt'])]
    for a,c in account.items()])
report+='''

恒等式：均线版净值−ER版净值 = 均线版独有交易净损益−ER版独有交易净损益+共同交易净损益差。两币残差均小于1e-7 USDT。本窗口四个账户期末均无持仓，全部损益已实现。

固定1500 USDT名义本金诊断换算另见CSV，用来区分单次价格收益和账户余额路径，并未重新改变仓位运行策略。分组为账面分解，不能解读为把某组交易删除后仍会得到同样余额和后续订单。

## 月度收益

按连续账户月初、月末净值计算，年内不重置。金额差为当月两版盈亏金额之差，百分比使用各自月初净值。

'''
monthly=csvrows('monthly_comparison.csv')
report+=table(['月份','ER收益','均线收益','当月盈亏金额差USDT'],[[t['month'],signed(t['ER_return_pct'])+'%',signed(t['MA_return_pct'])+'%',signed(t['MA_minus_ER_pnl_usdt'])] for t in monthly if t['asset']=='COMBINED'])
report+='\n\n## 所有独有交易分组\n\n'
report+=table(['币种','独有版本','另一版不成交的原因','笔数','独有版本净损益USDT'],[
    [t['asset'],t['version_only'],t['reason_zh'],t['count'],signed(t['pnl_usdt'])] for t in r['causes']])
report+='''

原因归类先看该根信号是否通过过滤，再看另一版本的信号前账户状态和挂单事件。分类过滤和占仓可能同时发生，CSV同时保留“另一版本是否占仓”字段，避免把单个原因当成唯一原因。

回放审计行先记录信号时点的账户，再在分钟内由原引擎处理成交/止损；同分钟信号若原引擎允许平仓后发单，也会在挂单事件内体现。不能把信号时点已有仓位的所有信号都机械地判为必然漏单。

## 最大新增亏损单

下列按实际USDT亏损排序，不能据此自动删除或优化交易。

'''
report+=table(['信号时间','币种/方向','成交时间','入场价','平仓时间','损益USDT','另一版原因'],[
    [short(t['signal_beijing']),t['asset']+('多' if t['side']=='LONG' else '空'),t['filled_beijing'],t['entry'],t['closed_beijing'],signed(t['net_usdt']),t['other_reason_zh']]
    for t in sorted(unique['MA'],key=lambda t:float(t['net_usdt']))[:15]])
report+='\n\n## ER独有的大额盈利单\n\n'
report+=table(['信号时间','币种/方向','ER损益USDT','均线版原因','占用信号时间'],[
    [short(t['signal_beijing']),t['asset']+('多' if t['side']=='LONG' else '空'),signed(t['net_usdt']),t['other_reason_zh'],t['blocker_signal_beijing']]
    for t in sorted(unique['ER'],key=lambda t:-float(t['net_usdt']))[:15]])
report+='''

ER独有盈利单不等于均线版在相同波段完全没有盈利。例如8月19日ER的ETH多单赚218.21 USDT时，均线版已有8月17日的多单；那笔均线多单最终赚145.97 USDT。因此必须一起核对全部盈利、亏损与仓位数量，不能仅把最大的漏单收益相加。

## 分类改变为什么会改变开仓

ER版在双窗口方向不一致时暂停新信号。均线分类没有这一过渡期状态，六线同向便归为趋势。基础开仓本来又要求六线同向，因此均线版不会从“有上有下”的震荡状态新开单；原来的震荡宽度限制与趋势确认也随分支切换。既有持仓和挂单继续按原有效期与止损管理。

这里不是给同一组交易贴不同的行情标签，而是改变了允许开仓的时点；后续一币最多一仓/挂单、账户余额乘3及数量步长会把差异传到后面的订单。

## 数据和执行核对范围

- Binance USDT-M官方原生15分钟/1分钟K线，46个官方压缩包，SHA256与官方CHECKSUM均一致；测试用分钟栅格无缺失或重复。
- 两版共享同一份逐日实际成交档案，时间戳按毫秒解析，5秒轮询相位2。可能成交、提档、止损的分钟使用实际成交，不合成高低顺序，不用OHLC降级离场。
- 每个实际使用的整日成交档案也验证官方CHECKSUM，档案内测试窗口的全部成交价格落在同源原生分钟高低内。本次没有发生成交价格异常导致的整日拒收或替换。
- 四种近期已验证Gate回放与本次观察驱动逐笔结果一致；四个2026年分币收益与此前结果完全一致。69笔共同交易的成交和离场时间/价格/档位/原因完全一致；财务计算依赖的原始源码全部通过Git blob SHA校验，未修改。
- 原版 `stamp > submit_at` 的+10秒边界问题依然保留，本次观察未命中“恰好+10秒且可能触价”的候选，不能把本次差额归咎于它。这个窄范围观察也不是对该边界所有可能影响的完整证明。
- 限价是全量触价成交代理，未验证真实排队、部分成交、冲击成本；资金费率未计入。未取得对方全年流水，不能证明哪一版更接近对方。

## 文件

- `all_trades.csv`：两版全部351笔交易；`paired_trades.csv`：69笔共同交易。
- `MA_only_trades.csv`：144笔均线独有单；`ER_only_trades.csv`：69笔ER独有单，均附信号时间和另一版拒绝/占仓原因。
- `*_signal_audit.csv`：信号、分类、过滤原因、信号前持仓/挂单状态。
- `attribution.csv/json`：全部账面归因及残差；`monthly_comparison.csv`：BTC、ETH与合计月度收益。
- `*_result.json`：完整交易事件、档位提升、账户状态与配置；`*_equity.npy`：分钟净值。
- `candle_sources.json` / `*_tick_sources.json`：官方来源、SHA256、数量、价格范围；`environment_source_check.json`：环境与原始源码完整性。
- `RUN_NOTES.md`：实际命令、数据边界和可比性限制；日志保存到本目录。原始数据包及日内全量数组不放入手机报告压缩包，按来源和校验和可重新获取。

本次没有调整阈值，没有选择仅某币应用均线分类，没有按年份或亏损单自我迭代。报告用于解释已授权的单一分类实验。
'''
(OUT/'report.md').write_text(report,encoding='utf-8')
(OUT/'failures.md').write_text('''# 本轮恢复与失败记录

- 开始时本工作区未恢复前一轮1—10月完整流水和币安缓存，因此未直接引用不存在的旧明细；仅取此前分币收益作回归核对，重新取得官方数据并运行2026年。
- 首次观察驱动的近期回归在期末标价观察处发生 `TypeError: StrictMarket object is not subscriptable`。更正新驱动读价格为 `market.market[end-60][3]`，未修改原引擎，再跑四种近期回归全部一致。
- 所有已使用数据的官方SHA256检查通过，无OHLC降级、无缺失分钟、无最终执行失败。下载采用会话批准的网络执行，保持代理与CA设置。
- 缺少对方机器人1—10月完整信号/订单/成交/余额流水，因此相对对方机器人的错单判定仍未验证。
''',encoding='utf-8')

with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.suffix in {'.py','.json','.csv','.md','.log','.npy'}:
            z.write(p,'attribution_2026/'+p.name)
    for name in ['BTC_15m.csv','ETH_15m.csv']:
        z.write(OUT/'data'/name,'attribution_2026/data/'+name)
print('REPORT_SAVED',OUT/'report.md','ZIP_BYTES',(OUT/'results.zip').stat().st_size)
