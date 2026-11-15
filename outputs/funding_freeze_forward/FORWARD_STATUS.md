# 实际前瞻/采集状态

原始采集与财务有效截止分开。HALTED行不提供收益/回撤，不把初始现金500误写成已验证0%收益；记录中的零手续费/零资金费只是尚无模拟交易的账本计数，不是未知成本填零。当前未形成可比较策略表现的有效样本。

```json
{
  "run": "freeze_1794697200000",
  "T0_UTC": "2026-11-14T23:00:00+00:00",
  "observed_last_received_UTC": "2026-11-14T23:06:00.868170+00:00",
  "financial_verified_cut_UTC": null,
  "status": "UNVERIFIED_FINANCIAL_HALTED",
  "halt_count": 362,
  "first_halt": {
    "reason": "RAW_TRADE_ID_GAP",
    "received_us": 1794696751821601,
    "asset": "ETH",
    "previous": 8991228049,
    "current": 8991228051
  },
  "raw_unique_validated_trade_messages": 272208,
  "forward_sample_sufficient": false
}
```
```json
{
  "run": "ws_closed_fix_1794699000000",
  "T0_UTC": "2026-11-14T23:30:00+00:00",
  "observed_last_received_UTC": "2026-11-14T23:51:13.357235+00:00",
  "financial_verified_cut_UTC": null,
  "status": "UNVERIFIED_FINANCIAL_HALTED",
  "halt_count": 639,
  "first_halt": {
    "reason": "PROCESSING_ERROR",
    "received_us": 1794698779994039,
    "error": "AssertionError()"
  },
  "raw_unique_validated_trade_messages": 386286,
  "forward_sample_sufficient": false
}
```
```json
{
  "run": "ws_fix_1794698100000",
  "status": "STARTUP_FAILED_NO_ACCOUNT_CHECKPOINT"
}
```

全部已创建账本的现金/已实现/未平仓估值可对账，但数据闸门未通过不能当完整前瞻收益。历史估算与本次实时观察独立。原始消息、接收/进入模拟器时间、原响应SHA及哈希链在云端保留；未运行未来30/60/90天，不承诺环境常驻。

目前实际观察到官方WS的p=0,q=0,X=NA消息，未核实语义前严格拒绝，不用0价止损、不跳过伪造收益。部分后继ID gap是拒绝零价消息后的派生标记，不等于已证明网络丢包。API历史补查无密钥返回401，文档查询未取得NA语义正文；限制仍在。
