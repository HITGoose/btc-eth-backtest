# ETH历史密集阈值：固定六组逐笔实验

## 当前结论

结果尚未完整，不能宣称任何放宽有效，也不能将未验证组填为零。暂保留0.25%，待数据问题解决再完成判断；缺失组见availability.csv与末尾，2019始终UNVERIFIED。

已验证部分暂不支持替换0.25%：新增ETH交易自身总体盈利，但四个放宽对照的独立区间账户期末损益差额合计均为负，并存在挤掉原盈利、回撤/最差月恶化和费用侵蚀。2025放宽组缺数据，不将这一观察称为全历史完整验证。

|对照|费用|新增ETH赢/亏|新增交易净额USDT|完整账户差额USDT|消失原盈利单|失去原盈利USDT|
|---|---|---:|---:|---:|---:|---:|
|C/A|ZERO|57/53|+833.83|-354.70|29|1602.03|
|C/A|ASSUMED_005_SIDE|57/53|+574.54|-417.69|29|1360.57|
|D/B|ZERO|57/53|+662.55|-269.91|29|1307.48|
|D/B|ASSUMED_005_SIDE|57/53|+412.20|-353.94|29|1109.07|
|E/A|ZERO|108/93|+1100.46|-108.86|40|1946.54|
|E/A|ASSUMED_005_SIDE|108/93|+674.59|-328.15|40|1664.12|
|F/B|ZERO|108/93|+932.27|-54.41|40|1592.05|
|F/B|ASSUMED_005_SIDE|108/93|+525.32|-279.34|40|1357.40|

以上为已验证独立区间的USDT描述性合计，不是连续复利收益，也未将原ER/V2或两种费用场景当作独立样本相加。匹配旧亏损单的USDT扩大与同初始名义扩大另列，不能混为价格风险。

## 六组逐区间比较

A=.25原出场；B=.25V2；C=.30原出场；D=.30V2；E=.35原出场；F=.35V2。仅ETH阈值改变，BTC固定.25。收益/回撤均为BTC+ETH分钟组合权益。每个区间各币500；2020仅02-16至年底；2026仅1—10月；NOV为11月独立起算至13日08:00。不拼接成年内连续收益。

