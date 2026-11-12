import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const work = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(work);
const analysis = JSON.parse(await fs.readFile(path.join(work, 'rolling_trade_diagnosis.json'), 'utf8'));
const source = JSON.parse(await fs.readFile(analysis.sources.roll, 'utf8'));
const outdir = path.join(root, 'outputs', '01a1c3a3-f884-7973-8e96-34dc26308c01');
const workbook = Workbook.create();
const summary = workbook.worksheets.add('年度复盘');
const detail = workbook.worksheets.add('逐笔诊断');
const methods = workbook.worksheets.add('判定口径');
const font = 'Microsoft YaHei';
const navy = '#19324D';
const ink = '#233747';
const gray = '#566674';
const line = '#D5DEE6';
const usd = '#,##0.00;[Red](#,##0.00);0.00';
const pct = '0.00%;[Red](0.00%);0.00%';
const date = 'yyyy-mm-dd hh:mm';
const toExcelDate = value => value ? (Date.parse(value) + 8 * 3600000) / 86400000 + 25569 : null;
const yesNo = value => value == null ? null : value ? '是' : '否';
const rowEnd = 5 + analysis.trades.length;
const sourceCol = letter => `'逐笔诊断'!$${letter}$6:$${letter}$${rowEnd}`;

function setup(sheet, range, widthMap, color) {
  sheet.showGridLines = false;
  if (color) sheet.tabColor = color;
  const area = sheet.getRange(range);
  area.format.font = { name: font, size: 10, color: ink };
  area.format.verticalAlignment = 'center';
  area.format.rowHeight = 21;
  for (const [column, width] of Object.entries(widthMap)) {
    sheet.getRange(`${column}1:${column}${range.match(/\d+$/)[0]}`).format.columnWidth = width;
  }
}

function title(sheet, text, subtitle, lastColumn) {
  sheet.getRange('A2').values = [[text]];
  sheet.getRange('A2').format.font = { name: font, size: 16, color: navy, bold: true };
  sheet.getRange(`A2:${lastColumn}2`).format.rowHeight = 30;
  sheet.getRange(`A2:${lastColumn}2`).format.borders = { bottom: { style: 'thin', color: line } };
  sheet.getRange('A3').values = [[subtitle]];
  sheet.getRange('A3').format.font = { name: font, size: 10, color: gray, italic: true };
}

function heading(sheet, row, text, col = 'K') {
  sheet.getRange(`A${row}`).values = [[text]];
  sheet.getRange(`A${row}:${col}${row}`).format = {
    fill: '#E7EFF5', font: { name: font, size: 10, bold: true, color: navy },
    rowHeight: 23, verticalAlignment: 'center',
  };
}

function header(sheet, range, values) {
  const r = sheet.getRange(range);
  r.values = [values];
  r.format = {
    fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 31, horizontalAlignment: 'center', verticalAlignment: 'center', wrapText: true,
    borders: { insideVertical: { style: 'thin', color: '#FFFFFF' } },
  };
}

function totalRow(sheet, range) {
  const r = sheet.getRange(range);
  r.format.font.bold = true;
  r.format.fill = '#E7EFF5';
  r.format.borders = { top: { style: 'thin', color: '#A5B8C7' } };
}

