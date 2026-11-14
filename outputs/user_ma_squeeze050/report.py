"""Measured0.50% comparison, retaining0.25% results without re-executing them."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys
import zipfile

import numpy as np
import run as e
sys.path.insert(0,str(e.ROOT/'outputs/attribution_2026'))
from attribute import normalized

OUT=e.OUT;TZ=timezone(timedelta(hours=8))


def csvrows(file):
    with file.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def dd(a,seed):
    a=np.r_[seed,a];return float(np.max(100*(1-a/np.maximum.accumulate(a))))


def correct_labels(folder,asset,kind,q):
    # The shared template originally described only30m and the annual window.
    # Correct metadata wording only; keep every financial/state/event value.
    before=hashlib.sha256(json.dumps({k:v for k,v in q.items() if k!='config'},sort_keys=True).encode()).hexdigest()
    config=dict(q['config']);fixes={
        'higher_classifier':'Same six requested SMAs on complete30m/1h/4h candles respectively, vs each own3bars ago',
        'high_bar_lookup':'Latest complete higher candle at or before15m signal close; UTC aligned',
        'test_period_beijing':q['period_beijing']}
    adjustments={k:dict(old=config.get(k),new=v) for k,v in fixes.items() if config.get(k)!=v}
    config.update(fixes);q['config']=config
    assert before==hashlib.sha256(json.dumps({k:v for k,v in q.items() if k!='config'},sort_keys=True).encode()).hexdigest()
    if adjustments:
        e.dump(folder,f'{asset}_{kind}_result.json',q)
        e.dump(folder,f'{asset}_{kind}_metadata_labels.json',dict(financial_content_unchanged_sha256=before,
            description='Clarify reused template timeframe/window labels only; no replay or parameter change',adjustments=adjustments))
    return q


def render_recent():
    rows=[];entries=[];closes=[];summary=[]
    for asset in ('BTC','ETH'):
        assert json.loads((e.RECENT/f'{asset}_status.json').read_text())['completed']
        for kind in e.PROFILES:
            q=json.loads((e.RECENT/f'{asset}_{kind}_result.json').read_text());q=correct_labels(e.RECENT,asset,kind,q)
            pos=q['state_at_end']['position']
            row=dict(asset=asset,profile=kind,label=e.LABELS[kind],threshold_pct=.50,
                window_start='2026-11-12T00:00:00+08:00',cutoff_beijing=q['period_beijing'][1],
                new_entries=len(q['entries_since_nov12']),orders=len(q['orders_since_nov12']),
                current_side=('SHORT' if pos['order']['side']==-1 else 'LONG') if pos else 'FLAT',
                current_entry=pos['order']['price'] if pos else '',quantity=pos['order']['qty'] if pos else '',
                rung=pos['rung'] if pos else '',stop=pos['stop'] if pos else '',floating_pnl=q['floating_pnl'],
                mark_price=q['final_mark_price'],cash=q['state_at_end']['cash'],
                PnL_from_nov9=q['ending_equity']-500,return_from_nov9_pct=q['return_pct'])
            rows.append(row)
            entries.extend(dict(asset=asset,profile=kind,label=e.LABELS[kind],**t) for t in q['entries_since_nov12'])
            begin=int(datetime(2026,11,12,tzinfo=TZ).timestamp())
            closes.extend(dict(asset=asset,profile=kind,label=e.LABELS[kind],
                closed_beijing=e.r.local_us(t['closed_us']),**t) for t in q['trades'] if t['closed_us']>=begin*1e6)
    e.write(e.RECENT,'summary.csv',rows);e.write(e.RECENT,'entries_since_nov12.csv',entries);e.write(e.RECENT,'closes_since_nov12.csv',closes)
    e.dump(e.RECENT,'summary.json',dict(completed=True,results=rows,source='Gate public REST actual prints',
        seed='Each profile/asset500 at2026-11-09; no reset Nov12;0.50 rerun from that seed',
        recent_return_not_same_as_nov12_window_return=True))
    text='''# 0.50%近期逐笔实验

只把新六SMA5/10/30/60/120/250的最近96根最小带宽门槛由≤0.25%改为≤0.50%。核心候选与震荡分支的密集条件同步更新；当前震荡带宽上限原本就是0.50%，保持不变；支撑阻力仍是2%绝对距离。

每币每版11月9日从500 USDT起始，重新计算0.50%版本的早前交易和占仓，不接用0.25%的中途持仓，也不在12日重置。使用Gate真实成交、5秒相位2秒、零手续费、3倍名义仓位、原滑点。

BTC核对到13日12:00，ETH核对到13日11:30，均为此前截图对应的固定截止点。

'''
    text+=table(['币种','版本','12日起新开仓','截止状态','当前浮盈USDT'],[
        [t['asset'],t['label'],t['new_entries'],('空单，第'+str(t['rung'])+'档') if t['current_side']=='SHORT' else '空仓' if t['current_side']=='FLAT' else '多单',f"{t['floating_pnl']:+.2f}"] for t in rows])
    text+='\n\n## 窗口内实际触价成交\n\n'
    text+=table(['币种','版本','信号收盘时间','成交时间','方向','限价'],[
        [t['asset'],t['label'],t['signal_beijing'],t['opened_beijing'],'空' if t['side']==-1 else '多',t['entry']] for t in entries])
    text+='''

BTC五版在13日08:45信号后，均于08:47:20.479按71,074.90开空。12日也均有一笔空单；30分钟组合入场较晚，详见表格。截止点均为第2档、止损69,653.40，浮盈差异来自账户余额路径与下单数量。

ETH在12日至截止点五版均没有新开仓，也没有未平仓。此前08:45的最近96根最小带宽为1.2769%，仍大于新阈值0.50%；当时六线向下只有5条，额外方向条件也未满足。走势相似不能代替逐币计算密集度。

具体未向下的是MA30：08:45为2015.1343，三根前08:00为2014.5187，差值+0.6157，按当前规则仍向上；其余五条向下。六条具体数值保存在ETH_0845_six_values.json。截图11:35的均线方向不能代替08:45已收盘K线的判断。

0.25%下BTC五个新版这段均无新开仓，已有结果见`../../btc_nov12_nov13_comparison/results.json`，未重跑其金融结果。ETH0.25%的近期五版完整金融流水此前未运行，不伪造其近期收益作比较；已核对的当日信号不满足密集条件。

窗口内平仓净收益按整笔交易入场以来计算，不能直接当作12日以来净值收益。summary.csv的return_from_nov9_pct也是11月9日起累计，不当作12日收益。

这是一组针对已查看样本提出的用户指定实验，不是独立样本验证。未自动更换默认版本或继续试其他阈值。数据来自Gate，币安截图平台精确成交和用户真实账户未验证。
'''
    (e.RECENT/'report.md').write_text(text,encoding='utf-8')
    return rows


def baseline(asset,kind):
    mapping={'MA15':(e.u.OUT,'USER_MA15'),'M30':(e.u.OUT,'USER_MA15_30M'),
        'H1':(e.h.OUT,'USER_MA15_1H'),'H4':(e.h.OUT,'USER_MA15_4H'),'ER':(e.h.OUT,'USER_MA15_ER')}
    folder,profile=mapping[kind]
    q=json.loads((folder/f'{asset}_{profile}_result.json').read_text());eq=np.load(folder/f'{asset}_{profile}_equity.npy')
    return q,eq


def render_annual():
    summary=[];monthly=[];ledger=[];traces={};comparison=[]
    for asset in ('BTC','ETH'):
        assert json.loads((e.ANNUAL/f'{asset}_status.json').read_text())['completed']
        for kind in e.PROFILES:
            q=json.loads((e.ANNUAL/f'{asset}_{kind}_result.json').read_text());q=correct_labels(e.ANNUAL,asset,kind,q)
            eq=np.load(e.ANNUAL/f'{asset}_{kind}_equity.npy');traces[asset,kind,.50]=eq
            assert abs(eq[-1]-q['ending_equity'])<1e-8
            new=normalized(q);ledger.extend(dict(threshold_pct=.50,**t) for t in new)
            old,old_eq=baseline(asset,kind);traces[asset,kind,.25]=old_eq
            for threshold,data,values,opens,hard in [(.50,q,eq,len(new),sum(t['reason']=='hard_stop' for t in new)),
                  (.25,old,old_eq,len(old['trades'])+bool(old['state_at_end']['position']),sum(t['reason']=='hard_stop' for t in old['trades']))]:
                summary.append(dict(asset=asset,profile=kind,label=e.LABELS[kind],threshold_pct=threshold,
                    return_pct=data['return_pct'],ending_equity=data['ending_equity'],max_drawdown_minute_pct=dd(values,500),
                    opens=opens,hard_stops=hard,old025_financial_result_reused=threshold==.25))
    for kind in e.PROFILES:
        for threshold in (.25,.50):
            eq=traces['BTC',kind,threshold]+traces['ETH',kind,threshold];traces['COMBINED',kind,threshold]=eq
            parts=[t for t in summary if t['profile']==kind and t['threshold_pct']==threshold and t['asset'] in ('BTC','ETH')]
            summary.append(dict(asset='COMBINED',profile=kind,label=e.LABELS[kind],threshold_pct=threshold,
                return_pct=100*(eq[-1]/1000-1),ending_equity=float(eq[-1]),max_drawdown_minute_pct=dd(eq,1000),
                opens=sum(t['opens'] for t in parts),hard_stops=sum(t['hard_stops'] for t in parts),
                old025_financial_result_reused=threshold==.25))
        a=next(t for t in summary if t['asset']=='COMBINED' and t['profile']==kind and t['threshold_pct']==.25)
        b=next(t for t in summary if t['asset']=='COMBINED' and t['profile']==kind and t['threshold_pct']==.50)
        comparison.append(dict(profile=kind,label=e.LABELS[kind],old025_return_pct=a['return_pct'],new050_return_pct=b['return_pct'],
            old025_DD_pct=a['max_drawdown_minute_pct'],new050_DD_pct=b['max_drawdown_minute_pct'],
            old025_opens=a['opens'],new050_opens=b['opens'],return_difference_pp=b['return_pct']-a['return_pct']))
    for asset in ('BTC','ETH','COMBINED'):
        for month in range(1,11):
            begin=int(datetime(2026,month,1,tzinfo=TZ).timestamp());end=int(datetime(2026,month+1,1,tzinfo=TZ).timestamp())
            for kind in e.PROFILES:
                for threshold in (.25,.50):
                    eq=traces[asset,kind,threshold];seed=1000 if asset=='COMBINED' else 500
                    opening=seed if begin==e.d.START else float(eq[(begin-e.d.START)//60-1]);ending=float(eq[(end-e.d.START)//60-1])
                    monthly.append(dict(asset=asset,month=f'2026-{month:02}',profile=kind,threshold_pct=threshold,
                        opening_equity=opening,ending_equity=ending,return_pct=100*(ending/opening-1),pnl_usdt=ending-opening))
    e.write(e.ANNUAL,'summary.csv',summary);e.write(e.ANNUAL,'comparison.csv',comparison)
    e.write(e.ANNUAL,'monthly.csv',monthly);e.write(e.ANNUAL,'trades050.csv',ledger)
    e.dump(e.ANNUAL,'summary.json',dict(results=summary,comparison=comparison,other_years='UNVERIFIED',
        counterparty_trade_match='UNVERIFIED',old025_performance_reused=True,no_automatic_search=True))
    text='''# 新六MA密集阈值0.25%与0.50%对照

用户指定一次对照：只把最近96根15分钟K线最小带宽门槛从≤0.25%放宽为≤0.50%。六条均线仍为SMA5/10/30/60/120/250，方向比较3根前、六线严格同向；当前震荡带宽上限仍0.50%，2%支撑阻力绝对距离、ER阈值、辅助SMA5/SMA20、MACD、挂单和止损规则均不变。

## 2026年1—10月实际回放

同一币安USD-M官方档案，每币500 USDT、独立账户、3倍名义仓位、零手续费、原滑点；原0.25%金融结果直接读取，未重跑。0.50%真实成交回放已实际执行。

'''
    text+=table(['版本','0.25%收益','0.50%收益','0.25%回撤','0.50%回撤','开仓0.25→0.50'],[
        [t['label'],f"{t['old025_return_pct']:+.2f}%",f"{t['new050_return_pct']:+.2f}%",f"{t['old025_DD_pct']:.2f}%",f"{t['new050_DD_pct']:.2f}%",
         f"{t['old025_opens']}→{t['new050_opens']}"] for t in comparison])
    text+='\n\n## 0.50%分币收益\n\n'
    text+=table(['版本','BTC收益','ETH收益'],[[e.LABELS[kind],*[
        f"{next(t for t in summary if t['asset']==asset and t['profile']==kind and t['threshold_pct']==.50)['return_pct']:+.2f}%"
          for asset in ('BTC','ETH')]] for kind in e.PROFILES])
    text+='''

近期Gate逐笔结果另见recent/report.md：BTC五版均在12日和13日新增空单；ETH12日至13日11:30均无新开仓。源市场、区间不同，不把近期收益和年度收益混算。

## 验证与边界

- 克隆原入场函数时，核心ENTRY.squeeze_threshold和对应range_squeeze_pct同时改0.50，避免只改外层门槛而底层仍卡0.25。两个字段代表同一个密集条件。
- 已先在相同新实现中设回0.25，逐一核对已有BTC近期及两币年度五版信号，全部一致；没有重复跑其金融回测。0.50候选保留原0.25候选，新增候选仍需原趋势/距离/量能/回踩等过滤。
- 五版只改该密集门槛；更早交易可改变余额、挂单和占仓，故0.50不采用0.25的中途持仓，并非在旧成交流水里补几笔单。
- 年度数据及逐笔档案沿用官方SHA256和分钟价位核对，严格禁止OHLC降级；5秒相位2秒，激活止损按真实成交价触发，保留原提交边界。
- 近期BTC/ETH使用同源Gate已闭合K线和实际成交；BTC截止13日12:00、ETH截止11:30。新参数从11月9日500 USDT重放且不在12日重置。
- 原0.25%源码、配置和结果均保留；原始Git blob校验不变。metadata_labels.json只修正共享模板中高周期/区间文字，金融内容的SHA256前后不变，没有重新计算或篡改交易/损益。
- 限价触价全量成交是代理，真实排队、部分成交及资金费率未验证/未计入；未使用真实账户或API密钥。
- 近期截图币安平台的精确成交仍因实时接口HTTP451未验证。使用Gate近期开单与Binance年度档案已明确区分。
- 这是用户指定参数的已观察样本对照，未自动选默认版本、未继续搜索阈值。其他年份、对方机器人完整交易匹配率未验证。

## 实际命令

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_squeeze050/run.py validate > outputs/user_ma_squeeze050/validation.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_squeeze050/run.py recent --asset BTC > outputs/user_ma_squeeze050/recent/BTC_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_squeeze050/run.py recent --asset ETH > outputs/user_ma_squeeze050/recent/ETH_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_squeeze050/run.py annual --asset BTC > outputs/user_ma_squeeze050/annual2026/BTC_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_squeeze050/run.py annual --asset ETH > outputs/user_ma_squeeze050/annual2026/ETH_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/user_ma_squeeze050/report.py all > outputs/user_ma_squeeze050/report_run.log 2>&1
```

Python3.12，现有环境，无新增依赖；下载使用已批准的Python网络执行，保留系统代理与TLS。原数据来源见各结果source及*source*.json；近期Gate请求URL/时间/响应SHA256保存在recent/api_requests.jsonl，年度日档案见annual2026/*_tick_sources.json。
'''
    (OUT/'report.md').write_text(text,encoding='utf-8')
    return summary,comparison


def provenance_and_zip():
    e.dump(OUT,'config.json',e.config())
    manifest=json.loads((e.ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text());checks=[]
    for item in manifest['files']:
        b=(e.ROOT/item['path']).read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=item['path'],unchanged=sha==item['sha']))
    assert all(x['unchanged'] for x in checks)
    e.dump(OUT,'source_integrity.json',dict(original_commit=manifest['source_commit'],all_original_files_unchanged=True,files=checks))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for folder in (OUT,e.RECENT,e.ANNUAL):
            for file in sorted(folder.iterdir()):
                if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log','.jsonl'}:z.write(file,'user_ma_squeeze050/'+str(file.relative_to(OUT)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['recent','all']);args=parser.parse_args()
    recent=render_recent()
    if args.mode=='all':
        summary,comparison=render_annual();provenance_and_zip();print(json.dumps(comparison,ensure_ascii=False,indent=2))
    else:print(json.dumps(recent,ensure_ascii=False,indent=2))
