from pathlib import Path
import json,csv,html
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
P=Path(__file__).resolve().parent;q=json.loads((P/'results.json').read_text());rows=q['trades'];summary=q['summary']
headers={'period':'区间','version':'版本','opened_asset':'已开币种','missing_asset':'未开币种','signal_beijing':'信号时间（北京时间）','direction':'开仓方向','outcome':'盈亏分类','net_usdt':'整笔净盈亏USDT','signal_close_price':'已开币信号收盘价','entry_price':'实际开仓价','entry_beijing':'实际开仓时间','exit_price':'实际最终平仓价','exit_beijing':'最终平仓时间','other_signal_close_price':'未开币同时信号收盘价','other_hypothetical_limit_price':'未开币规则限价（假设非成交）','other_minimum_bandwidth_pct':'未开币96根最小带宽%','other_current_bandwidth_pct':'未开币当前带宽%','other_aligned_lines':'未开币同向均线条数','other_close_outside_all_six':'未开币收盘在六线外','other_MACD_histogram':'未开币MACD柱','other_ER_regime':'未开币ER分类','other_actual_signal_direction':'未开币最终信号方向','other_execution_status':'未开币执行状态','other_failed_conditions':'未开币失败条件','other_has_position':'未开币已有持仓','other_has_pending_order':'未开币已有挂单','trend_extra_details':'额外趋势指标核对范围','id':'记录编号'}
wb=Workbook();wb.remove(wb.active)
def sheet(name,records,fields=None):
 ws=wb.create_sheet(name);fields=fields or list(records[0]) if records else ['说明'];ws.append([headers.get(k,k) for k in fields])
 for r in records:ws.append([str(r.get(k,'')) if isinstance(r.get(k),(dict,list)) else r.get(k,'') for k in fields])
 ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
 for c in ws[1]:c.font=Font(color='FFFFFF',bold=True);c.fill=PatternFill('solid',fgColor='23435B');c.alignment=Alignment(wrap_text=True)
 for i,k in enumerate(fields,1):ws.column_dimensions[get_column_letter(i)].width=45 if 'failed' in k else 27 if 'beijing'in k or 'status'in k else 21
 for row in ws.iter_rows(min_row=2):
  for c in row:c.alignment=Alignment(vertical='top',wrap_text=True)
 return ws
sheet('统计',summary)
for a in ('BTC','ETH'):
 for outcome in ('盈利','亏损','持平'):
  group=[r for r in rows if r['opened_asset']==a and r['outcome']==outcome]
  if not group:continue
  fields=list(headers);sheet(f'{a}独开{outcome}',group,fields)
  with (P/f'{a}_exclusive_{outcome}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(group)
conditions=list(csv.DictReader((P/'conditions.csv').open(encoding='utf-8-sig')));sheet('逐项条件表',conditions)
notes=['2019未验证，不能用0笔代替。','2020仅2月16日至年底；2021—2025全年。','2026年1—10月、11月1日至13日08:00分段；11月13日08:00至今天未验证。','11月各币初始500重新起跑，不拼入年度金额。','按同根15分钟信号判定另一币是否实际成交，不要求同秒成交；有相反方向成交亦排除。','盈亏来自已开币已平整笔交易，含减仓；未平仓不分胜负。未开币没有假设收益。','信号价格是已收盘K线收盘，不是成交价格。','原ER与V2分开，不能将两版记录相加。','失败条件可能多项同时发生；已有持仓/挂单与信号过滤分别列出。','只读既有逐笔结果并重算入场指标，没有改参数、重跑收益或执行真实交易。']
sheet('口径及缺失',[{'说明':n} for n in notes]);wb.save(P/'BTC_ETH_独立开仓全量核对.xlsx')
# Self-contained mobile case viewer: all data local; no external scripts.
payload=json.dumps({'trades':rows,'conditions':conditions,'notes':notes},ensure_ascii=False).replace('</','<\\/')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BTC/ETH独立开仓核对</title><style>body{font:16px system-ui;max-width:900px;margin:auto;padding:16px;background:#f6f8fa;color:#172332}select,input,button{font:inherit;padding:9px;margin:4px 0;width:100%;box-sizing:border-box}article{background:white;padding:14px;margin:14px 0;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}.bad{color:#bd3030}.good{color:#09754b}small{color:#536273}</style><h2>BTC/ETH独立开仓全量核对</h2><details><summary>统计口径与缺失区间</summary><div id="notes"></div></details><select id="version"><option>原ER</option><option>修正版V2</option></select><select id="period"><option value="">全部区间</option></select><select id="asset"><option value="">全部已开币种</option><option>BTC</option><option>ETH</option></select><select id="outcome"><option value="">全部盈亏</option><option>盈利</option><option>亏损</option><option>持平</option></select><input id="search" placeholder="搜索时间或未开仓原因"><p id="count"></p><div id="cases"></div><button id="more">继续显示50笔</button><script>const DATA=PAYLOAD;const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let limit=50;const groups={};for(const c of DATA.conditions)(groups[c.id]??=[]).push(c);$('notes').innerHTML=DATA.notes.map(n=>'<p>'+esc(n)+'</p>').join('');for(const p of [...new Set(DATA.trades.map(x=>x.period))])$('period').add(new Option(p,p));function render(){const a=DATA.trades.filter(x=>x.version===$('version').value&&(!$('period').value||x.period===$('period').value)&&(!$('asset').value||x.opened_asset===$('asset').value)&&(!$('outcome').value||x.outcome===$('outcome').value)&&(! $('search').value||JSON.stringify(x).includes($('search').value)));$('count').textContent=`匹配${a.length}笔；显示${Math.min(limit,a.length)}笔。两版不可相加。`;$('cases').innerHTML=a.slice(0,limit).map(x=>`<article><b>${esc(x.signal_beijing)}　${esc(x.opened_asset)}独开${esc(x.direction)}</b><p>${esc(x.outcome)} ${x.net_usdt.toFixed(2)} USDT</p><p>${esc(x.opened_asset)}信号价 ${x.signal_close_price} → 实际开 ${x.entry_price} → 最终平 ${x.exit_price}<br>${esc(x.missing_asset)}同时收盘价 ${x.other_signal_close_price}</p><table><tr><th>条件</th><th>${esc(x.missing_asset)}情况</th><th>结果</th></tr>${(groups[x.id]||[]).map(c=>`<tr><td>${esc(c.condition)}</td><td>${esc(c.value)}</td><td class="${c.result==='通过'?'good':'bad'}">${esc(c.result)}</td></tr>`).join('')}</table><p>执行：${esc(x.other_execution_status)}<br>失败条件：${esc(x.other_failed_conditions)}</p><small>实际开：${esc(x.entry_beijing)}；最终平：${esc(x.exit_beijing)}。${esc(x.version)}。</small></article>`).join('');$('more').hidden=limit>=a.length}for(const id of ['version','period','asset','outcome','search'])$(id).addEventListener('input',()=>{limit=50;render()});$('more').onclick=()=>{limit+=50;render()};render();</script></html>'''.replace('PAYLOAD',payload)
(P/'mobile.html').write_text(page);print('packaged',len(rows),'rows',len(conditions),'condition rows')
