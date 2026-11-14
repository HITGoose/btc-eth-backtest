# 2025 异常敏感性独立实验

源提交17366bb41b11ca82e3084f2f042c09e00b160234；独立分支codex/eth-2025-anomaly-sensitivity-20261114。策略完全不改。

90个ETH全年情景账户（5组×2费用×9视图）完成，BTC经独立路径验证复用。状态COMPLETED_WITH_DATA_ANOMALY；严格D/G/H/I仍UNVERIFIED；原七区间不混入本轮。九情景年度指标均相同，但局部1,824次轮询价格及152分钟权益有差异，最大0.0057U。成交与金融事件变化均0。没有修复官方数据的声明。

[中文报告](outputs/eth_2025_anomaly_sensitivity/report.md) · [年度完整CSV](outputs/eth_2025_anomaly_sensitivity/annual_scenarios.csv) · [手机年度表](outputs/eth_2025_anomaly_sensitivity/annual_mobile.csv) · [最终核验](outputs/eth_2025_anomaly_sensitivity/audit.json) · [复跑协议](outputs/eth_2025_anomaly_sensitivity/EXPERIMENT.md) · [限制](outputs/eth_2025_anomaly_sensitivity/ISSUES.md)

完整流水、冲突影响、原字段审计及日志在outputs/eth_2025_anomaly_sensitivity/artifacts/。原始数据/断点保留云端，不随Git上传；恢复要求见ISSUES.md。

G扣假设费后低于B15.03U，I高于B12.02U，九情景结论一致。2025独立条件结果不构成全历史策略推荐。额外三条quote_qty异常原样保留，不能声称九情景覆盖所有问题。
