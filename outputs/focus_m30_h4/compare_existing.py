"""Read-only comparison requested by user; no downloads or financial reruns.

Keep only new six-SMA +30m/+4h, squeeze0.50%, for subsequent experiments.
Use old six-line ER as the highest-return reference in the already-tested
2026Jan-Oct window. That label is not a claim of overall/out-of-sample best.
"""
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import csv
import hashlib
import json
import sys
import zipfile

import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'outputs/attribution_2026'))
from attribute import normalized
import binance_inputs as d

TZ=timezone(timedelta(hours=8))
SPECS={
 'OLD_ER':dict(label='旧六线ER参考版',folder=ROOT/'outputs/attribution_2026',profile='ER'),
 'M30_050':dict(label='新六MA＋30分钟，0.50%',folder=ROOT/'outputs/user_ma_squeeze050/annual2026',profile='M30'),
 'H4_050':dict(label='新六MA＋4小时，0.50%',folder=ROOT/'outputs/user_ma_squeeze050/annual2026',profile='H4')}


def write(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=lambda x:x.item())+'\n',encoding='utf-8')


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def dd(values,seed):
    a=np.r_[seed,values];return float(np.max(100*(1-a/np.maximum.accumulate(a))))


def streak(trades):
    maximum=current=0
    for t in sorted(trades,key=lambda t:(t['closed_us'],t['asset'])):
        current=current+1 if t['net_usdt']<0 else 0;maximum=max(maximum,current)
    return maximum


