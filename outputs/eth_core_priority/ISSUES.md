# 本轮实际问题记录

- 完整锁定树无AGENTS.md。本地提供执行源码与上一轮结果/缓存，没有.git元数据；经授权GitHub连接核对并从指定SHA创建独立实验分支。执行Python全与锁定blob一致。10个无关旧CSV只有换行转换不同；62个无关旧历史输出本地未取回，未冒充全部Git checkout。详细source_check.json。新实验不写旧目录。
- 开发阶段测试发现inspect.getsource不能读取已动态compile的generator；改为读取冻结engine保存的source字符串，所有源码替换都assert唯一命中。测试随后通过。
- 日志来源标签最初会覆盖原journal.side字符串；正式执行前已修正为不覆盖金融方向字段。部分退出事件保留旧字段以精确回归。开发基准试跑为补充影子状态快照而主动终止，全部单独保留development_run_before_shadow_snapshot，未计正式结果；没有复用其账本断点。
- 优先请求/影子快照及raw trade ID观察在最终代码冻结前加入，39项边界测试通过后重新正式执行。冻结代码指纹见frozen_config.json；旧代码从未覆盖。
- 延续已知严格阻断：2025-08-29 ETH日/月官方raw trades含3个冲突ID。旧原ZIP保留且各任务可硬链接，仍重新核对官方checksum，ID校验不放宽。每组是否遇到该日由真实完整路径决定，失败日志和月末断点保留，不能用完成的B替代D/G/H/I。
- 非零费率部分出场journal继承上一轮已验证分摊修正，cash交易逻辑不变。ZERO和假设每边.05%分别完整路径，不将压力费率说成用户实际费率；资金费缺失。