const head = [
  '交易编号', '年份', '开仓时间 UTC+8', '方向', '实际净盈亏', '进场诊断', '实际离场', '整笔离场诊断', '部分减仓诊断',
  '平仓时间 UTC+8', '持仓小时', '持仓内达0.8%', '延后入场达标', '离场后达0.8%', '原入场4小时', '延后1小时入场',
  '延后1小时出场差额', '延后4小时出场差额', '不减仓净额差', '持仓最大顺向', '持仓最大逆向', '首小时最大顺向', '入场前4小时顺向',
  '开仓价', '平仓价', '初始数量 BTC', '减仓数量 BTC', '2%硬止损价', '0.8%目标价', '首次达标时间 UTC+8',
  '扣费前盈亏', '手续费', '延后1小时净盈亏', '延后4小时净盈亏', '平仓后权益', '交易所', '季度',
];
const col = 'AK';
setup(detail, `A1:${col}${rowEnd}`, {
  A: 15, B: 9, C: 23, D: 8, E: 15, F: 24, G: 23, H: 30, I: 22,
  J: 23, K: 12, L: 15, M: 16, N: 16, O: 19, P: 19, Q: 19, R: 19,
  S: 16, T: 15, U: 15, V: 15, W: 16, X: 14, Y: 14, Z: 15, AA: 15,
  AB: 16, AC: 16, AD: 23, AE: 16, AF: 14, AG: 18, AH: 18, AI: 15, AJ: 12, AK: 10,
}, '#7998AE');
title(detail, '逐笔交易诊断', '金额单位 USDT。诊断分组和实际出场原因可以分别筛选。延后出场差额为假设净额减实际净额。', col);
header(detail, `A5:${col}5`, head);
const values = analysis.trades.map(t => [
  t.id, t.year, toExcelDate(t.opened), t.side, t.net, t.entry_class, t.reason, t.exit_class, t.partial_class,
  toExcelDate(t.closed), t.hold_hours, yesNo(t.reached), yesNo(t.timing), yesNo(t.post_target), t.original4, t.delayed4,
  t.delta1, t.delta4, t.no_partial_delta, t.mfe, t.mae, t.first_hour_mfe, t.pre4,
  t.entry, t.exit, t.qty, t.reduced_qty, t.hard_stop_price, t.target_price, toExcelDate(t.target_time),
  t.gross, t.fees, t.alt1, t.alt4, t.after_close_equity, t.exchange, t.quarter,
]);
detail.getRange(`A6:${col}${rowEnd}`).values = values;
for (const c of ['C', 'J', 'AD']) detail.getRange(`${c}6:${c}${rowEnd}`).setNumberFormat(date);
for (const c of ['E', 'Q', 'R', 'S', 'X', 'Y', 'AB', 'AC', 'AE', 'AF', 'AG', 'AH', 'AI']) {
  detail.getRange(`${c}6:${c}${rowEnd}`).setNumberFormat(usd);
}
for (const c of ['T', 'U', 'V', 'W']) detail.getRange(`${c}6:${c}${rowEnd}`).setNumberFormat(pct);
for (const c of ['Z', 'AA']) detail.getRange(`${c}6:${c}${rowEnd}`).setNumberFormat('0.000');
detail.getRange(`K6:K${rowEnd}`).setNumberFormat('0.00');
const table = detail.tables.add(`A5:${col}${rowEnd}`, true, 'TradeDiagnostics');
table.style = 'TableStyleMedium2';
table.showFilterButton = true;
detail.freezePanes.freezeRows(5);
detail.getRange(`G6:G${rowEnd}`).conditionalFormats.add('containsText', {
  text: '2%硬止损', format: { fill: '#FDE8E7', font: { color: '#9A3029', bold: true } },
});

setup(summary, 'A1:K62', {
  A: 12, B: 16, C: 16, D: 16, E: 16, F: 17, G: 17, H: 17, I: 17, J: 15, K: 16,
}, navy);
title(summary, 'BTCUSDT 15 分钟逐笔复盘', '2019–2025 年滚动账户。金额单位 USDT。2019、2020 年为部分区间。', 'K');
header(summary, 'A5:K5', ['年份', '期初权益', '期末权益', '收益率', '净盈亏', '扣费前盈亏', '手续费',
  '多单净盈亏', '空单净盈亏', '开仓笔数', '当年最大回撤']);
const allYears = Object.keys(analysis.years).map(Number);
const sumYear = (c, row) => `SUMIFS(${sourceCol(c)},${sourceCol('B')},$A${row})`;
const countYear = (c, row, label) => `COUNTIFS(${sourceCol('B')},$A${row},${sourceCol(c)},"${label}")`;
for (const [index, y] of allYears.entries()) {
  const row = 6 + index;
  summary.getRange(`A${row}`).values = [[y]];
  if (index === 0) summary.getRange(`B${row}`).values = [[analysis.initial]];
  else summary.getRange(`B${row}`).formulas = [[`=C${row-1}`]];
  summary.getRange(`C${row}:J${row}`).formulas = [[
    `=B${row}+E${row}`, `=C${row}/B${row}-1`, `=${sumYear('E', row)}`,
    `=${sumYear('AE', row)}`, `=${sumYear('AF', row)}`,
    `=SUMIFS(${sourceCol('E')},${sourceCol('B')},$A${row},${sourceCol('D')},"多")`,
    `=SUMIFS(${sourceCol('E')},${sourceCol('B')},$A${row},${sourceCol('D')},"空")`,
    `=COUNTIFS(${sourceCol('B')},$A${row})`,
  ]];
  summary.getRange(`K${row}`).values = [[analysis.years[y].max_drawdown_pct / 100]];
}
summary.getRange('A13').values = [['全程']];
summary.getRange('B13:J13').formulas = [[
  '=B6', '=C12', '=C13/B13-1', '=SUM(E6:E12)', '=SUM(F6:F12)', '=SUM(G6:G12)',
  '=SUM(H6:H12)', '=SUM(I6:I12)', '=SUM(J6:J12)',
]];
summary.getRange('K13').values = [[source.full_path_max_drawdown_pct / 100]];
for (const r of ['B6:C13', 'E6:I13']) summary.getRange(r).setNumberFormat(usd);
for (const r of ['D6:D13', 'K6:K13']) summary.getRange(r).setNumberFormat(pct);
totalRow(summary, 'A13:K13');

