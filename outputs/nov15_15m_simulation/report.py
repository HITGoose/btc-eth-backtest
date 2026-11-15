from pathlib import Path
import sys,json,csv,datetime,hashlib,zipfile
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import shared as s
TZ=datetime.timezone(datetime.timedelta(hours=8));FROM=1794153600;CUT=1794614400;C=R/'outputs/nov15_continuation';rows=[];trades=[];audit=[]
start9={r['asset']:r['Nov9_start_equity']for r in json.loads((C/'account_summary.json').read_text())}
def local(us):return datetime.datetime.fromtimestamp(us/1e6,TZ).isoformat()
def met(m,init):
 p=np.maximum.accumulate(np.r_[init,m]);return dict(ending_equity=float(m[-1]),net_since_Nov9=float(m[-1]-init),return_since_Nov9_pct=float(100*(m[-1]/init-1)),max_drawdown_since_Nov9_pct=float(np.max(100*(1-np.r_[init,m]/p))))
curves={}
for asset in ['BTC','ETH']:
 for path in ['OHLC','OLHC']:
  groups=['B','B_PLUS_REBOUND']if asset=='BTC'else ['B','I100','I50','I25','B_PLUS_REBOUND']
  for g in groups:
   folder=O/'runs'/asset/path/'results';q=json.loads((folder/f'{g}_result.json').read_text());v=np.load(folder/f'{g}_equity.npz')['marks'];ix=(FROM-1793462400)//60;part=v[ix:];curves[asset,path,g]=part;row=dict(asset=asset,path=path,version=g,Nov9_initial_equity=start9[asset],**met(part,start9[asset]),new_simulated_closed=sum(t['opened_us']>=CUT*1000000 for t in q['trades']),open_count=int(bool(q['state_at_end']['position'])),status=q['status']);rows.append(row)
   residual=q['cash']-500-sum(t['delta']for t in q['cash_events']);assert abs(residual)<1e-7;pos=q['state_at_end']['position'];float_pnl=pos['order']['side']*pos['order']['qty']*(q['actual_raw_last_mark']-pos['order']['price'])if pos else 0.;assert abs(q['ending_equity']-q['cash']-float_pnl)<1e-7
   oldfile=R/'outputs/rebound_followdown/runs/RECENT'/asset/'results/B_PLUS_REBOUND_result.json'if g=='B_PLUS_REBOUND'else C/'runs'/asset/'results'/f'C2_{g}_F_TOUCH_result.json';old=json.loads(oldfile.read_text());old_eq=np.load(oldfile.with_name(oldfile.name.replace('_result.json','_equity.npz')))['marks'];assert np.array_equal(v[:len(old_eq)],old_eq);assert q['trades'][:len(old['trades'])]==old['trades'];audit.append(dict(asset=asset,path=path,version=g,cash_event_residual=residual,old_equity_and_trade_prefix_exact=True,passed=True))
   for t in q['trades']:
    if t['opened_us']>=CUT*1000000:trades.append(dict(asset=asset,path=path,version=g,synthetic_times_not_observed=True,entry=t['entry'],exit=t['exit'],net=t['net'],rung=t['rung'],opened_Beijing_SYNTHETIC=local(t['opened_us']),closed_Beijing_SYNTHETIC=local(t['closed_us']),signal_close_Beijing=local(t['signal_close_ms']*1000),full_trade=json.dumps(t)))
for path in ['OHLC','OLHC']:
 for g in ['B','I100','I50','I25','B_PLUS_REBOUND']:
  btcg='B_PLUS_REBOUND'if g=='B_PLUS_REBOUND'else'B';v=curves['BTC',path,btcg]+curves['ETH',path,g];rows.append(dict(asset='COMBINED',path=path,version=g,Nov9_initial_equity=sum(start9.values()),**met(v,sum(start9.values())),status='COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS'))
def dumpcsv(name,rs):
 fields=list(dict.fromkeys(k for r in rs for k in r))
 with (O/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rs)
