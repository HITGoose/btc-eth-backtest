from pathlib import Path
import json,csv,numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent;rows=[]
for y in (2024,2025):
 for name,folder,key in [('CONTROL',OUT/str(y),'CONTROL'),('DYNAMIC25',ROOT/f'outputs/binance_perpetual_raw_execution/{y}','DYNAMIC'),('DYNAMIC10',ROOT/f'outputs/dynamic_first10_perpetual/{y}','DYNAMIC10'),('ADAPTIVE_RISK15',OUT/str(y),'DYNAMIC')]:
  qs=[json.loads((folder/a/f'{key}_result.json').read_text()) for a in ('BTC','ETH')]
  v=np.r_[1000.,sum(np.load(folder/a/f'{key}_equity.npy') for a in ('BTC','ETH'))]
  assert all(q.get('no_OHLC_fallback',q.get('no_OHLC_extreme_assumption',False)) for q in qs)
  rows.append(dict(year=y,version=name,return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-v/np.maximum.accumulate(v)))),opens=sum(q['opens'] for q in qs)))
 for a in ('BTC','ETH'):
  folder=OUT/str(y)/a
  actual=json.loads((folder/'CONTROL_result.json').read_text());prior=json.loads((ROOT/f'outputs/binance_perpetual_raw_execution/{y}/{a}/CONTROL_result.json').read_text())
  assert abs(actual['ending_equity']-prior['ending_equity'])<1e-7
  assert actual['trades']==prior['trades']
  path=folder/'DYNAMIC_result.json';q=json.loads(path.read_text())
  for event in q['events']:
   if event['event']=='partial_exit':event.update(trigger_gain_pct=None,trigger_reason='two closed15m both weak; fixed15USDT stop-distance risk budget')
  for t in q['trades']:
   for event in t.get('partial_fills',[]):event.update(trigger_gain_pct=None,trigger_reason='two closed15m both weak; fixed15USDT stop-distance risk budget')
  path.write_text(json.dumps(q,ensure_ascii=False)+'\n')
  c=json.loads((folder/'config.json').read_text());c.update(risk_estimation_price='latest completed15m close',risk_budget_basis='fixed15USDT,3pct initial500; does not grow with equity',confirmation='two consecutive closed15m: six-line alignment fails AND MACD does not support position',profit_prerequisite=False,reentry_on_recovery=False,minimum_remainder='one original quantity step',never_relax_stop=True)
  (folder/'config.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
fields=list(rows[0]);
with (OUT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
lines=['# 行情确认＋风险预算减仓：2024/2025永续实测','','仅币安USDT永续，手续费0，名义3倍，每年BTC与ETH各500USDT，原0.02%不利出场滑点。原ER入场、旧六线、2%绝对支撑阻力距离、硬止损和阶梯止损不变。', '', '新实验：不要求先盈利1%；每根15分钟收盘检查最近两根已完成K线，六线同向条件和MACD支持均失效时，用最新闭合15m收盘到当前有效止损的距离估算风险，目标余量=floor_to_step(15USDT/距离)。仅减少超出目标的数量，最少保留一个数量步长；不自动加回。预算15USDT固定为初始500的3%，不随余额扩大。若闭合价格已在止损另一侧，交给逐笔止损。实际减仓按下一笔真实成交价并计原滑点，止损优先。','', '预算是按已知K线收盘估算的未来回吐，不是账户最大回撤保证；实际跳价和执行价格变化会超出预算。所有原始逐笔按官方档案执行，差异只记录，不删除价格。','', '|年份|版本|收益|最大回撤（分钟组合权益）|开仓|','|---|---|---:|---:|---:|']
for q in rows:lines.append(f"|{q['year']}|{q['version']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['opens']}|")
lines+=['', '本轮为2024、2025完整原始逐笔执行，不是仅数量重放；两年原ER对照逐笔交易与之前结果完全一致。新预算版未扩展到其他年份，不能判定跨年有效或复刻对方机器人。无参数搜索，未自动继续调预算。DYNAMIC10参考版是之前完成的数量重放。', '', '来源、官方SHA256、ID跳号和K线差异见各年各币raw_sources.json及candle_tick_disagreements.json。资金费、深度、排队和真实部分成交未模拟。','', '命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/adaptive_risk_exit/supervisor.py > outputs/adaptive_risk_exit/run.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/adaptive_risk_exit/collect.py','```','调度器调用worker.py YEAR BTC|ETH，共4个全年任务；执行日志在各币run.log。原版本、原策略源码不覆盖。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows))
