# 固定EXTRA仓位与交易成本：已执行交付

锁定源提交87f94d2e29b9832526e0aa35c0400c7ed7496805；独立分支codex/extra-sizing-cost-stress-20261114。不合并main，不替换原策略或旧结果。

**结论：保留B正式对照。小仓能减轻部分增量回撤，也削弱收益优势，效果并非各年稳定；不能据本轮宣布实盘替换。** 2023扣费对照I三版本均低于B；2025 C2小仓优势极小，C4的I100反而低于B。2024/2026减小EXTRA仍未普遍与B风险对齐。不新增入场、不继续搜索比例或阈值。

- [手机数值结论与七项答复](outputs/extra_sizing_cost_stress/DECISION_NOTES.md)
- [中文完整结论](outputs/extra_sizing_cost_stress/CONCLUSION.md)
- [六版本年度简表CSV](outputs/extra_sizing_cost_stress/mobile_annual.csv) · [逐情景/资产/方向全表CSV](outputs/extra_sizing_cost_stress/annual_matrix.csv)
- [手机报告ZIP](outputs/extra_sizing_cost_stress/artifacts/mobile_report.zip) · [完整流水按年/情景拆分](outputs/extra_sizing_cost_stress/artifacts)
- [2025九情景重新核对](outputs/extra_sizing_cost_stress/SCENARIO_RECHECK.md) · [范围CSV](outputs/extra_sizing_cost_stress/2025_scenario_ranges.csv)
- [测试与财务核算](outputs/extra_sizing_cost_stress/TEST_RESULTS.md) · [最终验证记录](outputs/extra_sizing_cost_stress/final_validation.json)
- [配置](outputs/extra_sizing_cost_stress/configuration.json) · [固定协议](outputs/extra_sizing_cost_stress/EXPERIMENT.md) · [可复跑命令与输入前提](outputs/extra_sizing_cost_stress/RERUN.md)
- [资金费来源](outputs/extra_sizing_cost_stress/FUNDING.md) · [具体问题/失败恢复](outputs/extra_sizing_cost_stress/ISSUES.md) · [覆盖/未验证](outputs/extra_sizing_cost_stress/availability.csv)
- [逐笔分类与事件CSV.gz](outputs/extra_sizing_cost_stress) · [所有拆分包及SHA](outputs/extra_sizing_cost_stress/artifact_index.json)

完成所有可执行组合：532个组合（456个必需、76个明确退路），其中2025九视图不是独立样本。另88项含资金费因2020—2023缺结算标记价仍未验证，未补零。2024/2025/2026/NOV使用官方精确费率、时点与标记价进入现金；C1—C4费率是假设。资金费完整不代表排队或真实账户净收益已验证。

2025保留COMPLETED_WITH_DATA_ANOMALY：本轮九情景年度指标相同，仍有小幅分钟权益差异并保留各自历史，不能写官方行情已修复。181项测试和655份账本独立核对通过；旧严格失败记录不改。BTC14份原C0/C1路径经同源证明复用，具体清单见BTC_reuse_proof.json。

2020仅2月16日至年底；2026仅1—10月；NOV为11月1日至13日08:00北京独立起算；各币每段500，非跨年复利；2019未验证。回撤为分钟末权益口径。触价/越一tick全量均是代理，不是排队模型。已有年份不是样本外。

Git保留代码、表格、日志及完整逐笔账本包；GB级原生行情、原始异常ZIP、解析数组和分钟权益数组留在云端，清单与SHA随报告交付。新克隆需先恢复同SHA输入，不宣称下载报告即可无数据复跑。历史git_checkpoint.json仅记录中途提交；最终提交以本页所在commit为准。
