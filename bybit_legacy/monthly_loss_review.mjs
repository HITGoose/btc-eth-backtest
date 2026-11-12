import fs from 'node:fs';

const dir = new URL('./', import.meta.url);
const load = name => fs.readFileSync(new URL(name, dir), 'utf8');
const p = 'BTCUSDT_5Y_monthly_review';
const results = JSON.parse(load(p+'_summary.json'));
const old = JSON.parse(load('BTCUSDT_5Y_resonance_sizing_summary.json'));
const [header, ...lines] = load(p+'_trades.csv').trim().split('\n');
const fields = header.split(',');
const all = lines.map(line => Object.fromEntries(line.split(',').map((value,i) => [fields[i],value])));
const variants = ['base_15m','triple_double_squeeze_only'];
const offset = 8*3600000;
const bar = 900000;
const local = t => new Date(Date.parse(t)+offset).toISOString().slice(0,16).replace('T',' ');
const sum = a => a.reduce((s,v)=>s+v,0);
const raw = fs.readFileSync(process.argv[2],'utf8').trim().split(/\r?\n/).slice(1).map(line=>line.split(',',5).map(Number));
const at = new Map(raw.map(([t],i)=>[t,i]));
const review = all.filter(t=>variants.includes(t.scenario)).map(t=>({...t,month:local(t.closed).slice(0,7),net:+t.net}));
const losses = review.filter(t=>t.month>='2022-01'&&t.month<='2024-12'&&t.net<0);
const status = t => {
  const favorable = +t.favorable_before_exit;
  if (favorable>=.004) return '曾有明显浮盈后回吐（≥0.4%）';
  if (favorable>=.002) return '有小幅顺向波动后回吐（0.2%–0.4%）';
  return '入场后未见明显延续（<0.2%）';
};
const exits = {stop:'盘中硬止损',stop_gap:'跳空止损',macd_fades:'MACD动能衰减',ma5_ma30_cross:'MA5与MA30反向交叉',end_of_data:'样本结束平仓'};
const setups = {squeeze_downward_expansion:'均线聚集后向下发散',squeeze_breakout:'均线聚集后向上突破',squeeze_retest:'向上突破后回踩确认',spread_pullback:'向上发散回踩'};
const resonance = {triple:'4H＋1H＋15m共振',double:'1H＋15m同向', '15m_only':'15m独立信号'};
const names = {base_15m:'固定半R',triple_double_squeeze_only:'三周期共振升至1R'};
const columns = ['版本','开仓时间（马来西亚）','平仓时间（马来西亚）','方向','15m入场形态','共振分组','计划风险档（R）','入场价','初始止损价','平仓价','数量（BTC）','盈亏（USDT）','盘中最大有利变动（%）','入场信号距MA30（ATR倍数）','直接平仓触发','亏损路径分类','K线顺序说明'];
const records = losses.map(t=>{
  const i=at.get(Date.parse(t.signal)-bar);
  if(i<30||i===undefined||!exits[t.reason]||!setups[t.setup]||!resonance[t.resonance])throw Error('Invalid trade');
  const ma30=sum(raw.slice(i-29,i+1).map(b=>b[4]))/30;
  const atr=sum(raw.slice(i-13,i+1).map((b,j)=>{const prev=raw[i-14+j][4];return Math.max(b[2]-b[3],Math.abs(b[2]-prev),Math.abs(b[3]-prev));}))/14;
  const gap=(t.side==='SHORT'?-1:1)*(raw[i][4]-ma30)/atr;
  const stop=t.reason==='stop';
  const uncertain=stop&&(t.side==='SHORT' ? raw[at.get(Date.parse(t.closed)-bar)][3] <= +t.first_entry*.998 : raw[at.get(Date.parse(t.closed)-bar)][2] >= +t.first_entry*1.002);
  return [names[t.scenario],local(t.opened),local(t.closed),t.side==='SHORT'?'空':'多',setups[t.setup],resonance[t.resonance],t.risk_fraction_of_r,t.first_entry,t.initial_stop,t.exit,t.qty,t.net.toFixed(6),(100*t.favorable_before_exit).toFixed(4),gap.toFixed(3),exits[t.reason],status(t),uncertain?'止损当根也触及至少0.2%有利价位，先后不明，未计入最大有利变动':stop?'最大有利变动不计止损当根':'最大有利变动截至平仓前'];
});
const csv = rows=>rows.map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
fs.writeFileSync(new URL('BTCUSDT_2022_2024_loss_review.csv',dir),'\uFEFF'+csv([columns,...records]));
const months = {};
for(const v of variants){
  const a=results.summaries[v];
  if(a.endingEquity!==old.summaries[v].endingEquity) throw Error('Baseline changed');
  let prev=100;
  months[v]={};
  for(const [m,equity] of Object.entries(a.months)){months[v][m]=(equity/prev-1)*100;prev=equity;}
  for(const y of [2022,2023,2024]){
    const compounded=Object.entries(months[v]).filter(([m])=>m.startsWith(y+'-')).reduce((x,[,r])=>x*(1+r/100),1);
    if(Math.abs(compounded-a.years[y]/a.years[y-1])>1e-12)throw Error('Month reconciliation failed');
  }
  const vloss=losses.filter(t=>t.scenario===v);
  console.log('loss',v,JSON.stringify({total:vloss.length,uncertain:records.filter(r=>r[0]===names[v]&&r[16].includes('先后不明')).length,bySide:Object.fromEntries(['LONG','SHORT'].map(side=>[side,vloss.filter(t=>t.side===side).length])),byStatus:Object.fromEntries([...new Set(vloss.map(status))].map(s=>[s,vloss.filter(t=>status(t)===s).length])),byExit:Object.fromEntries([...new Set(vloss.map(t=>t.reason))].map(s=>[s,vloss.filter(t=>t.reason===s).length]))}));
}
for(const y of [2022,2023,2024])console.log('monthly',y,JSON.stringify(variants.map(v=>Object.entries(months[v]).filter(([m])=>m.startsWith(y+'-')).map(([,r])=>r.toFixed(2)))));
const key=t=>t.opened+'|'+t.side;
const base=new Map(review.filter(t=>t.scenario===variants[0]).map(t=>[key(t),t]));
for(const y of [2021,2022,2023,2024,2025]){
  const a=review.filter(t=>t.scenario===variants[0]&&t.month.startsWith(y+'-')&&t.resonance==='triple');
  const b=review.filter(t=>t.scenario===variants[1]&&t.month.startsWith(y+'-')&&t.resonance==='triple');
  const deltas=b.filter(t=>base.has(key(t))).map(t=>({side:t.side,delta:t.net-base.get(key(t)).net,date:local(t.closed)})).sort((a,b)=>b.delta-a.delta);
  console.log('year',y,JSON.stringify({baseCount:a.length,baseNet:sum(a.map(t=>t.net)),boostCount:b.length,boostNet:sum(b.map(t=>t.net)),pairedDelta:sum(deltas.map(t=>t.delta)),top2:deltas.slice(0,2),shortDelta:sum(deltas.filter(t=>t.side==='SHORT').map(t=>t.delta))}));
}
