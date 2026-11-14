"""Summarize the four predefined MTF experiments without choosing parameters."""
from collections import Counter
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
PROFILES=['ER','MA15_CONTROL',*e.PROFILES]
LABELS={'ER':'原ER版','MA15_CONTROL':'仅15分钟','MA15_1H':'15分钟＋1小时',
        'MA15_4H':'15分钟＋4小时','MA15_12H':'15分钟＋12小时','MA15_24H':'15分钟＋24小时'}
ASSETS=['BTC','ETH']


def write(name,rows):e.write(name,rows)


def load_csv(file):
    with file.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
         ['| '+' | '.join(str(x) for x in row)+' |' for row in rows])


def dd(values,seed):
    a=np.r_[seed,values];return float(np.max(100*(1-a/np.maximum.accumulate(a))))


def run():
    for asset in ASSETS:
        assert json.loads((OUT/f'{asset}_status.json').read_text())['completed']
        assert json.loads((OUT/f'{asset}_control_regression.json').read_text())['passed']
    assert json.loads((OUT/'validation.json').read_text())['passed']
    summary=[];monthly=[];ledger=[];traces={};results={}
    for asset in ASSETS:
        for profile in PROFILES:
            source=d.OUT if profile=='ER' else OUT
            result=json.loads((source/f'{asset}_{profile}_result.json').read_text())
            equity=np.load(source/f'{asset}_{profile}_equity.npy');traces[asset,profile]=equity;results[asset,profile]=result
            assert len(equity)==(d.END-d.START)//60
            assert abs(equity[-1]-result['ending_equity'])<1e-8
            trades=normalized(result);ledger.extend(trades)
            assert abs(sum(t['net_usdt'] for t in trades)-(result['ending_equity']-500))<1e-7
            summary.append(dict(asset=asset,profile=profile,label=LABELS[profile],
                return_pct=result['return_pct'],ending_equity=result['ending_equity'],
                max_drawdown_minute_pct=dd(equity,500),opens=len(trades),
                closed=sum(t['status']=='CLOSED' for t in trades),
                hard_stops=sum(t['reason']=='hard_stop' for t in trades),
                realized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='CLOSED'),
                unrealized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='OPEN_MARK')))
    for profile in PROFILES:
        traces['COMBINED',profile]=traces['BTC',profile]+traces['ETH',profile]
        selected=[s for s in summary if s['profile']==profile and s['asset'] in ASSETS]
        equity=traces['COMBINED',profile]
        summary.append(dict(asset='COMBINED',profile=profile,label=LABELS[profile],
            return_pct=100*(equity[-1]/1000-1),ending_equity=float(equity[-1]),
            max_drawdown_minute_pct=dd(equity,1000),opens=sum(s['opens'] for s in selected),
            closed=sum(s['closed'] for s in selected),hard_stops=sum(s['hard_stops'] for s in selected),
            realized_pnl_usdt=sum(s['realized_pnl_usdt'] for s in selected),
            unrealized_pnl_usdt=sum(s['unrealized_pnl_usdt'] for s in selected)))
    for asset in [*ASSETS,'COMBINED']:
        for month in range(1,11):
            begin=int(datetime(2026,month,1,tzinfo=TZ).timestamp())
            end=int(datetime(2026,month+1,1,tzinfo=TZ).timestamp())
            for profile in PROFILES:
                trace=traces[asset,profile];seed=1000 if asset=='COMBINED' else 500
                opening=seed if begin==d.START else float(trace[(begin-d.START)//60-1])
                ending=float(trace[(end-d.START)//60-1])
                monthly.append(dict(asset=asset,month=f'2026-{month:02}',profile=profile,label=LABELS[profile],
                    opening_equity=opening,ending_equity=ending,return_pct=100*(ending/opening-1),
                    pnl_usdt=ending-opening,opens=sum(begin*1e6<=t['filled_us']<end*1e6
                        for t in ledger if t['profile']==profile and (asset=='COMBINED' or t['asset']==asset))))
    cases=[('BTC','2026-03-30T06:45:00+08:00'),('ETH','2026-05-18T08:00:00+08:00'),('ETH','2026-06-22T02:30:00+08:00'),
           ('ETH','2026-06-22T21:45:00+08:00'),('ETH','2026-07-07T22:00:00+08:00'),
           ('ETH','2026-10-04T16:00:00+08:00'),('ETH','2026-10-06T01:00:00+08:00')]
    checks=[];audits={asset:load_csv(OUT/f'{asset}_signal_audit.csv') for asset in ASSETS}
    for asset,time in cases:
        ms=int(datetime.fromisoformat(time).timestamp()*1000)
        for profile in e.PROFILES:
            a=next(a for a in audits[asset] if int(a['signal_ms'])==ms and a['profile']==profile)
            actual=[t for t in ledger if t['asset']==asset and t['profile']==profile and t['signal_ms']==ms]
            assert len(actual)<=1
            blocked=a['combined_state']=='transition'
            decision='周期冲突暂停' if blocked else '入场其他条件未通过' if not int(a['eligible_side']) else '形成成交' if actual else '信号通过但未形成成交'
            if blocked:assert not actual
            checks.append(dict(asset=asset,profile=profile,label=LABELS[profile],signal_beijing=time,
                MA15_state=a['MA15_state'],higher_state=a['higher_state'],combined_state=a['combined_state'],
                higher_last_close_beijing=a['higher_last_close_beijing'],eligible_side=a['eligible_side'],
                decision=decision,filled_beijing=actual[0]['filled_beijing'] if actual else '',
                exit_beijing=actual[0]['closed_beijing'] if actual else '',
                net_usdt=actual[0]['net_usdt'] if actual else '',rung=actual[0]['rung'] if actual else ''))
    signal_counts=[]
    for asset in ASSETS:
        signal_counts.extend(json.loads((OUT/f'{asset}_signal_counts.json').read_text()))
    write('summary.csv',summary);write('monthly.csv',monthly);write('trades.csv',ledger)
    write('key_signal_comparison.csv',checks)
    e.dump('summary.json',dict(period='2026-01-01 00:00 to 2026-11-01 00:00 Asia/Shanghai',
        summary=summary,signal_counts=signal_counts,key_signals=checks,parameter_selection_performed=False,
        counterparty_replication_accuracy='UNVERIFIED: reference complete ledger missing'))
    phone='''# 多周期均线分类对照

可以结合。本次将15分钟分别搭配1小时、4小时、12小时和24小时，建立四个独立实验版本；原ER版和单15分钟版均保留。

| 15分钟分类 | 高周期分类 | 新信号处理 |
|---|---|---|
| 上涨 | 上涨 | 允许多，仍需满足原入场条件 |
| 下跌 | 下跌 | 允许空，仍需满足原入场条件 |
| 震荡 | 震荡 | 保留原震荡分支 |
| 其他组合 | | 暂停新信号 |

每个周期均计算SMA20/60/120及EMA20/60/120，与该周期3根前比较，六线全向上为上涨、全向下为下跌，其余为震荡。高周期只取信号时已收盘的K线。暂停时，原挂单继续按60分钟有效期管理，原持仓继续原止损，不因分类冲突直接平仓。

基础入场仍要求15分钟六线同向，所以“两个周期都震荡”不会通过六线同向的新开仓条件；没有为增加交易而放松它。

以下已用同源币安USDT-M真实成交档案实际回放2026年1—10月，每币500 USDT、独立账户、3倍名义仓位、零手续费和原0.02%出场不利滑点。年内不重置，不按高低顺序合成出场。

'''
    by={(s['asset'],s['profile']):s for s in summary}
    phone+=table(['版本','BTC收益','ETH收益','合计收益','合计最大回撤','开仓'],[
        [LABELS[profile],f"{by['BTC',profile]['return_pct']:+.2f}%",f"{by['ETH',profile]['return_pct']:+.2f}%",
         f"{by['COMBINED',profile]['return_pct']:+.2f}%",f"{by['COMBINED',profile]['max_drawdown_minute_pct']:.2f}%",
         by['COMBINED',profile]['opens']] for profile in PROFILES])
    phone+='''

这四组只测试了2026年1—10月，其他年份收益未验证；不能据此判定哪个周期全年更好，或更接近对方机器人。本次没有选出最高收益周期作为默认配置，没有修改其他参数。

24小时均线的SMA120代表120天，明显慢于原120小时ER；12/24小时K线按币安UTC对齐，日线北京时间08:00收盘。该对齐方式和预热起点已单独保存在config.json，并非声称是对方原模型规则。
'''
    (OUT/'phone_report.md').write_text(phone,encoding='utf-8')
    full=phone+'\n\n## 合计月度收益\n\n'
    full+=table(['月份',*[LABELS[x] for x in PROFILES]],[[f'2026-{m:02}',*[
        f"{next(t for t in monthly if t['asset']=='COMBINED' and t['month']==f'2026-{m:02}' and t['profile']==profile)['return_pct']:+.2f}%"
         for profile in PROFILES]] for m in range(1,11)])
    full+='\n\n## 前一轮关键订单的分类与成交\n\n'
    full+=table(['原信号时间','币种','版本','15m方向','高周期方向','处理','该信号成交净损益USDT'],[
        [t['signal_beijing'],t['asset'],t['label'],t['MA15_state'],t['higher_state'],t['decision'],
         f"{t['net_usdt']:+.2f}" if t['net_usdt']!='' else '—'] for t in checks])
    full+='''

该表跟踪原信号时点，不会把其他时间、不同价格的同一波段交易硬配为同一笔。信号通过不等于必然成交；持仓、挂单占用与未触及限价仍会影响成交。

## 计算、数据与执行记录

- 使用原始入场函数，仅将行情分类替换为本次双周期一致性分类。原密集条件、SMA5/MACD确认、2%绝对支撑阻力距离、放量突破及回踩均保留。没有叠加ER第三道过滤。
- 回踩状态在原状态机内继续推进，冲突分类为transition，依原逻辑处理；并非事后从已完成交易中删除亏损或冲突单。
- 暂停会影响原状态机中回踩确认被消耗的时点。审计发现ETH的1小时组合在5月18日08:00保留了一个单15分钟版已消耗的回踩确认，所以当根多了一个合格候选：水平距离2.1203%未通过2%距离，但回踩确认通过。详见`retest_pause_audit.json`。其他七组没有这种新增候选。这是继承原分类状态机的结果，未改变距离或回踩公式，留作与对方核对的细节。
- 高周期输入来自币安官方小时K线，聚合完整UTC 1h/4h/12h/24h块。从2023-01-01 UTC开始预热；测试开始前有1095根完整日线，六线方向有效的预热根数超过900。预热不计收益。
- 官方小时档案SHA256与CHECKSUM逐一核对；小时栅格无缺失或重复；2026年小时OHLC与上一轮原生15分钟数据聚合值全部一致。
- `validation.json`包含九组检查：全部九种分类组合，以及两币四周期的历史前缀重算/未来价格扰动。所有有效信号均断言最新高周期K线已收盘且与15分钟方向相同。
- 回放由原实际成交引擎执行，每5秒检查、相位2秒；冲突只影响新信号，所有挂单/持仓仍由原引擎管理。四个实验及单15分钟对照共享同一份日档案，无OHLC降级。
- 单15分钟对照完整重新运行，其最终净值及逐笔成交/平仓时间、价格、数量、损益、档位、原因与上一轮完全一致；结果保存为`*_control_regression.json`。
- 原源文件未修改，保留Git blob SHA校验；费用只在独立进程设0。逐笔档案只在有可能发生交易事件的日期下载，每个实际使用日档案记录在`*_tick_sources.json`，校验价格处于同源分钟范围。
- 限价全量触价成交是代理，真实排队和部分成交未验证；资金费率按原设置未计入。原提交恰好+10秒边界逻辑保留，未擅自修复。
- `summary.csv`包含分币及合计收益/最大回撤/开仓/硬止损；`monthly.csv`含各币及合计每月收益；`trades.csv`为全部成交和期末持仓估值。
- 本实验不构成对原机器人规则的已验证复刻；缺少对方完整交易流水，交易匹配率和其他年份表现未验证。

## 实际运行命令

工作目录 `/workspace/btc-eth-backtest`，Python 3.12，使用现有虚拟环境，无需另装依赖。

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/ma_multitimeframe_2026/experiment.py prepare > outputs/ma_multitimeframe_2026/prepare.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/ma_multitimeframe_2026/experiment.py prepare > outputs/ma_multitimeframe_2026/prepare_network.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/ma_multitimeframe_2026/experiment.py validate > outputs/ma_multitimeframe_2026/validation.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/ma_multitimeframe_2026/experiment.py replay --asset BTC > outputs/ma_multitimeframe_2026/BTC_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/ma_multitimeframe_2026/experiment.py replay --asset ETH > outputs/ma_multitimeframe_2026/ETH_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/ma_multitimeframe_2026/report.py > outputs/ma_multitimeframe_2026/report_run.log 2>&1
```

首次prepare在默认沙箱因`Operation not permitted`无法连接会话代理，日志保留；同命令获自动审批后在外层执行成功，仍保留系统代理及证书。两个币种回放同样使用获批网络执行，不调用交易账户或密钥。
'''
    (OUT/'report.md').write_text(full,encoding='utf-8')
    manifest=json.loads((e.ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text())
    checks=[]
    for item in manifest['files']:
        b=(e.ROOT/item['path']).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=item['path'],unchanged=actual==item['sha']))
    assert all(t['unchanged'] for t in checks)
    e.dump('source_integrity.json',dict(original_commit=manifest['source_commit'],all_original_files_unchanged=True,files=checks))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(OUT.iterdir()):
            if f.is_file() and f.suffix in {'.json','.csv','.md','.py','.log'}:z.write(f,'ma_multitimeframe_2026/'+f.name)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('REPORTS_COMPLETE','ZIP_BYTES',(OUT/'results.zip').stat().st_size)


if __name__=='__main__':run()
