import fs from 'node:fs';

const folder=new URL('./',import.meta.url);
const read=name=>fs.readFileSync(new URL(name,folder),'utf8');
const prefix='BTCUSDT_5Y_long_exit';
const summary=JSON.parse(read(prefix+'_summary.json'));
const original=JSON.parse(read('BTCUSDT_5Y_long_only_summary.json'));
const baseline=summary.summaries.long_only_half_r;
if(baseline.endingEquity!==original.summaries.long_only_half_r.endingEquity)throw Error('Baseline mismatch');
const [h,...lines]=read(prefix+'_trades.csv').trim().split('\n');
const cols=h.split(',');
const trades=lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[cols[i],v])));
const prices=fs.readFileSync(process.argv[2],'utf8').trim().split(/\r?\n/).slice(1).map(line=>line.split(',',5).map(Number));
const at=new Map(prices.map(([t],i)=>[t,i]));
const totals=[0];
for(const b of prices)totals.push(totals.at(-1)+b[4]);
const spread=i=>(totals[i+1]-totals[i-4])/5-(totals[i+1]-totals[i-29])/30;
const bar=900000, offset=8*3600000, slip=.0002;
const local=t=>new Date(t+offset).toISOString().slice(0,16).replace('T',' ');
const rangeStart=Date.parse('2022-01-01T00:00:00+08:00');
const rangeEnd=Date.parse('2025-01-01T00:00:00+08:00');
const range=t=>Date.parse(t.opened)>=rangeStart&&Date.parse(t.opened)<rangeEnd;
const sum=x=>x.reduce((s,v)=>s+v,0);
const med=x=>x.length?x.toSorted((a,b)=>a-b)[Math.floor(x.length/2)]:null;

function replay(trade){
  const start=at.get(Date.parse(trade.opened));
  const stop=+trade.initial_stop;
  const end=Date.parse(summary.until);
  let pending=false;
  for(let i=start;prices[i][0]<end;i++){
    const [t,o,,l,c]=prices[i];
    if(o<=stop)return [t,o*(1-slip),'跳空止损'];
    if(pending)return [t,o*(1-slip),'15m死叉'];
    if(l<=stop)return [t+bar,stop*(1-slip),'盘中硬止损'];
    if(t+bar===end)return [end,c*(1-slip),'期末平仓'];
    pending=spread(i-1)>=0&&spread(i)<0;
  }
  throw Error('Unclosed replay trade');
}

const exits={stop:'盘中硬止损',stop_gap:'跳空止损',macd_fades:'MACD动能衰减',ma5_ma30_cross:'15m死叉',end_of_data:'期末平仓'};
const setups={squeeze_breakout:'均线聚集后向上突破',squeeze_retest:'突破后回踩确认',spread_pullback:'向上发散回踩'};
const active=trades.filter(t=>t.scenario==='long_only_half_r'&&range(t));
const rows=active.map(t=>{
  const entry=+t.first_entry;
  const open=Date.parse(t.opened), close=Date.parse(t.closed);
  const max=+t.favorable_before_exit;
  const isStop=t.reason==='stop';
  const sameBar=isStop&&prices[at.get(close-bar)][2]>=entry*1.002;
  const net=+t.net;
  const phase=net>0?'最终盈利':max>=.004?'明显浮盈后回吐（≥0.4%）':max>=.002?'小幅顺向后回吐（0.2%–0.4%）':'未见明显延续（<0.2%）';
  const [altTime,altPrice,altReason]=replay(t);
  const alt=(altPrice-entry)*+t.qty;
  const forward=prices[at.get(close+3*bar)][4]/+t.exit-1;
  return {open,close,max,sameBar,net,phase,alt,forward,reason:t.reason,values:[local(open),local(close),setups[t.setup],t.first_entry,t.initial_stop,t.exit,t.qty,net.toFixed(6),(100*max).toFixed(4),exits[t.reason],phase,sameBar?'止损K线也触及至少0.2%有利价位，先后不明':'',(100*forward).toFixed(4),local(altTime),altPrice.toFixed(4),altReason,alt.toFixed(6),(alt-net).toFixed(6)]};
});
const header=['入场时间（马来西亚）','原出场时间（马来西亚）','15m入场形态','入场价','硬止损价','原出场价','数量BTC','原盈亏USDT','平仓前最大有利变动%（不含止损当根）','原平仓触发','价格路径','盘中顺序标记','原出场后1小时价格变动%','同一入场只等15m死叉的出场时间','对照出场价','对照平仓触发','对照盈亏USDT','对照盈亏差USDT'];
const csv=[header,...rows.map(t=>t.values)].map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
fs.writeFileSync(new URL('BTCUSDT_2022_2024_long_entry_exit_review.csv',folder),'\uFEFF'+csv+'\r\n');
const loss=rows.filter(t=>t.net<0);
const macd=rows.filter(t=>t.reason==='macd_fades');
const calc=r=>({n:r.length,net:sum(r.map(t=>t.net)),alt:sum(r.map(t=>t.alt)),better:r.filter(t=>t.alt>t.net+1e-8).length,worse:r.filter(t=>t.alt<t.net-1e-8).length,forwardUp:r.filter(t=>t.forward>0).length,forwardAbovePoint4:r.filter(t=>t.forward>=.004).length,medianMFE:med(r.map(t=>t.max)),uncertain:r.filter(t=>t.sameBar).length});
console.log('ALL',JSON.stringify(calc(rows)));
console.log('LOSS',JSON.stringify(calc(loss)));
console.log('MACD',JSON.stringify(calc(macd)));
for(const phase of new Set(loss.map(t=>t.phase)))console.log(phase,JSON.stringify(calc(loss.filter(t=>t.phase===phase))));
for(const [name,s] of Object.entries(summary.summaries)){
  if(s.bySide.SHORT)throw Error('Unexpected shorts');
  const selected=trades.filter(t=>t.scenario===name&&range(t));
  const years=[2022,2023,2024].map(y=>100*(s.years[y]/s.years[y-1]-1));
  console.log(name,JSON.stringify({years,compound:100*(s.years[2024]/s.years[2021]-1),trades:selected.length,stops:selected.filter(t=>t.reason.startsWith('stop')).length}));
}
