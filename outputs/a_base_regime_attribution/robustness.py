from pathlib import Path
import csv,json,numpy as np
O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
y=read('yearly_state.csv');stage=read('stage_comparison.csv');summary=read('state_summary.csv');trades=read('trade_details.csv');rows=[]
for x in summary:
 same=lambda z:all(z[k]==x[k]for k in ['asset','fee_scenario','label_anchor','state'])
 yy=[z for z in y if same(z)];ss={z['stage']:z for z in stage if same(z)};cl=[float(z['closed_r1000_mean'])for z in yy if z['closed_r1000_mean']];al=[float(z['all_marked_net_r1000_mean'])for z in yy if z['all_marked_net_r1000_mean']]
 rows.append(dict(asset=x['asset'],fee_scenario=x['fee_scenario'],label_anchor=x['label_anchor'],state=x['state'],closed_N=x['closed_count'],open_N=x['open_count'],closed_years_with_samples=len(cl),closed_positive_years=sum(v>0 for v in cl),closed_negative_years=sum(v<0 for v in cl),unweighted_mean_of_available_yearly_closed_means=float(np.mean(cl))if cl else None,all_positive_years=sum(v>0 for v in al),all_negative_years=sum(v<0 for v in al),early_closed_N=ss['2020_2022']['closed_count'],early_closed_r1000_mean=ss['2020_2022']['closed_r1000_mean'],late_closed_N=ss['2023_2026']['closed_count'],late_closed_r1000_mean=ss['2023_2026']['closed_r1000_mean'],early_all_r1000_mean=ss['2020_2022']['all_marked_net_r1000_mean'],late_all_r1000_mean=ss['2023_2026']['all_marked_net_r1000_mean']))
with(O/'consistency.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
key=lambda x:(x['year'],x['asset'],x['side'],x['signal_close_ms'],x['record_type'])
a={key(x):(x['opened_us'],x['closed_us'])for x in trades if x['fee_scenario']=='ZERO'};b={key(x):(x['opened_us'],x['closed_us'])for x in trades if x['fee_scenario']=='MAKER_002_SIDE'}
(O/'fee_path_overlap.json').write_text(json.dumps(dict(same_record_keys_and_fill_exit_times=a==b,zero_records=len(a),maker_records=len(b),fee_scenarios_not_independent_samples=True),indent=2));print('Robustness rows',len(rows),'paired fee timelines identical',a==b)
