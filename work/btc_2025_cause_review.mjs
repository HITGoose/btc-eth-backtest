import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const [source, output, since = '2021-11-09', until = '2026-11-09', venue = 'binance', experiment, startingCash = '100'] = process.argv.slice(2);
if (!source || !output) throw Error('Usage: node btc_perp_backtest.mjs DATA_DIR_OR_CSV OUTPUT_PREFIX [START_UTC] [END_UTC] [binance|bybit]');

const bar = 900_000;
const start = Date.parse(since);
const end = Date.parse(until);
const fee = venue === 'bybit' ? 0.00055 : 0.0005;
const slippage = 0.0002;
const startingEquity = Number(startingCash);
if (!Number.isFinite(startingEquity) || startingEquity <= 0) throw Error('Invalid starting equity');
const riskFraction = 0.01;
const minQty = 0.001;
const iso = time => new Date(time).toISOString();
const sum = values => values.reduce((total, value) => total + value, 0);

const market = new Map();
const files = statSync(source).isDirectory()
  ? readdirSync(source).filter(name => /^BTCUSDT-15m-.*\.(?:zip|csv)$/i.test(name)).map(name => join(source, name))
  : [source];
for (const file of files) {
  const csv = file.endsWith('.zip') ? execFileSync('tar', ['-xOf', file], { encoding: 'utf8' }) : readFileSync(file, 'utf8');
  for (const row of csv.trim().split(/\r?\n/)) {
    const [t, o, h, l, c] = row.split(',', 5).map(Number);
    if (!Number.isFinite(t)) continue;
    if (t % bar || ![o, h, l, c].every(x => x > 0) || l > Math.min(o, c) || h < Math.max(o, c)) throw Error(`Invalid OHLC in ${file} at ${t}`);
    const previous = market.get(t);
    if (previous && [o, h, l, c].some((x, i) => x !== [previous.o, previous.h, previous.l, previous.c][i])) throw Error(`Conflicting price data at ${iso(t)}`);
    market.set(t, { t, o, h, l, c });
  }
}
const input = [...market.values()].filter(b => b.t >= start - 15 * 96 * bar && b.t < end).sort((a, b) => a.t - b.t);
const segments = [];
for (const candle of input) {
  const segment = segments.at(-1);
  if (!segment || candle.t !== segment.at(-1).t + bar) segments.push([candle]);
  else segment.push(candle);
}
if (!input.length) throw Error('No candles found for the requested window');

function aggregate(candles, count) {
  const groups = [];
  for (let i = 0; i + count <= candles.length; i++) {
    if (candles[i].t % (count * bar)) continue;
    const group = candles.slice(i, i + count);
    groups.push({ t: group[0].t, o: group[0].o, h: Math.max(...group.map(b => b.h)), l: Math.min(...group.map(b => b.l)), c: group.at(-1).c });
    i += count - 1;
  }
  return groups;
}

function indicators(candles) {
  let fast = candles[0].c, slow = fast, signal = 0;
  const closes = [0], ranges = [0], tops = [], bottoms = [];
  return candles.map((b, i) => {
    closes.push(closes[i] + b.c);
    const prev = candles[i - 1]?.c ?? b.c;
    ranges.push(ranges[i] + Math.max(b.h - b.l, Math.abs(b.h - prev), Math.abs(b.l - prev)));
    fast += (b.c - fast) * 2 / 13;
    slow += (b.c - slow) * 2 / 27;
    signal += (fast - slow - signal) * 2 / 10;
    if (i >= 4) {
      const mid = candles[i - 2];
      const neighbors = [candles[i - 4], candles[i - 3], candles[i - 1], b];
      if (neighbors.every(x => x.h < mid.h)) tops.push(mid.h);
      if (neighbors.every(x => x.l > mid.l)) bottoms.push(mid.l);
    }
    const up = tops.at(-1) > tops.at(-2) && bottoms.at(-1) > bottoms.at(-2);
    const down = tops.at(-1) < tops.at(-2) && bottoms.at(-1) < bottoms.at(-2);
    const structure = up && b.c >= bottoms.at(-1) ? 1 : down && b.c <= tops.at(-1) ? -1 : 0;
    const averages = [7, 10, 30, 60].map(n => i + 1 >= n ? (closes[i + 1] - closes[i + 1 - n]) / n : NaN);
    const atr = i >= 13 ? (ranges[i + 1] - ranges[i - 13]) / 14 : NaN;
    const ma5 = i >= 4 ? (closes[i + 1] - closes[i - 4]) / 5 : NaN;
    const ma20 = i >= 19 ? (closes[i + 1] - closes[i - 19]) / 20 : NaN;
    return { ...b, averages, ma5, ma20, atr, dif: fast - slow, dea: signal, histogram: fast - slow - signal, structure, top: tops.at(-1), bottom: bottoms.at(-1) };
  });
}

function oneHourTrend(row, previous) {
  if (!row || !previous) return 0;
  for (const side of [1, -1]) {
    const pivot = side === 1 ? row.bottom : row.top;
    if (row.structure !== -side && (row.c - pivot) * side > 0 &&
      (row.c - row.averages[2]) * side > 0 && (row.histogram - previous.histogram) * side > 0) return side;
  }
  return 0;
}

function trigger(row, previous) {
  const [a, b, c] = row.averages;
  const order = Math.sign(a - b);
  if (order && (b - c) * order > 0 && row.averages.slice(0, 3).every((value, i) => (value - previous.averages[i]) * order > 0)) return order;
  return 0;
}

function spread(row) { return Math.max(...row.averages) - Math.min(...row.averages); }

function bullishOrder(row) {
  const [fast, middle, slow] = row.averages;
  return fast > middle && middle > slow;
}

function histogramConfirms(candles, index, side, bars) {
  if (!bars) return true;
  const first = candles[index - bars].histogram;
  if (side === 1 ? first >= 0 : candles[index - 1].histogram >= 0) return false;
  for (let i = index - bars + 1; i <= index; i++) {
    if ((candles[i].histogram - candles[i - 1].histogram) * side <= 0) return false;
  }
  return true;
}

