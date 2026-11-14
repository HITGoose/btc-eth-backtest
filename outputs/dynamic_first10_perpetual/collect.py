"""Collect the fixed first-partial 25% -> 10% Binance perpetual experiment.

Run after run.py finishes. Missing or failed asset runs remain UNVERIFIED, never
zero. This collector does not download data or traverse historical trade prints.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TZ = timezone(timedelta(hours=8))
ASSETS = ("BTC", "ETH")
PROFILES = ("CONTROL", "DYNAMIC25", "DYNAMIC10")
PYTHON = "/workspace/.venv-btc-eth-original/bin/python"
COMMANDS = [
    f"{PYTHON} -u outputs/dynamic_first10_perpetual/run.py > outputs/dynamic_first10_perpetual/run.log 2>&1",
    f"{PYTHON} outputs/dynamic_first10_perpetual/collect.py",
]


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sources(year: int, profile: str) -> tuple[Path, str]:
    if profile == "DYNAMIC10":
        return OUT / str(year), "DYNAMIC10"
    if year == 2020:
        sub = "outputs/er_partial_2020" if profile == "CONTROL" else "outputs/er_dynamic_compare/2020"
    elif year in (2021, 2022, 2023):
        sub = (f"outputs/monthly_three_versions_2016_2026/{year}" if profile == "CONTROL"
               else f"outputs/er_dynamic_annual_2019_2026/{year}")
    elif year in (2024, 2025):
        sub = f"outputs/binance_perpetual_raw_execution/{year}"
    else:
        sub = "outputs/er_partial_2026" if profile == "CONTROL" else "outputs/er_dynamic_compare/2026"
    return ROOT / sub, "CONTROL" if profile == "CONTROL" else "DYNAMIC"


def period_for_year(year: int) -> tuple[datetime, datetime]:
    start = datetime(year, 2, 16, tzinfo=TZ) if year == 2020 else datetime(year, 1, 1, tzinfo=TZ)
    end = datetime(2026, 11, 1, tzinfo=TZ) if year == 2026 else datetime(year + 1, 1, 1, tzinfo=TZ)
    return start, end


def scope(year: int) -> str:
    return "2月16日—12月31日（非全年）" if year == 2020 else "1—10月（非全年）" if year == 2026 else "全年"


def drawdown(values: np.ndarray, initial: float) -> float:
    marks = np.r_[initial, values]
    return float(np.max(100.0 * (1.0 - marks / np.maximum.accumulate(marks))))


def read_asset(year: int, profile: str, asset: str) -> tuple[dict, np.ndarray, dict]:
    folder, stored_profile = sources(year, profile)
    folder /= asset
    result_path = folder / f"{stored_profile}_result.json"
    equity_path = folder / f"{stored_profile}_equity.npy"
    if profile == "DYNAMIC10":
        failure = folder / "failure.json"
        if failure.exists():
            raise ValueError(f"{relative(failure)}: {json.loads(failure.read_text()).get('error', 'failed')}")
    result = json.loads(result_path.read_text())
    marks = np.load(equity_path, allow_pickle=False)
    start, end = period_for_year(year)
    source_period = result.get("period", result.get("period_beijing"))
    assert source_period is not None and len(source_period) == 2, "Missing period metadata"
    got = tuple(datetime.fromisoformat(t) for t in source_period)
    assert got == (start, end), f"Wrong period: {source_period}"
    assert result["asset"] == asset and result["profile"] == stored_profile
    assert float(result.get("starting_equity", 500.0)) == 500.0
    assert marks.ndim == 1 and len(marks) == int((end - start).total_seconds()) // 60
    assert np.isfinite(marks).all(), "Non-finite equity marks"
    assert abs(float(marks[-1]) - result["ending_equity"]) < 1e-7, "Ending equity mismatch"
    assert abs(float(result["return_pct"]) - 100 * (float(marks[-1]) / 500 - 1)) < 1e-7
    assert result.get("stats", {}).get("fees", 0.0) == 0.0, "Different fee setting"
    assert int(result["opens"]) == result["stats"].get("long", 0) + result["stats"].get("short", 0)
    assert result.get("no_OHLC_fallback", result.get("no_OHLC_extreme_assumption", False)) is True
    manifest = {
        "result": relative(result_path), "result_sha256": digest(result_path),
        "equity": relative(equity_path), "equity_sha256": digest(equity_path),
        "minute_marks": len(marks), "source_period": source_period,
    }
    if profile == "DYNAMIC10":
        validation_path = folder / "validation.json"
        validation = json.loads(validation_path.read_text())
        flags = (
            "old25_regression_passed", "full_end_state_regression_passed",
            "open_partial_state_regression_passed", "effective_submission_time_preserved",
            "entry_order_acceptance_unchanged", "entry_exit_path_unchanged", "mark_relation_verified",
        )
        assert all(validation.get(k) is True for k in flags), f"Incomplete validation: {validation}"
        assert result.get("old25_regression_passed") is True
        assert result.get("new_entry_acceptance_unchanged") is True
        assert result.get("entry_exit_price_path_unchanged") is True
        assert result["first_fraction"] == 0.10 and result["second_fraction"] == 0.25
        manifest.update(validation=relative(validation_path), validation_sha256=digest(validation_path),
                        validation_flags={key: validation[key] for key in flags},
                        replay_source=result["source_result"])
    else:
        manifests = [folder / f"{asset}_tick_sources.json", folder / "raw_sources.json"]
        manifest["existing_tick_source_manifests"] = [relative(p) for p in manifests if p.exists()]
    return result, marks, manifest


def month_windows(year: int):
    start, end = period_for_year(year)
    cursor = datetime(start.year, start.month, 1, tzinfo=TZ)
    while cursor < end:
        following = datetime(cursor.year + 1, 1, 1, tzinfo=TZ) if cursor.month == 12 else datetime(cursor.year, cursor.month + 1, 1, tzinfo=TZ)
        yield cursor.month, max(start, cursor), min(end, following)
        cursor = following


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    annual, monthly, provenance = [], [], []
    errors = []
    for year in range(2020, 2027):
        start, end = period_for_year(year)
        row = dict(year=year, market="BINANCE_USDT_PERPETUAL_ONLY", scope=scope(year),
                   period_start=start.isoformat(), period_end_exclusive=end.isoformat())
        month_rows = {
            month: dict(year=year, month=month, market="BINANCE_USDT_PERPETUAL_ONLY",
                        period_start=begin.isoformat(), period_end_exclusive=finish.isoformat(),
                        partial_month=begin.day != 1)
            for month, begin, finish in month_windows(year)
        }
        for profile in PROFILES:
            try:
                assets = [read_asset(year, profile, asset) for asset in ASSETS]
                results = [item[0] for item in assets]
                marks = assets[0][1] + assets[1][1]
                row.update({
                    f"{profile}_status": "COMPLETE",
                    f"{profile}_return_pct": 100 * (float(marks[-1]) / 1000 - 1),
                    f"{profile}_max_drawdown_pct": drawdown(marks, 1000.0),
                    f"{profile}_opens": sum(int(q["opens"]) for q in results),
                    f"{profile}_BTC_opens": int(results[0]["opens"]),
                    f"{profile}_ETH_opens": int(results[1]["opens"]),
                    f"{profile}_BTC_return_pct": results[0]["return_pct"],
                    f"{profile}_ETH_return_pct": results[1]["return_pct"],
                    f"{profile}_ending_equity": float(marks[-1]),
                })
                provenance.append(dict(year=year, profile=profile,
                                       assets={asset: item[2] for asset, item in zip(ASSETS, assets)}))
                for month, begin, finish in month_windows(year):
                    i = int((begin - start).total_seconds()) // 60
                    j = int((finish - start).total_seconds()) // 60
                    initial = 1000.0 if i == 0 else float(marks[i - 1])
                    selected = marks[i:j]
                    assert len(selected) > 0 and initial > 0
                    month_rows[month].update({
                        f"{profile}_status": "COMPLETE",
                        f"{profile}_return_pct": 100 * (float(selected[-1]) / initial - 1),
                        f"{profile}_max_drawdown_pct": drawdown(selected, initial),
                        f"{profile}_starting_equity": initial,
                        f"{profile}_ending_equity": float(selected[-1]),
                    })
            except (OSError, ValueError, AssertionError, KeyError, TypeError) as error:
                detail = dict(year=year, profile=profile, error=f"{type(error).__name__}: {error}")
                errors.append(detail)
                row.update({f"{profile}_status": "UNVERIFIED", f"{profile}_reason": detail["error"],
                            f"{profile}_return_pct": None, f"{profile}_max_drawdown_pct": None,
                            f"{profile}_opens": None})
                for month_row in month_rows.values():
                    month_row.update({f"{profile}_status": "UNVERIFIED", f"{profile}_return_pct": None,
                                      f"{profile}_max_drawdown_pct": None})
        if all(row[f"{profile}_status"] == "COMPLETE" for profile in PROFILES):
            row["DYNAMIC10_minus_DYNAMIC25_return_pp"] = row["DYNAMIC10_return_pct"] - row["DYNAMIC25_return_pct"]
            row["DYNAMIC10_minus_DYNAMIC25_drawdown_pp"] = row["DYNAMIC10_max_drawdown_pct"] - row["DYNAMIC25_max_drawdown_pct"]
            row["all_three_opens_equal"] = len({row[f"{profile}_opens"] for profile in PROFILES}) == 1
        annual.append(row)
        monthly.extend(month_rows.values())

    metadata = dict(
        generated_at_utc=datetime.now(timezone.utc).isoformat(), market="BINANCE_USDT_PERPETUAL_ONLY",
        status="COMPLETE" if not errors else "PARTIALLY_UNVERIFIED", commands=COMMANDS,
        method="Quantity-only replay of existing official-print financial event paths; old25 regression and unchanged entry acceptance/position paths required; new minute equity derived at identical timestamps from old marks, cash and remaining quantity. Not a new full tick download or traversal.",
        equity_relation="new_equity = new_cash + (new_remaining_qty / old_remaining_qty) * (old_equity - old_cash); flat periods use new_cash",
        versions={
            "CONTROL": "Original ER; entire remaining position exits at original hard/ladder stop",
            "DYNAMIC25": "Favorable1%:25% initial quantity; first subsequent closed15m trend weakness:25%; remainder original stop",
            "DYNAMIC10": "Only first fraction25%->10%; second25%, entry/ER and remaining original stop unchanged",
        },
        starting_equity_each_asset_each_year=500.0, fee_rate=0.0, nominal_leverage=3.0,
        adverse_exit_slippage=0.0002, funding="omitted as original", support_resistance_absolute_distance=0.02,
        mark_interval_seconds=60, drawdown="combined BTC+ETH minute equity including unrealized PnL, initial1000 included; not intraminute maximum",
        monthly_return="prior month ending equity as denominator; no monthly rebalance; February2020 startsFeb16",
        original_versions_preserved=True, second_stage_cancellation_tested=False,
        incomplete_periods={"2020": "OnlyFeb16-Dec31; Jan1-Feb15 unverified", "2026": "OnlyJan1-Oct31; November onward untested"},
        untested_earlier_years="2016-18: Binance perpetual not launched; 2019 listing-after interval untested",
        limits=["Full-size limit-touch proxy; queue/depth/actual partial fills unverified", "Raw archive completeness not independently proved", "No claim that this experiment matches the other robot"],
        provenance=provenance, errors=errors,
    )
    (OUT / "comparison.json").write_text(json.dumps(dict(metadata=metadata, annual=annual), ensure_ascii=False, indent=2) + "\n")
    write_csv(OUT / "comparison.csv", annual)
    write_csv(OUT / "monthly.csv", monthly)

    def cell(row: dict, profile: str) -> str:
        if row[f"{profile}_status"] != "COMPLETE":
            return "未验证"
        return f"{row[f'{profile}_return_pct']:+.2f}% / {row[f'{profile}_max_drawdown_pct']:.2f}%"

    lines = [
        "# 币安USDT永续：首档10%固定实验", "",
        "本轮只把动态版首档减仓从初始数量的25%改为10%：顺向达到1%后请求；第二档仍为首根已收盘15分钟趋势减弱时减初始数量25%，余仓按原阶梯止损。原ER、旧六线SMA/EMA20/60/120、2%支撑阻力绝对距离及其他配置不动。原ER与旧动态保留，未测试取消第二档。", "",
        "每年BTC、ETH各500USDT独立起算，手续费0、名义3倍、原0.02%出场不利滑点；未计资金费。仅使用已有币安USDT永续区间。2020不是全年，2026仅1—10月，不与现货结果混用。", "",
        "表中每格为 **收益 / 最大回撤**。回撤按同一时点BTC+ETH分钟权益含浮盈亏计算，包含初始1000USDT，未声称覆盖分钟内最大回撤。", "",
        "|年份|范围|原ER|原动态25%|新动态10%|开仓ER/25/10|",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in annual:
        opened = "/".join(str(row[f"{profile}_opens"]) if row[f"{profile}_status"] == "COMPLETE" else "未验证" for profile in PROFILES)
        lines.append(f"|{row['year']}|{row['scope']}|{cell(row, 'CONTROL')}|{cell(row, 'DYNAMIC25')}|{cell(row, 'DYNAMIC10')}|{opened}|")
    complete = [row for row in annual if all(row[f"{p}_status"] == "COMPLETE" for p in PROFILES)]
    if complete:
        increases = sum(row["DYNAMIC10_return_pct"] > row["DYNAMIC25_return_pct"] for row in complete)
        dd_increases = sum(row["DYNAMIC10_max_drawdown_pct"] > row["DYNAMIC25_max_drawdown_pct"] for row in complete)
        lines += ["", f"在{len(complete)}个已完成区间中，新10%版相对旧25%版有{increases}个区间收益提高，{dd_increases}个区间回撤变大。结果不代表能保证各年正收益，也不据此自动继续调参。"]
    lines += [
        "", "## 本轮实际执行口径", "",
        "这是对既有官方逐笔成交事件路径的数量重放，没有重新下载或完整遍历全历史逐笔。先用原25%重放，要求旧成交、资金、期末持仓及开放仓减仓状态复现；再检查10%版开仓接受资格、挂单/持仓占用和入场/最终离场价格时间路径不变。各币validation.json保存逐项结果。路径或资格检查失败的结果标为未验证。", "",
        "分钟权益使用旧版同一时点估值、当时现金和剩余数量精确换算：新权益=新现金+(新余量/旧余量)×(旧权益−旧现金)；空仓直接取新现金。原始事件价格、轮询时点、触发顺序保持原已验证路径，不假设K线高低先后。2024/25底层是原始官方逐笔全活动分钟执行，其他区间沿用此前已验证数据版本；本轮数量重放不会独立证明底层逐笔全集完整。", "",
        "限价成交沿用全额触价代理，排队、深度及真实部分成交未验证；资金费未计。2016—2018没有币安永续产品，2019上市后区间未测；2020年1月1日—2月15日、2026年11月以后未验证。", "",
        "## 文件与命令", "",
        "comparison.csv/json保存年度收益、回撤、两币收益及开仓；monthly.csv保存三版月收益与月内分钟回撤。2020年2月仅16日起，月收益使用上月末权益为分母，全年中不重置或再平衡。comparison.json元数据记录实际源结果、权益、验证文件的路径及SHA256；既有tick_sources/raw_sources记录底层官方URL。", "",
        "工作目录：`/workspace/btc-eth-backtest`。实际运行命令：", "", "```sh", *COMMANDS, "```",
    ]
    if errors:
        lines += ["", "## 未验证项", ""]
        lines.extend(f"- {item['year']} {item['profile']}: {item['error']}" for item in errors)
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(dict(status=metadata["status"], annual=annual, errors=errors), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
