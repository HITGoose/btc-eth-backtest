# 正确ER＋V2历史逐项复测清单

基准登记f8aa6a9440ce3a0b486a3b1245a1051b77b8d145。2026按用户追加改至北京时间11月15日全天，Jan1连续至Nov16 00:00，不能11月重置。其他年区间保持。全部ZERO/资金费0/退出滑点.02%，真实逐笔模拟代理，2025仅原S_ALL。
各历史配置源码已认证读取指定提交，逐文件SHA见source_manifest.json。这里只迁移声明部分，不携带旧无V2/fixed/OHLC基准。

|序号|规范身份|准确规则|原基准／处理|
|---|---|---|---|
|0|REF|原ER＋V2、uncapped；2026延长至11月15日全天|仅2026补完整区间|
|1|FAIL_EXIT|成交4h后首闭15m一次；两根各在自身六线带内；整笔分批毛盈亏+余仓浮盈<0；T+60首逐笔退出|旧无V2/FIXED5/OHLC；已移植修正版完整保留V2，只导入已完成|
|1|VOL_SIZE|ATR96/close；此前2880有效值中位数；倍率clip(ref/v,.5,1)冻结；无效1|旧无V2/FIXED5/OHLC；已移植修正版只导入已完成|
|1|FIXED_LOW|正确V2的2020—2022 VOL成功提交订单目标L算术平均；两币同一L冻结|重新训练校准，不用旧无V2 L_fixed|
|2|ATR_STOP|d=clip(2ATR96/原限价,.01,.03)；L=min(3,.06/d)，只冻结初始stop，原阶梯不按ATR缩放|旧无V2/FIXED5/OHLC；移植保留V2、uncapped|
|3|CANCEL|新闭15m long close<=带上沿／short close>=带下沿；T+60撮合前取消未成交原单；成交后不撤|旧无V2/FIXED5/OHLC；移植不改持仓及V2|
|4|CAP5|exit_policy=fixed，锁利最多5档，非盈利5%即退出|原无V2/OHLC；只改cap，保留V2|
|4|TRAIL8|原trail_from_8pct：有利幅度>=8%后解除cap继续阶梯，不是cap8|原无V2/OHLC；只改声明出场，保留V2|
|5|REGIME_SIZE|120h ER阈值.10方向与原信号同向×1.3，其余×.7；信号冻结|原无V2/fixed/OHLC；只移植权重，保持V2 uncapped|
|6|ETH030|仅ETH历史96最小六线带宽<=.30%；当前range带宽.50不变|原ER+V2同口径可复用|
|6|ETH035|仅ETH历史96最小六线带宽<=.35%；当前range带宽.50不变|原ER+V2；缺2025 S_ALL需补，2026延长需补|
|7|Q15|原过去2880根不含当前S/W线性分位数 [0.15, 0.4]；无绝对上下限|原无V2/RAW；仅2020—22训练三候选，留V2；冻结B赢家评估后续|
|7|Q20|原过去2880根不含当前S/W线性分位数 [0.2, 0.45]；无绝对上下限|原无V2/RAW；仅2020—22训练三候选，留V2；冻结B赢家评估后续|
|7|Q25|原过去2880根不含当前S/W线性分位数 [0.25, 0.5]；无绝对上下限|原无V2/RAW；仅2020—22训练三候选，留V2；冻结B赢家评估后续|
|8|N05|原N=六线价差/ATR96(首TR NaN)；min96N与当前N阈值 [0.5, 1.0]|原无V2/RAW；仅2020—22训练三候选，留V2；冻结C赢家评估后续|
|8|N10|原N=六线价差/ATR96(首TR NaN)；min96N与当前N阈值 [1.0, 2.0]|原无V2/RAW；仅2020—22训练三候选，留V2；冻结C赢家评估后续|
|8|N15|原N=六线价差/ATR96(首TR NaN)；min96N与当前N阈值 [1.5, 3.0]|原无V2/RAW；仅2020—22训练三候选，留V2；冻结C赢家评估后续|
|9|ADAPT_CORE_LIGHT|A完整CORE3x＋冻结自适应EXTRA1x，双币；CORE+10s原优先替换；不叠仓|旧无V2/uncapped/RAW；本次留V2，组合含信号并集+仓位+优先级|
|10|BTC_CONFIRM|ETH.30，仅EXTRA须BTC同根原CORE信号同向；CORE不受影响|原ER+V2，可复用；不使用BTC后续成交/盈亏|
|10|CORE_PRIORITY|ETH.30，CORE原+10s撤EXTRA单或请求逐笔先平再挂；止损优先，不用退出同事件成交|原ER+V2，可复用|
|10|BOTH100|ETH.30+BTC确认+CORE优先，EXTRA1.0原目标|既有明确组合，非新增组合；原ER+V2|
|10|BOTH50|同既有I组合，仅ETH EXTRA×.5，CORE不缩小|既有明确组合，原ER+V2|
|10|BOTH25|同既有I组合，仅ETH EXTRA×.25，CORE不缩小，V2余额3%预算不改|既有明确组合，原ER+V2|
|11|REBOUND|沿用原反弹形态/ER down/六线/MACD/SMA5/20与near OR volume OR retest；不重设密集|原ER+V2同口径；分别组合仅BTC、仅ETH、双币；只算两条单币路径|

