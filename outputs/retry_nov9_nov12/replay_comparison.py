"""Actual Gate API replay, ER vs user-requested MA classifier, same inputs.

Original work/ source is restored byte-for-byte and never edited. This helper
reconstructs the prior observer/driver after the cloud workspace was replaced.
It does not reconstruct or claim access to the external robot's source code.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode
import csv
import hashlib
import inspect
import json
import sys
import traceback
import zipfile

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
OUT=Path(__file__).resolve().parent
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
RESPONSES=DATA/'responses';RESPONSES.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'work'))
import combined_crypto_portfolio as costs
costs.FEE=0.
import fit_squeeze_ladder_bot as model
import replay_gate_october_seconds as seconds
import replay_gate_selected_3x as selected
import gate_october_regime_entries as regime
import gate_public_data as public
from fit_gate_entry_overlay import RegimeOverlay,stacked_signals
from replay_gate_bot import GateMinutes,ENTRY
from backtest_squeeze_short import WARMUP,HOUR
from replay_formal_bot_trades import FILLS

TZ=timezone(timedelta(hours=8));UTC=timezone.utc
START=int(datetime(2026,11,9,tzinfo=TZ).timestamp())
LEGACY_START=int(datetime(2026,11,10,tzinfo=TZ).timestamp())
END=int(datetime(2026,11,12,23,tzinfo=TZ).timestamp())
WARM=START-30*86400
public.CACHE=DATA
LOCK=Lock()
FETCH=public.public_json


def dump(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,default=lambda x:x.item())+'\n');temp.replace(path)


def local_s(stamp):return datetime.fromtimestamp(stamp,TZ).isoformat(timespec='milliseconds')
def local_us(stamp):return local_s(stamp/1e6)


def audited_json(endpoint,**params):
    response=FETCH(endpoint,**params)
    text=json.dumps(response,separators=(',',':'),ensure_ascii=False)
    url=public.API+endpoint+'?'+urlencode(params)
    name=hashlib.sha256(url.encode()).hexdigest()+'.json'
    payload=text.encode();path=RESPONSES/name
    with LOCK:
        path.write_bytes(payload)
        with (OUT/'api_requests.jsonl').open('a') as f:
            f.write(json.dumps(dict(url=url,retrieved_utc=datetime.now(UTC).isoformat(),
                     records=len(response),stored_response=str(path.relative_to(OUT)),
                     response_sha256=hashlib.sha256(payload).hexdigest()))+'\n')
    return response


public.public_json=audited_json


def complete_candles(asset,start,end,interval):
    """Fetch a padding bar, discard it; requested bars are fully closed.