|区间|费用|组|收益%|回撤%|最差月%|最长连亏|已平/未平|
|---|---|---|---:|---:|---:|---:|---:|
|2019|ZERO|A|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ZERO|B|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ZERO|C|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ZERO|D|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ZERO|E|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ZERO|F|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|A|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|B|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|C|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|D|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|E|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2019|ASSUMED_005_SIDE|F|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2020|ZERO|A|-2.43|47.08|-22.19|6|145/0|
|2020|ZERO|B|+7.87|38.40|-19.16|6|145/0|
|2020|ZERO|C|+50.73|49.93|-24.59|7|159/0|
|2020|ZERO|D|+53.50|41.39|-22.16|7|159/0|
|2020|ZERO|E|+57.51|53.33|-24.64|7|170/0|
|2020|ZERO|F|+60.74|45.39|-22.28|7|170/0|
|2020|ASSUMED_005_SIDE|A|-21.09|54.00|-24.44|6|145/0|
|2020|ASSUMED_005_SIDE|B|-13.28|46.53|-21.51|6|145/0|
|2020|ASSUMED_005_SIDE|C|+19.52|56.72|-26.90|7|159/0|
|2020|ASSUMED_005_SIDE|D|+20.69|49.29|-24.54|7|159/0|
|2020|ASSUMED_005_SIDE|E|+21.96|59.70|-26.95|7|170/0|
|2020|ASSUMED_005_SIDE|F|+23.55|52.96|-24.64|7|170/0|
|2021|ZERO|A|+44.91|27.89|-23.59|5|66/0|
|2021|ZERO|B|+44.06|24.63|-20.79|5|66/0|
|2021|ZERO|C|+32.32|27.93|-23.75|5|71/0|
|2021|ZERO|D|+33.47|24.72|-20.83|5|71/0|
|2021|ZERO|E|+69.73|20.42|-15.14|5|85/0|
|2021|ZERO|F|+62.12|18.43|-13.99|5|85/0|
|2021|ASSUMED_005_SIDE|A|+31.20|30.03|-25.15|5|66/0|
|2021|ASSUMED_005_SIDE|B|+30.44|26.57|-22.29|5|66/0|
|2021|ASSUMED_005_SIDE|C|+18.99|29.61|-25.15|5|71/0|
|2021|ASSUMED_005_SIDE|D|+19.49|26.54|-22.30|5|71/0|
|2021|ASSUMED_005_SIDE|E|+49.63|25.13|-17.24|5|85/0|
|2021|ASSUMED_005_SIDE|F|+43.22|23.08|-15.99|5|85/0|
|2022|ZERO|A|+103.45|28.34|-17.81|9|126/1|
|2022|ZERO|B|+83.75|22.51|-14.58|9|126/1|
|2022|ZERO|C|+100.18|27.56|-16.57|5|140/1|
|2022|ZERO|D|+81.01|21.51|-13.26|5|140/1|
|2022|ZERO|E|+77.50|28.72|-16.02|5|146/1|
|2022|ZERO|F|+62.30|22.34|-12.91|5|146/1|
|2022|ASSUMED_005_SIDE|A|+68.25|29.27|-20.15|9|126/1|
|2022|ASSUMED_005_SIDE|B|+52.25|23.57|-16.97|9|126/1|
|2022|ASSUMED_005_SIDE|C|+61.90|28.78|-18.94|5|140/1|
|2022|ASSUMED_005_SIDE|D|+46.82|22.82|-15.74|5|140/1|
|2022|ASSUMED_005_SIDE|E|+42.10|31.31|-18.39|5|146/1|
|2022|ASSUMED_005_SIDE|F|+30.22|26.48|-15.33|5|146/1|
|2023|ZERO|A|+85.38|37.96|-15.82|6|182/1|
|2023|ZERO|B|+73.46|27.23|-13.62|6|182/1|
|2023|ZERO|C|+64.20|43.22|-18.70|6|191/1|
|2023|ZERO|D|+57.29|30.70|-15.75|6|191/1|
|2023|ZERO|E|+82.18|34.00|-17.44|6|199/1|
|2023|ZERO|F|+69.52|24.71|-14.51|6|199/1|
|2023|ASSUMED_005_SIDE|A|+41.12|45.91|-18.09|6|182/1|
|2023|ASSUMED_005_SIDE|B|+32.06|35.10|-15.90|6|182/1|
|2023|ASSUMED_005_SIDE|C|+23.40|51.08|-21.04|6|191/1|
|2023|ASSUMED_005_SIDE|D|+18.39|40.17|-18.09|6|191/1|
|2023|ASSUMED_005_SIDE|E|+35.73|43.28|-19.97|6|199/1|
|2023|ASSUMED_005_SIDE|F|+26.25|33.27|-17.03|6|199/1|
|2024|ZERO|A|+50.80|32.54|-17.95|5|165/0|
|2024|ZERO|B|+49.85|26.41|-13.68|5|165/0|
|2024|ZERO|C|+41.91|38.58|-21.25|5|181/0|
|2024|ZERO|D|+35.36|31.59|-17.24|5|181/0|
|2024|ZERO|E|+48.10|37.21|-18.94|5|200/0|
|2024|ZERO|F|+38.60|29.92|-14.89|5|200/0|
|2024|ASSUMED_005_SIDE|A|+17.53|34.13|-19.04|5|165/0|
|2024|ASSUMED_005_SIDE|B|+17.07|27.87|-14.91|5|165/0|
|2024|ASSUMED_005_SIDE|C|+8.35|43.97|-22.64|5|181/0|
|2024|ASSUMED_005_SIDE|D|+2.85|37.39|-18.68|5|181/0|
|2024|ASSUMED_005_SIDE|E|+10.10|42.92|-20.39|5|200/0|
|2024|ASSUMED_005_SIDE|F|+3.38|36.67|-16.53|5|200/0|
|2025|ZERO|A|+205.33|22.61|-2.83|7|150/1|
|2025|ZERO|B|+167.86|19.37|-3.86|7|150/1|
|2025|ZERO|C|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ZERO|D|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ZERO|E|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ZERO|F|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ASSUMED_005_SIDE|A|+144.92|23.58|-4.95|7|150/1|
|2025|ASSUMED_005_SIDE|B|+114.43|20.38|-6.05|7|150/1|
|2025|ASSUMED_005_SIDE|C|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ASSUMED_005_SIDE|D|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ASSUMED_005_SIDE|E|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2025|ASSUMED_005_SIDE|F|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|
|2026|ZERO|A|+83.00|32.28|-18.07|4|138/0|
|2026|ZERO|B|+57.88|27.27|-15.50|4|138/0|
|2026|ZERO|C|+40.29|33.57|-17.98|4|148/0|
|2026|ZERO|D|+29.27|29.27|-15.78|4|148/0|
|2026|ZERO|E|+17.48|35.77|-20.68|5|161/0|
|2026|ZERO|F|+17.29|30.58|-17.72|5|161/0|
|2026|ASSUMED_005_SIDE|A|+49.21|34.75|-19.88|4|138/0|
|2026|ASSUMED_005_SIDE|B|+28.58|29.94|-17.36|4|138/0|
|2026|ASSUMED_005_SIDE|C|+12.28|36.81|-19.99|4|148/0|
|2026|ASSUMED_005_SIDE|D|+3.48|32.80|-17.90|4|148/0|
|2026|ASSUMED_005_SIDE|E|-7.67|39.62|-22.83|5|161/0|
|2026|ASSUMED_005_SIDE|F|-8.11|35.24|-20.06|5|161/0|
|NOV|ZERO|A|+9.60|7.36|+9.60|1|7/0|
|NOV|ZERO|B|+7.86|7.36|+7.86|1|7/0|
|NOV|ZERO|C|+9.60|7.36|+9.60|1|7/0|
|NOV|ZERO|D|+7.86|7.36|+7.86|1|7/0|
|NOV|ZERO|E|+11.32|7.41|+11.32|1|8/0|
|NOV|ZERO|F|+8.73|7.36|+8.73|1|8/0|
|NOV|ASSUMED_005_SIDE|A|+8.54|7.40|+8.54|1|7/0|
|NOV|ASSUMED_005_SIDE|B|+6.80|7.38|+6.80|1|7/0|
|NOV|ASSUMED_005_SIDE|C|+8.54|7.40|+8.54|1|7/0|
|NOV|ASSUMED_005_SIDE|D|+6.80|7.38|+6.80|1|7/0|
|NOV|ASSUMED_005_SIDE|E|+10.08|7.40|+10.08|1|8/0|
|NOV|ASSUMED_005_SIDE|F|+7.47|7.39|+7.47|1|8/0|

