from pathlib import Path
import json,csv,datetime
O=Path(__file__).resolve().parent;R=O.parents[1]
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
a=read('comparison.csv');summary=json.loads((O/'audit_summary.json').read_text());evidence=json.loads((O/'account_reuse_manifest.json').read_text())
f=lambda x:format(float(x),'.2f')if x not in ['',None]else'未验证'
rr=[]
for y in range(2020,2027):
 for asset in ['BTC','ETH']:
  folder=O/'runs'/str(y)/asset;fail=json.loads((folder/'failure.json').read_text())if(folder/'failure.json').exists()else{};progress=json.loads((folder/'whole/progress.json').read_text())if(folder/'whole/progress.json').exists()else{};done=folder/'status.json'
  if not done.exists():rr.append(dict(year=y,asset=asset,status='UNVERIFIED',error=fail.get('error','RUNNING_OR_PENDING'),checkpoint_next_time=progress.get('next_time'),resume_command=f'/workspace/.venv-btc-eth-original/bin/python outputs/baseline_registry/compare_runner.py {y} {asset}'))
with(O/'missing_intervals.csv').open('w',encoding='utf-8-sig',newline='')as fh:
 w=csv.DictWriter(fh,fieldnames=['year','asset','status','error','checkpoint_next_time','resume_command']);w.writeheader();w.writerows(rr)
lines=['# 项目基准纠正与两候选对照','', '**先纠正名称：ER_V2_REFERENCE是用户指定的原ER＋V2；MA_DIRECTION_REFERENCE是旧六线方向分类＋无V2无上限阶梯。近期A_BASE登记为ER_FIXED5_OHLC_EXPERIMENT，不能再作为二者的“原版”。**','',f"本次直接复用ER_V2的{summary['reused_ER_accounts']}个年度单币账户，源码与133f959指定提交逐文件相符；没有重跑这些账户。只补MA同引擎账户，已完成{summary['completed_MA_supplementary_accounts']}个；两币都完整、可公平比较的区间为{summary['complete_comparable_intervals']}个。所有可用结果来自实际账本，不使用截图数填空。",'','## 两套候选代码','', '- ER：133f959的outputs/rebound_annual_zero/worker.py输出CONTROL路径，实际经cost_engine.Book→priority_engine.Book(w.Dynamic)→worker.Dynamic(Ledger,BoundedAdaptive)运行V2。V2为两根闭15m弱化、当前余额3%参考预算、最多一次且最多减初始数量25%。不能按CONTROL这个输出名判断有无V2。','- MA：同一提交保存的retry_nov9_nov12/replay_comparison.py::ma_schedules及attribution_2026/paired_replay.py::prepare/new_book；六条SMA/EMA20/60/120与3根前比较，全部上／下，否则range；原无V2AuditSleeve、uncapped阶梯。不是新MA5/10/30/60/120/250。','- 已找回MA的2026两币完整历史结果，合计+12.1699377%，匹配截图；2020—2025旧截图原账本、权益及2020原窗口未找回，不伪称这些截图数字已验证。','', '## 同引擎统一年度表','', '均为币安USDT永续、官方逐笔、原5秒相位2轮询和触价全量模拟代理。统一每年每币500、3x、手续费0、资金费0、退出滑点0.02%；2020仅Feb16起，2026仅Jan—Oct。候选各自出场完整保留，比较的是两套策略，不是分类单变量归因。','', '|区间|ER＋V2收益／分钟回撤%|MA收益／分钟回撤%|MA相对ER损益USDT|MA状态|','|---|---:|---:|---:|---|']
complete=[]
for y in range(2020,2027):
 ers=next(r for r in a if r['period']==str(y)and r['asset']=='COMBINED'and r['version']=='ER_V2_REFERENCE');ma=next(r for r in a if r['period']==str(y)and r['asset']=='COMBINED'and r['version']=='MA_DIRECTION_REFERENCE');valid=bool(ma.get('return_pct'));complete.append((ers,ma))if valid else None
 lines.append('|'+str(y)+'|'+f(ers['return_pct'])+' / '+f(ers['minute_max_drawdown_pct'])+'|'+(f(ma['return_pct'])+' / '+f(ma['minute_max_drawdown_pct'])if valid else'未验证')+'|'+f(ma.get('difference_vs_other_USDT'))+'|'+ma['status']+'|')