## 去重与冲突顺序

{"uncapped": "REF", "ETH025": "REF", "density_B": "REF", "priority_B": "REF", "priority_D": "ETH030", "density_D": "ETH030", "density_F": "ETH035", "priority_G": "BTC_CONFIRM", "priority_H": "CORE_PRIORITY", "priority_I": "BOTH100", "I100": "BOTH100", "I50": "BOTH50", "I25": "BOTH25"}

- uncapped＋V2与0.25基准仅一份。ETH修改组的BTC引用基准，不重算。REBOUND仅两种单币路径，按时间轴组成三种组合，不自动挑币。
- 双币ADAPT_CORE_LIGHT与ETH I25/I50/I100范围及信号来源不同，不能按D/I字母合并。
- 初始ATR只换初始stop与下单量；V2仍先按既定规则减仓，阶梯绝不放松stop。CAP5/TRAIL8仍走真实BoundedAdaptive。
- FAIL_EXIT检查毛盈亏包括同笔已兑现部分，不包括别的交易；实际逐笔先原止损、再原V2队列、仍有余仓才执行请求。
- CORE替换沿原优先级：止损优先，其次主动替换（先于本事件可选V2减仓），平后提交不消费同退出事件。已发生V2部分退出保留。
- CANCEL在分钟前原到期之后、价格撮合之前处理T+60撤单，只撤同订单对象；不改已有持仓。实际取消有独立计数，非伪记到期。

## 训练与复用

固定低杠杆只取正确V2 VOL训练六账户成功提交目标L。B/C各自三候选、评分三年组合mean(return−DD)，并列最差年度回撤低/实际成交少/原预设顺序；冻结后再评估后续。D用B/C赢家同评分择源，仍旧组合，不新增参数。
53份既有2020—2025非基准账户可复用，reuse_manifest.json及reuse_baseline_checks.json有证据；原基准12份同区间复用。2026结束时间改变，旧Jan-Oct结果只保留历史，不算新全段结果。若无兼容完整状态断点，2026必须原起点重放；不能从结果JSON捏造V2状态。
两个已完成变体：从Drive或用户ZIP导入正确ef0b074实现，旧c6d23ea错误输出拒收。未导入的早年账号标WAITING，不重算。2026因新区间例外需要补齐。所有市场缓存可复用。

本轮Codex不执行年度矩阵。运行状态：UNRUN_IN_THIS_ENVIRONMENT；必要短试算与已有账本只读核对另列。