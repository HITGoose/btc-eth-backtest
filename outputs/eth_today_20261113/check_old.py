"""Old six-line MA classifier around08:00, same Gate data and verified book.

No orders exist and no new signals occur after the last verified empty book.
Therefore no tick fill is invented or needed to conclude no new entry here.
"""
from datetime import datetime
from pathlib import Path
import json
import sys

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'outputs/attribution_2026'))
import paired_replay as p
r=p.r;d=p.d


def main():
    file=OUT/'data/ETH_Gate_15m_extended.csv'
    prior=json.loads((ROOT/'outputs/retry_nov9_nov12/MA_9_12_ETH_result.json').read_text())
    end=int(datetime(2026,11,13,9,30,tzinfo=r.TZ).timestamp())
    leg=r.model.build(file,r.WARM*1000,(end+900)*1000)
    policy=r.RegimeOverlay(**prior['policy']);pair=tuple(tuple(x) for x in prior['original_ER'])
    schedules,ctx=r.ma_schedules('ETH',leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
    signals=r.stacked_signals(schedules['baseline'],ctx,policy)
    old_signals=json.loads((ROOT/'outputs/retry_nov9_nov12/MA_9_12_ETH_signals.json').read_text())
    expected={x['signal_ms']:x['side'] for x in old_signals}
    actual={t:s for t,s in signals.items() if r.START*1000<=t<r.END*1000}
    assert expected==actual,'Previously verified signal prefix changed'
    resumed=[dict(time_beijing=r.local_s(t/1000),side=s) for t,s in signals.items() if r.END*1000<=t<end*1000]
    assert prior['ending_position'] is None and prior['ending_order'] is None
    assert not resumed,'Cannot infer no entry without an actual fill replay when signals exist'
    first=int(datetime(2026,11,13,7,tzinfo=r.TZ).timestamp())
    rows=[]
    for t in range(first,end,900):
        ms=t*1000;i=int((ms-r.regime.BAR-leg.first)//r.regime.BAR)
        dense=np.flatnonzero(leg.width[:i+1]<=.25)
        last_dense=int(dense[-1]) if len(dense) else None
        rows.append(dict(profile='OLD_SIX_MA15',signal_beijing=r.local_s(t),signal_ms=ms,
            close=leg.bars[ms-r.regime.BAR].c,down_lines=int(leg.down[i]),close_below_all_six=bool(leg.below_band[i]),
            histogram=float(leg.histogram[i]),minimum96_bandwidth_pct=float(leg.squeeze[96][i]),
            current_bandwidth_pct=float(leg.width[i]),regime=ctx[ms]['regime'],eligible_side=signals.get(ms,0),
            last_compressed_bar_close=r.local_s((leg.first+(last_dense+1)*r.regime.BAR)/1000) if last_dense is not None else '',
            hours_since_last_compression=(i-last_dense)*.25 if last_dense is not None else ''))
    p.csv_out(OUT/'old_six_signal_check.csv',rows)
    result=dict(source='Gate ETH_USDT public candles, same venue as prior saved replay',
        definition=['SMA20','SMA60','SMA120','EMA20','EMA60','EMA120'],classifier='Old single15m six-line direction',
        original_signal_prefix_unchanged=True,prior_verified_at=prior['end_beijing'],
        prior_verified_position=None,prior_verified_order=None,prior_verified_cash=prior['ending_equity'],
        resumed_to_exclusive=r.local_s(end),resumed_new_signals=resumed,
        no_new_entry_proven_by_no_signals_and_initially_empty_book=True,
        actual_today_tick_replay_performed=False,reason_no_tick_replay_needed='No order is submitted and no position is held in this interval',
        source_screenshot_venue_Binance_exact_result='UNVERIFIED_HTTP451',real_user_account_state='UNVERIFIED',
        signal_checks=rows)
    d.dump(OUT/'old_six_check.json',result)
    selected=[t for t in rows if 'T08:' in t['signal_beijing']]
    text=['# 旧均线版今天08点会开单吗','','按旧SMA20/60/120＋EMA20/60/120的单15分钟均线分类版，使用Gate ETH_USDT同源数据核对，今天8点这段也不会新开空单。','',
        '| 信号收盘时间（北京） | 六线向下数量 | MACD柱 | 最近96根最小带宽 | 新信号 |','|---|---:|---:|---:|---|']
    for t in selected:text.append(f"| {t['signal_beijing'][11:16]} | {t['down_lines']}/6 | {t['histogram']:.4f} | {t['minimum96_bandwidth_pct']:.4f}% | 无 |")
    text+=['', '08:45虽已六线向下、MACD柱为负，但最近96根最小带宽0.3564%仍大于要求≤0.25%，足以挡住开仓；未宣称其他全部条件均通过。', '',
        '云端模拟账户不是用户真实账户。从上一轮11月12日23:00的已验证状态（无持仓、无挂单）继续核对至11月13日09:30，该段没有任何新信号，因此没有新发订单，也不存在此前挂单在8点成交。这个结论不需要虚构逐笔成交；本次未声称执行了今天的逐笔重放。', '',
        f"当时最后一个满足≤0.25%的密集K线收盘是{selected[0]['last_compressed_bar_close']}，距08:00已有{selected[0]['hours_since_last_compression']:.2f}小时，已不在当前96根窗口内。",'',
        '新六MA5/10/30/60/120/250在同一时点的最近96根最小带宽为1.2769%，同样不通过。两个版本都未为了抓住截图这一段下跌而修改密集阈值。','',
        '币安实时合约接口HTTP451，故本次是Gate数据结论。截图平台的精确成交、真实账户占仓和真实成交均未验证。','',
        '实际命令：','```sh','/workspace/.venv-btc-eth-original/bin/python outputs/eth_today_20261113/check_old.py > outputs/eth_today_20261113/check_old.log 2>&1','```']
    (OUT/'old_six_report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
