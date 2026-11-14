实际命令（仓库根目录）：

```sh
/workspace/.venv-btc-eth-original/bin/python -u outputs/cross_asset_entry_audit/run.py > outputs/cross_asset_entry_audit/run.log 2>&1
/workspace/.venv-btc-eth-original/bin/python outputs/cross_asset_entry_audit/package.py
node --check /tmp/cross_asset_mobile_check.js
```

只读既有币安永续逐笔结果、官方原生K线并重建指标；没有下载全历史或重跑收益。原始数据来源及SHA在原结果目录raw_sources.json、各年原生K线manifest。本次结果、口径、缺失范围与逐项明细见report.md、audit.json、results.json。未改策略参数，无新网络下载失败。