## 七项核算答复（仅已验证的比较区间）


### C对A / ZERO
1. 新增ETH已平仓整体净额+833.83 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损53笔，新增亏损额2248.20 USDT；全体ETH已平仓总亏损额变化+1923.60 USDT。
3. 消失的原盈利单29笔，失去盈利1602.03 USDT；避免原亏损521.05 USDT。
4. 匹配原亏损单中，实际USDT损失扩大55笔；统一初始名义后扩大0笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2021', '2023', '2026']；最差月恶化['2024', '2020', '2021', '2023']；ETH最大单笔USDT亏损恶化['2024', '2020']。
6. 组合收益改善区间['2020']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2024', '2020', '2021', '2022', '2023', '2026']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### C对A / ASSUMED_005_SIDE
1. 新增ETH已平仓整体净额+574.54 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损53笔，新增亏损额2102.94 USDT；全体ETH已平仓总亏损额变化+1711.19 USDT。
3. 消失的原盈利单29笔，失去盈利1360.57 USDT；避免原亏损501.11 USDT。
4. 匹配原亏损单中，实际USDT损失扩大55笔；统一初始名义后扩大0笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2023', '2026']；最差月恶化['2024', '2020', '2023', '2026']；ETH最大单笔USDT亏损恶化['2024', '2020']。
6. 组合收益改善区间['2020']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2024', '2020', '2021', '2022', '2023', '2026']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### E对A / ZERO
1. 新增ETH已平仓整体净额+1100.46 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损93笔，新增亏损额4274.49 USDT；全体ETH已平仓总亏损额变化+3880.74 USDT。
3. 消失的原盈利单40笔，失去盈利1946.54 USDT；避免原亏损842.03 USDT。
4. 匹配原亏损单中，实际USDT损失扩大82笔；统一初始名义后扩大0笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2022', '2026', 'NOV']；最差月恶化['2024', '2020', '2023', '2026']；ETH最大单笔USDT亏损恶化['2024', '2020', '2021', 'NOV']。
6. 组合收益改善区间['2020', '2021', 'NOV']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2021', '2022', '2023', '2026', 'NOV']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### E对A / ASSUMED_005_SIDE
1. 新增ETH已平仓整体净额+674.59 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损93笔，新增亏损额3923.49 USDT；全体ETH已平仓总亏损额变化+3372.67 USDT。
3. 消失的原盈利单40笔，失去盈利1664.12 USDT；避免原亏损805.06 USDT。
4. 匹配原亏损单中，实际USDT损失扩大71笔；统一初始名义后扩大0笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2022', '2026', 'NOV']；最差月恶化['2024', '2020', '2023', '2026']；ETH最大单笔USDT亏损恶化['2024', '2020', '2021', 'NOV']。
6. 组合收益改善区间['2020', '2021', 'NOV']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2021', '2022', '2023', '2026', 'NOV']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### D对B / ZERO
1. 新增ETH已平仓整体净额+662.55 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损53笔，新增亏损额1788.67 USDT；全体ETH已平仓总亏损额变化+1473.10 USDT。
3. 消失的原盈利单29笔，失去盈利1307.48 USDT；避免原亏损415.81 USDT。
4. 匹配原亏损单中，实际USDT损失扩大52笔；统一初始名义后扩大62笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2021', '2023', '2026']；最差月恶化['2024', '2020', '2021', '2023', '2026']；ETH最大单笔USDT亏损恶化['2020']。
6. 组合收益改善区间['2020']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2024', '2020', '2021', '2022', '2023', '2026']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### D对B / ASSUMED_005_SIDE
1. 新增ETH已平仓整体净额+412.20 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损53笔，新增亏损额1684.63 USDT；全体ETH已平仓总亏损额变化+1305.03 USDT。
3. 消失的原盈利单29笔，失去盈利1109.07 USDT；避免原亏损407.11 USDT。
4. 匹配原亏损单中，实际USDT损失扩大45笔；统一初始名义后扩大51笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2023', '2026']；最差月恶化['2024', '2020', '2021', '2023', '2026']；ETH最大单笔USDT亏损恶化['2020']。
6. 组合收益改善区间['2020']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2024', '2020', '2021', '2022', '2023', '2026']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### F对B / ZERO
1. 新增ETH已平仓整体净额+932.27 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损93笔，新增亏损额3372.96 USDT；全体ETH已平仓总亏损额变化+2997.62 USDT。
3. 消失的原盈利单40笔，失去盈利1592.05 USDT；避免原亏损661.89 USDT。
4. 匹配原亏损单中，实际USDT损失扩大66笔；统一初始名义后扩大55笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2026']；最差月恶化['2024', '2020', '2023', '2026']；ETH最大单笔USDT亏损恶化['2020', '2021', 'NOV']。
6. 组合收益改善区间['2020', '2021', 'NOV']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2021', '2022', '2023', '2026', 'NOV']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

