# 实际调用链与main差异
main对照e66859aff89490b9b02c286e59d7d8270802972a：work/fit_squeeze_ladder_bot.py、replay_gate_october_seconds.py、gate_october_regime_entries.py、fit_gate_entry_overlay.py、replay_gate_bot.py、replay_gate_selected_3x.py均与本地使用文件逐字节相同，见main_source_comparison.json。

后续云端helper outputs/retry_nov9_nov12/replay_comparison.py不在该main快照，不能称它就是main。它只提供旧观察器/加载桥；真正财务函数继承上述main的model.Sleeve。main中RegimeOverlay默认pause_transition=False，但旧selected驱动会从fast-window JSON载入True；本轮遵从用户明确指定False，不继承旧JSON覆盖。main默认selected入口还是双穿越实验，本轮明确使用CONTROL/BASELINE，不声称默认main入口与本实验全部相同。

本轮调用链：worker→signals.make→main model.build(原六SMA/EMA20/60/120、MACD)→MaskLeg.signals(原Settings96/5，替换历史密集条件)→原regime.market_schedules(ENTRY96/5/.25，调用被代理候选，不让.25前置拦截；ER显式12h/.2828427和120h/.10；use_entry_crosses=False)→与原stacked_signals一致的6线/ER/趋势门槛，range密集两项按A/B/C实际mask→engine.Book→原CONTROL Ledger/AuditSleeve→原model.Sleeve无分批减仓→原逐笔minute事件循环。

A额外与原leg+原schedule+原stacked_signals逐信号核对；POLICY(.25,.50,2,False)显式，不继承旧p.prepare政策。45天历史用于均线/ATR/2880观测预热，账户仍每年从500空仓开始。

engine动态复用已审计CORE优先事件方法，但将其货币基类从Dynamic替换成原CONTROL。book.profile=CONTROL、不是Dynamic实例，逐日拒绝任何partial事件；因此虽旧加载桥会导入V2类定义，本轮不继承/执行V2，不调用反弹续跌signals。D仅复用+10s优先请求、原止损优先、退出后下一事件才能填新单的既有机制，EXTRA倍数双币均1/3×原3x。

市场来自现有币安USDT永续15m/1m与原始逐笔框架，原档案checksum/严格ID路径不变；2025ETH仅已授权白名单S_ALL。没有调用旧simulate入口来代替逐笔账户，也没有使用旧含V2年度A收益。