heading(summary, 15, '进场诊断和实际离场次数');
header(summary, 'A16:K16', ['年份', '净盈利笔数', '持仓内达标', '延后入场达标', '出场后走出方向', '短线未达目标',
  '2%止损先到', '窗口不足', '实际2%硬止损', '低ER一小时退出', '净亏笔数']);
const entryLabels = ['持仓内达标', '延后入场达标', '出场后方向走出', '短线内未达目标', '2%硬止损先到', '后续窗口不足'];
for (const [index, y] of allYears.entries()) {
  const r = 17 + index;
  summary.getRange(`A${r}`).values = [[y]];
  summary.getRange(`B${r}:K${r}`).formulas = [[
    `=COUNTIFS(${sourceCol('B')},$A${r},${sourceCol('E')},">0")`,
    ...entryLabels.map(x => `=${countYear('F', r, x)}`),
    `=${countYear('G', r, '2%硬止损')}+${countYear('G', r, '2%硬止损（跳空）')}`,
    `=${countYear('G', r, '低ER一小时退出')}`,
    `=COUNTIFS(${sourceCol('B')},$A${r},${sourceCol('E')},"<0")`,
  ]];
}
summary.getRange('A24').values = [['合计']];
summary.getRange('B24:K24').formulas = [[...'BCDEFGHIJK'].map(c => `=SUM(${c}17:${c}23)`)];
totalRow(summary, 'A24:K24');

heading(summary, 26, '离场与部分减仓复盘');
header(summary, 'A27:I27', ['年份', '盈利出场偏早', '亏损软退偏早', '延后均改善', '原退出更优',
  '两档不一致或差距小', '减仓少赚', '减仓保护收益', '无减仓']);
for (const [index, y] of allYears.entries()) {
  const r = 28 + index;
  summary.getRange(`A${r}`).values = [[y]];
  summary.getRange(`B${r}:I${r}`).formulas = [[
    ...['盈利离场偏早候选', '亏损软退偏早候选', '两档延后均改善', '原退出优于两档延后',
      '两档结论不一致或差距小'].map(x => `=${countYear('H', r, x)}`),
    ...['减仓少赚', '减仓保护收益', '未减仓'].map(x => `=${countYear('I', r, x)}`),
  ]];
}
summary.getRange('A35').values = [['合计']];
summary.getRange('B35:I35').formulas = [[...'BCDEFGHI'].map(c => `=SUM(${c}28:${c}34)`)];
totalRow(summary, 'A35:I35');

heading(summary, 37, '负收益年份按季度拆解');
header(summary, 'A38:H38', ['年份', '季度', 'BTC 涨跌', '开仓笔数', '多单净盈亏', '空单净盈亏', '净盈亏', '手续费']);
for (const [index, q] of analysis.quarters.entries()) {
  const r = 39 + index;
  summary.getRange(`A${r}:C${r}`).values = [[q.year, q.quarter, q.btc_return]];
  const criteria = `${sourceCol('B')},$A${r},${sourceCol('AK')},$B${r}`;
  summary.getRange(`D${r}:H${r}`).formulas = [[
    `=COUNTIFS(${criteria})`,
    `=SUMIFS(${sourceCol('E')},${criteria},${sourceCol('D')},"多")`,
    `=SUMIFS(${sourceCol('E')},${criteria},${sourceCol('D')},"空")`,
    `=SUMIFS(${sourceCol('E')},${criteria})`,
    `=SUMIFS(${sourceCol('AF')},${criteria})`,
  ]];
}
const quarterEnd = 38 + analysis.quarters.length;
summary.getRange(`C39:C${quarterEnd}`).setNumberFormat(pct);
summary.getRange(`E39:H${quarterEnd}`).setNumberFormat(usd);

heading(summary, 50, '三个亏损年的主要差异');
const comments = [
  ['2019', '2019-001 多单在 0.8% 之前触发 2% 硬止损，净亏 52.68，超过该区间净亏 51.07。'],
  ['2020', '四季度 BTC 涨 166.75%。空单净亏 61.13，其中 2020-017 先减仓再触发硬止损，净亏 35.97。'],
  ['2025', '扣费前赚 69.46，手续费 398.55，净亏 329.09。多单净亏 242.48，二季度组合净亏 301.10。'],
  ['2025 早退', '一小时退出共 6 笔。相同仓位延后 1 小时合计改善 124.99，延后 4 小时合计恶化 112.61。'],
];
for (const [i, line] of comments.entries()) summary.getRange(`A${51+i}:B${51+i}`).values = [line];