### F对B / ASSUMED_005_SIDE
1. 新增ETH已平仓整体净额+525.32 USDT（各独立区间合计，非复利收益率）。
2. 新增亏损93笔，新增亏损额3130.54 USDT；全体ETH已平仓总亏损额变化+2628.04 USDT。
3. 消失的原盈利单40笔，失去盈利1357.40 USDT；避免原亏损640.85 USDT。
4. 匹配原亏损单中，实际USDT损失扩大59笔；统一初始名义后扩大51笔，两者不得混淆。
5. 回撤恶化区间['2024', '2020', '2022', '2026', 'NOV']；最差月恶化['2024', '2020', '2023', '2026']；ETH最大单笔USDT亏损恶化['2020', '2021', 'NOV']。
6. 组合收益改善区间['2020', '2021', 'NOV']，比较覆盖['2024', '2020', '2021', '2022', '2023', '2026', 'NOV']；新增盈利前5笔占比≥50%的区间['2020', '2021', '2022', '2023', '2026', 'NOV']。完整集中度及归因值见concentration.csv。
7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。

## 解释和文件

yearly_metrics.csv分资产、方向列收益、权益、回撤、最差月、连续亏损、胜率、盈利因子、盈利亏损总额、尾部单笔和订单数。方向收益是同初始资本分母的PnL归因，不是另一个可执行方向账户。
组合连续亏损按平仓微秒时间排序，同时间BTC优先；方向曲线是PnL归因，不是拆开的独立可交易账户。
BTC的C/E重用A完整逐笔重放，D/F重用B；策略和独立子账户状态完全相同，非另一个独立样本，ETH所有六组均单独执行。
trade_attribution.csv及四类CSV按资产/方向/signal_close_ms匹配，保留不能配对记录；实际USDT差额与同1000USDT初始名义归一化分开。归一化含费用、数量取整和减仓比例的差异，不是纯价格路径指标，后者只作归因。所有已平仓净收益＋年末未平仓费用/部分退出/估值精确核对期末权益。
concentration.csv列新增盈利及正向归因差额的前1/前5笔集中度，不按结果挑样本；全年改善分布见yearly_metrics.csv。
impact.csv分年、资产、方向统计新增亏损、被挤盈利、旧亏损扩大及归一化变化。overlap_risk.csv列精确重叠秒数及发生在另一币持仓时的负现金流（含费用），另列分钟末同时持仓及最差合计浮亏、当前止损参考回吐及重叠时段回撤，不是实盘保证。
diagnostics_*.csv.gz记录所有预带宽候选的完整价格/指标/ER/趋势确认/回踩与实际提交或重建占用；NOT_EVALUATED不视为通过。诊断不反馈信号，不使用BTC将来成交或盈利。
非零费用下legacy close事件的net_usdt是旧观察器口径，整笔净收益以修正后的trade.net及cash_events核对；修正不改变账户交易。
费用ZERO=0；ASSUMED_005_SIDE=每边0.05%假设压力，并非核实用户实际费率。资金费未计，不能声称真实净收益验证；所有成交为真实逐笔价格上的全量触价代理，不保证实盘成交。
已有年份反复查看，不称样本外；只测试预设.25/.30/.35，没有逐年调参。新阈值都跑全部可验证区间，不因早期表现差省略。
data/config/provenance、官方raw_sources和逐币run_attempt日志保留；月末checkpoint为继续执行断点，pickle仅限本项目自产可信文件。入口与命令见EXPERIMENT.md。