The API can emit a partial final bar when its to parameter clips that bar.
Padding is transport only; no bar at or after end enters the strategy.
"""
    step=public.INTERVALS[interval]
    file=DATA/f'{asset}_{interval}_{start}_{end}_complete.json'
    if file.exists():raw=json.loads(file.read_text())
    else:
        raw=[]
        for begin in range(start,end,1800*step):
            last=min(begin+1800*step,end)
            batch=audited_json('candlesticks',contract=asset+'_USDT',interval=interval,
                               **{'from':begin,'to':last+step-1})
            raw.extend([int(r['t']),*(float(r[k]) for k in ('o','h','l','c','v'))]
                       for r in batch if begin<=int(r['t'])<last)
        raw.sort(key=lambda r:r[0]);dump(file,raw)
    if [r[0] for r in raw]!=list(range(start,end,step)):raise RuntimeError('Incomplete '+asset+' '+interval+' candles')
    if not all(0<l<=min(o,c)<=max(o,c)<=h and v>=0 for _,o,h,l,c,v in raw):raise RuntimeError('Invalid candle fields')
    return {t:tuple(r) for t,*r in raw}


class ObservedSleeve(model.Sleeve):
    """Only record events. Every financial operation delegates to original."""
    def place(self,t,ref,side,**kw):
        super().place(t,ref,side,**kw)
        if self.order:self.events.append(dict(event='order_sent',time_us=int(t)*1000,
                 price=self.order.price,side=side,quantity=self.order.qty))

    def visit(self,price,t,at_open,**kw):
        before=self.stats['long']+self.stats['short'];order=self.order
        super().visit(price,t,at_open,**kw)
        if self.stats['long']+self.stats['short']>before:
            stamp=round(self.audit_timestamp*1e6)
            self.events.append(dict(event='limit_touch_proxy_fill',time_us=stamp,price=float(price),
                    entry=order.price,side=order.side,quantity=order.qty,submitted_ms=order.time))
            if self.position:self.position.opened_us=stamp

    def close(self,price,reason,t):
        opened=getattr(self.position,'opened_us',self.position.opened*1000)
        super().close(price,reason,t)
        self.journal[-1].update(trigger_print=float(price),closed_us=round(self.audit_timestamp*1e6),opened_us=opened)
        self.events.append(dict(event=reason,time_us=round(self.audit_timestamp*1e6),price=float(price),
                     rung=self.journal[-1]['rung'],net_usdt=self.journal[-1]['net']))

    def update_ladder(self,price):
        before=self.position.rung if self.position else None
        super().update_ladder(price)
        if self.position and self.position.rung!=before:
            self.events.append(dict(event='poll_moves_stop',time_us=round(self.audit_timestamp*1e6),
                         price=float(price),rung=self.position.rung,stop=self.position.stop))


def observed_replay(book):
    code=inspect.getsource(seconds.replay_asset)
    needle='            for stamp, price, poll in events:\n'
    if code.count(needle)!=1:raise RuntimeError('Unexpected original execution source')
    code=code.replace(needle,needle+'                book.audit_timestamp = stamp\n')
    namespace=dict(seconds.__dict__);namespace['Sleeve']=lambda *a,**kw:book
    exec(compile(code,'<original executor: observation-only timestamp hook>','exec'),namespace)
    return namespace['replay_asset']


class StrictMarket(GateMinutes):
    def events(self,*args,**kw):
        try:yield from super().events(*args,**kw)
        except Exception as error:raise RuntimeError('UNVERIFIED_TAPE_NO_OHLC_FALLBACK: '+repr(error)) from error


SOURCE=inspect.getsource(regime.market_schedules)
NEEDLE='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n'
REPLACEMENT='        state = "up" if leg.up[i] == 6 else "down" if leg.down[i] == 6 else "range"\n'
if SOURCE.count(NEEDLE)!=1:raise RuntimeError('Unexpected original regime source')
NAMESPACE=dict(regime.__dict__)
exec(compile(SOURCE.replace(NEEDLE,REPLACEMENT),'<isolated MA_DIRECTION_15M_V1>','exec'),NAMESPACE)
ma_schedules=NAMESPACE['market_schedules']


def run_case(asset,label,start,file,market,policy,pair):
    target=OUT/f'{label}_{asset}_result.json'
    if target.exists():return json.loads(target.read_text())
    warm=start-30*86400
    leg=model.build(file,warm*1000,END*1000)
    classify=ma_schedules if label=='MA_9_12' else regime.market_schedules
    schedules,context=classify(asset,leg,price_file=file,include_gate_confirmation=True,
                               regime_thresholds=pair,use_entry_crosses=False)
    signals=stacked_signals(schedules['baseline'],context,policy)
    selected_signals={t:s for t,s in signals.items() if start*1000<=t<END*1000}
    dump(OUT/f'{label}_{asset}_signals.json',[
        dict(signal_ms=t,signal_beijing=local_s(t/1000),side=s,regime=context[t]['regime'])
        for t,s in sorted(selected_signals.items())])
    print(label,asset,'SIGNALS_READY',len(selected_signals),flush=True)
    book=ObservedSleeve(asset,ENTRY.exit_policy,cash=500.,sizing=model.Sizing(3.,.0001,False),journal=[])
    book.events=[];book.audit_timestamp=None
    q=observed_replay(book)(asset,leg=leg,signals=signals,market=market,print_progress=True,
           start=start*1000,end=END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2)
    if q['approximated_minutes']:raise RuntimeError('Fictitious OHLC prices forbidden')
    quote=q['window_mark_price'];ending=book.equity(quote)
    trade_comparison=[]
    if start==START:
        for fill in FILLS:
            if fill.asset!=asset:continue
            t=int(datetime.fromisoformat(fill.signal_time).timestamp()*1000)
            matched=next((v for v in book.events if v['event']=='limit_touch_proxy_fill'
                    and v['side']==-1 and abs(v['entry']-fill.entry)<1e-8
                    and v['time_us']//1000000==int(datetime.fromisoformat(fill.opened).timestamp())),None)
            trade_comparison.append(dict(reference_signal=fill.signal_time,signal_time_inferred=fill.signal_inferred,
                 eligible=signals.get(t)==-1,reference_entry=fill.entry,reference_opened=fill.opened,
                 entry_same_price_and_second=matched is not None,matched_event=matched,
                 reference_quantity=fill.quantity,quantity_match=bool(matched and abs(matched['quantity']-fill.quantity)<1e-10),
                 quantity_comparison_caveat='Our account starts500; reference balances around50, so quantities not directly comparable'))
    result=dict(label=label,asset=asset,source='GATE_PUBLIC_REST_USDT_PERPETUAL',
             profile='MA_DIRECTION_15M_V1' if label=='MA_9_12' else 'ER_BASELINE',
             start_beijing=local_s(start),end_beijing=local_s(END),starting_cash=500.,ending_equity=ending,
             return_pct=100*(ending/500-1),total_pnl_usdt=ending-500.,realized_pnl_usdt=book.cash-500.,
             unrealized_pnl_usdt=book.position.marked(quote) if book.position else 0.,
             opens=q['opens'],closed_count=len(book.journal),stats=dict(book.stats),trades=book.journal,events=book.events,
             ending_position=asdict(book.position) if book.position else None,
             ending_position_opened_us=getattr(book.position,'opened_us',None) if book.position else None,
             ending_order=asdict(book.order) if book.order else None,final_mark_price=quote,
             eligible_signals=len(selected_signals),verified_event_minutes=q['verified_minutes_with_trade_prints'],
             approximated_minutes=q['approximated_minutes'],tape_close_discrepancies=q['tape_close_discrepancies'],
             reference_entries=trade_comparison,fee=0.,slippage=.0002,leverage=3.,poll_seconds=5,poll_phase=2,
             compare_ma_bars_ago=3,policy=asdict(policy),original_ER=pair,
             old_orders_keep_60minute_lifetime=True,strict_six_line_entries_retained=True,
             original_source_changed=False,known_original_submit_boundary_preserved=True,
             funding='omitted as in prior replay',limit_fill='full-size touch proxy; queue and partial fills unverified')
    dump(target,result);np.save(OUT/f'{label}_{asset}_equity.npy',np.asarray(q['marks']))
    print(label,asset,'COMPLETE','opens',result['opens'],'realized',result['realized_pnl_usdt'],
          'floating',result['unrealized_pnl_usdt'],'total',result['total_pnl_usdt'],flush=True)
    return result


def asset_worker(asset,policy,pair):
    contract=asset+'_USDT'
    candles=complete_candles(asset,WARM-WARMUP//1000,END,'15m')
    file=DATA/f'{asset}_15m.csv'
    with file.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['timestamp','open','high','low','close','volume'])
        writer.writerows([t*1000,*r] for t,r in candles.items())
    minutes=complete_candles(asset,START-60,END,'1m')
    market=StrictMarket(asset,minutes)
    results=[]
    for label,start in [('ER_9_12',START),('MA_9_12',START),('ER_10_12_REFERENCE',LEGACY_START)]:
        results.append(run_case(asset,label,start,file,market,policy,pair))
    dump(OUT/f'{asset}_market_validation.json',dict(cached_tape_minutes=len(market._tapes),
             prints=sum(len(t) for t in market._tapes.values()),close_discrepancies=market.close_discrepancies))
    return results


def csv_file(name,rows,fields=None):
    if fields is None:fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def collect(results):
    summaries=[];fills=[];orders=[];references=[]
    for label in ('ER_9_12','MA_9_12','ER_10_12_REFERENCE'):
        group=[r for r in results if r['label']==label]
        if len(group)!=2:continue
        summaries.append(dict(label=label,source='GATE_PUBLIC_REST',start_beijing=group[0]['start_beijing'],
              end_beijing=group[0]['end_beijing'],initial_equity=1000.,
              ending_equity=sum(r['ending_equity'] for r in group),
              return_pct=sum(r['return_pct'] for r in group)/2,
              total_pnl_usdt=sum(r['total_pnl_usdt'] for r in group),
              realized_pnl_usdt=sum(r['realized_pnl_usdt'] for r in group),
              unrealized_pnl_usdt=sum(r['unrealized_pnl_usdt'] for r in group),
              opens=sum(r['opens'] for r in group),closed=sum(r['closed_count'] for r in group),
              BTC_opens=next(r['opens'] for r in group if r['asset']=='BTC'),
              ETH_opens=next(r['opens'] for r in group if r['asset']=='ETH')))
    for r in results:
        closed={t['opened_us']:t for t in r['trades']}
        references.extend(dict(label=r['label'],asset=r['asset'],**v) for v in r['reference_entries'])
        for event in r['events']:
            if event['event']=='order_sent':
                orders.append(dict(label=r['label'],asset=r['asset'],order_beijing=local_us(event['time_us']),
                       direction='LONG' if event['side']==1 else 'SHORT',price=event['price'],quantity=event['quantity']))
            if event['event']=='limit_touch_proxy_fill':
                t=closed.get(event['time_us']);pnl=t['net'] if t else r['unrealized_pnl_usdt']
                fills.append(dict(label=r['label'],asset=r['asset'],order_beijing=local_s(event['submitted_ms']/1000),
                     signal_beijing=local_s((event['submitted_ms']-10000)/1000),
                     opened_beijing=local_us(event['time_us']),direction='LONG' if event['side']==1 else 'SHORT',
                     entry=event['entry'],quantity=event['quantity'],status='CLOSED' if t else 'OPEN',
                     closed_beijing=local_us(t['closed_us']) if t else '',exit=t['exit'] if t else '',
                     rung=t['rung'] if t else (r['ending_position']['rung'] if r['ending_position'] else ''),
                     realized_pnl_usdt=pnl if t else 0.,unrealized_pnl_usdt=0. if t else pnl))
    fills.sort(key=lambda r:(r['label'],r['opened_beijing'],r['asset']))
    csv_file('summary_comparison.csv',summaries)
    csv_file('fills_comparison.csv',fills)
    csv_file('orders_comparison.csv',orders)
    dump(OUT/'reference_entry_comparison.json',references)
    legacy=next(r for r in summaries if r['label']=='ER_10_12_REFERENCE')
    regression=dict(previous_report_total_pnl_usdt=57.27841825200039,
                    rerun_total_pnl_usdt=legacy['total_pnl_usdt'],
                    difference_usdt=legacy['total_pnl_usdt']-57.27841825200039,
                    matches_prior_amount_within_1e_6=abs(legacy['total_pnl_usdt']-57.27841825200039)<1e-6,
                    not_used_to_fit_parameters=True,
                    caveat='Same original strategy, newly retrieved public API snapshot and fully closed candle requests')
    dump(OUT/'prior_window_regression.json',regression)
    text=['# 11月9日00:00至12日23:00连续回放','',
          '北京时间；Gate USDT永续公开API。同一套15m/1m行情及真实逐笔，两个版本每币500 USDT、空仓空挂单起算；0费、3倍、出场滑点0.02%、5秒轮询相位2秒。',
          '这次按4天连续管理持仓和余额，不将11月10日起独立测试拼入。额外重跑10日起ER旧窗口仅用于恢复后核对。',
          'MA_DIRECTION_15M_V1只把ER分类替换为六线与3根前严格同向，上涨/下跌/其他震荡。原入场和2%支撑阻力绝对距离不变。','',
          '|版本|BTC开仓|ETH开仓|已实现USDT|浮盈亏USDT|总收益USDT|收益率|',
          '|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        text.append(f"|{r['label']}|{r['BTC_opens']}|{r['ETH_opens']}|{r['realized_pnl_usdt']:+.2f}|{r['unrealized_pnl_usdt']:+.2f}|{r['total_pnl_usdt']:+.2f}|{r['return_pct']:+.2f}%|")
    text+=['','|版本|开仓北京时间|币种|方向|入场价|数量|平仓时间|已实现USDT|浮盈USDT|',
           '|---|---|---|---|---:|---:|---|---:|---:|']
    for r in fills:
        text.append(f"|{r['label']}|{r['opened_beijing']}|{r['asset']}|{r['direction']}|{r['entry']}|{r['quantity']}|{r['closed_beijing']}|{r['realized_pnl_usdt']:+.2f}|{r['unrealized_pnl_usdt']:+.2f}|")
    text+=['','所有入场仍为触价全额成交代理，排队、部分成交与实际滑点未验证。资金费沿用原配置未计；原+10秒替代挂单边界未改。',
           '逐笔只用于价格范围判定可能改变成交/档位/止损的分钟，不是全市场逐笔审计。任何逐笔缺失或K线冲突均终止，不允许OHLC回退。',
           '原仓库85个必要文件来自授权GitHub连接、逐个Git blob校验；新工作区没有旧云端缓存。观测辅助驱动从会话记录重建，原策略源码未改。',
           '参考机器人账户余额约50 USDT，与本次每币500不同；参考单仅按价格、成交整秒另列核对，不能据此宣称数量及收益完全复刻。']
    (OUT/'report.md').write_text('\n'.join(text)+'\n')
    dump(OUT/'run_status.json',dict(completed=len(summaries)==3,source='Gate public API',
                first_beijing=local_s(START),end_beijing=local_s(END),strategy_unchanged_except_requested_classifier=True,
                old_cloud_workspace_missing=True,original_source_git_blob_verified=True))
    print('COMBINED',summaries,flush=True)


def main():
    if datetime.now(UTC).timestamp()<END:raise RuntimeError('End time has not elapsed')
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    prior=json.loads(selected.FAST_WINDOW_REPORT.read_text());policy=RegimeOverlay(**prior['policy'])
    pair=tuple(tuple(v) for v in prior['cases'][selected.MODE]['er_windows_and_thresholds'])
    assert policy.trend_level_distance_pct==2.
    results=[];failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks={pool.submit(asset_worker,a,policy,pair):a for a in ('BTC','ETH')}
        for task in as_completed(tasks):
            a=tasks[task]
            try:results.extend(task.result())
            except Exception as error:
                failures.append(dict(asset=a,error=str(error),traceback=traceback.format_exc()))
                print(a,'UNVERIFIED',str(error),flush=True)
    if failures:
        dump(OUT/'run_status.json',dict(completed=False,failures=failures))
        raise RuntimeError('Actual replay incomplete; see run_status.json')
    collect(results)


if __name__=='__main__':main()