function downwardExpansion(row, previous) {
  return spread(row) > spread(previous) && row.averages.every((value, i) =>
    value < previous.averages[i] && (i === 0 || value > row.averages[i - 1]));
}

function reversalExit(candles, index, side, shortExitBars, crossoverOnly) {
  const [first, prev, row] = candles.slice(index - 2, index + 1);
  if ((prev.ma5 - prev.averages[2]) * side >= 0 && (row.ma5 - row.averages[2]) * side < 0) return 'ma5_ma30_cross';
  if (crossoverOnly) return undefined;
  if (side === -1 && shortExitBars === 1) {
    return prev.histogram < 0 && row.histogram > prev.histogram ? 'macd_fades' : undefined;
  }
  if (first.histogram * side > 0 && (prev.histogram - first.histogram) * side < 0 && (row.histogram - prev.histogram) * side < 0) return 'macd_fades';
  return undefined;
}

function backtest(config) {
  const { leverage } = config;
  const quantityStep = config.quantityStep ?? minQty;
  const independent = config.mode === '15m';
  const signalExit = config.stopPercent !== undefined;
  const maxHold = config.maxHours ?? 48;
  const yearOffset = (config.calendarOffsetHours ?? 0) * 3600000;
  let cash = startingEquity, peak = startingEquity, drawdown = 0, rejected = 0, rejectedAdds = 0, maximumExposure = 0;
  const reportStart = Date.parse('2022-01-01T00:00:00+08:00');
  const reportEnd = Date.parse('2025-01-01T00:00:00+08:00');
  let windowPeak, windowDrawdown = 0, inReportWindow = false;
  const trades = [], balances = [], coverage = [];
  const blockedByStructure = { LONG: { broken: 0, room: 0 }, SHORT: { broken: 0, room: 0 } };
  const mark = price => cash + (position ? position.side * position.qty * (price - position.entry) : 0);
  const track = value => {
    peak = Math.max(peak, value);
    drawdown = Math.max(drawdown, 1 - value / peak);
    if (inReportWindow) {
      windowPeak = Math.max(windowPeak ?? value, value);
      windowDrawdown = Math.max(windowDrawdown, 1 - value / windowPeak);
    }
  };
  let position;
  const fill = (price, side) => price * (1 + side * config.slip);
  function takeProfitPlan(entry, stop, quantity) {
    if (!config.takeProfitSteps) return [];
    if (config.takeProfitFraction) {
      const desired = quantity * config.takeProfitFraction;
      const amount = config.fractionalTakeProfit ? desired : Math.floor((desired + 1e-12) / quantityStep) * quantityStep;
      const price = entry + (entry - stop) * config.takeProfitSteps[0];
      return amount > 0 && amount * price >= (config.minExitNotional ?? 0) ? [{ price, quantity: amount, level: 1 }] : [];
    }
    const n = config.takeProfitSteps.length;
    const units = Math.round(quantity / quantityStep);
    let previous = 0;
    return config.takeProfitSteps.flatMap((multiple, i) => {
      const cumulative = config.fractionalTakeProfit ? quantity * (i + 1) / n : Math.round(units * (i + 1) / n) * quantityStep;
      const amount = cumulative - previous;
      previous = cumulative;
      return amount > 1e-12 ? [{ price: entry + (entry - stop) * multiple, quantity: amount, level: i + 1 }] : [];
    });
  }
  function close(price, time, reason) {
    const exit = fill(price, -position.side);
    const finalFee = config.fee * exit * position.qty;
    const remainingGross = position.side * position.qty * (exit - position.entry);
    const gross = remainingGross + (position.partialGross ?? 0);
    cash += remainingGross - finalFee;
    const { side, setup, resonance, signal, opened, entry, qty, added, fees, funding, initialRisk } = position;
    const earlier = position.earlierExit;
    const earlyExitDelta = earlier && earlier.time < time ? side * qty * (earlier.price - exit) - config.fee * qty * (earlier.price - exit) : undefined;
    trades.push({ side: side === 1 ? 'LONG' : 'SHORT', setup, resonance, signal: iso(signal), opened: iso(opened), closed: iso(time), first_entry: position.firstEntry, entry, exit, first_qty: position.firstQty, qty, add_fills: added, initial_stop: position.firstStop, final_stop: position.stop, target: position.target, gross, fees: fees + finalFee, funding, net: gross - fees - finalFee - funding, risk_budget: initialRisk, reason, equity: cash, ...(config.diagnose ? { trend4: position.trend4, favorable_before_exit: position.favorable, early_exit_delta: earlyExitDelta, risk_fraction_of_r: position.riskOfR } : {}), ...(config.takeProfitSteps ? { tp_orders: position.tpOrders, tp_fills: position.tpFills.join('|'), partial_gross: position.partialGross } : {}) });
    position = undefined;
    track(cash);
  }
  function fillTakeProfits(price, time) {
    while (position && position.tpPlan.length && (price - position.tpPlan[0].price) * position.side >= 0) {
      const level = position.tpPlan.shift();
      position.tpFills.push(level.level);
      if (config.diagnosticFullTarget) {
        close(level.price, time, 'full_target_0p8');
        break;
      }
      if (position.tpPlan.length === 0 && !config.takeProfitFraction) {
        close(level.price, time, 'tp_all');
        break;
      }
      const exit = fill(level.price, -position.side);
      const realized = position.side * (exit - position.entry) * level.quantity;
      const fees = config.fee * exit * level.quantity;
      position.partialGross += realized;
      position.fees += fees;
      position.qty -= level.quantity;
      cash += realized - fees;
    }
  }
  function size(price, reference, time, stop, side, riskBudget, equity, existing = 0, exposureFraction = 1) {
    const exit = fill(stop, -side);
    const lossPerUnit = (price - exit) * side + config.fee * (price + exit);
    if (lossPerUnit <= 0) return 0;
    const marginCap = (equity * leverage * exposureFraction - existing * price) / (price * (1 + 2 * leverage * config.fee));
    let quantity = config.useLeverageCap ? marginCap : Math.min(riskBudget / lossPerUnit, marginCap);
    if (config.minOrder) {
      quantity = Math.floor((quantity + 1e-12) / quantityStep) * quantityStep;
      const minNotional = config.minOrderNotional ?? (venue === 'binance' && time >= Date.parse('2026-04-14T06:30Z') ? 50 : 100);
      if (quantity * reference < minNotional) return 0;
    }
    return Math.max(0, quantity);
  }

  for (const raw of segments.filter(s => s.length > 480)) {
    const small = indicators(raw), mid = indicators(aggregate(raw, 4)), big = indicators(aggregate(raw, 16));
    let hi = -1, bi = -1, zone, pending, retest, shortExpansion, lastProbe = 0;
    let lastZeroUp = -1, lastBullishOrder = -1;
    let recentPeak, peakSetup, macdDeath;
    const first = Math.max(480, raw.findIndex(b => b.t >= start));
    if (raw[first]?.t < start || !raw[first]) continue;
    coverage.push([iso(raw[first].t), iso(raw.at(-1).t + bar)]);
    for (let i = first; i < small.length; i++) {
      const b = small[i], prev = small[i - 1];
      if (config.shortPeakHours) {
        const maCrossDown = prev.ma5 >= prev.ma20 && b.ma5 < b.ma20;
        if (maCrossDown) peakSetup = recentPeak && i - recentPeak.index <= 4 ? { ...recentPeak, crossIndex: i } : undefined;
        const lookback = config.shortPeakHours * 4;
        if (i >= lookback && b.h > Math.max(...small.slice(i - lookback, i).map(x => x.h))) recentPeak = { index: i, price: b.h };
        if (prev.histogram >= 0 && b.histogram < 0) {
          const zone = b.dif > 0 && b.dea > 0 ? 'above' : b.dif < 0 && b.dea < 0 ? 'below' : 'mixed';
          macdDeath = { index: i, zone };
        }
        if (peakSetup && (i - peakSetup.crossIndex > 4 || b.h > peakSetup.price || b.ma5 >= b.ma20)) peakSetup = undefined;
      }
      if (config.zeroEntry && config.zeroEntry !== 'none') {
        if (prev[config.zeroEntry] <= 0 && b[config.zeroEntry] > 0) {
          const nearZero = config.macdNearZeroAtr === undefined || Math.max(Math.abs(b.dif), Math.abs(b.dea)) <= config.macdNearZeroAtr * b.atr;
          const correctSide = config.macdBelowZero ? b.dif < 0 && b.dea < 0 : !config.macdAboveZero || (b.dif > 0 && b.dea > 0);
          const aboveDifFloor = config.macdDifFloor === undefined || b.dif >= config.macdDifFloor;
          lastZeroUp = nearZero && correctSide && aboveDifFloor ? i : -1;
        }
      }
      if (config.zeroEntry) {
        if (!bullishOrder(prev) && bullishOrder(b)) lastBullishOrder = i;
      }
      inReportWindow = config.reportWindow && b.t >= reportStart && b.t < reportEnd;
      if (inReportWindow && windowPeak === undefined) windowPeak = mark(b.o);
      if (position && config.funding && b.t % (32 * bar) === 0) {
        const charge = config.funding * b.o * position.qty;
        cash -= charge;
        position.funding += charge;
      }
      if (position?.earlyExitPending && !position.earlierExit) position.earlierExit = { time: b.t, price: fill(b.o, 1) };
      if (pending?.type === 'exit' && position) {
        const crossedStop = signalExit && (b.o - position.stop) * position.side <= 0;
        close(b.o, b.t, crossedStop ? 'stop_gap' : pending.reason);
      }
      if (config.structureEntry && pending?.type === 'entry' && !position) {
        const hour = mid[hi];
        if (hour && hour.t + 4 * bar > pending.signal) throw Error('Unclosed 1h structure at signal');
        const long = pending.side === 1;
        const nearSide = long ? hour?.bottom : hour?.top;
        const farSide = long ? hour?.top : hour?.bottom;
        const close = prev.c;
        const broken = Number.isFinite(nearSide) && (nearSide - close) * pending.side >= 0;
        const room = (farSide - close) * pending.side / close;
        const tooClose = config.structureEntry === 'require_room' && room >= 0 && room < 0.008;
        if (broken || tooClose) {
          blockedByStructure[long ? 'LONG' : 'SHORT'][broken ? 'broken' : 'room']++;
          pending = undefined;
        }
      }
      if (pending?.type === 'entry' && !position && (signalExit || (b.o - pending.stop) * pending.side > 0)) {
        const entry = fill(b.o, pending.side);
        const initialRisk = cash * riskFraction;
        const stop = signalExit ? entry * (1 - pending.side * config.stopPercent) : pending.stop;
        const baseFraction = signalExit && pending.fraction === 0.5 ? config.squeezeRisk : pending.fraction;
        const boost = pending.resonance === 'triple' && (!config.squeezeBoostOnly || pending.fraction === 0.5);
        const fraction = boost ? baseFraction * (config.resonanceRiskMultiplier ?? 1) : baseFraction;
        const erWindow = config.rangeReview ? small.slice(i - 21, i) : [];
        const travel = erWindow.slice(1).reduce((total, candle, j) => total + Math.abs(candle.c - erWindow[j].c), 0);
        const inRange = erWindow.length === 21 && (travel === 0 || Math.abs(erWindow.at(-1).c - erWindow[0].c) / travel < 0.25);
        const skip = inRange && config.rangeSkipShort && pending.side === -1;
        const exposureFraction = inRange && config.rangeHalf ? 0.5 : 1;
        const qty = skip ? 0 : size(entry, b.o, b.t, stop, pending.side, initialRisk * fraction, cash, 0, exposureFraction);
        if (qty > 0) {
          const fees = entry * qty * config.fee;
          maximumExposure = Math.max(maximumExposure, entry * qty / cash);
          cash -= fees;
          const signalHour = mid[hi];
          if (config.timeoutAtrMultiple && inRange && pending.side === -1
              && (!(signalHour?.atr > 0) || signalHour.t + 4 * bar > pending.signal)) {
            throw Error(`Missing closed 1h ATR at ${iso(pending.signal)}`);
          }
          const atrMovePct = config.timeoutAtrMultiple === undefined ? 0.004 : config.timeoutAtrMultiple * signalHour?.atr / entry;
          position = { timeoutMovePct: Math.min(atrMovePct, config.timeoutMoveCap ?? Infinity), ...pending, stop, entry, qty, firstEntry: entry, firstQty: qty, firstStop: stop, fees, funding: 0, initialRisk, riskOfR: fraction, opened: b.t, inRange, hourFavorable: 0, added: 0, target: signalExit ? '' : entry + 2 * (entry - stop), favorable: 0 };
          if (config.takeProfitSteps) {
            position.tpPlan = takeProfitPlan(entry, stop, qty);
            position.tpOrders = position.tpPlan.length;
            position.tpFills = [];
            position.partialGross = 0;
          }
        } else if (!skip) rejected++;
      }
      if (pending?.type === 'add' && position && (b.o - pending.stop) * position.side > 0 && (position.target - b.o) * position.side > 0) {
        const entry = fill(b.o, position.side);
        const stopExit = fill(pending.stop, -position.side);
        const openRisk = Math.max(0, position.qty * ((position.entry - stopExit) * position.side + config.fee * stopExit) + position.fees + position.funding);
        const equity = mark(b.o);
        const qty = size(entry, b.o, b.t, pending.stop, position.side, position.initialRisk - openRisk, equity, position.qty);
        position.stop = pending.stop;
        if (qty > 0) {
          const fees = config.fee * entry * qty;
          maximumExposure = Math.max(maximumExposure, (position.qty + qty) * entry / equity);
          cash -= fees;
          position.entry = (position.entry * position.qty + entry * qty) / (position.qty + qty);
          position.qty += qty;
          position.fees += fees;
          position.added++;
        } else rejectedAdds++;
      }
      pending = undefined;
      if (position) {
        const { side, stop, target } = position;
        const adverse = side === 1 ? b.l : b.h;
        const favorable = side === 1 ? b.h : b.l;
        if ((b.o - stop) * side <= 0) close(b.o, b.t, 'stop_gap');
        else if (config.takeProfitSteps) {
          fillTakeProfits(b.o, b.t);
          if (position && (adverse - stop) * side <= 0) close(stop, b.t + bar, 'stop');
          else if (position) fillTakeProfits(favorable, b.t + bar);
        }
        else if (!signalExit && (b.o - target) * side >= 0) close(target, b.t, 'target');
        else if ((adverse - stop) * side <= 0) close(stop, b.t + bar, 'stop');
        else if (!signalExit && (favorable - target) * side >= 0) close(target, b.t + bar, 'target');
        else if (config.diagnose) position.favorable = Math.max(position.favorable, side * (favorable - position.firstEntry) / position.firstEntry);
      }
      if (position?.inRange && config.rangeTimeout && b.t < position.opened + 4 * bar) {
        const price = position.side === 1 ? b.h : b.l;
        position.hourFavorable = Math.max(position.hourFavorable, position.side * (price - position.entry) / position.entry);
      }
      track(mark(b.c));
      const time = b.t + bar;
      if ((time + yearOffset) % (96 * bar) === 0) balances.push({ time: iso(time), equity: mark(b.c) });
      if (i === small.length - 1) {
        if (position) close(b.c, time, 'end_of_data');
        break;
      }

      while (mid[hi + 1]?.t + 4 * bar <= time) hi++;
      while (big[bi + 1]?.t + 16 * bar <= time) bi++;
      const trend1 = oneHourTrend(mid[hi], mid[hi - 1]);
      const trend4 = big[bi]?.structure ?? 0;
      const side = trigger(b, prev);
      const resonanceFor = direction => trend1 !== direction || trend4 === -direction ? '15m_only' : trend4 === direction ? 'triple' : 'double';
      const eligible = direction => !(config.shortOnly && direction === 1) && (independent || (trend1 === direction && (trend4 === direction || (trend4 === 0 && config.mode !== 'triple'))));
      const momentum = direction => histogramConfirms(small, i, direction, config.histBars);
      const shortTrendAllowed = !config.longOnly && (!config.shortWith4h || trend4 === -1);

      if (position && signalExit) {
        const crossover = reversalExit(small, i, position.side, config.shortExitBars, config.crossoverOnly);
        const rangeTimeout = position.inRange && config.rangeTimeout && (!config.timeoutShortOnly || position.side === -1)
          && time - position.opened === 4 * bar && position.hourFavorable < position.timeoutMovePct;
        const reason = crossover ?? (config.exitOnTrendFlip && b.structure === -position.side ? '15m_structure_flip' : rangeTimeout ? 'er_1h_timeout' : undefined);
        if (config.diagnose && position.side === -1 && prev.histogram < 0 && b.histogram > prev.histogram) position.earlyExitPending = true;
        const exit = fill(b.c, -position.side);
        const netAtClose = position.qty * ((exit - position.entry) * position.side - exit * config.fee) - position.fees - position.funding;
        if (reason && (!config.profitOnly || netAtClose > 0)) pending = { type: 'exit', reason };
        continue;
      }

      const timedOut = position && time - position.opened >= maxHold * 4 * bar;
      if (position && (timedOut || (!independent && (trend4 === -position.side || mid[hi]?.structure === -position.side)))) {
        pending = { type: 'exit', reason: timedOut ? `${maxHold}h` : 'structure_flip' };
        continue;
      }

      if (config.shortPeakHours) {
        const maSpreadDown = b.ma5 < prev.ma5 && b.ma5 - b.ma20 < prev.ma5 - prev.ma20;
        const wider = spread(b) > config.squeeze * b.atr && spread(b) > spread(prev);
        const macdConfirmed = macdDeath?.zone === config.shortPeakMacdSide && b.histogram < 0 && peakSetup &&
          macdDeath.index >= peakSetup.index && Math.abs(macdDeath.index - peakSetup.crossIndex) <= 4;
        const entryOnTime = !config.immediateShortCross || peakSetup?.crossIndex === i;
        if (entryOnTime && macdConfirmed && wider && maSpreadDown && (!config.strictShortExpansion || downwardExpansion(b, prev))) {
          pending = { type: 'entry', side: -1, fraction: 0.5, setup: 'peak_ma5_ma20_macd_death', resonance: resonanceFor(-1), signal: time, trend4 };
          peakSetup = undefined;
        }
        if (!config.zeroEntry) continue;
      }

      if (config.zeroEntry) {
        if (zone && (i - zone.index > 8 || b.c < zone.low)) zone = undefined;
        const zeroConfirmed = config.zeroEntry === 'none' || (zone && lastZeroUp > zone.firstIndex && b[config.zeroEntry] > 0);
        if (zone && side === 1 && lastBullishOrder > zone.firstIndex && zeroConfirmed && b.c > zone.high) {
          pending = pending?.side === -1 ? undefined : { type: 'entry', side: 1, stop: zone.low, fraction: 0.5, setup: 'squeeze_triangle_macd_zero', resonance: resonanceFor(1), signal: time };
          zone = undefined;
        } else if (spread(b) <= config.squeeze * b.atr) {
          const window = small.slice(i - 3, i + 1);
          const firstIndex = zone?.index === i - 1 ? zone.firstIndex : i;
          zone = { high: Math.max(...window.map(x => x.h)), low: Math.min(...window.map(x => x.l)), index: i, firstIndex };
        }
        continue;
      }

      if (retest && i - retest.index > 12) retest = undefined;
      if (retest && (b.c - retest.stop) * retest.side < 0) retest = undefined;
      if (retest && i > retest.index && (independent || (trend1 === retest.side && trend4 !== -retest.side)) && momentum(retest.side)) {
        const { side: direction, level, stop } = retest;
        const resonance = resonanceFor(direction);
        const edge = direction === 1 ? b.l : b.h;
        if ((edge - level) * direction <= 0.25 * b.atr && (b.c - level) * direction > 0 && (b.c - b.o) * direction > 0) {
          const tighter = direction === 1 ? Math.max(stop, edge - 0.15 * b.atr) : Math.min(stop, edge + 0.15 * b.atr);
          if (!position && eligible(direction)) pending = { type: 'entry', side: direction, stop: tighter, fraction: 0.5, setup: 'squeeze_retest', resonance, signal: time };
          if (!independent && position?.setup === 'squeeze_breakout' && position.side === direction && resonance === 'triple' && !position.added) pending = { type: 'add', stop: direction === 1 ? Math.max(position.stop, tighter) : Math.min(position.stop, tighter) };
          retest = undefined;
          if (pending) continue;
        }
      }

      const squeezed = spread(b) <= config.squeeze * b.atr;
      if (zone && i - zone.index > 8) zone = undefined;
      if (shortExpansion && (i - shortExpansion.index > 8 || b.c >= shortExpansion.level)) shortExpansion = undefined;
      if (shortExpansion && shortTrendAllowed && !squeezed && downwardExpansion(b, prev) && momentum(-1)) {
        pending = { type: 'entry', side: -1, fraction: 0.5, setup: 'squeeze_downward_expansion', resonance: resonanceFor(-1), signal: time, trend4 };
        shortExpansion = undefined;
        continue;
      }
      if (zone && side && i > zone.index) {
        const level = side === 1 ? zone.high : zone.low;
        if ((b.c - level) * side > 0 && (prev.c - level) * side <= 0) {
          if (signalExit && side === -1) {
            if (shortTrendAllowed && !squeezed && downwardExpansion(b, prev) && momentum(-1)) {
              pending = { type: 'entry', side: -1, fraction: 0.5, setup: 'squeeze_downward_expansion', resonance: resonanceFor(-1), signal: time, trend4 };
            } else if (!config.longOnly) shortExpansion = { level, index: zone.index };
            zone = undefined;
            continue;
          }
          const stop = side === 1 ? zone.low : zone.high;
          if (eligible(side)) {
            const resonance = resonanceFor(side);
            retest = { side, level, stop, index: i };
            if (!position && (independent || resonance === 'triple') && momentum(side)) pending = { type: 'entry', side, stop, fraction: 0.5, setup: 'squeeze_breakout', resonance, signal: time };
          }
          zone = undefined;
          continue;
        }
      }
      if (squeezed) {
        const window = small.slice(i - 3, i + 1);
        zone = { high: Math.max(...window.map(x => x.h)), low: Math.min(...window.map(x => x.l)), index: i };
      }

      if (position || retest || zone || !side || (signalExit && side === -1) || !eligible(side) || !momentum(side)) continue;
      if (!side || spread(b) <= config.squeeze * b.atr || !b.averages.every((ma, k) => (ma - prev.averages[k]) * side > 0)) continue;
      if (i - lastProbe < 12 || !b.averages.slice(1).every((ma, k) => (b.averages[k] - ma) * side > 0)) continue;
      const edge = side === 1 ? b.l : b.h;
      const level = b.averages.slice(2).find((ma, k) => (prev.c - prev.averages[k + 2]) * side > 0 && (edge - ma) * side <= 0 && (b.c - ma) * side > 0);
      if (level !== undefined && (b.c - b.o) * side > 0) {
        const stop = edge - side * b.atr * 0.15;
        pending = { type: 'entry', side, stop, fraction: 0.25, setup: 'spread_pullback', resonance: resonanceFor(side), signal: time };
        lastProbe = i;
      }
    }
  }

  const statistics = sample => {
    const winners = sample.filter(t => t.net > 0), losers = sample.filter(t => t.net < 0);
    return { trades: sample.length, wins: winners.length, losses: losers.length, adds: sample.filter(t => t.add_fills).length, net: sum(sample.map(t => t.net)), gross: sum(sample.map(t => t.gross)), fees: sum(sample.map(t => t.fees)), funding: sum(sample.map(t => t.funding)), profitFactor: losers.length ? -sum(winners.map(t => t.net)) / sum(losers.map(t => t.net)) : null, medianHours: sample.length ? sample.map(t => (Date.parse(t.closed) - Date.parse(t.opened)) / 3600000).sort((a,b) => a-b)[Math.floor(sample.length / 2)] : null };
  };
  const by = key => Object.fromEntries([...new Set(trades.map(t => t[key]))].map(label => [label, statistics(trades.filter(t => t[key] === label))]));
  const years = {};
  const months = {};
  for (const balance of [...balances, { time: coverage.at(-1)?.[1] ?? iso(end), equity: cash }]) {
    const calendar = iso(Date.parse(balance.time) + yearOffset - 1);
    years[calendar.slice(0, 4)] = balance.equity;
    months[calendar.slice(0, 7)] = balance.equity;
  }
  const shorts = trades.filter(t => t.side === 'SHORT');
  const stoppedShorts = shorts.filter(t => ['stop', 'stop_gap'].includes(t.reason));
  const diagnostics = config.diagnose ? {
    by4h: Object.fromEntries([-1, 0, 1].map(trend => [trend, statistics(shorts.filter(t => t.trend4 === trend))])),
    stoppedShorts: stoppedShorts.length,
    stoppedAfterHalfRiskFavorable: stoppedShorts.filter(t => t.favorable_before_exit >= config.stopPercent / 2).length,
    stoppedAfterFullRiskFavorable: stoppedShorts.filter(t => t.favorable_before_exit >= config.stopPercent).length,
    earlierExitTrades: shorts.filter(t => t.early_exit_delta !== undefined).length,
    earlierExitSameEntriesNetChange: sum(shorts.map(t => t.early_exit_delta ?? 0)),
  } : undefined;
  return { config, endingEquity: cash, drawdown, ...(config.reportWindow ? { windowDrawdown } : {}), maximumExposure, rejected, rejectedAdds, coverage, years, months, overall: statistics(trades), byResonance: by('resonance'), bySetup: by('setup'), bySide: by('side'), byExit: by('reason'), diagnostics, ...(config.structureEntry ? { blockedByStructure } : {}), trades, balances };
}

