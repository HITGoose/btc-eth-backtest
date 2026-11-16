# 实现与统计修复记录（不改策略）

- 下载调度：并行2账户改为串行1账户，以避免同盘日ZIP争用；已完成账户不重跑。
- 原金融执行器、compare_runner.py及原数据指纹保持不变。断点恢复仍核对原financial fingerprint与账户键。
- 2025 ETH的ScenarioCache原已有load实现，但原progress读取cache.sources时缺少属性。恢复器仅添加到strict.sources的只读委托，不改load、价格或交易。
- 少数官方日档加32MiB保留空间超过剩余容量。恢复器在串行下载、解析后原机制删除临时ZIP的条件下，保留16MiB；仍验证原官方CHECKSUM，真实不足继续失败。
- 临时空间恢复：清理现有Git仍保存、且blob SHA逐一匹配的base64上传编码副本；不是删除原行情、账本或审计数据。清单见temporary_cleanup.json。
- audit.py中旧历史MA列表与raw parity循环局部变量重名，导致报告生成中断。改用oldraw变量，修复后从原账本重做只读汇总，不回放金融账户。

每次容量与日志恢复的原失败、checkpoint SHA、适配器SHA及不变的金融／数据指纹见runs/YEAR/ASSET/transport_recovery.json，完整调用日志见logs/。
