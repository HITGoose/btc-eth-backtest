"""Carry both verified BTC sleeves forward to a fixed, actual market snapshot.

Reuse original financial/execution methods. The still-open 15m tail is only an
excluded padding bar; a perturbation check proves it cannot alter used signals.
Current partial-minute OHLC is built from actual prints before the cutoff.
"""
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import csv
import json
import math
import shutil
import traceback
import zipfile

import replay_comparison as r

HISTORY=Path(r.__file__).resolve().parent
BASE=r.ROOT/'outputs/btc_followup_20261113'
OUT=BASE/('run_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
OUT.mkdir(parents=True,exist_ok=True)
r.OUT=OUT;r.DATA=OUT/'data';r.DATA.mkdir()
r.RESPONSES=r.DATA/'responses';r.RESPONSES.mkdir()
r.public.CACHE=r.DATA
RESUME=r.END


class MinuteMap(dict):
    def __getitem__(self,key):
        return super().__getitem__(int(key)//60*60)


class SnapshotMarket(r.StrictMarket):
    def __init__(self,minutes,cutoff):
        super().__init__('BTC',MinuteMap(minutes));self.cutoff=cutoff

    def events(self,*args,**kw):
        for stamp,price,poll in super().events(*args,**kw):
            if stamp<self.cutoff:yield stamp,price,poll


def extend_15m(cutoff):
    end15=(cutoff//900+1)*900
    batch=r.audited_json('candlesticks',contract='BTC_USDT',interval='15m',
                        **{'from':RESUME,'to':end15-1})
    rows=sorted([[int(x['t'])*1000,*(float(x[k]) for k in ('o','h','l','c','v'))]
                 for x in batch if RESUME<=int(x['t'])<end15],key=lambda x:x[0])
    if [x[0] for x in rows]!=list(range(RESUME*1000,end15*1000,900000)):
        raise RuntimeError('Missing appended 15m bar')
    file=r.DATA/'BTC_extended_15m.csv'
    old=(HISTORY/'data/BTC_15m.csv').read_text()
    file.write_text(old if old.endswith('\n') else old+'\n')
    with file.open('a',newline='') as f:csv.writer(f).writerows(rows)
    probe=r.DATA/'unused_tail_probe.csv'
    raw=list(csv.reader(file.open()))
    changed=list(raw[-1]);price=float(changed[4])*1.25
    changed[1:5]=[str(price)]*4;changed[5]=str(float(changed[5])*10)
    with probe.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerows(raw[:-1]);writer.writerow(changed)
    return file,probe,end15


def signals_for(label,file,probe,end15,cutoff,prior):
    policy=r.RegimeOverlay(**prior['policy']);pair=tuple(tuple(v) for v in prior['original_ER'])
    classify=r.ma_schedules if label=='MA_9_12' else r.regime.market_schedules
    outcomes=[];legs=[]
    for path in (file,probe):
        leg=r.model.build(path,r.WARM*1000,end15*1000);legs.append(leg)
        schedules,context=classify('BTC',leg,price_file=path,include_gate_confirmation=True,
                                  regime_thresholds=pair,use_entry_crosses=False)
        sig=r.stacked_signals(schedules['baseline'],context,policy)
        outcomes.append({t:s for t,s in sig.items() if t<cutoff*1000})
    if outcomes[0]!=outcomes[1]:raise RuntimeError('Incomplete tail influenced usable signals')
    old=json.loads((HISTORY/f'{label}_BTC_signals.json').read_text())
    old={x['signal_ms']:x['side'] for x in old}
    prefix={t:s for t,s in outcomes[0].items() if r.START*1000<=t<RESUME*1000}
    if prefix!=old:raise RuntimeError('Previously verified signal prefix changed')
    if any(t>cutoff//900*900*1000 for t in outcomes[0]):raise RuntimeError('Unclosed bar generated a signal')
    r.dump(OUT/f'{label}_causality.json',dict(old_signal_prefix_unchanged=True,
              unused_partial_15m_perturbation_passed=True,
              usable_signals_use_closed_bars_only=True,
              appended_signals=sum(RESUME*1000<=t<cutoff*1000 for t in outcomes[0])))
    return legs[0],outcomes[0]


def restore(prior):
    book=r.ObservedSleeve('BTC',r.ENTRY.exit_policy,cash=500.+prior['realized_pnl_usdt'],
              realized=prior['realized_pnl_usdt'],sizing=r.model.Sizing(3.,.0001,False),
              journal=[dict(x) for x in prior['trades']],stats=Counter(prior['stats']))
    book.events=[dict(x) for x in prior['events']];book.audit_timestamp=None
    if prior['ending_position']:
        data=dict(prior['ending_position']);data['order']=r.model.Order(**data['order'])
        book.position=r.model.Position(**data)
        book.position.opened_us=prior['ending_position_opened_us']
    if prior['ending_order']:book.order=r.model.Order(**prior['ending_order'])
    return book


def main():
    # Freeze one completed second. We never claim the final answer is live.
    latest=r.audited_json('trades',contract='BTC_USDT',limit=1)[0]
    stamp=float(latest['create_time_ms'])
    if abs(stamp-datetime.now(timezone.utc).timestamp())>120:
        raise RuntimeError('Latest trade timestamp is stale or unit is invalid')
    cutoff=math.floor(stamp)
    if cutoff<=RESUME:raise RuntimeError('Snapshot does not extend the old replay')
    r.dump(OUT/'snapshot.json',dict(cutoff_beijing=r.local_s(cutoff),
             latest_observed_trade=latest,cutoff_end_exclusive=True))
    end_minute=(cutoff+59)//60*60
    minutes=r.complete_candles('BTC',RESUME-60,end_minute,'1m')
    market=SnapshotMarket(minutes,cutoff)
    last_minute=(cutoff-1)//60*60
    if cutoff%60:
        complete=r.public.trades('BTC_USDT',last_minute,last_minute+60)
        prefix=[x for x in complete if x[0]<cutoff]
        native=minutes[last_minute]
        if any(p<native[2]-1e-8 or p>native[1]+1e-8 for _,_,p,_ in prefix):
            raise RuntimeError('Partial-minute prints outside API price range')
        if prefix:
            prices=[x[2] for x in prefix]
            market.market[last_minute]=(prices[0],max(prices),min(prices),prices[-1],sum(abs(x[3]) for x in prefix))
        else:
            value=minutes[last_minute-60][3]
            market.market[last_minute]=(value,value,value,value,0.)
        market._tapes[last_minute]=prefix
    else:prefix=market.tape(last_minute)
    if not prefix:
        previous=market.tape(last_minute-60)
        if not previous:raise RuntimeError('No actual recent quote for valuation')
        mark=previous[-1]
    else:mark=prefix[-1]
    file,probe,end15=extend_15m(cutoff)
    results=[]
    for label in ('ER_9_12','MA_9_12'):
        prior=json.loads((HISTORY/f'{label}_BTC_result.json').read_text())
        book=restore(prior);original_opened=prior['ending_position_opened_us']
        leg,signals=signals_for(label,file,probe,end15,cutoff,prior)
        before_events=len(book.events)
        q=r.observed_replay(book)('BTC',leg=leg,signals=signals,market=market,
              start=RESUME*1000,end=cutoff*1000,starting_cash=500.,leverage=3.,
              poll_seconds=5,poll_phase=2,print_progress=True)
        if q['approximated_minutes']:raise RuntimeError('OHLC fallback forbidden')
        original_close=next((x for x in book.journal if x['opened_us']==original_opened),None)
        last_position=asdict(book.position) if book.position else None
        result=dict(profile=label,cutoff_beijing=r.local_s(cutoff),
                  mark_price=mark[2],mark_trade_beijing=r.local_s(mark[0]),
                  original_position_closed=original_close is not None,original_close=original_close,
                  original_entry=prior['ending_position']['order']['price'],
                  original_stop_at_resume=prior['ending_position']['stop'],
                  cash=book.cash,ending_equity=book.equity(mark[2]),
                  realized_pnl_since_nov9=book.cash-500.,
                  current_floating_pnl=book.position.marked(mark[2]) if book.position else 0.,
                  current_position=last_position,current_order=asdict(book.order) if book.order else None,
                  current_position_opened_us=getattr(book.position,'opened_us',None) if book.position else None,
                  events_after_resume=book.events[before_events:],trades=book.journal,stats=dict(book.stats),
                  no_OHLC_fallback=True,source='Gate public REST actual prints',
                  funding_omitted_as_before=True,fee=0.,slippage=.0002)
        r.dump(OUT/f'{label}_result.json',result);results.append(result)
        print(label,'RESULT',result,flush=True)
    r.dump(OUT/'summary.json',dict(completed=True,resume_beijing=r.local_s(RESUME),
                  cutoff_beijing=r.local_s(cutoff),mark_price=mark[2],results=results))
    text=[f"截至北京时间{r.local_s(cutoff)}；最近核对成交价{mark[2]}，成交时间{r.local_s(mark[0])}。",'',
          '从已验证的11月12日23:00状态续接BTC；保留余额、数量、挂单、止损与档位，原参数不变。若平仓后再次产生信号，按原规则继续执行。','',
          '|版本|原空单已平仓|当前持仓|当前档位|当前止损|当前浮盈USDT|',
          '|---|---|---|---:|---:|---:|']
    for x in results:
        pos=x['current_position']
        text.append(f"|{x['profile']}|{x['original_position_closed']}|{'SHORT' if pos and pos['order']['side']==-1 else 'LONG' if pos else 'FLAT'}|{pos['rung'] if pos else ''}|{pos['stop'] if pos else ''}|{x['current_floating_pnl']:+.2f}|")
    for x in results:
        if x['original_close']:
            t=x['original_close']
            text.append(f"\n原单退出：{r.local_us(t['closed_us'])}，档位{t['rung']}，触发价{t['trigger_print']}，含滑点平仓价{t['exit']}，该单收益{t['net']:+.2f} USDT。\n")
    text+=['','空单价格下跌本身不触发平仓。每5秒相位2秒检查升档，激活的止损由逐笔反弹触发；当下价格不能证明此前没触发止损。',
           '当前未完成15分钟K线只作末尾排除的边界行；修改该行后的信号一致性测试及旧信号前缀一致性检查均通过。它没有生成开仓信号。',
           '最后不足一分钟按截止秒之前的真实逐笔重建，只使用截止秒之前的轮询和成交。逐笔完整性依赖分钟索引，真实撮合排队与部分成交未验证。']
    (OUT/'report.md').write_text('\n'.join(text)+'\n')
    BASE.mkdir(exist_ok=True)
    shutil.copy2(OUT/'report.md',BASE/'latest_report.md')
    r.dump(BASE/'latest.json',dict(directory=str(OUT),cutoff_beijing=r.local_s(cutoff)))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in OUT.rglob('*'):
            if path.is_file() and path.suffix in ('.json','.jsonl','.csv','.md','.log'):
                archive.write(path,path.relative_to(OUT))
    print('FOLLOWUP_COMPLETE',OUT,flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        r.dump(OUT/'failure.json',dict(completed=False,error=traceback.format_exc()))
        raise