const base = { mode: 'both', squeeze: 0.75, fee, slip: slippage, minOrder: false, funding: 0, leverage: 5 };
const legacyScenarios = [
  ['base', base],
  ['triple_only', { ...base, mode: 'triple' }],
  ['order_limits', { ...base, minOrder: true }],
  ['one_x', { ...base, leverage: 1 }],
  ['order_limits_stress', { ...base, minOrder: true, slip: 0.0005, funding: 0.0001 }],
  ['cost_stress', { ...base, slip: 0.0005, funding: 0.0001 }],
  ['tighter_squeeze', { ...base, squeeze: 0.5 }],
  ['looser_squeeze', { ...base, squeeze: 1 }],
];
const practical = { ...base, minOrder: true };
const shortHold = { ...practical, maxHours: 2 };
const withHistogram = { ...shortHold, histBars: 2 };
const fifteenOnly = { ...withHistogram, mode: '15m' };
const shortScenarios = [
  ['order_limits', practical],
  ['max_2h', shortHold],
  ['max_2h_macd_with_higher', withHistogram],
  ['15m_macd_2h', fifteenOnly],
  ['15m_no_macd_2h', { ...fifteenOnly, histBars: 0 }],
  ['15m_macd_2h_one_change', { ...fifteenOnly, histBars: 1 }],
  ['15m_macd_4h', { ...fifteenOnly, maxHours: 4 }],
  ['15m_macd_2h_fractional', { ...fifteenOnly, minOrder: false }],
];
const roiStop = { ...fifteenOnly, maxHours: undefined, stopPercent: 0.02 / fifteenOnly.leverage, squeezeRisk: 0.5 };
const priceStop = { ...roiStop, stopPercent: 0.02 };
const roiFullRisk = { ...roiStop, squeezeRisk: 1 };
const signalExitScenarios = [
  ['previous_15m_macd_2h', fifteenOnly],
  ['roi_stop_2pct_half_r', roiStop],
  ['price_stop_2pct_half_r', priceStop],
  ['roi_stop_2pct_full_r', roiFullRisk],
  ['price_stop_2pct_full_r', { ...priceStop, squeezeRisk: 1 }],
  ['roi_stop_2pct_profit_only', { ...roiFullRisk, profitOnly: true }],
  ['roi_stop_2pct_funding_stress', { ...roiFullRisk, funding: 0.0001 }],
  ['roi_stop_2pct_fractional', { ...roiStop, minOrder: false }],
  ['price_stop_2pct_fractional', { ...priceStop, minOrder: false }],
];
const noFeeSignalExits = signalExitScenarios
  .filter(([, config]) => config.funding === 0)
  .map(([label, config]) => [label, { ...config, fee: 0 }]);