setup(methods, 'A1:B20', { A: 26, B: 108 }, '#A6B7C3');
title(methods, '诊断口径与数据', '事后比较按固定时间窗口和相同费用口径计算。', 'B');
header(methods, 'A5:B5', ['字段', '口径']);
const notes = [
  ['样本与本金', '2019 年 Binance 永续、2020–2025 年 Bybit 永续。按上次已核验的区间连续滚动。初始 500 USDT，换所空档持现金。'],
  ['实际成交成本', '每笔成交按 0.05% 手续费、单边 0.02% 滑点，资金费率为零。扣费前盈亏已经包含滑点。'],
  ['持仓内达标', '持仓期间按原撮合顺序触及顺向 0.8% 并执行减仓。价格方向达标后，整笔成交仍可能亏损。'],
  ['进场时机对照', '从同一笔原开仓起观察 4 小时，比较原开盘进场与延后 1 小时开盘进场。原时点未达 0.8%、延后时点先达 0.8% 才标记。两种进场均保留 2% 硬止损。'],
  ['方向后来走出', '实际离场前未达 0.8%。用原成交价继续模拟，若离场后 4 小时内先达 0.8% 而未先触发 2% 止损，记录为方向后来走出。'],
  ['趋势未达目标', '实盘模拟和本表的有限观察窗口都没有观察到满足分类条件的 0.8% 顺向延续。指短线窗口的表现。'],
  ['整笔离场偏早', '同一笔软退出分别延后 1 小时、4 小时，保留 2% 硬止损和原减仓。两档改善都至少达到原名义仓位 0.10% 才标记。亏损软退偏早还要求两档都转为非负。'],
  ['部分减仓对照', '用同一进场和最终退出价，比较保留全部仓位与实际减仓。差额为不减仓净额减实际净额。正数表示这笔提前减仓少赚，负数表示减仓保护收益。'],
  ['2% 硬止损', '沿用原 2% 价格止损，按回测成交顺序重放。硬止损交易单独列出。当前 212 笔中没有交易所强平模拟。'],
  ['同根 K 线顺序', '开盘已越过止损先处理。否则先检查开盘能否减仓，再按原引擎优先处理盘中止损。盘中同时触及止损和目标时采用原模型的保守顺序。'],
  ['时间与窗口', '交易时间均用 UTC+8。后续行情不足时留空。固定时点对照以单笔原仓位复核，数值不合成为一条新的账户回测。'],
  ['逐笔来源', 'rolling_account_2019_trades.csv、rolling_account_2020_2025_trades.csv。行情为已核验的 Binance / Bybit BTCUSDT 15 分钟永续 K 线。年度权益来自上轮连续账户回测。'],
];
methods.getRange(`A6:B${5 + notes.length}`).values = notes;
methods.getRange(`B6:B${5 + notes.length}`).format.wrapText = true;
methods.getRange(`A6:A${5 + notes.length}`).format.font.bold = true;
methods.getRange(`A6:B${5 + notes.length}`).format.rowHeight = 41;
for (let r = 7; r <= 5 + notes.length; r += 2) methods.getRange(`A${r}:B${r}`).format.fill = '#F4F7FA';

workbook.recalculate();
const results = summary.getRange('C6:K13').values;
for (const [index, year] of allYears.entries()) {
  assert.ok(Math.abs(results[index][0] - analysis.years[year].ending_equity_usdt) < 1e-8, `year ${year}`);
  assert.equal(results[index][7], analysis.years[year].count);
}
assert.equal(results[7][7], 212);
assert.ok(Math.abs(results[7][0] - analysis.final) < 1e-8);
assert.deepEqual(summary.getRange('B24:K24').values[0], [79, 95, 5, 21, 86, 4, 1, 9, 16, 133]);
assert.deepEqual(summary.getRange('B35:I35').values[0], [23, 9, 21, 46, 103, 39, 56, 117]);
assert.equal(table.name, 'TradeDiagnostics');
assert.equal(table.showFilterButton, true);
console.log((await workbook.inspect({
  kind: 'table', range: '年度复盘!A5:K13', include: 'values,formulas', tableMaxRows: 9, tableMaxCols: 11, maxChars: 2500,
})).ndjson);
console.log((await workbook.inspect({
  kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: { useRegex: true, maxResults: 50 }, summary: 'formula errors',
})).ndjson);

for (const [sheet, range, label] of [
  [summary, 'A1:K54', 'summary'], [detail, 'A1:I12', 'detail'], [methods, 'A1:B17', 'methods'],
]) {
  const preview = await workbook.render({ sheetName: sheet.name, range, scale: 1, format: 'png' });
  await fs.writeFile(path.join(work, `trade_diagnosis_${label}.png`), new Uint8Array(await preview.arrayBuffer()));
}
await fs.mkdir(outdir, { recursive: true });
const file = path.join(outdir, 'BTCUSDT_2019-2025_逐笔交易复盘.xlsx');
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(file);
console.log(file);
