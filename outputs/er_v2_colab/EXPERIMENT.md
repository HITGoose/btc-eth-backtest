# Frozen ER_V2 portability experiment

SOURCE_BASELINE_COMMIT=f8aa6a9440ce3a0b486a3b1245a1051b77b8d145

Only ER_V2_FAIL_EXIT and ER_V2_VOL_SIZE, independently. No combined variant. No signal/threshold/fee search. Baseline reuse only, no new baseline account replay. Fixed formulas and semantics are in README.md and variant_engine.py. Core signal dictionaries must exactly match the archived original dictionaries in the tested interval. Fee=0, funding=0, slip=.0002, leverage=3 before volatility multiplier, per-asset yearly initial cash500. Original entry/capacity/rounding/poll5 phase2, hard stop and unlimited ladder intact.

Runtime checkpoint fingerprint includes original shared/cost/replay financial source fingerprint, new financial code, exact native hashes, original core map, boundaries and experiment versions. S_ALL only the original known SHA/day/asset/array hashes. All other strict errors block. I/O errors cannot activate original OHLC fallback. No automatic cache deletion. Raw touched-full fill is only a simulation proxy.

Implementation validation scope: compile/import, synthetic V2/whole-trade gross/one-shot/stop-priority mechanics, one8h official raw interval (2020 ETH first signal), same short checkpoint resume, empty-results report handling. No yearly new account or full matrix is run by Codex. Small evidence stays in validation/; it is not a profitability claim. Git source files from the baseline are untouched.

Colab full run creates14 independent processes/tasks sequentially or bounded parallelism; each task advances2 separate books against shared loaded native/raw data. No baseline generator is created. The notebook pins implementation by commit, uses private secrets out of persisted source, restores Drive files to local data, and backs completed daily checkpoints to Drive. GPU is not used.

2023—2026 is repeatedly observed historical data, not new out-of-sample. Per-year accounts reset. Period USDT sums are independent sums, not linked compounding or pooled multi-year drawdown. Matched normalized effects are diagnostic, not independently executable profits.