const diagnosticBase = { ...roiStop, fee: 0, calendarOffsetHours: 8, diagnose: true };
const leverageDiagnostics = [
  ['full_r_5x', { ...diagnosticBase, squeezeRisk: 1 }],
  ['full_r_short_4h_filter', { ...diagnosticBase, squeezeRisk: 1, shortWith4h: true }],
  ['short_4h_filter', { ...diagnosticBase, shortWith4h: true }],
  ['short_early_exit', { ...diagnosticBase, shortExitBars: 1 }],
  ['short_4h_and_early_exit', { ...diagnosticBase, shortWith4h: true, shortExitBars: 1 }],
  ...[1, 2, 3, 4, 5].map(leverage => [`fixed_roi_${leverage}x`, { ...diagnosticBase, leverage, stopPercent: 0.02 / leverage }]),
  ...[1, 2, 3].map(leverage => [`fixed_price_${leverage}x`, { ...diagnosticBase, leverage }]),
];
const resonanceSizing = [
  ['base_15m', diagnosticBase],
  ['triple_double_risk', { ...diagnosticBase, resonanceRiskMultiplier: 2 }],
  ['triple_double_squeeze_only', { ...diagnosticBase, resonanceRiskMultiplier: 2, squeezeBoostOnly: true }],
];
const longOnlyScenarios = [
  resonanceSizing[0],
  resonanceSizing[2],
  ['long_only_half_r', { ...diagnosticBase, longOnly: true }],
  ['long_only_resonance_boost', { ...diagnosticBase, longOnly: true, resonanceRiskMultiplier: 2, squeezeBoostOnly: true }],
];
const shortOnlyScenarios = [
  ['short_only_half_r', { ...diagnosticBase, shortOnly: true }],
  ['short_only_resonance_boost', { ...diagnosticBase, shortOnly: true, resonanceRiskMultiplier: 2, squeezeBoostOnly: true }],
];
const longExitReview = [
  longOnlyScenarios[2],
  ['long_only_ma_cross_15m', { ...diagnosticBase, longOnly: true, crossoverOnly: true }],
];
const fiveStepExit = { ...longExitReview[1][1], takeProfitSteps: [0.5, 1, 1.5, 2, 3] };
const takeProfitReview = [
  longExitReview[0], longExitReview[1],
  ['take_profit_5_steps_actual', fiveStepExit],
  ['take_profit_5_steps_ideal', { ...fiveStepExit, fractionalTakeProfit: true }],
];
const oneCutBase = { ...longExitReview[1][1], exitOnTrendFlip: true };
const oneCutReview = [
  longExitReview[1], ['trend_exit_no_partial', oneCutBase],
  ...[1, 2, 3, 5, 10].map(m => [`reduce_20_at_${m}x`, { ...oneCutBase, takeProfitFraction: 0.2, takeProfitSteps: [m] }]),
];
const fullExposureReview = [
  ['risk_sized_control', { ...oneCutBase, reportWindow: true }],
  ...oneCutReview.slice(1).map(([name, config]) => [name, { ...config, useLeverageCap: true, reportWindow: true }]),
];
const zeroEntryReview = [
  ['previous_entry_half_r', { ...oneCutReview[3][1], reportWindow: true }],
  fullExposureReview[3],
  ['strict_triangle_5x', { ...fullExposureReview[3][1], zeroEntry: 'none' }],
  ...['histogram', 'dif'].flatMap(zeroEntry => [
    [zeroEntry+'_5x', { ...fullExposureReview[3][1], zeroEntry }],
    [zeroEntry+'_half_r', { ...oneCutReview[3][1], zeroEntry, reportWindow: true }],
  ]),
];
const nearZeroReview = [
  ...zeroEntryReview.filter(([name]) => ['previous_entry_half_r', 'reduce_20_at_2x', 'histogram_5x', 'histogram_half_r'].includes(name)),
  ...[0.1, 0.2, 0.3].flatMap(macdNearZeroAtr => [
    ['near_'+macdNearZeroAtr+'_5x', { ...fullExposureReview[3][1], zeroEntry: 'histogram', macdNearZeroAtr }],
    ['near_'+macdNearZeroAtr+'_half_r', { ...oneCutReview[3][1], zeroEntry: 'histogram', macdNearZeroAtr, reportWindow: true }],
  ]),
];
const aboveZeroReview = nearZeroReview.filter(([, config]) => config.macdNearZeroAtr !== undefined)
  .map(([label, config]) => [label.replace('near_', 'above_'), { ...config, macdAboveZero: true }]);
