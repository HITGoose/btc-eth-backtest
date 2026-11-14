"""Read-only aggregation/audit of the fixed 2024/25 ADAPTIVE_V2 experiment.

Run after all four workers finish. Input results/configs are never rewritten.
Incomplete or failed runs are UNVERIFIED, never represented as zero returns.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

ROOT = Path('/workspace/btc-eth-backtest')
OUT = Path(__file__).resolve().parent
YEARS = (2024, 2025)
ASSETS = ('BTC', 'ETH')
VERSIONS = ('CONTROL', 'ADAPTIVE_RISK15', 'ADAPTIVE_V2')
TZ = timezone(timedelta(hours=8))
REASON = 'two closed15m both weak; 3pct realized balance reference budget; at most one reduction capped at25pct initial'
COMMANDS = [
    '/workspace/.venv-btc-eth-original/bin/python -u outputs/adaptive_risk_exit_v2/supervisor.py > outputs/adaptive_risk_exit_v2/run.log 2>&1',
    '/workspace/.venv-btc-eth-original/bin/python outputs/adaptive_risk_exit_v2/collect.py',
]


def read(path):
    return json.loads(path.read_text())


def rel(path):
    return str(path.relative_to(ROOT))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b, message='', atol=1e-7):
    assert math.isfinite(float(a)) and math.isfinite(float(b)) and abs(a-b) <= atol, (message, a, b)


def drawdown(marks, initial):
    values = np.r_[initial, marks]
    return float(np.max(100 * (1 - values / np.maximum.accumulate(values))))


def files(year, asset, version):
    if version == 'CONTROL':
        folder, profile = ROOT / f'outputs/binance_perpetual_raw_execution/{year}/{asset}', 'CONTROL'
    elif version == 'ADAPTIVE_RISK15':
        folder, profile = ROOT / f'outputs/adaptive_risk_exit/{year}/{asset}', 'DYNAMIC'
    else:
        folder, profile = OUT / str(year) / asset, 'DYNAMIC'
    return folder / f'{profile}_result.json', folder / f'{profile}_equity.npy'


def load_series(year, asset, version):
    result_path, marks_path = files(year, asset, version)
    q, marks = read(result_path), np.load(marks_path, allow_pickle=False)
    start, end = datetime(year, 1, 1, tzinfo=TZ), datetime(year+1, 1, 1, tzinfo=TZ)
    assert tuple(datetime.fromisoformat(t) for t in q['period']) == (start, end)
    assert q['source'] == 'BINANCE_USDT_PERPETUAL_ONLY' and q['asset'] == asset
    assert q['no_OHLC_fallback'] is True and q['starting_equity'] == 500
    assert q['stats'].get('fees', 0) == 0
    assert marks.ndim == 1 and len(marks) == int((end-start).total_seconds()) // 60
    assert np.isfinite(marks).all()
    close(float(marks[-1]), q['ending_equity'], 'end mark')
    close(q['return_pct'], 100*(q['ending_equity']/500-1), 'asset return')
    assert q['opens'] == q['stats'].get('long', 0) + q['stats'].get('short', 0)
    provenance = dict(result=rel(result_path), result_sha256=sha256(result_path),
                      equity=rel(marks_path), equity_sha256=sha256(marks_path))
    return q, marks, provenance


def audit_original_blobs():
    path = ROOT / 'outputs/retry_nov9_nov12/source_restore.json'
    manifest = read(path)
    assert manifest['GitHub_authenticated'] is True and manifest['all_restored_blobs_verified'] is True
    assert len(manifest['files']) == 85
    checked = []
    for item in manifest['files']:
        path = ROOT / item['path']
        body = path.read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
        checked.append(dict(path=item['path'], expected_git_blob=item['sha'], actual_git_blob=actual,
                            matched=actual == item['sha'], bytes=len(body)))
    assert all(item['matched'] for item in checked), [item for item in checked if not item['matched']]
    return dict(passed=True, count=len(checked), source_commit=manifest['source_commit'],
                restoration_manifest='outputs/retry_nov9_nov12/source_restore.json', files=checked)


def audit_source_manifest(path, kind):
    q = read(path)
    records = list(q.values()) if isinstance(q, dict) else q
    assert records, f'Empty {path}'
    for item in records:
        url = urlparse(item['url'])
        assert url.scheme == 'https' and url.netloc == 'data.binance.vision'
        assert url.path.startswith('/data/futures/um/'), item['url']
        assert item['official_checksum_match'] is True, item['url']
        digest = item.get('sha256', '')
        assert len(digest) == 64 and all(c in '0123456789abcdefABCDEF' for c in digest)
        if kind == 'raw':
            assert item['source_market'] == 'BINANCE_USDT_PERPETUAL'
            assert item['price_rewritten'] is False and item['raw_IDs_strictly_increasing'] is True
    return dict(path=rel(path), sha256=sha256(path), records=len(records),
                futures_um_only=True, official_checksum_matches=True,
                checksum_evidence='worker-recorded downloaded ZIP SHA256 matches official CHECKSUM; no redownload by collector')


def partial_stats(q):
    ratios = [sum(fill['quantity'] for fill in trade.get('partial_fills', []))/trade['quantity'] for trade in q['trades']]
    reduced = [ratio for ratio in ratios if ratio > 0]
    return dict(closed_trades=len(ratios), reduced_closed_trades=len(reduced),
                unreduced_closed_trades=len(ratios)-len(reduced),
                all_closed_median_reduction_pct=float(np.median(ratios))*100 if ratios else None,
                reduced_closed_median_reduction_pct=float(np.median(reduced))*100 if reduced else None,
                maximum_reduction_pct=max(ratios, default=0)*100,
                reduction_ratios=ratios)


def audit_partial_rules(q, year, asset):
    step = .0001 if asset == 'BTC' else .01
    requests = [event for event in q['events'] if event['event'] == 'adaptive_v2_request']
    partials = [event for event in q['events'] if event['event'] == 'partial_exit']
    assert not any(event['event'] in ('adaptive_request', 'dynamic_exit_requested', 'partial_exit_requested') for event in q['events'])
    positions = []
    cash = 500.0
    for trade in q['trades']:
        close(trade['opening_sleeve_cash_usdt'], cash, 'opening realized balance')
        positions.append(dict(opened=trade['opened_us'], closed=trade['closed_us'],
                              initial=trade['quantity'], remaining=trade['final_exit_quantity'],
                              side=1 if trade['side'] == 'LONG' else -1, entry=trade['entry'],
                              opening_cash=cash, partials=trade['partial_fills'], is_closed=True))
        close(sum(fill['quantity'] for fill in trade['partial_fills']) + trade['final_exit_quantity'], trade['quantity'], 'quantity conservation')
        close(sum(fill['net_usdt'] for fill in trade['partial_fills']), trade['partial_net'], 'partial PnL')
        cash += trade['net']
    position = q['state_at_end']['position']
    if position:
        order = position['order']
        opened = q['state_at_end']['position_opened_us']
        opening_events = [event for event in q['events'] if event['event'] == 'limit_touch_proxy_fill' and event['time_us'] == opened]
        assert len(opening_events) == 1, 'Open position initial fill missing'
        opening = opening_events[0]
        open_fills = [event for event in partials if event['time_us'] >= opened]
        close(position['opening_cash'], cash, 'open position opening realized balance')
        close(opening['entry'], order['price'], 'open position entry')
        positions.append(dict(opened=opened,
                              closed=int(datetime(year+1, 1, 1, tzinfo=TZ).timestamp()*1e6),
                              initial=opening['quantity'], remaining=order['qty'],
                              side=order['side'], entry=order['price'], opening_cash=cash,
                              partials=open_fills, is_closed=False))
        cash += sum(fill['net_usdt'] for fill in open_fills)
    close(cash, q['state_at_end']['cash'], 'final realized balance')
    mapped_requests, mapped_partials = [], []
    cap_requests = cap_filled = 0
    for position in positions:
        fills = position['partials']
        own_requests = [event for event in requests if position['opened'] <= event['time_us'] <= position['closed']]
        assert len(own_requests) <= 1 and len(fills) <= 1, 'More than one reduction per position'
        cut = sum(fill['quantity'] for fill in fills)
        assert cut <= .25*position['initial'] + 1e-9
        assert position['remaining'] >= step - 1e-9
        close(position['remaining']+cut, position['initial'], 'position remaining')
        for request in own_requests:
            mapped_requests.append(request)
            close(request['realized_balance'], position['opening_cash'], 'request balance')
            assert request['budget_rate'] == .03 and request['realized_balance'] >= 0
            close(request['budget'], request['realized_balance']*.03, 'balance3pct budget')
            close(request['initial_quantity'], position['initial'], 'request initial quantity')
            assert request['budget_is_reference_not_guarantee'] is True
            assert request['time_us'] % (900*1000000) == 0
            distance = position['side']*(request['known_close']-request['stop'])
            close(request['price_stop_distance'], distance, 'stop distance')
            assert distance > 0
            initial_lots = round(position['initial']/step)
            cap_lots = math.floor(initial_lots*.25+1e-12)
            target_lots = math.floor(request['budget']/distance/step+1e-12)
            requested_lots = min(max(0, initial_lots-target_lots), cap_lots, initial_lots-1)
            close(request['cap_quantity'], cap_lots*step, 'cap quantity')
            close(request['target_quantity'], target_lots*step, 'target quantity')
            close(request['requested_quantity'], requested_lots*step, 'requested quantity')
            close(request['estimated_remaining_risk'], (initial_lots-requested_lots)*step*distance, 'estimated risk')
            assert requested_lots > 0
            cap_bound = requested_lots == cap_lots and initial_lots-target_lots > cap_lots
            cap_requests += cap_bound
            cap_filled += cap_bound and bool(fills) and position['is_closed']
        for fill in fills:
            mapped_partials.append(fill)
            assert len(own_requests) == 1, 'Partial without audited V2 request'
            request = own_requests[0]
            assert fill['event'] == 'partial_exit' and fill['stage'] == request['stage']
            assert isinstance(fill['time_us'], int) and request['time_us'] <= fill['time_us'] <= position['closed']
            assert fill['trigger_gain_pct'] is None and fill['trigger_reason'] == REASON
            assert fill['trigger_print'] > 0 and fill['execution_price'] > 0 and fill['quantity'] > 0
            assert fill['side'] == position['side']
            close(fill['execution_price'], fill['trigger_print']*(1-position['side']*.0002), 'real-print slippage')
            close(fill['quantity'], request['requested_quantity'], 'filled request quantity')
            close(fill['remaining_quantity'], position['remaining'], 'fill remaining')
            close(fill['net_usdt'], position['side']*(fill['execution_price']-position['entry'])*fill['quantity'], 'partial PnL actual fields')
            assert fill in partials, 'Trade partial fields differ from raw event record'
    assert len(mapped_requests) == len(requests) and len(mapped_partials) == len(partials)
    assert sorted((x['time_us'], x['stage']) for x in mapped_partials) == sorted((x['time_us'], x['stage']) for x in partials)
    assert q['stats'].get('partial_exits', 0) == len(partials)
    stats = partial_stats(q)
    stats.update(requests=len(requests), actual_partial_fills=len(partials),
                 cap_bound_requests=cap_requests, cap_bound_filled_closed_positions=cap_filled,
                 realized_balance_at_request_min=min((e['realized_balance'] for e in requests), default=None),
                 realized_balance_at_request_max=max((e['realized_balance'] for e in requests), default=None),
                 budget_min=min((e['budget'] for e in requests), default=None),
                 budget_max=max((e['budget'] for e in requests), default=None),
                 partials_at_a_loss=sum(e['net_usdt'] < 0 for e in partials))
    return dict(passed=True, every_position_at_most_one_request_and_fill=True,
                cumulative_reduction_le25pct=True, budget_balance3pct=True,
                partial_actual_fields_consistent=True, closed_and_open_positions_checked=len(positions), stats=stats)


def audit_task(year, asset):
    folder = OUT/str(year)/asset
    assert not (folder/'failure.json').exists(), read(folder/'failure.json') if (folder/'failure.json').exists() else ''
    status, config = read(folder/'status.json'), read(folder/'config.json')
    assert status['completed'] is True and status['source'] == 'BINANCE_USDT_PERPETUAL_ONLY'
    assert set(status['versions']) == {'CONTROL', 'DYNAMIC'}
    assert config['experiment'] == 'ADAPTIVE_V2_BALANCE3_CAP25_ONCE'
    assert config['risk_budget_rate'] == .03 and config['maximum_initial_quantity_reduction'] == .25
    assert config['max_requests_per_position'] == 1 and config['parameter_search'] is False
    assert config['fee'] == 0 and config['leverage'] == 3 and config['slippage'] == .0002
    assert config['policy']['trend_level_distance_pct'] == 2.0
    assert config['no_OHLC_fallback'] is True and config['no_price_rewrite'] is True
    actual = read(folder/'CONTROL_result.json')
    prior, prior_marks, _ = load_series(year, asset, 'CONTROL')
    assert actual['trades'] == prior['trades'], 'CONTROL trades changed'
    close(actual['ending_equity'], prior['ending_equity'], 'CONTROL ending equity')
    actual_marks = np.load(folder/'CONTROL_equity.npy', allow_pickle=False)
    assert actual_marks.shape == prior_marks.shape and np.allclose(actual_marks, prior_marks, rtol=0, atol=1e-7), 'CONTROL marks changed'
    q, _, provenance = load_series(year, asset, 'ADAPTIVE_V2')
    assert q['experiment'] == config['experiment']
    fields = ('signal_ms', 'opened_us', 'closed_us', 'side', 'entry', 'exit', 'rung', 'reason')
    path_matches = (q['opens'] == prior['opens'] and
                    [tuple(t[k] for k in fields) for t in q['trades']] ==
                    [tuple(t[k] for k in fields) for t in prior['trades']])
    actual_open, prior_open = q['state_at_end']['position'], prior['state_at_end']['position']
    path_matches = path_matches and bool(actual_open) == bool(prior_open)
    if actual_open and prior_open:
        path_matches = path_matches and all(actual_open[k] == prior_open[k] for k in ('opened', 'stop', 'rung'))
        path_matches = path_matches and all(actual_open['order'][k] == prior_open['order'][k] for k in ('time', 'side', 'price'))
    assert path_matches, 'V2 accepted entry/final-exit paths differ from original ER'
    result = dict(year=year, asset=asset, passed=True, task_complete=True,
                  CONTROL_trades_end_and_marks_regression=True, provenance=provenance,
                  V2_accepted_entries_and_final_exits_match_original=True,
                  partial_rules=audit_partial_rules(q, year, asset),
                  raw_manifest=audit_source_manifest(folder/'raw_sources.json', 'raw'),
                  candle_manifest=audit_source_manifest(ROOT/f'outputs/other_years_050/{year}/{asset}_candle_sources.json', 'candle'))
    assert result['raw_manifest']['records'] == q['raw_day_count']
    return result


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    audit = dict(created_utc=datetime.now(timezone.utc).isoformat(), commands=COMMANDS,
                 collector_read_only_inputs=True, tasks=[], errors=[], statistics=[])
    try:
        audit['original_source'] = audit_original_blobs()
    except Exception as error:
        audit['original_source'] = dict(passed=False, error=repr(error))
        audit['errors'].append(dict(scope='original_source85', error=repr(error)))
    for year in YEARS:
        for asset in ASSETS:
            try:
                task = audit_task(year, asset)
            except Exception as error:
                task = dict(year=year, asset=asset, passed=False, error=repr(error))
                audit['errors'].append(task)
            audit['tasks'].append(task)
    try:
        tests = read(OUT/'test_results.json')
        assert tests['total'] == tests['passed'] == 32 and tests['failed'] == 0
        audit['financial_tests'] = dict(passed=True, total=32, synthetic_only=True,
                                       path='test_results.json', sha256=sha256(OUT/'test_results.json'))
    except Exception as error:
        audit['financial_tests'] = dict(passed=False, error=repr(error))
        audit['errors'].append(dict(scope='financial_tests', error=repr(error)))
    audit['four_tasks_complete_and_audited'] = len(audit['tasks']) == 4 and all(t['passed'] for t in audit['tasks'])
    audit['passed'] = audit['original_source']['passed'] and audit['four_tasks_complete_and_audited'] and audit['financial_tests']['passed']
    rows, monthly = [], []
    for year in YEARS:
        for version in VERSIONS:
            row = dict(year=year, version=version, market='BINANCE_USDT_PERPETUAL_ONLY', scope='全年', status='COMPLETE')
            try:
                if version == 'ADAPTIVE_V2':
                    assert audit['passed'], 'V2 audit incomplete/failed; see audit.json'
                loaded = [load_series(year, asset, version) for asset in ASSETS]
                qq = [item[0] for item in loaded]
                marks = loaded[0][1]+loaded[1][1]
                row.update(return_pct=100*(float(marks[-1])/1000-1), max_drawdown_pct=drawdown(marks, 1000),
                           opens=sum(q['opens'] for q in qq), BTC_opens=qq[0]['opens'], ETH_opens=qq[1]['opens'],
                           BTC_return_pct=qq[0]['return_pct'], ETH_return_pct=qq[1]['return_pct'], ending_equity=float(marks[-1]))
                start = datetime(year, 1, 1, tzinfo=TZ)
                for month in range(1, 13):
                    begin = datetime(year, month, 1, tzinfo=TZ)
                    end = datetime(year+1, 1, 1, tzinfo=TZ) if month == 12 else datetime(year, month+1, 1, tzinfo=TZ)
                    i, j = int((begin-start).total_seconds())//60, int((end-start).total_seconds())//60
                    initial = 1000.0 if i == 0 else float(marks[i-1])
                    monthly.append(dict(year=year, month=month, version=version, status='COMPLETE',
                                        start_beijing=begin.isoformat(), end_exclusive_beijing=end.isoformat(),
                                        starting_equity=initial, ending_equity=float(marks[j-1]),
                                        return_pct=100*(float(marks[j-1])/initial-1),
                                        max_drawdown_pct=drawdown(marks[i:j], initial)))
                compounded = 100*(math.prod(1+m['return_pct']/100 for m in monthly if m['year']==year and m['version']==version)-1)
                close(compounded, row['return_pct'], 'monthly compounded annual return')
                if version != 'CONTROL':
                    combined = {'trades': [t for q in qq for t in q['trades']]}
                    stats = partial_stats(combined)
                    stats.pop('reduction_ratios')
                    if version == 'ADAPTIVE_V2':
                        jobs = [t['partial_rules']['stats'] for t in audit['tasks'] if t['year']==year]
                        for key in ('requests', 'actual_partial_fills', 'cap_bound_requests', 'cap_bound_filled_closed_positions', 'partials_at_a_loss'):
                            stats[key] = sum(s[key] for s in jobs)
                        for key in ('realized_balance_at_request_min', 'budget_min'):
                            vals = [s[key] for s in jobs if s[key] is not None]
                            stats[key] = min(vals) if vals else None
                        for key in ('realized_balance_at_request_max', 'budget_max'):
                            vals = [s[key] for s in jobs if s[key] is not None]
                            stats[key] = max(vals) if vals else None
                    audit['statistics'].append(dict(year=year, version=version, **stats))
                row['sources'] = json.dumps([item[2] for item in loaded], ensure_ascii=False)
            except Exception as error:
                row.update(status='UNVERIFIED', reason=repr(error), return_pct=None, max_drawdown_pct=None, opens=None)
                audit['errors'].append(dict(scope='comparison', year=year, version=version, error=repr(error)))
                monthly = [month for month in monthly if not (month['year']==year and month['version']==version)]
                monthly.extend(dict(year=year, month=month, version=version, status='UNVERIFIED',
                                    reason=repr(error), return_pct=None, max_drawdown_pct=None)
                               for month in range(1, 13))
            rows.append(row)
    audit['passed'] = audit['passed'] and not audit['errors']
    (OUT/'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    (OUT/'comparison.json').write_text(json.dumps(dict(metadata=dict(
        market='BINANCE_USDT_PERPETUAL_ONLY', source='https://data.binance.vision/data/futures/um/',
        method='full official raw-trade execution for new V2 and simultaneous CONTROL; prior versions read unchanged',
        commands=COMMANDS, audit='audit.json', audit_passed=audit['passed'], annual_start_each_asset=500,
        annual_reset=True, interyear_compounding=False, fee=0, leverage=3, adverse_exit_slippage=.0002,
        funding='omitted', drawdown='BTC+ETH minute-end equity incl unrealized PnL, initial1000 included',
        monthly_return='previous month-end denominator; no monthly reset/rebalance'), rows=rows), ensure_ascii=False, indent=2)+'\n')
    write_csv(OUT/'comparison.csv', rows)
    write_csv(OUT/'monthly.csv', monthly)
    lines = [
        '# 自适应减仓V2：2024、2025币安永续', '',
        '只比原ER、旧固定15USDT风险预算版、V2。两年各自BTC/ETH各500USDT起算，年内余额累积、跨年重置；不是跨年连续复利。手续费0、名义3倍、原0.02%出场不利滑点。原ER入场、旧六线、2%支撑阻力绝对距离及原止损不变。', '',
        'V2：连续两根已完成15分钟K线均不再满足六线同向且MACD不支持时，参考预算=本币已实现余额×3%，按已收盘价到有效止损距离计算减仓量；每笔最多请求一次、累计最多减初始数量25%，保留至少一步余量。不要求先盈利，不在反弹时追加削减、不加回。25%上限优先，因此3%不是最大亏损保证。', '',
        '|年份|版本|收益|最大回撤|开仓|', '|---|---|---:|---:|---:|',
    ]
    labels = {'CONTROL': '原ER', 'ADAPTIVE_RISK15': '旧固定15预算', 'ADAPTIVE_V2': 'V2余额3%/最多减25%'}
    for row in rows:
        if row['status'] == 'COMPLETE':
            lines.append(f"|{row['year']}|{labels[row['version']]}|{row['return_pct']:+.2f}%|{row['max_drawdown_pct']:.2f}%|{row['opens']}|")
        else:
            lines.append(f"|{row['year']}|{labels[row['version']]}|未验证|未验证|未验证|")
    lines += ['', '回撤为BTC+ETH同一分钟末权益（含浮盈亏及期初1000）回撤，不覆盖分钟内极值。月度结果见monthly.csv，按北京时间相邻月末计算，月内回撤包含月初权益。', '',
              '## 实际减仓分布', '', '以下仅比较已平仓交易；累计减仓量÷初始数量。中位数同时列全部交易和实际有减仓交易，未减仓按0计。开放仓另在audit.json逐仓检查，不混入这个分布。', '',
              '|年份|版本|未减仓/已平仓|中位数 全部/有减仓|最大累计减仓|', '|---|---|---:|---:|---:|']
    fmt = lambda v: '无' if v is None else f'{v:.2f}%'
    for stats in audit['statistics']:
        lines.append(f"|{stats['year']}|{labels[stats['version']]}|{stats['unreduced_closed_trades']}/{stats['closed_trades']}|{fmt(stats['all_closed_median_reduction_pct'])}/{fmt(stats['reduced_closed_median_reduction_pct'])}|{fmt(stats['maximum_reduction_pct'])}|")
    for stats in audit['statistics']:
        if stats['version'] != 'ADAPTIVE_V2':
            continue
        money = lambda v: '无请求' if v is None else f'{v:.2f}'
        lines += ['', f"{stats['year']} V2：{stats['requests']}次请求中{stats['cap_bound_requests']}次由25%上限约束；其中{stats['cap_bound_filled_closed_positions']}笔已平仓交易实际减仓。请求时本币已实现余额范围{money(stats['realized_balance_at_request_min'])}—{money(stats['realized_balance_at_request_max'])} USDT，对应预算{money(stats['budget_min'])}—{money(stats['budget_max'])} USDT。上限按数量步长向下取整，实际比例可能略低于25%；触发上限不等于达到3%剩余风险目标。"]
    lines += ['', '## 数据、审计与限制', '',
              ('四个全年任务完成，32项合成金融测试通过；V2规则及原ER交易/期末权益/分钟曲线回归均通过。V2开仓与最终止损退出时间、价格和档位也全部与原ER一致。' if audit['passed'] else '存在未完成或审计失败项，V2结果标为未验证，详见下列失败原因。'), '',
              '本轮V2是完整官方原始逐笔执行，原ER同时运行并与已保存原版对照；旧15预算版只读取原结果。不是数量路径重放。raw_sources及原生K线来源必须全部为data.binance.vision/data/futures/um，ZIP官方SHA256匹配；收集器核查保存的校验记录，没有重新下载档案。行情全集完整性不能单凭checksum证明。K线/逐笔差异保留，不删改价格。', '',
              'audit.json保存每仓至多一次请求/一次减仓、累计≤25%、预算为请求时余额3%、原始成交价/滑点/PnL字段一致性、四任务完成状态、源档案及85个Git blob核对。原始源码和旧版结果不覆盖。资金费、深度、排队和真实部分成交未模拟；触价全额成交仍为代理，预算不保证实际亏损或回撤。只测试2024/25，不代表其他年份有效或完全复刻对方机器人，没有参数搜索。', '',
              '实际命令（工作目录/workspace/btc-eth-backtest）：', '', '```sh', *COMMANDS, '```',
              'supervisor调用worker.py YEAR BTC|ETH，共4个任务；各任务run.log、failure.json保留执行与失败记录。']
    if audit['errors']:
        lines += ['', '## 未验证/失败原因', '']
        lines.extend('- '+json.dumps(error, ensure_ascii=False) for error in audit['errors'])
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(audit_passed=audit['passed'], rows=[{k:v for k,v in row.items() if k!='sources'} for row in rows], errors=audit['errors']), ensure_ascii=False, indent=2))
    if not audit['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
