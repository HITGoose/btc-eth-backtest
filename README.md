# BTC／ETH 15 分钟策略回测

- [策略计划与修改清单](outputs/BTC_ETH_12h5d_model_audit_checklist.md)
- [当前穿越版的逐年与逐笔结果](outputs/BTC_ETH_Gate_12h_5d_2019_2026_3x_entry_crosses.json)
- [同口径的上一版结果](outputs/BTC_ETH_Gate_12h_5d_2019_2026_3x_v13_comparison.json)
- [早期 Bybit BTCUSDT 策略交接](bybit_legacy/CODEX_HANDOFF.md)

当前版本回测 Gate 的 BTCUSDT 和 ETHUSDT 永续。15 分钟收盘确认入场，按 12 小时和 5 天 ER 划分行情。两个子账户每个窗口分别以 500 USDT 起算，固定 3 倍名义仓位。趋势分支在同一根确认 MA7／MA10 与 MACD DIF／DEA 的同向穿越，震荡分支在原确认位置使用 MACD 穿越。完整的开仓、挂单、止损和梯子止盈规则见策略计划。

## 在云端 Codex 复跑

在仓库根目录使用 Python 3.12。下载历史行情需要访问 `download.gatedata.org` 和 `api.gateio.ws`。首次准备年度行情需要数 GB 磁盘空间。两份近期回放及重叠核对所需的 15 分钟 K 线随仓库提供，年度档案和逐笔缓存由脚本获取。

```bash
python -m pip install -r requirements.txt
python work/gate_annual_market.py download
python work/gate_annual_market.py prepare
python work/replay_gate_selected_3x.py
```

输出见 `outputs/BTC_ETH_Gate_12h_5d_2019_2026_3x_entry_crosses.json`。2019 年覆盖 12 月 6 日起的区间，2026 年的年度窗口为 1–10 月。11 月 9 日的订单匹配作为单独的逐笔回放。

## 源码入口

| 用途 | 入口 |
|---|---|
| 当前 3 倍模型 | [`work/replay_gate_selected_3x.py`](work/replay_gate_selected_3x.py) |
| 入场、行情分段与回踩 | [`work/gate_october_regime_entries.py`](work/gate_october_regime_entries.py) |
| 挂单和逐笔止损回放 | [`work/replay_gate_october_seconds.py`](work/replay_gate_october_seconds.py) |
| 穿越时机对照 | [`work/compare_gate_crossover_timing.py`](work/compare_gate_crossover_timing.py) |
| Bybit 原版与震荡空单退出 | [`bybit_legacy/btc_perp_backtest.mjs`](bybit_legacy/btc_perp_backtest.mjs) 和 [`bybit_legacy/btc_er_review_scratch.mjs`](bybit_legacy/btc_er_review_scratch.mjs) |

早期 Bybit 实验需要 Node.js 和交接文件列出的历史输入。Python 的 Bybit 核验和分析脚本通过 `BTC_BACKTEST_BYBIT_DIR` 指定行情目录。默认使用本机已有的原 Bybit 工作目录，其他环境使用 `bybit_legacy/`。Excel 导出脚本 `work/build_trade_diagnosis.mjs` 另外使用 `@oai/artifact-tool`。
