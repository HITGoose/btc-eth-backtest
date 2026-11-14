"""User-requested 15m + 30m experiment. Previous versions remain unchanged.

The 30m filter has the same 3-bar finite difference and state-composition rule
as the prior MTF experiment. No new compression-to-expansion entry rule is
invented. Complete 30m candles are aggregated from the already verified 15m
source; financial execution delegates to the previous original-code driver.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/ma_multitimeframe_2026'))
import experiment as e

OUT=Path(__file__).resolve().parent
OUT.mkdir(parents=True,exist_ok=True)
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
d=e.d;r=e.r


def higher30(asset,hours):
    assert hours==.5,'This isolated experiment only supports 30m'
    raw=np.load(DATA/f'{asset}_30m.npy')
    closes=raw[:,4]
    values=np.stack([r.model.sma(closes,n) for n in (20,60,120)]+
                    [r.model.ema(closes,n) for n in (20,60,120)])
    closed=(raw[:,0]+1800).astype(np.int64)*1000
    return closed,e.direction(values),closes,values


original_config=e.config


def config():
    c=original_config()
    c.update(name='MA15_PLUS_30M_USER_REQUEST',higher_candle_anchor='UTC xx:00/xx:30, also Beijing xx:00/xx:30',
        source_begin_utc=datetime.fromtimestamp(d.FIRST15,timezone.utc).isoformat(),
        higher_source='Two complete native15m bars from prior checksum-verified Binance input',
        thirty_minute_ma_comparison_elapsed_minutes=90,signal_ma_comparison_elapsed_minutes=45,
        compression_rule='minimum of current+previous95 15m bandwidths <=0.25%',
        fresh_mixed_to_aligned_transition_required=False,bandwidth_expansion_required=False,
        sequence_rule_status='Original source does not require immediate prior mixed/compressed state; no new entry condition added')
    return c


e.OUT=OUT;e.DATA=DATA;e.HOURS=(.5,);e.PROFILES={'MA15_30M':.5};e.higher=higher30;e.config=config


def prepare():
    metadata=[]
    for asset in ('BTC','ETH'):
        file=d.DATA/f'{asset}_15m.csv';raw=np.loadtxt(file,delimiter=',',skiprows=1)
        raw[:,0]/=1000
        assert np.array_equal(raw[:,0],np.arange(d.FIRST15,d.END,900))
        assert len(raw)%2==0 and raw[0,0]%1800==0
        blocks=raw.reshape(-1,2,6)
        rows=np.column_stack((blocks[:,0,0],blocks[:,0,1],blocks[:,:,2].max(axis=1),
                              blocks[:,:,3].min(axis=1),blocks[:,-1,4],blocks[:,:,5].sum(axis=1)))
        assert np.array_equal(rows[:,0],np.arange(d.FIRST15,d.END,1800))
        np.save(DATA/f'{asset}_30m.npy',rows)
        # Same-venue native1m OHLC corroborates every execution-window 30m bar.
        minute=np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r')
        window=minute[(d.START-d.FIRST1)//60:(d.END-d.FIRST1)//60]
        mb=window.reshape(-1,30,5)
        corroborated=np.column_stack((mb[:,0,0],mb[:,:,1].max(axis=1),mb[:,:,2].min(axis=1),mb[:,-1,3]))
        test=rows[(rows[:,0]>=d.START)&(rows[:,0]<d.END),1:5]
        assert np.array_equal(test,corroborated),asset+' 1m/30m OHLC mismatch'
        source=dict(asset=asset,source_15m=str(file),source_15m_sha256=hashlib.file_digest(file.open('rb'),'sha256').hexdigest(),
            original_official_checksums_manifest=str(d.OUT/'candle_sources.json'),
            complete_30m_bars=len(rows),pretest_complete_bars=int(((rows[:,0]+1800)<=d.START).sum()),
            first_open_beijing=r.local_s(rows[0,0]),last_close_beijing=r.local_s(rows[-1,0]+1800),
            dense_unique_grid=True,all_native_1m_OHLC_agree=True,any_forming_30m_bar_included=False)
        metadata.append(source);print(asset,'30M_INPUTS_READY',source,flush=True)
    e.dump('prepared_inputs.json',metadata);e.dump('config.json',config())


def sequence_audit():
    """Describe current rules and actual histories; do not change any signals."""
    metrics=[];examples=[]
    for asset in ('BTC','ETH'):
        file=d.DATA/f'{asset}_15m.csv'
        leg,signals,contexts,base,policy,pair=e.p.prepare(asset,file,d.START,d.END)
        rows=np.loadtxt(file,delimiter=',',skiprows=1)
        bars=rows[(rows[:,0]>=leg.first)&(rows[:,0]<leg.end)]
        closes=bars[:,4]
        lines=np.stack([r.model.sma(closes,n) for n in (20,60,120)]+
                       [r.model.ema(closes,n) for n in (20,60,120)])
        assert lines.shape[1]==len(leg.width)
        state=np.where(leg.up==6,1,np.where(leg.down==6,-1,0))
        counts=dict(asset=asset,candidate_signals=0,all_recent96_density_pass=0,
            prior_bar_density_pass=0,prior_bar_mixed_direction=0,
            prior_bar_same_direction=0,prior_three_bar_state_same_direction=0,
            currently_not_compressed=0,current_width_not_increasing=0)
        for t,side in signals['MA'].items():
            if not d.START*1000<=t<d.END*1000:continue
            i=int((t-r.regime.BAR-leg.first)//r.regime.BAR)
            counts['candidate_signals']+=1
            assert leg.squeeze[96][i]<=.25
            counts['all_recent96_density_pass']+=1
            counts['prior_bar_density_pass']+=int(leg.width[i-1]<=.25)
            counts['prior_bar_mixed_direction']+=int(state[i-1]==0)
            counts['prior_bar_same_direction']+=int(state[i-1]==side)
            counts['prior_three_bar_state_same_direction']+=int(state[i-3]==side)
            counts['currently_not_compressed']+=int(leg.width[i]>.25)
            counts['current_width_not_increasing']+=int(leg.width[i]<=leg.width[i-1])
            if len([x for x in examples if x['asset']==asset])<3 and state[i-1]==side and leg.width[i-1]>.25:
                dense=np.flatnonzero(leg.width[i-95:i+1]<=.25)+i-95
                last=int(dense[-1])
                examples.append(dict(asset=asset,signal_beijing=r.local_s(t/1000),side='LONG' if side==1 else 'SHORT',
                    prior_bar_already_same_direction=True,prior_bar_width_pct=float(leg.width[i-1]),
                    current_width_pct=float(leg.width[i]),latest_compressed_bar_close_beijing=r.local_s((leg.first+(last+1)*r.regime.BAR)/1000),
                    bars_since_latest_compression=i-last,
                    every_current_MA_vs_its_3bars_ago=[dict(name=name,current=float(lines[j,i]),three_bars_ago=float(lines[j,i-3]))
                        for j,name in enumerate(('SMA20','SMA60','SMA120','EMA20','EMA60','EMA120'))]))
        metrics.append(counts)
    e.dump('sequence_audit.json',dict(source_rule='Original code, observation only; signal candidates, not fills',
        tested_period_beijing=[r.local_s(d.START),r.local_s(d.END)],
        current_rule_requires_recent_compression=True,
        current_rule_requires_previous_bar_mixed=False,current_rule_requires_expanding_width=False,
        three_bars_ago_is_each_line_own_value_not_prior_state=True,
        comparison_is_endpoint_difference_not_three_consecutive_slopes=True,metrics=metrics,examples=examples))
    print('SEQUENCE_AUDIT_COMPLETE',metrics,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','validate','replay'])
    parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.mode=='prepare':prepare()
    elif args.mode=='validate':e.validate();sequence_audit()
    else:
        assert args.asset is not None
        e.replay(args.asset)


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