const noLeverageReview = aboveZeroReview.filter(([label]) => label.endsWith('_5x')).flatMap(([label, config]) => {
  const name = label.replace('_5x', '');
  const one = { ...config, leverage: 1 };
  const spotProxy = { ...one, quantityStep: 0.000001, minOrderNotional: 5, minExitNotional: 5 };
  return [
    [name+'_perp_1x', one],
    [name+'_spot_04', spotProxy],
    [name+'_spot_2', { ...spotProxy, stopPercent: 0.02, takeProfitSteps: [0.4] }],
  ];
});
const belowZeroReview = noLeverageReview.filter(([label]) => label.includes('_spot_'))
  .map(([label, config]) => [label.replace('above_', 'below_'), { ...config, macdAboveZero: false, macdBelowZero: true }]);
const fixedDifReview = belowZeroReview.filter(([label]) => label.startsWith('below_0.2_'))
  .map(([label, config]) => [label.replace('below_0.2', 'dif_minus3'), { ...config, macdNearZeroAtr: undefined, macdDifFloor: -3 }]);
const selectedAtrConfig = belowZeroReview.find(([label]) => label === 'below_0.2_spot_2')[1];
const selectedAtrReview = [
  ['selected_atr_1x_spot', selectedAtrConfig],
  ['selected_atr_5x_full', { ...selectedAtrConfig, leverage: 5, quantityStep: undefined, minOrderNotional: undefined, minExitNotional: undefined }],
];
const peakShortBase = { ...oneCutBase, longOnly: false, shortOnly: true, useLeverageCap: true, reportWindow: true, stopPercent: 0.02, takeProfitFraction: 0.2, takeProfitSteps: [0.4] };
const peakShortReview = [1, 3, 6, 9].flatMap(shortPeakHours => ['above', 'below'].flatMap(shortPeakMacdSide => [false, true].map(strictShortExpansion => [
  'peak_'+shortPeakHours+'h_'+shortPeakMacdSide+(strictShortExpansion ? '_strict' : ''),
  { ...peakShortBase, shortPeakHours, shortPeakMacdSide, strictShortExpansion },
])));
const immediatePeakReview = Array.from({ length: 24 }, (_, i) => {
  const shortPeakHours = i + 1;
  return ['peak_'+shortPeakHours+'h_immediate', { ...peakShortBase, shortPeakHours, shortPeakMacdSide: 'above', immediateShortCross: true }];
});
const confirmationPeakReview = immediatePeakReview.map(([label, config]) => [label.replace('_immediate', '_confirmed'), { ...config, immediateShortCross: false }]);
const selectedShort8h = confirmationPeakReview.find(([, config]) => config.shortPeakHours === 8);
const combinedReview = [
  selectedAtrReview[1], selectedShort8h,
  ['combined_selected_long_and_8h_short', { ...selectedAtrReview[1][1], longOnly: false, shortPeakHours: 8, shortPeakMacdSide: 'above' }],
];
const rangeVariants = [
  ['half', {rangeHalf:true}],
  ['timeout', {rangeTimeout:true}],
  ['both', {rangeHalf:true,rangeTimeout:true}],
  ['skip_short', {rangeSkipShort:true}],
];
const erScenarios = [combinedReview[1], combinedReview[2]].flatMap(([key, config]) => [
  [key, config],
  ...rangeVariants.map(([variant, settings]) => [key+'_'+variant, {...config, rangeReview:true, ...settings}]),
  ...(config.shortOnly ? [] : [[key+'_timeout_shorts_only', {...config,rangeReview:true,rangeTimeout:true,timeoutShortOnly:true}]]),
]);
const scenarioSets = { er_review: erScenarios, short: shortScenarios, signal_exit: signalExitScenarios, signal_exit_no_fee: noFeeSignalExits, leverage: leverageDiagnostics, resonance_sizing: resonanceSizing, long_only: longOnlyScenarios, short_only: shortOnlyScenarios, long_exit_review: longExitReview, take_profit_review: takeProfitReview, one_cut_review: oneCutReview, full_exposure_review: fullExposureReview, zero_entry_review: zeroEntryReview, near_zero_review: nearZeroReview, above_zero_review: aboveZeroReview, no_leverage_review: noLeverageReview, below_zero_review: belowZeroReview, fixed_dif_review: fixedDifReview, selected_atr_review: selectedAtrReview, peak_short_review: peakShortReview, immediate_peak_review: immediatePeakReview, confirmation_peak_review: confirmationPeakReview };
const fixedShortTimeout = erScenarios.find(([name]) => name === combinedReview[2][0] + '_timeout_shorts_only');
const atrTimeoutReview = [
  combinedReview[2],
  fixedShortTimeout,
  ['combined_short_timeout_atr_half', { ...fixedShortTimeout[1], timeoutAtrMultiple: 0.5 }],
  ['combined_short_timeout_atr_half_capped', { ...fixedShortTimeout[1], timeoutAtrMultiple: 0.5, timeoutMoveCap: 0.004 }],
];
const structuralBase = atrTimeoutReview.find(([name]) => name.endsWith('_capped'));
const causeReview = [
  structuralBase,
  ['support_resistance_veto', { ...structuralBase[1], structureEntry: 'veto' }],
  ['support_resistance_with_room', { ...structuralBase[1], structureEntry: 'require_room' }],
  ['full_target_0p8', { ...structuralBase[1], diagnosticFullTarget: true }],
];
const scenarios = experiment === 'cause_review' ? causeReview : experiment === 'atr_timeout_review' ? atrTimeoutReview : experiment === 'confirmation_8h_only' ? [selectedShort8h] : experiment === 'combined_review' ? combinedReview : scenarioSets[experiment] ?? legacyScenarios;
const results = scenarios.map(([label, config]) => [label, backtest(config)]);

