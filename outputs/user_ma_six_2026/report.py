"""Report the newly specified six SMAs; do not relabel old results."""
from datetime import datetime,timedelta,timezone
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import experiment as e
sys.path.insert(0,str(e.ROOT/'outputs/attribution_2026'))
from attribute import normalized

OUT=e.OUT;d=e.d;TZ=timezone(timedelta(hours=8))
ASSETS=('BTC','ETH');PROFILES=('OLD_SIX_CONTROL',*e.PROFILES)
LABELS={'OLD_SIX_CONTROL':'旧六线15分钟（留档）','USER_MA15':'新六MA：15分钟',
        'USER_MA15_30M':'新六MA：15分钟＋30分钟'}


def readcsv(file):
    with file.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def dd(values,seed):
    v=np.r_[seed,values];return float(np.max(100*(1-v/np.maximum.accumulate(v))))


def sequence_observations():
    counts=[];examples=[]
    for asset in ASSETS:
        candidates=[t for t in readcsv(OUT/f'{asset}_signal_audit.csv')
             if t['profile']=='USER_MA15' and int(t['eligible_side'])]
        counts.append(dict(asset=asset,candidates=len(candidates),
            previous_bar_already_same_direction=sum(t['previous_MA15_state']==t['MA15_state'] for t in candidates),
            previous_bar_mixed_or_flat=sum(t['previous_MA15_state']=='range' for t in candidates),
            previous_bar_density_at_most_025=sum(float(t['previous_width_pct'])<=.25 for t in candidates),
            current_width_not_expanding=sum(float(t['current_width_pct'])<=float(t['previous_width_pct']) for t in candidates),
            more_than_one_bar_since_last_compression=sum(int(t['bars_since_last_compression'])>1 for t in candidates),
            all_candidates_recent96_density_pass=all(float(t['min96_width_pct'])<=.25 for t in candidates)))
        file=d.DATA/f'{asset}_15m.csv';leg=e.user_build(file,(d.START-30*86400)*1000,d.END*1000)
        raw=np.loadtxt(file,delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)]
        lines=np.stack([e.r.model.sma(raw[:,4],n) for n in e.PERIODS])
        chosen=[]
        for mode in ('previous_mixed','already_aligned'):
            candidate=next((t for t in candidates if (t['previous_MA15_state']=='range' if mode=='previous_mixed'
                           else t['previous_MA15_state']==t['MA15_state'] and int(t['bars_since_last_compression'])>1)),None)
            if candidate:chosen.append((mode,candidate))
        for mode,t in chosen:
            i=int((int(t['signal_ms'])-e.r.regime.BAR-leg.first)//e.r.regime.BAR)
            examples.append(dict(asset=asset,example_type=mode,signal=t,
                each_MA_compared_with_its_own_3bars_ago=[dict(MA='SMA'+str(n),current=float(lines[j,i]),
                    own_value_3bars_ago=float(lines[j,i-3]),difference=float(lines[j,i]-lines[j,i-3]))
                    for j,n in enumerate(e.PERIODS)]))
    e.dump('sequence_audit.json',dict(source='New user-specified six SMA candidate signals, not completed trades',
        immediate_prior_mixed_state_not_required=True,bandwidth_expansion_not_required=True,
        three_bars_ago_means_numeric_endpoint_comparison=True,counts=counts,examples=examples))
    return counts


def run():
    for asset in ASSETS:
        assert json.loads((OUT/f'{asset}_status.json').read_text())['completed']
        assert json.loads((OUT/f'{asset}_control_regression.json').read_text())['passed']
    assert json.loads((OUT/'validation.json').read_text())['passed']
    traces={};summary=[];ledger=[];monthly=[]
    for asset in ASSETS:
        for profile in PROFILES:
            q=json.loads((OUT/f'{asset}_{profile}_result.json').read_text())
            equity=np.load(OUT/f'{asset}_{profile}_equity.npy');traces[asset,profile]=equity
            assert len(equity)==(d.END-d.START)//60 and abs(equity[-1]-q['ending_equity'])<1e-8
            trades=normalized(q);ledger.extend(trades)
            summary.append(dict(asset=asset,profile=profile,label=LABELS[profile],
                return_pct=q['return_pct'],ending_equity=q['ending_equity'],
                max_drawdown_minute_pct=dd(equity,500),opens=len(trades),
                closed=sum(t['status']=='CLOSED' for t in trades),hard_stops=sum(t['reason']=='hard_stop' for t in trades),
                realized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='CLOSED'),
                unrealized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='OPEN_MARK')))
    for profile in PROFILES:
        equity=traces['BTC',profile]+traces['ETH',profile];traces['COMBINED',profile]=equity
        selected=[t for t in summary if t['profile']==profile and t['asset'] in ASSETS]
        summary.append(dict(asset='COMBINED',profile=profile,label=LABELS[profile],
            return_pct=100*(equity[-1]/1000-1),ending_equity=float(equity[-1]),
            max_drawdown_minute_pct=dd(equity,1000),opens=sum(t['opens'] for t in selected),
            closed=sum(t['closed'] for t in selected),hard_stops=sum(t['hard_stops'] for t in selected),
            realized_pnl_usdt=sum(t['realized_pnl_usdt'] for t in selected),
            unrealized_pnl_usdt=sum(t['unrealized_pnl_usdt'] for t in selected)))
    for asset in (*ASSETS,'COMBINED'):
        for month in range(1,11):
            begin=int(datetime(2026,month,1,tzinfo=TZ).timestamp());end=int(datetime(2026,month+1,1,tzinfo=TZ).timestamp())
            for profile in PROFILES:
                eq=traces[asset,profile];seed=1000 if asset=='COMBINED' else 500
                opening=seed if begin==d.START else float(eq[(begin-d.START)//60-1]);ending=float(eq[(end-d.START)//60-1])
                monthly.append(dict(asset=asset,profile=profile,label=LABELS[profile],month=f'2026-{month:02}',
                    opening_equity=opening,ending_equity=ending,return_pct=100*(ending/opening-1),pnl_usdt=ending-opening,
                    opens=sum(begin*1e6<=t['filled_us']<end*1e6 for t in ledger
                        if t['profile']==profile and (asset=='COMBINED' or t['asset']==asset))))
    counts=sequence_observations()
    e.write('summary.csv',summary);e.write('monthly.csv',monthly);e.write('trades.csv',ledger)
    e.dump('summary.json',dict(config=e.config(),results=summary,sequence_counts=counts,
        new_periods_other_years='UNVERIFIED',new_periods_ER_profile='NOT_RUN',
        robot_trade_match='UNVERIFIED: no full reference ledger',optimization_performed=False))
    by={(t['asset'],t['profile']):t for t in summary}
    phone='''# 新六条MA及半小时对照

按用户最新明确指令，本版本的六条主均线为 **SMA5、SMA10、SMA30、SMA60、SMA120、SMA250**，MA按简单移动平均计算。

旧版是SMA20/60/120和EMA20/60/120，原文件与结果均保留。旧版收益不能代表这组新六MA。此前旧六线定义的30分钟版本只准备了数据，未执行收益回测，已在旧目录标记SUPERSEDED。

本次实际跑2026年1—10月，分别测试新六MA的“单15分钟”与“15分钟＋30分钟”，使用相同币安真实成交档案、每币500 USDT独立账户、3倍名义仓位、零手续费、原0.02%不利出场滑点。

'''
    phone+=table(['新六MA版本','BTC收益','ETH收益','合计收益','合计最大回撤','开仓'],[
        [LABELS[p],f"{by['BTC',p]['return_pct']:+.2f}%",f"{by['ETH',p]['return_pct']:+.2f}%",
         f"{by['COMBINED',p]['return_pct']:+.2f}%",f"{by['COMBINED',p]['max_drawdown_minute_pct']:.2f}%",by['COMBINED',p]['opens']]
         for p in e.PROFILES])
    phone+='''

**“与3根前比较”**：当前每条均线的数值，分别与它自身3根K线前的数值比较。15分钟相隔45分钟，30分钟相隔90分钟。不是要求3根前已六线同向，也不要求中间每一根都同向变化。

所以“3根前还聚集或混合、现在六线都向上/向下”可以同时成立。方向比较与均线距离是两个条件：聚集看六线之间距离，混合看各线方向。

当前保留的聚集条件是：最近96根15分钟K线（含当前根）里，至少一次六线带宽≤0.25%。没有要求紧邻上一根必须聚集/混合，也没有单独要求本根带宽扩大。若要求“刚从聚集或混合转为发散”，还需要明确转变窗口和发散定义；本次未擅自加入。

方向同向也未强制短长均线按MA5>MA10>MA30>MA60>MA120>MA250排序；“多头/空头排列”与“六条各自向上/向下”是不同条件，本次保留后者。

全部六条仍用于密集带宽、方向及收盘突破判断，开仓方向需6/6同向，没有启用5/6放行。30分钟组合只用已收盘30分钟K线，两周期方向冲突时暂停新信号；旧挂单和持仓按原有效期与止损继续管理。

MACD及原趋势辅助SMA5/SMA20确认保留，其中SMA20不属于新六条主均线。2%绝对支撑阻力距离、回踩、放量、限价和止损规则未改。没有按收益再调参数。

其他年份、新六MA搭配原ER版的收益、以及对方机器人交易匹配度均未验证。
'''
    (OUT/'phone_report.md').write_text(phone,encoding='utf-8')
    report=phone+'\n\n## 合计月度收益\n\n'
    report+=table(['月份',*[LABELS[p] for p in e.PROFILES]],[[f'2026-{month:02}',*[
        f"{next(t for t in monthly if t['asset']=='COMBINED' and t['profile']==profile and t['month']==f'2026-{month:02}')['return_pct']:+.2f}%"
            for profile in e.PROFILES]] for month in range(1,11)])
    report+='\n\n## 先聚集/混合再发散的核对\n\n'
    report+=table(['币种','单15m合格候选','上一根已同向','上一根混合/持平','上一根带宽≤0.25%','本根带宽未扩大'],[
        [t['asset'],t['candidates'],t['previous_bar_already_same_direction'],t['previous_bar_mixed_or_flat'],
         t['previous_bar_density_at_most_025'],t['current_width_not_expanding']] for t in counts])
    report+='''

上表是候选信号而非成交单。所有合格候选都符合最近96根密集条件，但不强制紧邻前一根密集/混合，也不强制本根带宽增加。`sequence_audit.json`给出实际数值和已在同向状态仍触发候选的例子。

本轮未决定“混合或密集出现后多少根内必须触发”“发散具体按方向还是带宽增加”“首次信号只允许一次”等缺失定义，不将猜测写入当前规则。

## 执行和来源

- 新build函数从原函数只替换六均线定义这一条语句，原始文件字节不改；密集、方向、全线突破使用新六SMA。MACD序列与旧build完全一致。
- 新30分钟K线由此前官方校验过的两根连续15分钟完整K线合并，测试开始前有2160根完整30分钟预热K线，足够SMA250及三根前比较；全部测试用30分钟OHLC与原生1分钟聚合值完全一致。
- `validation.json`保存新六SMA计算、密集度、方向、突破、MACD不变及30分钟历史前缀/未来价格扰动检查，均通过。
- 新15分钟与15分钟＋30分钟使用原行情分类和回踩状态机，仅替换六MA定义与本次一致性分类。没有加第三层ER过滤，也没有事后筛选交易。
- 旧六线控制账户同步完整重跑，余额与逐笔开平仓时间、价格、数量、损益、档位、原因与之前完全一致。`*_control_regression.json`保存核对。
- 实际成交档案来自币安官方USD-M，逐日CHECKSUM校验和原生分钟价格范围检查；清单见`*_tick_sources.json`。原生15m/1m及官方校验和清单见`../attribution_2026/candle_sources.json`。
- 沿用原引擎分钟高低价排除不可能事件的分钟，再用实际成交和5秒相位2秒轮询推进有事件的分钟；禁止OHLC降级。不合成“有利/不利先到”。日档案解析后删除，保留来源和SHA256供复现。
- 限价是全量触价成交代理，排队及部分成交未验证，资金费率未计入；原恰好+10秒提交边界按原版保留。
- `summary.csv`含分币/合计收益、回撤、开仓、硬止损；`monthly.csv`含分币及合计逐月收益；`trades.csv`为完整流水，未平仓若有则按窗口收盘价另记OPEN_MARK，不伪造平仓。
- 新六MA搭配原ER版未运行；其他年份未运行；对方机器人完整流水缺失，交易复刻准确度未验证。

## 实际命令

工作目录`/workspace/btc-eth-backtest`，Python3.12，使用现有环境，无新增依赖。

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_2026/experiment.py prepare > outputs/user_ma_six_2026/prepare.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_2026/experiment.py validate > outputs/user_ma_six_2026/validation.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_2026/experiment.py replay --asset BTC > outputs/user_ma_six_2026/BTC_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_2026/experiment.py replay --asset ETH > outputs/user_ma_six_2026/ETH_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/user_ma_six_2026/report.py > outputs/user_ma_six_2026/report_run.log 2>&1
```

准备与验证仅读本地已核对数据；逐笔下载按已批准的Python网络执行，保留代理/TLS，未访问真实交易账户或API密钥。
'''
    (OUT/'report.md').write_text(report,encoding='utf-8')
    manifest=json.loads((e.ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text());checks=[]
    for item in manifest['files']:
        b=(e.ROOT/item['path']).read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=item['path'],unchanged=sha==item['sha']))
    assert all(t['unchanged'] for t in checks)
    e.dump('source_integrity.json',dict(original_commit=manifest['source_commit'],all_original_files_unchanged=True,files=checks))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(OUT.iterdir()):
            if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log'}:z.write(file,'user_ma_six_2026/'+file.name)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('USER_SIX_MA_REPORT_COMPLETE','ZIP_BYTES',(OUT/'results.zip').stat().st_size)


if __name__=='__main__':run()
