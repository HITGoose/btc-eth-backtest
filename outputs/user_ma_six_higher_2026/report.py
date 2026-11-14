"""Phone report: all versions here use the same new six SMA entry definition."""
from datetime import datetime,timedelta,timezone
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import run_higher as e
sys.path.insert(0,str(e.ROOT/'outputs/attribution_2026'))
from attribute import normalized

OUT=e.OUT;d=e.d;TZ=timezone(timedelta(hours=8))
ASSETS=('BTC','ETH')
PROFILES=('USER_MA15_CONTROL','USER_MA15_30M','USER_MA15_1H','USER_MA15_4H','USER_MA15_ER')
LABELS={'USER_MA15_CONTROL':'新六MA：单15分钟','USER_MA15_30M':'新六MA：15分钟＋30分钟',
    'USER_MA15_1H':'新六MA：15分钟＋1小时','USER_MA15_4H':'新六MA：15分钟＋4小时',
    'USER_MA15_ER':'新六MA入场＋原ER分类'}


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def dd(values,seed):
    a=np.r_[seed,values];return float(np.max(100*(1-a/np.maximum.accumulate(a))))


def run():
    for asset in ASSETS:
        assert json.loads((OUT/f'{asset}_status.json').read_text())['completed']
        assert json.loads((OUT/f'{asset}_control_regression.json').read_text())['passed']
    assert json.loads((OUT/'validation.json').read_text())['passed']
    summary=[];monthly=[];ledger=[];traces={}
    for asset in ASSETS:
        for profile in PROFILES:
            source=e.u.OUT if profile=='USER_MA15_30M' else OUT
            result=json.loads((source/f'{asset}_{profile}_result.json').read_text())
            eq=np.load(source/f'{asset}_{profile}_equity.npy');traces[asset,profile]=eq
            assert len(eq)==(d.END-d.START)//60 and abs(eq[-1]-result['ending_equity'])<1e-8
            trades=normalized(result);ledger.extend(trades)
            summary.append(dict(asset=asset,profile=profile,label=LABELS[profile],
                return_pct=result['return_pct'],ending_equity=result['ending_equity'],
                max_drawdown_minute_pct=dd(eq,500),opens=len(trades),closed=sum(t['status']=='CLOSED' for t in trades),
                hard_stops=sum(t['reason']=='hard_stop' for t in trades),
                realized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='CLOSED'),
                unrealized_pnl_usdt=sum(t['net_usdt'] for t in trades if t['status']=='OPEN_MARK')))
    for profile in PROFILES:
        eq=traces['BTC',profile]+traces['ETH',profile];traces['COMBINED',profile]=eq
        members=[t for t in summary if t['profile']==profile and t['asset'] in ASSETS]
        summary.append(dict(asset='COMBINED',profile=profile,label=LABELS[profile],
            return_pct=100*(eq[-1]/1000-1),ending_equity=float(eq[-1]),max_drawdown_minute_pct=dd(eq,1000),
            opens=sum(t['opens'] for t in members),closed=sum(t['closed'] for t in members),hard_stops=sum(t['hard_stops'] for t in members),
            realized_pnl_usdt=sum(t['realized_pnl_usdt'] for t in members),unrealized_pnl_usdt=sum(t['unrealized_pnl_usdt'] for t in members)))
    for asset in (*ASSETS,'COMBINED'):
        for month in range(1,11):
            begin=int(datetime(2026,month,1,tzinfo=TZ).timestamp());end=int(datetime(2026,month+1,1,tzinfo=TZ).timestamp())
            for profile in PROFILES:
                eq=traces[asset,profile];seed=1000 if asset=='COMBINED' else 500
                opening=seed if begin==d.START else float(eq[(begin-d.START)//60-1]);ending=float(eq[(end-d.START)//60-1])
                monthly.append(dict(asset=asset,month=f'2026-{month:02}',profile=profile,label=LABELS[profile],
                    opening_equity=opening,ending_equity=ending,return_pct=100*(ending/opening-1),pnl_usdt=ending-opening,
                    opens=sum(begin*1e6<=t['filled_us']<end*1e6 for t in ledger
                         if t['profile']==profile and (asset=='COMBINED' or t['asset']==asset))))
    e.write('summary.csv',summary);e.write('monthly.csv',monthly);e.write('trades.csv',ledger)
    e.dump('summary.json',dict(config=e.config(),results=summary,other_years='UNVERIFIED',
        robot_trade_replication_accuracy='UNVERIFIED: full reference ledger missing',
        higher_pair_interpretation='Separate15m+1h and15m+4h, not all frames stacked',
        new_30m_reference='Previous completed run, same new six SMAs, not rerun here'))
    by={(t['asset'],t['profile']):t for t in summary}
    phone='''# 新六MA＋1小时/4小时，与原ER分类对照

本表所有版本均使用SMA5、SMA10、SMA30、SMA60、SMA120、SMA250作为六条15分钟入场均线。

六MA决定入场形态，ER决定环境分类，两者可以搭配。ER公式只用小时收盘价的净变化/逐小时绝对变化总和，不依赖旧六均线；本次“新六MA＋原ER”保持12小时阈值0.28284271247461906、120小时阈值0.10，重新运行，不引用旧六线的ER收益。

1小时和4小时分别独立测试：高周期同样使用新六SMA，与各自3根前比较；与15分钟方向一致才允许对应方向的新信号，冲突或一方震荡时暂停，双方震荡保留原分支。高周期只用已收盘K线。没有把1h/4h全部叠在一起，也没有同时再加ER过滤。

2026年1—10月，币安官方真实成交档案回放；每币500 USDT独立账户，3倍名义仓位、零手续费、原0.02%出场不利滑点，其他规则不变。

'''
    phone+=table(['版本','BTC收益','ETH收益','合计收益','最大回撤','开仓'],[
        [LABELS[p],f"{by['BTC',p]['return_pct']:+.2f}%",f"{by['ETH',p]['return_pct']:+.2f}%",
         f"{by['COMBINED',p]['return_pct']:+.2f}%",f"{by['COMBINED',p]['max_drawdown_minute_pct']:.2f}%",by['COMBINED',p]['opens']]
         for p in PROFILES])
    phone+='''

单15分钟控制账户的完整开平仓事件和余额与上一轮完全一致。30分钟组引用上一轮同一新六MA定义的已完成结果。未把旧SMA/EMA20/60/120结果混入本表。

## 今天约08点ETH会做空吗

按Gate ETH_USDT公开行情和当前规则，2026年11月13日08:00—09:00没有合格新空头信号。07:00—09:15也没有合格空头信号。

08:00、08:15、08:30、08:45分别只有3、4、4、5条均线向下，未满足六条全部向下；最近96根最小带宽1.2769%，超过必须≤0.25%的条件。基础入场不通过，加入高周期或换ER环境分类均不能绕过它。

币安实时合约接口返回HTTP451，因此日内核对改用Gate并记录原始响应。截图平台的精确结果、已有真实持仓和实际成交未验证；此处仅完成信号核对，没有声称执行了今天的逐笔成交回放。详见`../eth_today_20261113/report.md`及`signal_check.csv`。

旧SMA20/60/120＋EMA20/60/120的单15分钟均线分类版也不会新开单：08:45已六线向下、MACD柱为负，但最近96根最小带宽0.3564%仍超过0.25%。从11月12日23:00已验证的空仓、无挂单云端模拟状态继续核对至13日09:30，没有任何新信号。旧信号前缀与此前保存结果完全一致，故没有需要逐笔判定成交的新挂单。用户真实账户状态不在此结论内。详见`../eth_today_20261113/old_six_report.md`。

本轮只跑以上固定对照，未按收益再调均线、ER阈值或密集条件。其他年份、对方机器人交易匹配度未验证。
'''
    (OUT/'phone_report.md').write_text(phone,encoding='utf-8')
    full=phone+'\n\n## 合计月度收益\n\n'
    full+=table(['月份',*[LABELS[p] for p in PROFILES]],[[f'2026-{month:02}',*[
        f"{next(t for t in monthly if t['asset']=='COMBINED' and t['profile']==profile and t['month']==f'2026-{month:02}')['return_pct']:+.2f}%"
          for profile in PROFILES]] for month in range(1,11)])
    full+='''

## 保留条件和完整性

- 六线密集、方向及收盘突破均使用新六SMA；当前与自身3根前比较，既不要求之前已经同向，也不强制中间每根单调。
- 保留最近96根（含当前根）至少一次带宽≤0.25%，并未额外加入“上一根必须混合/聚集、本根首次发散”、带宽扩大或MA短长排序条件。
- 保留原MACD、趋势辅助SMA5/SMA20、2%绝对支撑阻力距离、突破/回踩和一币一仓或挂单；暂停只阻止新信号，旧挂单按60分钟有效期管理，已有仓位继续止损。
- 1h/4h数据来自先前已按官方CHECKSUM验证的Binance小时K线，从2023年开始预热，按UTC整点完整聚合。使用SMA250，1h对应250小时、4h对应1000小时。验证时小时栅格完整，未来价格扰动与历史前缀重算通过。
- 入场核心候选在各分类分支相同，只更改分类。回踩确认与消耗仍继承原状态机，不是事后从已完成交易里删除订单。
- 实际成交档案逐日官方SHA256校验，价位核对同源原生分钟范围，无OHLC降级。事件可能分钟使用真实成交和5秒相位2秒轮询，保留原提交边界逻辑。
- 限价采用全量触价代理，排队、部分成交与资金费率未验证/未计入；没有真实账户和交易API密钥。
- 原始GitHub源码文件未修改。新六MA单15分钟控制账户完整重跑，与上一轮逐笔时间、价格、数量、损益、档位、原因和期末余额完全一致。
- `summary.csv`含分币及合计收益、回撤、开仓、硬止损；`monthly.csv`含分币和合计逐月收益；`trades.csv`为全部流水，未平仓如有按共同窗口收盘价另标OPEN_MARK。
- 官方K线来源和校验和：`../ma_multitimeframe_2026/hourly_sources.json`与`../attribution_2026/candle_sources.json`；实际使用逐笔档案见本目录`*_tick_sources.json`。
- 此次为2026年1—10月固定对照，未据此选默认参数，也未声称最高收益版本更接近对方机器人。

## 实际命令

工作目录`/workspace/btc-eth-backtest`，Python3.12，复用已验证数据及虚拟环境。

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_higher_2026/run_higher.py validate > outputs/user_ma_six_higher_2026/validation.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_higher_2026/run_higher.py replay --asset BTC > outputs/user_ma_six_higher_2026/BTC_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/user_ma_six_higher_2026/run_higher.py replay --asset ETH > outputs/user_ma_six_higher_2026/ETH_run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/user_ma_six_higher_2026/report.py > outputs/user_ma_six_higher_2026/report_run.log 2>&1
```

逐笔下载使用获批准的Python网络执行，保留代理和TLS证书；年度档案可访问。HTTP451仅发生在本次截图核对所需的币安实时fapi接口，错误与Gate替代来源已单独保存。
'''
    (OUT/'report.md').write_text(full,encoding='utf-8')
    original=json.loads((e.ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text());checks=[]
    for item in original['files']:
        b=(e.ROOT/item['path']).read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=item['path'],unchanged=sha==item['sha']))
    assert all(t['unchanged'] for t in checks)
    e.dump('source_integrity.json',dict(original_commit=original['source_commit'],all_original_files_unchanged=True,files=checks))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(OUT.iterdir()):
            if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log'}:z.write(file,'user_ma_six_higher_2026/'+file.name)
        today=e.ROOT/'outputs/eth_today_20261113'
        for file in sorted(today.iterdir()):
            if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log','.jsonl'}:z.write(file,'eth_today_20261113/'+file.name)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('NEW_SIX_HIGHER_REPORT_COMPLETE','ZIP_BYTES',(OUT/'results.zip').stat().st_size)


if __name__=='__main__':run()