const summaries = {};
const tradeRows = [];
for (const [label, { trades, balances, ...summary }] of results) {
  summaries[label] = summary;
  const exportScenarios = experiment === 'take_profit_review' ? ['take_profit_5_steps_actual', 'take_profit_5_steps_ideal'] : experiment === 'long_exit_review' ? ['long_only_half_r', 'long_only_ma_cross_15m'] : experiment === 'resonance_sizing' ? ['base_15m', 'triple_double_risk', 'triple_double_squeeze_only'] : experiment === 'signal_exit'
    ? ['roi_stop_2pct_full_r', 'roi_stop_2pct_profit_only', 'roi_stop_2pct_fractional', 'price_stop_2pct_fractional']
    : experiment === 'short' ? ['order_limits', 'max_2h', 'max_2h_macd_with_higher', '15m_macd_2h'] : ['base', 'order_limits', 'triple_only', 'one_x', 'order_limits_stress'];
  if (experiment === 'cause_review' || experiment === 'atr_timeout_review' || exportScenarios.includes(label) || (['one_cut_review', 'full_exposure_review', 'zero_entry_review', 'near_zero_review', 'above_zero_review', 'no_leverage_review', 'below_zero_review', 'fixed_dif_review', 'selected_atr_review', 'peak_short_review', 'immediate_peak_review', 'confirmation_peak_review', 'confirmation_8h_only', 'combined_review', 'er_review'].includes(experiment) && summary.config.takeProfitFraction)) {
    tradeRows.push(...trades.map(trade => ({ scenario: label, ...trade })));
  }
  if (label === 'base' || experiment === 'confirmation_8h_only') {
    writeFileSync(`${output}_equity.csv`, ['time,equity', ...balances.map(row => `${row.time},${row.equity}`)].join('\n') + '\n');
  }
}
if (tradeRows.length) {
  const columns = Object.keys(tradeRows[0]);
  writeFileSync(`${output}_trades.csv`, [columns.join(','), ...tradeRows.map(row => columns.map(k => row[k]).join(','))].join('\n') + '\n');
}
const inWindow = input.filter(b => b.t >= start).length;
const expected = (end - start) / bar;
const result = { since: iso(start), until: iso(end), observedCandles: inWindow, expectedCandles: expected, continuous: inWindow === expected, summaries };
writeFileSync(`${output}_summary.json`, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));

