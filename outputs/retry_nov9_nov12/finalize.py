"""Publish verified recent comparison and clearly label older annual evidence."""
from pathlib import Path
from datetime import datetime,timezone
import csv
import hashlib
import json
import sys
import zipfile

import replay_comparison as r


def read_csv(path):return list(csv.DictReader(path.open(encoding='utf-8-sig')))


def main():
    p=r.OUT
    status=json.loads((p/'run_status.json').read_text());assert status['completed']
    sources=json.loads((p/'source_restore.json').read_text())
    for item in sources['files']:
        b=(r.ROOT/item['path']).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==item['sha']
    summaries=read_csv(p/'summary_comparison.csv')
    summary={x['label']:x for x in summaries}
    results=[json.loads(f.read_text()) for f in p.glob('*_result.json')]
    assert len(results)==6 and all(not x['approximated_minutes'] for x in results)
    for x in results:
        assert abs(x['total_pnl_usdt']-x['realized_pnl_usdt']-x['unrealized_pnl_usdt'])<1e-8
    request_rows=[json.loads(x) for x in (p/'api_requests.jsonl').read_text().splitlines()]
    for x in request_rows:
        assert hashlib.sha256((p/x['stored_response']).read_bytes()).hexdigest()==x['response_sha256']
    ledger=read_csv(p/'fills_comparison.csv');differences=[]
    for asset in ('BTC','ETH'):
        old=[x for x in ledger if x['label']=='ER_9_12' and x['asset']==asset]
        new=[x for x in ledger if x['label']=='MA_9_12' and x['asset']==asset]
        assert len(old)==len(new)==3
        fields=('signal_beijing','opened_beijing','direction','entry','quantity','closed_beijing','exit','rung','realized_pnl_usdt','unrealized_pnl_usdt')
        for i,(a,b) in enumerate(zip(old,new),1):
            changed=[k for k in fields if a[k]!=b[k]]
            differences.append(dict(asset=asset,trade_index=i,identical=not changed,changed_fields=';'.join(changed),
                 ER_opened=a['opened_beijing'],MA_opened=b['opened_beijing'],ER_entry=a['entry'],MA_entry=b['entry'],
                 ER_quantity=a['quantity'],MA_quantity=b['quantity'],
                 ER_realized_usdt=a['realized_pnl_usdt'],MA_realized_usdt=b['realized_pnl_usdt'],
                 ER_floating_usdt=a['unrealized_pnl_usdt'],MA_floating_usdt=b['unrealized_pnl_usdt']))
    r.csv_file('trade_changes.csv',differences)
    references=json.loads((p/'reference_entry_comparison.json').read_text())
    match={label:dict(reference_count=5,entry_price_and_integer_second_matches=sum(x['entry_same_price_and_second'] for x in references if x['label']==label),
                 whole_trade_match='UNVERIFIED',quantity_comparability='not equal initial balances')
           for label in ('ER_9_12','MA_9_12')}
    # Values below come from already verified tool outputs in this conversation,
    # not from restored old files and not from another annual replay today.
    prior=[dict(year=2020,asset='ETH',ER_pct=8.326338036000314,MA_pct=192.09883192400076),
           dict(year=2021,asset='BTC',ER_pct=52.02250483636042,MA_pct=48.82453636244109),
           dict(year=2021,asset='ETH',ER_pct=37.79578359200006,MA_pct=135.4276244080002),
           dict(year=2022,asset='BTC',ER_pct=116.4203755612018,MA_pct=44.96203911260126),
           dict(year=2022,asset='ETH',ER_pct=90.48067097600088,MA_pct=96.62427539200166),
           dict(year=2026,asset='BTC',ER_pct=11.799076504400885,MA_pct=27.908509281201745),
           dict(year=2026,asset='ETH',ER_pct=154.20134612800095,MA_pct=-3.568633923999387)]
    for x in prior:
        x.update(evidence='Prior completed and verified outputs in this conversation; original cloud annual files not mounted in current workspace',
                 rerun_today=False,period='Jan-Oct' if x['year']==2026 else 'full year')
    r.csv_file('prior_annual_evidence_from_conversation.csv',prior)
    # Diagnose the actual changed entry rather than infer it from annual PnL.
    file=p/'data/BTC_15m.csv'
    leg=r.model.build(file,r.WARM*1000,r.END*1000)
    config=next(x for x in results if x['label']=='ER_9_12' and x['asset']=='BTC')
    policy=r.RegimeOverlay(**config['policy']);pair=tuple(tuple(v) for v in config['original_ER'])
    _,er_context=r.regime.market_schedules('BTC',leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
    _,ma_context=r.ma_schedules('BTC',leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
    key=int(datetime.fromisoformat('2026-11-11T10:15:00+08:00').timestamp()*1000)
    why=dict(signal_beijing=r.local_s(key/1000),ER_context=er_context[key],MA_context=ma_context[key])
    r.dump(p/'changed_entry_context.json',why)
    delta=float(summary['MA_9_12']['total_pnl_usdt'])-float(summary['ER_9_12']['total_pnl_usdt'])
    final=dict(completed=True,window_beijing=[r.local_s(r.START),r.local_s(r.END)],
               source='Gate public USDT perpetual API',fee=0.,leverage=3.,cash_per_asset=500.,
               comparison=summaries,MA_minus_ER_profit_usdt=delta,changed_trades=[x for x in differences if not x['identical']],
               reference_entry_matching=match,only_BTC_conclusion_supported=False,
               interpretation='Recent ETH entries and exits unchanged; multi-year evidence has improvements and declines in both assets. No asset-specific switch selected.',
               original_source_bytes_unchanged=True,api_responses_checked=len(request_rows),
               legacy_window_reproduced=json.loads((p/'prior_window_regression.json').read_text())['matches_prior_amount_within_1e_6'],
               original_workspace_not_restored=True,required_original_files_authenticated_and_restored=True,
               annual_results_used_as_prior_evidence_not_rerun=True)
    r.dump(p/'summary.json',final)
    text=['不能据2026年单年结果认定均线分类只适合BTC。历史对照中，2020年ETH从+8.33%变为+192.10%；2021年BTC从+52.02%变为+48.82%，ETH从+37.80%变为+135.43%。这些是前次已完成记录，本次没有重新跑全年。','',
          '本次已实际重跑：北京时间11月9日00:00—12日23:00，Gate公开行情，同一价格输入、各币500起始、0手续费、3倍，按5秒相位2秒轮询，已激活止损逐笔触发。','',
          '|版本|开仓数|已实现USDT|浮盈USDT|合计USDT|收益率|','|---|---:|---:|---:|---:|---:|']
    for label in ('ER_9_12','MA_9_12'):
        x=summary[label]
        text.append(f"|{label}|{x['opens']}|{float(x['realized_pnl_usdt']):+.2f}|{float(x['unrealized_pnl_usdt']):+.2f}|{float(x['total_pnl_usdt']):+.2f}|{float(x['return_pct']):+.2f}%|")
    text+=['',f'均线版相差{delta:+.2f} USDT，差额全部来自期末未平仓浮盈，已平仓利润一致。两版各BTC3笔、ETH3笔。',
           'ETH三笔及BTC前两笔相同。最后一笔BTC空单：ER在11月11日22:38:02.870以73655.00、数量0.0196开仓；MA在当日10:40:30.096以73567.30、数量0.0197开仓。',
           '按参考5笔的开仓价和成交整秒，两版均4/5。两版都在9日00:50:18.995多出BTC多单（入场75886.90，信号00:00），止损亏30.19 USDT，持仓占用了首笔参考BTC空单时段。该结论来自本次回放，不沿用旧00:45推断。',
           '参考账户资金不同，数量和平仓/整笔收益完全匹配未验证。所有触价成交仍是模型代理，真实队列和部分成交未验证。',
           '此前11月10日起独立测试57.278418252 USDT已按原参数精确复现，但该窗口与9日起连续回放分开。']
    (p/'phone_report.md').write_text('\n'.join(text)+'\n')
    (p/'commands.md').write_text('''实际运行命令：

```bash
python -m venv --system-site-packages /workspace/.venv-btc-eth-original
/workspace/.venv-btc-eth-original/bin/python -m pip install --disable-pip-version-check -r requirements.txt > outputs/retry_nov9_nov12/dependency_install.log 2>&1
/workspace/.venv-btc-eth-original/bin/python -m py_compile outputs/retry_nov9_nov12/replay_comparison.py
/workspace/.venv-btc-eth-original/bin/python -u outputs/retry_nov9_nov12/replay_comparison.py > outputs/retry_nov9_nov12/run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/retry_nov9_nov12/finalize.py
```

默认沙箱无法连接继承代理，已在允许的外层环境用同一代理运行安装和公开行情读取。没有绕过地域限制或使用账户密钥。新空工作区没有旧项目/虚拟环境；已通过授权GitHub连接恢复85个必要原文件，逐个Git blob匹配原提交e66859aff89490b9b02c286e59d7d8270802972a。

恢复辅助观测驱动后，10日起旧窗口金额精确复现，用于核对恢复工作；没有为了匹配金额修改参数。请求末尾增加一根已完成K线作为传输边界补充，所有超出目标终点的K线都剔除，没有用于信号或估值。每个公开API响应按本地SHA256保存，该哈希不是官方签名。
''')
    r.dump(p/'delivery_manifest.json',dict(completed=True,created_utc=datetime.now(timezone.utc).isoformat(),
               original_source_sha='e66859aff89490b9b02c286e59d7d8270802972a',verified_original_files=len(sources['files']),
               data_source='Gate public API',matched_legacy_amount=True,only_BTC_supported=False,
               report=str(p/'phone_report.md'),ledger=str(p/'fills_comparison.csv')))
    with zipfile.ZipFile(p/'results.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in p.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix in ('.json','.jsonl','.md','.py','.csv','.log'):
                archive.write(file,file.relative_to(p))
    print(json.dumps(final,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