lines+=['','收益、分钟回撤、已平笔数、已平净额、期末未平贡献及分币差额见comparison.csv。期末未平贡献=该未平交易已实现的V2部分退出净额＋剩余浮盈−已付入场费；本轮费用0。账户差额用完整期末权益核对，不把单笔归因加到旧收益上。年度独立重置，不拼跨年复利或跨年回撤。2025保留S_ALL／COMPLETED_WITH_DATA_ANOMALY，不称严格官方修复。','', '## 是否有明确胜者、锁定哪个','']
if len(complete)<7:lines+=['目前没有七期全部统一完成的公平对照，不能根据截图与新账本直接宣布任何一套胜出。已完成区间可以描述，缺失年度不填零，也不据此挑选版本。']
if complete:
 n=sum(float(m['return_pct'])>float(e['return_pct'])for e,m in complete);risk=sum(float(m['minute_max_drawdown_pct'])<float(e['minute_max_drawdown_pct'])for e,m in complete);lines +=[f'在已完整可比的{len(complete)}个区间，MA收益较高{n}个、分钟回撤较低{risk}个。区间集合按完成状态确定，不按结果筛选；这不替代缺失年份，也不将差额全归因于分类。']
lines+=['建议先锁定ER_V2_REFERENCE作为研究对照：用户明确指定、七期完整账本及V2实现链可审计。这是基准身份选择，不是按事后收益择优，也不是更改实盘部署；实际部署版本未知。MA保留为独立候选，待数据支持的统一对照完整后再评价，不为凑截图改参数。','', '## 哪些旧结果仍可用','', '- 原ER＋V2上的密集阈值、BTC确认／CORE优先、2025异常敏感性、EXTRA仓位成本、反弹分支等，按各自配置与异常／费用限制保留原结论；名称字母要结合目录，不能把本轮rebound的A误当无V2。','- 无V2、5档封顶、OHLC等其他基准上的早退、撤单、高波动仓位、ATR止损实验保留；结论仅适用那个基准。无V2失败不证明V2也失败，但也不自动全部重跑。','- 2026旧MA历史执行器采用不同活动分钟／数据产品路径，单独放historical_ma_2026.csv。只有新统一引擎结果才进入公平表，旧MA结果不冒充新结果。','', '## 数据与资源缺口／恢复','', '官方档案存在，但旧RawCache解析后删除ZIP，本机并未保留所有原始逐笔。K线缓存和旧账本均保留，无法替代新订单所需的逐笔路径。本轮只读取必要官方日档，逐项CHECKSUM；data_queries.jsonl记URL、HEAD响应、大小及空闲磁盘。已存在且校验有效的本地ZIP优先复用。磁盘保护保留32MiB用于checkpoint与结果，没有删除原数据。']
for row in rr:lines+=['',f"- {row['year']} {row['asset']}：{row['error']}；共同有效断点下一时刻{row['checkpoint_next_time']or'尚未形成完整日断点'}。恢复命令见missing_intervals.csv。"]
lines+=['', '若并发日档造成暂时容量不足，下载结束后仅对容量失败串行重试；若单日档仍超过可用空间，保留断点并明确需要更多磁盘。不能擅自换1m OHLC、删冲突或跳过一天来填完整收益。初次非提权网络权限失败已用获授权网络执行重试，不把它误报成币安404。','', '## 交付','', '[完整登记表](../../BASELINE_REGISTRY.md) · [年度分币对照](comparison.csv) · [复用清单及SHA](account_reuse_manifest.json) · [源码身份](source_code_manifest.csv) · [缺口及恢复命令](missing_intervals.csv) · [复跑说明](RUN.md)','', '本轮到此项基准整理及必要对照为止，没有重跑旧优化，没有新增参数或费用场景，没有更改main、原账本或实际部署。']
(O/'CONCLUSION.md').write_text('\n'.join(lines),encoding='utf-8')
print('REPORT complete pairs',len(complete),'missing asset-years',len(rr))
