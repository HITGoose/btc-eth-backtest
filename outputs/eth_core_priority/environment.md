# 实际环境与执行

- 工作目录/workspace/btc-eth-backtest；Python3.12.14（/workspace/.venv-btc-eth-original/bin/python）；Git2.52.0。
- 当前依赖已可导入并实际完成回放，无需本轮重装。原requirements.txt保留；新克隆应先安装。
- 无本地.git元数据，经已授权GitHub连接读取锁定完整树并创建/提交独立分支；未以公开404判断私有仓库不存在。锁定树及本地均无AGENTS.md。
- 新实验写outputs/eth_core_priority和新根审查入口；旧源码/结果及main不替换。冻结代码SHA见frozen_config，原138个Python blob核对一致。
- 运行中磁盘7.9GiB总量，剩余约4.6GiB；内存约9.7GiB，未发生OOM或磁盘耗尽。公开Binance官方HTTPS下载和CHECKSUM实际可用，一次文件SHA不匹配已隔离并恢复；2025冲突属于已验证官方数据内容问题。
- 所有HTTP行情均仅data.binance.vision/data/futures/um；无真实账户/API密钥/下单。其他年份BTC缓存复用明确记录reuse_manifest，不宣称重播。
- 逐任务命令、stdout/stderr、源清单、配置及失败都保留；commands.log/EXPERIMENT.md给出入口。每次只从相同财务代码指纹自有月末断点恢复，费用独立账本选择有subset manifest和回归测试。