def main():
    summary=[];monthly=[];ledger=[];arrays={};sources=[];match=[];matched_rows=[]
    for key,spec in SPECS.items():
        for asset in ('BTC','ETH'):
            jf=spec['folder']/f'{asset}_{spec["profile"]}_result.json'
            ef=spec['folder']/f'{asset}_{spec["profile"]}_equity.npy'
            q=json.loads(jf.read_text());eq=np.load(ef);arrays[key,asset]=eq
            assert q['period_beijing']==['2026-01-01T00:00:00.000+08:00','2026-11-01T00:00:00.000+08:00']
            assert q['fee']==0. and q['leverage']==3. and q['slippage']==.0002
            assert q['no_OHLC_fallback'] and len(eq)==(d.END-d.START)//60
            assert abs(eq[-1]-q['ending_equity'])<1e-8
            ts=[dict(**t,model=key,label=spec['label']) for t in normalized(q)]
            ledger.extend(ts)
            for file in (jf,ef):sources.append(dict(path=str(file),sha256=hashlib.file_digest(file.open('rb'),'sha256').hexdigest(),read_only=True))
    for key,spec in SPECS.items():
        arrays[key,'COMBINED']=arrays[key,'BTC']+arrays[key,'ETH']
        for asset in ('BTC','ETH','COMBINED'):
            eq=arrays[key,asset];seed=1000 if asset=='COMBINED' else 500
            ts=[t for t in ledger if t['model']==key and (asset=='COMBINED' or t['asset']==asset)]
            closed=[t for t in ts if t['status']=='CLOSED']
            row=dict(model=key,label=spec['label'],asset=asset,return_pct=100*(eq[-1]/seed-1),
                ending_equity=float(eq[-1]),max_drawdown_minute_pct=dd(eq,seed),opens=len(ts),closed=len(closed),
                open_at_cutoff=len(ts)-len(closed),hard_stops=sum(t['reason']=='hard_stop' for t in closed),
                realized_pnl=sum(t['net_usdt'] for t in closed),unrealized_pnl=sum(t['net_usdt'] for t in ts if t['status']=='OPEN_MARK'),
                maximum_consecutive_losses_by_close_time=streak(closed))
            for side in ('LONG','SHORT'):
                group=[t for t in closed if t['side']==side]
                row[side.lower()+'_closed_count']=len(group)
                row[side.lower()+'_win_rate_pct']=100*sum(t['net_usdt']>0 for t in group)/len(group) if group else None
            summary.append(row)
            for m in range(1,11):
                begin=int(datetime(2026,m,1,tzinfo=TZ).timestamp());end=int(datetime(2026,m+1,1,tzinfo=TZ).timestamp())
                opening=seed if begin==d.START else float(eq[(begin-d.START)//60-1]);ending=float(eq[(end-d.START)//60-1])
                monthly.append(dict(model=key,label=spec['label'],asset=asset,month=f'2026-{m:02}',
                    opening_equity=opening,ending_equity=ending,return_pct=100*(ending/opening-1),pnl_usdt=ending-opening,
                    opens=sum(begin*1e6<=t['filled_us']<end*1e6 for t in ts)))
    def logical(t):return t['asset'],t['signal_ms'],t['side']
    def exact(t):return t['asset'],t['filled_us'],t['side'],t['entry']
    old=[t for t in ledger if t['model']=='OLD_ER'];old_map={logical(t):t for t in old};old_exact={exact(t):t for t in old}
    for key in ('M30_050','H4_050'):
        new=[t for t in ledger if t['model']==key];new_map={logical(t):t for t in new};new_exact={exact(t):t for t in new}
        common=old_map.keys()&new_map.keys();same_fill=old_exact.keys()&new_exact.keys()
        for k in sorted(common):
            a,b=old_map[k],new_map[k]
            matched_rows.append(dict(model=key,asset=a['asset'],signal_beijing=a['signal_beijing'],side=a['side'],
                old_fill=a['filled_beijing'],new_fill=b['filled_beijing'],old_entry=a['entry'],new_entry=b['entry'],
                same_exact_fill=(a['filled_us'],a['entry'])==(b['filled_us'],b['entry']),old_status=a['status'],new_status=b['status'],
                same_exit=(a['closed_us'],a['exit_or_mark'],a['reason'],a['rung'],a['status'])==
                          (b['closed_us'],b['exit_or_mark'],b['reason'],b['rung'],b['status']),
                old_quantity=a['quantity'],new_quantity=b['quantity'],old_pnl=a['net_usdt'],new_pnl=b['net_usdt']))
        match.append(dict(model=key,label=SPECS[key]['label'],old_reference_opens=len(old),new_opens=len(new),
            same_origin_signal_and_side=len(common),same_exact_entry_price_time_direction=len(same_fill),
            exact_entry_overlap_vs_old_pct=100*len(same_fill)/len(old),new_only_origin_signals=len(new_map.keys()-common),
            old_only_origin_signals=len(old_map.keys()-common),is_counterparty_bot_match=False))
    write('summary.csv',summary);write('monthly.csv',monthly);write('trades.csv',ledger)
    write('reference_overlap.csv',match);write('matched_trades.csv',matched_rows)
    old_all=json.loads((ROOT/'outputs/attribution_2026/attribution.json').read_text())['annual']
    benchmark_candidates=[t for t in old_all if t['asset']=='COMBINED']
    best=max(benchmark_candidates,key=lambda t:t['return_pct']);assert best['profile']=='ER'
    selection=dict(only_follow_up_profiles=['M30','H4'],squeeze_pct=.50,
        six_averages=['SMA5','SMA10','SMA30','SMA60','SMA120','SMA250'],
        no_new_tests=['standalone_MA15','new_MA_plus_ER','H1'],old_versions_preserved=True,
        benchmark='Old six-line ER',benchmark_definition='Highest combined return among old MA and old ER in2026Jan-Oct only',
        benchmark_candidates=benchmark_candidates,no_future_default_selected_by_this_comparison=True,
        this_run='Read saved results only; no price download, no financial replay',
        additional_test_window='Not yet specified; user clarification requested asynchronously')
    save('selection.json',selection)
    save('comparison.json',dict(summary=summary,monthly=monthly,reference_overlap=match,sources=sources,
        all_inputs_same_window_fee_leverage_execution=True,no_financial_backtest_rerun=True,
        counterparty_replication_accuracy='UNVERIFIED; full reference ledger missing'))
    by={(t['model'],t['asset']):t for t in summary}
    text='''# 仅保留30分钟、4小时两组，与旧六线参考对照

用户要求：后续只跟踪新六MA的15分钟＋30分钟、15分钟＋4小时，密集阈值0.50%；不再追加单15分钟、1小时、新六MA＋ER测试。旧版本和已运行结果完整保留。

这两组2026年1—10月已经实际跑过，本次直接读取结果，不重复回测，不下载行情。追加测试区间尚未指定。

旧六线参考取该窗口合计收益最高的旧ER配置（+83.00%）；旧均线分类版同窗口+12.17%。这个“最高”只指已测2026年1—10月收益，不代表所有年份最优或最接近对方机器人。

同一币安USD-M实际成交档案，BTC/ETH各500 USDT、独立账户、3倍名义仓位、零手续费、0.02%不利出场滑点。窗口为北京时间2026-01-01 00:00至2026-11-01 00:00，不含截止点后的交易。

'''
    text+=table(['指标',*[SPECS[k]['label'] for k in SPECS]],[
        ['BTC收益',*[f"{by[k,'BTC']['return_pct']:+.2f}%" for k in SPECS]],
        ['ETH收益',*[f"{by[k,'ETH']['return_pct']:+.2f}%" for k in SPECS]],
        ['合计收益',*[f"{by[k,'COMBINED']['return_pct']:+.2f}%" for k in SPECS]],
        ['最大回撤（分钟净值）',*[f"{by[k,'COMBINED']['max_drawdown_minute_pct']:.2f}%" for k in SPECS]],
        ['开仓总数',*[by[k,'COMBINED']['opens'] for k in SPECS]],
        ['BTC/ETH开仓',*[f"{by[k,'BTC']['opens']}/{by[k,'ETH']['opens']}" for k in SPECS]],
        ['期末未平仓',*[by[k,'COMBINED']['open_at_cutoff'] for k in SPECS]],
        ['硬止损次数',*[by[k,'COMBINED']['hard_stops'] for k in SPECS]]])
    text+='\n\n## 合计逐月收益\n\n'
    text+=table(['月份',*[SPECS[k]['label'] for k in SPECS]],[[f'2026-{m:02}',*[
        f"{next(t for t in monthly if t['model']==key and t['asset']=='COMBINED' and t['month']==f'2026-{m:02}')['return_pct']:+.2f}%"
          for key in SPECS]] for m in range(1,11)])
    text+='\n\n## 交易入口与旧参考的重合\n\n'
    text+=table(['新版本','同源信号且同方向','同成交时间/价格/方向','旧参考开仓总数'],[
        [t['label'],t['same_origin_signal_and_side'],t['same_exact_entry_price_time_direction'],t['old_reference_opens']] for t in match])
    text+='''

这里只比较两套模型流水，不能称为对方机器人的交易匹配率。信号重合以币种、原始信号收盘时间和方向配对；成交重合按币种、逐笔时间戳、价格和方向严格一致，数量不作为入口重合条件。

30分钟组总收益与旧参考接近，但资产来源不同：新30分钟组BTC+106.30%、ETH+54.26%；旧参考BTC+11.80%、ETH+154.20%。总收益接近不代表交易规则或开仓时间相同。

新两组在截止点各有两笔未平仓，收益已按相同截止价计入浮盈亏，未虚构平仓；旧参考截止为空仓。多空胜率和连续亏损只用已平仓交易，组合最大连亏按平仓时间跨币种排列，不等于单个账户连亏。

旧参考的六线是SMA20/60/120＋EMA20/60/120，密集阈值0.25%，环境用原ER。新两组六线是SMA5/10/30/60/120/250、密集阈值0.50%，环境用相应高周期MA方向。此对照同时涉及均线定义、密集阈值和分类方式，不能把差额全部归因于一个周期。

原始结果文件及SHA256见comparison.json。summary.csv包含分币/合计指标；monthly.csv包括逐月收益和开仓；trades.csv为三版完整流水，matched_trades.csv为共同信号的开平仓及数量差异。

本次没有新市场数据下载或金融回放，没有自动调参，没有删除或覆盖旧配置。未来追加历史窗口待用户指定；其他年份及对方机器人完整交易匹配度未验证。

实际运行命令：

```sh
/workspace/.venv-btc-eth-original/bin/python outputs/focus_m30_h4/compare_existing.py > outputs/focus_m30_h4/run.log 2>&1
```
'''
    (OUT/'report.md').write_text(text,encoding='utf-8')
    with zipfile.ZipFile(OUT/'comparison.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(OUT.iterdir()):
            if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log'}:z.write(file,'focus_m30_h4/'+file.name)
    print(json.dumps(dict(summary=summary,reference_overlap=match),ensure_ascii=False,indent=2))
    print('READ_ONLY_COMPARISON_COMPLETE_NO_FINANCIAL_RERUN')


if __name__=='__main__':main()
