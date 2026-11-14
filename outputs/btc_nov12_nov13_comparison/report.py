"""Render the actual BTC window replay; signals, orders and fills kept distinct."""
from pathlib import Path
import hashlib
import json
import zipfile

import run as e

OUT=e.OUT;r=e.r


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
       ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def main():
    data=json.loads((OUT/'results.json').read_text());assert data['completed']
    validation=json.loads((OUT/'validation.json').read_text());assert validation['passed']
    summary=[];entries=[];closes=[]
    for result in data['results']:
        pos=result['current_position'];opened=result['current_position_opened_us']
        summary.append(dict(profile=result['profile'],label=result['label'],
            new_entries=len(result['new_entries_in_window']),new_orders=len(result['orders_sent_in_window']),
            long_signals=len(result['long_signals_in_window']),short_signals=len(result['short_signals_in_window']),
            carried_at_start=bool(result['position_at_window_start'] and
                (result['profile'].startswith('OLD') or result['position_at_window_start'].get('position'))),
            current_side=('SHORT' if pos['order']['side']==-1 else 'LONG') if pos else 'FLAT',
            current_entry=pos['order']['price'] if pos else '',current_quantity=pos['order']['qty'] if pos else '',
            current_opened=r.local_us(opened) if opened else '',current_rung=pos['rung'] if pos else '',
            current_stop=pos['stop'] if pos else '',floating_pnl=result['floating_pnl'],mark_price=result['mark_price'],
            cash=result['cash'],equity=result['ending_equity'],verified_event_minutes_this_extension=result['verified_tape_minutes']))
        entries.extend(dict(profile=result['profile'],label=result['label'],**x) for x in result['new_entries_in_window'])
        closes.extend(dict(profile=result['profile'],label=result['label'],closed_beijing=r.local_us(x['closed_us']),**x)
            for x in result['closed_in_window'])
    e.p.csv_out(OUT/'summary.csv',summary);e.p.csv_out(OUT/'entries.csv',entries);e.p.csv_out(OUT/'closes.csv',closes)
    mark=data['results'][0]['mark_price'];assert all(x['mark_price']==mark for x in data['results'])
    phone='''# BTC：11月12日至13日12:00，哪个版本开仓

使用Gate BTC_USDT公开行情与真实成交，截止北京时间2026-11-13 12:00。

共同近期对照从11月9日每版500 USDT开始，未在12日重置。旧两版直接续接此前已验证的仓位；新六MA五个版本补跑11月9日起的同一近期区间，带着账户状态进入12日。这里不是从全年余额续接，也不是用户真实账户。

'''
    phone+=table(['版本','12日～13日12:00新开仓','截至12:00'],[
        [t['label'],str(t['new_entries'])+'笔空单' if t['new_entries'] else '无',
         ('持空，第'+str(t['current_rung'])+'档') if t['current_side']=='SHORT' else '空仓' if t['current_side']=='FLAT' else '持多']
          for t in summary])
    phone+='''

旧均线分类版与旧ER版：12日持有11日开的空单，12日没有新开仓。13日凌晨旧单第2档退出后，08:45收盘再次产生空头信号，08:45:10提交限价单，08:47:20.479按71,074.90触价成交，数量各0.0216 BTC。

'''
    old=[t for t in summary if t['profile'].startswith('OLD')]
    assert len(old)==2 and all(t['new_entries']==1 for t in old)
    assert all(t['current_side']=='SHORT' for t in old)
    assert all(t['new_entries']==0 and t['current_side']=='FLAT' for t in summary if t['profile'].startswith('NEW'))
    phone+=f"截至12:00，两旧版仍持该空单，止损档位{old[0]['current_rung']}，止损价{old[0]['current_stop']:,.2f}。按Gate最后完整1分钟收盘价{mark:,.2f}估值，每笔当前浮盈约{old[0]['floating_pnl']:.2f} USDT；没有因价格继续下跌而全平。\n"
    phone+='''

新六MA五版：12日到截止点都没有合格新信号，也没有早前挂单在窗口内成交；进入12日和截止时均为空仓。没有把“有信号”当成已成交。

旧两版六线为SMA20/60/120＋EMA20/60/120。新五版六线为SMA5/10/30/60/120/250，分别使用单15分钟、加30分钟、加1小时、加4小时或ER分类。

本次没有改参数、没有真实交易。截图是币安，当前结果来自Gate；币安实时接口此前返回HTTP451，截图平台的精确价格/成交和用户真实账户状态未验证。
'''
    (OUT/'phone_report.md').write_text(phone,encoding='utf-8')
    full=phone+'\n\n## 窗口内成交记录\n\n'
    full+=table(['版本','信号收盘时间','发送时间','实际触价成交','方向','限价','数量'],[
        [x['label'],x['signal_beijing'],r.local_s(x['submitted_ms']/1000),x['opened_beijing'],
         '空' if x['side']==-1 else '多',x['entry'],x['quantity']] for x in entries])
    full+='\n\n## 窗口内平仓（整笔交易收益）\n\n'
    full+=table(['版本','平仓时间','档位','触发价','含滑点平仓价','整笔净收益USDT'],[
        [x['label'],x['closed_beijing'],x['rung'],x['trigger_print'],x['exit'],f"{x['net']:+.6f}"] for x in closes])
    full+='''

上表平仓收益是从该笔11日入场开始计算，不能当作单独12日以来的净值收益。当前浮盈只对当前未平仓单计算。

## 执行与验证

- 旧两版复用已验证的11月9日至13日09:32:32流水、余额、持仓、挂单、止损档位和数量，不重置、不重新估计旧成交；这里只补回放09:32:32至12:00。
- 续接点在分钟中间。先回到09:32所属分钟，以原引擎完整分钟高低价作保守事件排除，再仅重放时间戳≥09:32:32的实际成交和轮询，避免重复处理快照之前的事件。原止损和金融计算未改。
- 新五版没有既有Gate近期账户快照，因此按与旧近期实验相同的11月9日500 USDT起点实际回放，记录进入12日时的状态；未从12日空仓重置，也未假称接续了年度账户。
- 各版使用相同Gate15分钟和1分钟行情，同一份实际成交缓存；5秒轮询相位2、零手续费、3倍名义仓位、原0.02%不利出场滑点与原价量步长。
- 高周期按同源完整15分钟K线聚合，新SMA250高周期历史足够。只有截至信号时已经完成的30m/1h/4h K线用于分类。
- 原始旧信号前缀与之前保存文件完全一致。将当前未收盘12:00—12:15边界K线价格/成交量大幅改动，七版截至12:00的信号均不变；未用未收盘K线生成信号。
- 12:00收盘信号如有，只在12:00:10之后可能提交，未计入截止12:00的新开仓。完整signal_audit.csv保留截止信号便于核对。
- 实际价格数据与原生分钟OHLC核对，严格禁止OHLC降级或有利/不利顺序假设。触价全量成交仍是代理，排队和部分成交未验证；资金费率未计入。
- 原恰好+10秒边界按原版保留。本次只检验指定版本，不改2%绝对支撑阻力距离、密集阈值、周期或入场条件。
- 原始响应、URL、抓取时间和SHA256在api_requests.jsonl和data/responses中；旧数据和快照引用保存在inputs.json及各结果文件，原始代码文件校验未变化。

## 实际运行命令

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/btc_nov12_nov13_comparison/run.py prepare > outputs/btc_nov12_nov13_comparison/prepare.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/btc_nov12_nov13_comparison/run.py validate > outputs/btc_nov12_nov13_comparison/validation.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -u outputs/btc_nov12_nov13_comparison/run.py replay > outputs/btc_nov12_nov13_comparison/replay.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/btc_nov12_nov13_comparison/report.py > outputs/btc_nov12_nov13_comparison/report_run.log 2>&1
```

工作目录/workspace/btc-eth-backtest，Python3.12，现有环境，无新增依赖；Gate公开行情下载使用已获批准的Python网络执行，保留系统代理/TLS，不使用账户密钥。
'''
    (OUT/'report.md').write_text(full,encoding='utf-8')
    manifest=json.loads((e.ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text());checks=[]
    for item in manifest['files']:
        b=(e.ROOT/item['path']).read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=item['path'],unchanged=sha==item['sha']))
    assert all(t['unchanged'] for t in checks)
    e.dump('source_integrity.json',dict(original_commit=manifest['source_commit'],all_original_files_unchanged=True,files=checks))
    with zipfile.ZipFile(OUT/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(OUT.iterdir()):
            if file.is_file() and file.suffix in {'.py','.json','.csv','.md','.log','.jsonl'}:z.write(file,'btc_nov12_nov13_comparison/'+file.name)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('BTC_WINDOW_REPORT_COMPLETE','ZIP_BYTES',(OUT/'results.zip').stat().st_size)


if __name__=='__main__':main()
