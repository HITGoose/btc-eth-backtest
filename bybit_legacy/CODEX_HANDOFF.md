# BTCUSDT 15 分钟策略 · Codex 交接

## 工作位置

- 工作目录为 `D:\coding\btc_backtest_work`。
- `btc_perp_backtest.mjs` 是原始基线。用 `combined_review` 运行只多、只空和多空合并。
- `btc_er_review_scratch.mjs` 从原脚本衍生，`er_review` 模式包含所有已跑的震荡对照。
- `bybit_2025_completed_scratch.csv` 是已用来重跑的 Bybit BTCUSDT 永续 15m OHLC，覆盖到 2025 年末。2024 和 2025 原策略结果及逐笔记录已核对一致。
- `BTCUSDT_er_2024_summary.json`、`BTCUSDT_er_2025_summary.json` 与同前缀的 `_trades.csv` 是核对过的输出。

## 冻结的规则

- 15m 产生进场信号，下一根开盘成交。多单用均线聚集、金三角、零轴下方且在 0.20 ATR 内的 MACD 金叉及突破，精确定义以原脚本为准。空单用 8H 新高、MA5 下穿 MA20，再确认均线发散和零轴上方 MACD 死叉。4H 不设开仓门槛。
- 多空共用一份资金、同时一笔仓位。每个独立窗口从 100 USDT 起跑，最高 5 倍，开仓量按 0.001 BTC 取整。2% 是标的价格止损。顺势 0.8% 尝试减仓 20%，余仓按原有反转规则退出。单边滑点 0.02%，手续费与资金费率不计，沿用原模拟口径。
- 仅空单时间退出版本用开仓信号时已收盘的 15m K 线计算 ER(20)。ER < 0.25 才锁定为震荡单。仅在该空单入场满一小时，且首四根 K 线最大顺向波幅 < 0.4% 时，于下一根开盘平仓。原止损或反转规则可先执行。多单按原出场处理。
- 对照情景名是 `combined_selected_long_and_8h_short`，候选名是 `combined_selected_long_and_8h_short_timeout_shorts_only`。

## 已核实结果

| 多空合并 | 2024 收益 | 2025 收益 | 2025 最大回撤 |
|---|---:|---:|---:|
| 原策略 | +121.06% | -12.93% | 27.09% |
| 仅空单加时间退出 | +123.20% | -5.07% | 22.82% |
| 多空都加时间退出 | +103.90% | -4.93% | 18.24% |

2025 年只空对照为 -11.88%，加时间退出为 -1.40%。2024 年只空对照为 +79.12%，加时间退出为 +84.79%。2022–2024 用于原始参数筛选，2025 用于设计时间退出。历史数字是模拟结果。

## 下一步

对照冻结的原策略和仅震荡空单加时间退出两版，优先使用 2026 年 1–9 月 Bybit BTCUSDT 永续 15m 行情作为这条新规则的样本外。起止为马来西亚时间 2026-01-01 00:00 至 2026-10-01 00:00，结束不含。目标为 26,208 根连续 K 线，另保留前 15 天预热数据。报告两版收益、最大回撤、笔数、多空盈亏和触发退出的笔数。冻结参数，按数据核验情况标注实际覆盖范围。

已经下载候选行情 `bybit_BTCUSDT_15m_source_scratch.parquet`，来源为 Hugging Face rogerdehe/klines-bybit 的 futures/15m/BTC_USDT_USDT.parquet。`btc_2026_prepare_scratch.py` 的 2025 全年重叠逐值一致断言失败。尚无 2026 验证结果。先量化不匹配行和误差并抽查 Bybit 官方 K 线。若行情确实不同，保持同一合约和数据来源，重新验证连续覆盖与衔接。仅使用历史行情和本地模拟。

可在工作目录运行下列命令，前提是已生成且验证输入 CSV。

```powershell
node btc_er_review_scratch.mjs bybit_BTCUSDT_15m_2026_JanSep_scratch.csv BTCUSDT_er_2026_JanSep '2025-12-31T16:00:00Z' '2026-09-30T16:00:00Z' bybit er_review
```