## 缺失或失败

2019：UNVERIFIED，未补造；2026年11月13日08:00之后：UNVERIFIED。
{"period": "2025", "group": "C", "status": "UNVERIFIED", "error": "FileNotFoundError(2, 'No such file or directory')", "actual_error": "RuntimeError('Duplicate or unordered raw trade IDs')", "evidence_file": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/isolation/30/runs/2025/ETH/failure.json", "official_archive_issue": "2025-08-29 ETH raw trade IDs conflict; official daily and monthly day are byte-identical", "recovery_evidence": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/recovery_20250829_ETH/result.json"}
{"period": "2025", "group": "D", "status": "UNVERIFIED", "error": "FileNotFoundError(2, 'No such file or directory')", "actual_error": "RuntimeError('Duplicate or unordered raw trade IDs')", "evidence_file": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/isolation/30/runs/2025/ETH/failure.json", "official_archive_issue": "2025-08-29 ETH raw trade IDs conflict; official daily and monthly day are byte-identical", "recovery_evidence": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/recovery_20250829_ETH/result.json"}
{"period": "2025", "group": "E", "status": "UNVERIFIED", "error": "FileNotFoundError(2, 'No such file or directory')", "actual_error": "RuntimeError('Duplicate or unordered raw trade IDs')", "evidence_file": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/isolation/35/runs/2025/ETH/failure.json", "official_archive_issue": "2025-08-29 ETH raw trade IDs conflict; official daily and monthly day are byte-identical", "recovery_evidence": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/recovery_20250829_ETH/result.json"}
{"period": "2025", "group": "F", "status": "UNVERIFIED", "error": "FileNotFoundError(2, 'No such file or directory')", "actual_error": "RuntimeError('Duplicate or unordered raw trade IDs')", "evidence_file": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/isolation/35/runs/2025/ETH/failure.json", "official_archive_issue": "2025-08-29 ETH raw trade IDs conflict; official daily and monthly day are byte-identical", "recovery_evidence": "/workspace/btc-eth-backtest/outputs/eth_density_experiment/recovery_20250829_ETH/result.json"}

## 数据阻断与继续执行

2025-08-29 ETH官方daily档案有3个重复成交ID，对应不同时间/价格；同市场官方monthly目标日与daily解压CSV逐字节相同，不能靠换档案或去重恢复。没有更可靠原始逐笔之前，仍依赖该档案的组保持UNVERIFIED。0.25独立组若已恢复成功则单列，不用其结果填充0.30/0.35。
每组隔离恢复入口：python outputs/eth_density_experiment/isolate_2025.py .25 / .30 / .35（各为独立命令）；后两组在现有冲突档案下仍会停止。全量已完成任务用python outputs/eth_density_experiment/supervisor.py跳过，网络失败从月末断点继续；代码指纹变化拒绝复用断点。
发现新可信官方原始档案后，需先核实SHA、ID/时间与完整覆盖，再建立有记录的数据恢复流程，不得直接将某一冲突记录删掉以跑通。