dumpcsv('comparison.csv',rows);dumpcsv('new_simulated_trades.csv',trades);(O/'tests.json').write_text(json.dumps(dict(passed=True,total=len(audit),checks=audit),indent=2))
text=['# 11月9日至15日15分钟行情执行敏感性测试','', '实际已执行到北京时间2026-11-15 10:30。保留原11月1日起资金路径及9日前状态，不在9日重新投入本金。北京时间14日08:00之前沿用已经完成的真实逐笔回放，之后为明确假设的15m路径模拟，不能合称全段逐笔验证。','', '冻结B/I100/I50/I25入场与仓位、V2、止损不变；B_PLUS_REBOUND使用已固定独立反弹续跌规则。主成本每边0.05%假设手续费、0.02%退出不利滑点，官方结算费率/精确标记价按实际时刻进入现金与后续定量。','', '缺逐笔部分分别假设每根15m为开→高→低→收、开→低→高→收；拐点在0、300、600、899秒，其间每秒线性插值。这些时间和价格路径是建模假设，不是实际成交、真实5秒轮询，也不是严格最好/最坏收益界；不同仓位方向下同一路径不一定始终最有利或最不利。只用已闭15m生成信号，触价模拟全量，保留原订单延迟/到期/单币单仓/退出事件顺序。未用K线结果冒充实际tick。','', '|版本|路径|截止组合权益|9日起收益%|9日起组合回撤%|','|---|---|---:|---:|---:|']
for r in rows:
 if r['asset']=='COMBINED':text.append(f"|{r['version']}|{r['path']}|{r['ending_equity']:.4f}|{r['return_since_Nov9_pct']:.3f}|{r['max_drawdown_since_Nov9_pct']:.3f}|")
text+=['','新增区间：原B/I版本均无新成交；新分支BTC和ETH各新增一笔模拟空单，详细见new_simulated_trades.csv。ETH两路径分别第2档和第1档退出，说明K线顺序假设对结果有实质影响，不能选高收益路径当正式结果。','', '14份完整现金、未平仓估值及原交易/分钟权益前缀核对通过。原历史亏损压力测试结论保持：2020ETH新增亏损62.05USDT，组合回撤扩大，不因本次近期盈利改阈值或宣布稳定优于B。','', '复跑：Python3.12，仓库根目录：','```bash','python outputs/nov15_15m_simulation/prepare.py','python outputs/nov15_15m_simulation/run.py BTC','python outputs/nov15_15m_simulation/run.py ETH','python outputs/nov15_15m_simulation/report.py','```','', '结果用于描述K线假设敏感性；15日完整原始逐笔执行仍UNVERIFIED。']
(O/'CONCLUSION.md').write_text('\n'.join(text));A=O/'artifacts';A.mkdir(exist_ok=True)
files=[p for p in O.rglob('*')if p.is_file() and 'artifacts'not in p.parts and '__pycache__'not in p.parts];M=R/'outputs/binance_15m_nov9_15';files+=[p for p in M.rglob('*')if p.is_file()and p.suffix!='.zip']
files += [C/'account_summary.json']
files += list((R/'outputs/nov9_today_simultaneous/data').glob('*_15m.csv')) + list((R/'outputs/nov9_today_simultaneous/data').glob('*_1m.npy'))
for asset in ['BTC','ETH']:
 files += list((C/'runs'/asset/'results').glob('*'))
 files += list((R/'outputs/rebound_followdown/runs/RECENT'/asset/'results').glob('*'))
 files+=[C/'runs'/asset/'extension/checkpoint.pkl.gz',R/'outputs/rebound_followdown/runs/RECENT'/asset/'whole/checkpoint.pkl.gz',C/'data'/f'{asset}_15m.csv',C/'data'/f'{asset}_funding.json']
with zipfile.ZipFile(A/'complete_delivery.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in files:z.write(p,p.relative_to(R))
(O/'artifact_index.json').write_text(json.dumps([dict(file=p.name,bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())for p in A.iterdir()],indent=2));print('DONE',len(rows),len(trades),len(audit))
