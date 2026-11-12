import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { ladderAlongPrices, ladderCandleIsAmbiguous, ladderOnCandle } from './ladder_exit.mjs';

const [source, output, since = '2021-11-09', until = '2026-11-09', venue = 'binance', experiment, startingCash = '100', ethSource, ethSince, ladderData, ladderPath = 'adverse', entryPolicyFile] = process.argv.slice(2);
if (!source || !output) throw Error('Usage: node btc_perp_backtest.mjs DATA_DIR_OR_CSV OUTPUT_PREFIX [START_UTC] [END_UTC] [binance|bybit]');
if (!['adverse', 'favorable'].includes(ladderPath)) throw Error('Invalid ladder path');
const ladderMinutes = ladderData ? JSON.parse(readFileSync(ladderData, 'utf8')) : {};
const entryPolicies = entryPolicyFile ? JSON.parse(readFileSync(entryPolicyFile, 'utf8')) : {};

const bar = 900_000;
const rangeErPeriods = 20;
const rangeErLimit = 0.25;
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

function loadMarket(path, firstTradeAt) {
  const market = new Map();
  const files = statSync(path).isDirectory()
    ? readdirSync(path).filter(name => /^BTCUSDT-15m-.*\.(?:zip|csv)$/i.test(name)).map(name => join(path, name))
    : [path];
  for (const file of files) {
    const csv = file.endsWith('.zip') ? execFileSync('tar', ['-xOf', file], { encoding: 'utf8' }) : readFileSync(file, 'utf8');
    for (const row of csv.trim().split(/\r?\n/)) {
      const [t, o, h, l, c, v] = row.split(',', 6).map(Number);
      if (!Number.isFinite(t)) continue;
      if (t % bar || ![o, h, l, c].every(x => x > 0) || l > Math.min(o, c) || h < Math.max(o, c)) throw Error(`Invalid OHLC in ${file} at ${t}`);
      const previous = market.get(t);
      if (previous && [o, h, l, c].some((x, i) => x !== [previous.o, previous.h, previous.l, previous.c][i])) throw Error(`Conflicting price data at ${iso(t)}`);
      market.set(t, { t, o, h, l, c, v });
    }
  }
  const input = [...market.values()].filter(b => b.t >= firstTradeAt - 15 * 96 * bar && b.t < end).sort((a, b) => a.t - b.t);
  const segments = [];
  for (const candle of input) {
    const segment = segments.at(-1);
    if (!segment || candle.t !== segment.at(-1).t + bar) segments.push([candle]);
    else segment.push(candle);
  }
  if (!input.length) throw Error(`No candles found for the requested window in ${path}`);
  return { input, segments };
}
const { input, segments } = loadMarket(source, start);

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

function withDownVolume(candles) {
  return candles.map((row, i) => {
    if (!Number.isFinite(row.v) || row.v < 0) throw Error(`Invalid volume at ${iso(row.t)}`);
    if (i < 20) return row;
    const history = candles.slice(i - 20, i).map(b => b.v).sort((a, b) => a - b);
    const median = (history[9] + history[10]) / 2;
    const rising = row.c > row.o && row.c > candles[i - 1].c;
    const falling = row.c < row.o && row.c < candles[i - 1].c;
    const downVolume = median > 0 && falling && row.v >= 1.5 * median;
    const upVolume = median > 0 && rising && row.v >= 1.5 * median;
    const weakDown = median > 0 && falling && row.v <= median / 1.5;
    return { ...row, downVolume, upVolume, weakDown };
  });
}

function withRsi(candles, period) {
  let gain = 0, loss = 0;
  return candles.map((row, i) => {
    if (i === 0) return row;
    const change = row.c - candles[i - 1].c;
    const up = Math.max(0, change), down = Math.max(0, -change);
    if (i <= period) {
      gain += up;
      loss += down;
    } else {
      gain += up - gain / period;
      loss += down - loss / period;
    }
    const rsi = i < period ? undefined : gain + loss === 0 ? 50 : 100 * gain / (gain + loss);
    return { ...row, rsi };
  });
}

function rangeEfficiencyRatio(candles, lastClosedIndex) {
  const first = lastClosedIndex - rangeErPeriods;
  if (first < 0) return NaN;
  let travel = 0;
  for (let i = first + 1; i <= lastClosedIndex; i++) travel += Math.abs(candles[i].c - candles[i - 1].c);
  return travel === 0 ? 0 : Math.abs(candles[lastClosedIndex].c - candles[first].c) / travel;
}

function roundOrder(quantity, price, step, minimumNotional) {
  const rounded = Math.floor((quantity + 1e-12) / step) * step;
  return rounded * price >= minimumNotional ? rounded : 0;
}

function* simulate(config, { history = segments, firstTradeAt = start, shared = false } = {}) {
  const { leverage } = config;
  const quantityStep = config.quantityStep ?? minQty;
  const independent = config.mode === '15m';
  const signalExit = config.stopPercent !== undefined;
  const maxHold = config.maxHours ?? 48;
  const ladder = config.ladderScale !== undefined;
  const ladderOverlay = config.ladderOverlay === true;
  const marketEntryPolicy = config.marketEntryPolicy;
  const policySchedule = entryPolicies[config.marketEntryAsset]?.[marketEntryPolicy];
  if (marketEntryPolicy && !policySchedule) throw Error(`Missing ${marketEntryPolicy} policy for ${config.marketEntryAsset}`);
  const favorableFirst = ladderPath === 'favorable';
  const minutesByBar = ladderMinutes[config.ladderAsset] ?? {};
  const ticksByMinute = ladderMinutes.ticks?.[config.ladderAsset] ?? {};
  const ticksByBar = ladderMinutes.fullBars?.[config.ladderAsset] ?? {};
  const ladderAudit = { uncertain15m: [], uncertain1m: [], usedMinuteBars: 0, usedTradeWindows: 0 };
  const yearOffset = (config.calendarOffsetHours ?? 0) * 3600000;
  let cash = startingEquity, peak = startingEquity, drawdown = 0, rejected = 0, rejectedAdds = 0, maximumExposure = 0;
  const reportStart = Date.parse('2022-01-01T00:00:00+08:00');
  const reportEnd = Date.parse('2025-01-01T00:00:00+08:00');
  let windowPeak, windowDrawdown = 0, inReportWindow = false;
  const trades = [], balances = [], coverage = [];
  const rsi4hConflicts = [];
  const rsiRangeGate = { allowed: 0, blocked: 0 };
  const yearlyEquity = {};
  let activeYear, lowEquity = startingEquity, lastTrackedEquity = startingEquity;
  const entryFunnel = {
    long: { histogramCrosses: 0, belowZeroCrosses: 0, nearZeroBelowCrosses: 0, zone: 0,
      bullishTrigger: 0, goldenTriangle: 0, macdConfirmed: 0, priceBreakout: 0, distanceOrVolume: 0 },
    short: { flatDecisionBars: 0, peakSetup: 0, macdConfirmed: 0, wider: 0, maSpreadDown: 0, distanceOrVolume: 0 },
  };
  const resistanceLongChecks = { candidates: 0, nearResistance: 0, upVolumeBreakout: 0, weakDownReclaim: 0, blocked: 0 };
  const supportShortChecks = { candidates: 0, noSupport: 0, belowSupport: 0, tooFar: 0, nearSupport: 0, volumeException: 0 };
  const mark = price => cash + (position ? position.side * position.qty * (price - position.entry) : 0);
  const track = (value, side = position?.side) => {
    const annual = yearlyEquity[activeYear];
    const move = value - lastTrackedEquity;
    if (side === 1) annual.longNet += move;
    else if (side === -1) annual.shortNet += move;
    else if (Math.abs(move) > 1e-9) throw Error('Equity moved without a position');
    lastTrackedEquity = value;
    annual.endingEquity = value;
    annual.peak = Math.max(annual.peak, value);
    annual.drawdown = Math.max(annual.drawdown, 1 - value / annual.peak);
    lowEquity = Math.min(lowEquity, value);
    peak = Math.max(peak, value);
    drawdown = Math.max(drawdown, 1 - value / peak);
    if (inReportWindow) {
      windowPeak = Math.max(windowPeak ?? value, value);
      windowDrawdown = Math.max(windowDrawdown, 1 - value / windowPeak);
    }
  };
  let position, currentBarOpen;
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
    trades.push({ side: side === 1 ? 'LONG' : 'SHORT', setup, resonance, signal: iso(signal), opened: iso(opened), closed: iso(time), first_entry: position.firstEntry, entry, exit, first_qty: position.firstQty, qty, add_fills: added, initial_stop: position.firstStop, final_stop: position.stop, target: position.target, gross, fees: fees + finalFee, funding, net: gross - fees - finalFee - funding, entry_support: position.support, entry_resistance: position.resistance, long_entry_gate: position.longEntryGate, volume_exception: position.volumeException, risk_budget: initialRisk, reason, equity: cash, ...(config.diagnose ? { trend4: position.trend4, favorable_before_exit: position.favorable, early_exit_delta: earlyExitDelta, risk_fraction_of_r: position.riskOfR } : {}), ...(config.takeProfitSteps ? { tp_orders: position.tpOrders, tp_fills: position.tpFills.join('|'), partial_gross: position.partialGross } : {}) });
    Object.assign(trades.at(-1), {
      cross_at_or_before_squeeze: position.crossAtOrBeforeSqueeze,
      no_high_breakout: position.noHighBreakout,
      macd_lead_minutes: position.macdLeadMinutes,
      macd_age_minutes: position.macdAgeMinutes,
      hourly_structure: position.hourlyStructure,
    });
    if (config.rsi4hPeriod) trades.at(-1).entry_rsi_4h = position.entryRsi4h;
    if (config.rsiRangeOnly) trades.at(-1).entry_er_20 = position.entryEr20;
    if (ladder) Object.assign(trades.at(-1), { exit_bar_open: iso(currentBarOpen), ladder_rung: position.ladderRung ?? 0 });
    if (ladderOverlay && position.tpBarOpen !== undefined) trades.at(-1).tp_bar_open = iso(position.tpBarOpen);
    position = undefined;
    track(cash, side);
  }
  const gapReason = () => position.ladderRung > 0 ? 'ladder_gap' : position.profitLocked ? 'profit_floor_gap' : 'stop_gap';

  function applyLadder(barRow) {
    const { entry, side, stop, ladderRung = 0 } = position;
    const canReduce = ladderOverlay && barRow.t >= position.softExitFrom;
    if (canReduce) fillTakeProfits(barRow.o, barRow.t);
    let state = { stop, rung: ladderRung, hit: false };
    const step = candle => {
      const selected = ladderOnCandle(entry, side, state, candle, favorableFirst, config.ladderScale);
      const alternative = ladderOnCandle(entry, side, state, candle, !favorableFirst, config.ladderScale);
      const differs = ladderCandleIsAmbiguous(entry, side, state, candle, selected, alternative, config.ladderScale);
      state = selected;
      return differs;
    };
    const stepTrades = prices => {
      state = ladderAlongPrices(entry, side, state, prices, config.ladderScale);
      ladderAudit.usedTradeWindows++;
    };
    const minutes = minutesByBar[barRow.t];
    if (ticksByBar[barRow.t]) {
      stepTrades(ticksByBar[barRow.t]);
    } else if (minutes) {
      ladderAudit.usedMinuteBars++;
      for (const [i, [o, h, l, c]] of minutes.entries()) {
        const time = barRow.t + 60_000 * i;
        if (ticksByMinute[time]) stepTrades(ticksByMinute[time]);
        else if (step({ o, h, l, c })) ladderAudit.uncertain1m.push(time);
        if (state.hit) break;
      }
    } else if (step(barRow)) {
      ladderAudit.uncertain15m.push(barRow.t);
    }
    position.stop = state.stop;
    position.ladderRung = state.rung;
    if (canReduce) {
      const time = barRow.t + bar;
      if (!state.hit) fillTakeProfits(side === 1 ? barRow.h : barRow.l, time);
      // The original 0.8% partial is reached before a positive ladder lock.
      else if (state.rung > 0) fillTakeProfits(state.stop, time);
    }
    if (state.hit) close(state.stop, barRow.t + bar, state.rung > 0 ? 'ladder_lock' : 'stop');
  }
  function fillTakeProfits(price, time) {
    while (position && position.tpPlan.length && (price - position.tpPlan[0].price) * position.side >= 0) {
      const level = position.tpPlan.shift();
      position.tpFills.push(level.level);
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
      if (ladderOverlay) position.tpBarOpen = currentBarOpen;
      cash += realized - fees;
    }
  }
  function size(price, reference, time, stop, side, riskBudget, equity, existing = 0, exposureFraction = 1) {
    const exit = fill(stop, -side);
    const lossPerUnit = (price - exit) * side + config.fee * (price + exit);
    if (lossPerUnit <= 0) return 0;
    const feeReserveLeverage = config.feeReserveLeverage ?? leverage;
    const marginCap = (equity * leverage * exposureFraction - existing * price) / (price * (1 + 2 * feeReserveLeverage * config.fee));
    let quantity = config.useLeverageCap ? marginCap : Math.min(riskBudget / lossPerUnit, marginCap);
    if (config.minOrder) {
      const minNotional = config.minOrderNotional ?? (venue === 'binance' && time >= Date.parse('2026-04-14T06:30Z') ? 50 : 100);
      quantity = roundOrder(quantity, reference, quantityStep, minNotional);
    }
    return Math.max(0, quantity);
  }

  for (const raw of history.filter(s => s.length > 480)) {
    const baseSmall = indicators(raw);
    const small = config.volumeExceptionBars ? withDownVolume(baseSmall) : baseSmall;
    const mid = indicators(aggregate(raw, 4));
    let big = indicators(aggregate(raw, 16));
    if (config.rsi4hPeriod) big = withRsi(big, config.rsi4hPeriod);
    let hi = -1, bi = -1, zone, pending, retest, shortExpansion, lastProbe = 0;
    let lastZeroUp = -1, lastBullishOrder = -1;
    let recentPeak, peakSetup, macdDeath;
    const first = Math.max(480, raw.findIndex(b => b.t >= firstTradeAt));
    if (raw[first]?.t < firstTradeAt || !raw[first]) continue;
    coverage.push([iso(raw[first].t), iso(raw.at(-1).t + bar)]);
    for (let i = first; i < small.length; i++) {
      const b = small[i], prev = small[i - 1];
      currentBarOpen = b.t;
      const calendarYear = iso(b.t + yearOffset).slice(0, 4);
      if (calendarYear !== activeYear) {
        const openingEquity = activeYear === undefined ? startingEquity : yearlyEquity[activeYear].endingEquity;
        activeYear = calendarYear;
        yearlyEquity[activeYear] = { openingEquity, endingEquity: openingEquity, peak: openingEquity, drawdown: 0, longNet: 0, shortNet: 0 };
      }
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
          entryFunnel.long.histogramCrosses++;
          if (correctSide) entryFunnel.long.belowZeroCrosses++;
          if (nearZero && correctSide && aboveDifFloor) entryFunnel.long.nearZeroBelowCrosses++;
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
        close(b.o, b.t, crossedStop ? gapReason() : pending.reason);
      }
      if (shared && position && (b.o - position.stop) * position.side <= 0) close(b.o, b.t, gapReason());
      const wantsEntry = pending?.type === 'entry' && !position && (signalExit || (b.o - pending.stop) * pending.side > 0);
      let sharedQuantity;
      if (shared) {
        // Both assets close any open-price exits before allocating the new orders.
        sharedQuantity = yield { time: b.t, equity: mark(b.o), gross: position ? position.qty * b.o : 0,
          order: wantsEntry ? { entry: fill(b.o, pending.side), reference: b.o } : undefined };
      }
      if (wantsEntry) {
        const entry = fill(b.o, pending.side);
        const initialRisk = cash * riskFraction;
        const stop = signalExit ? entry * (1 - pending.side * config.stopPercent) : pending.stop;
        const baseFraction = signalExit && pending.fraction === 0.5 ? config.squeezeRisk : pending.fraction;
        const boost = pending.resonance === 'triple' && (!config.squeezeBoostOnly || pending.fraction === 0.5);
        const fraction = boost ? baseFraction * (config.resonanceRiskMultiplier ?? 1) : baseFraction;
        const inRange = config.rangeReview && rangeEfficiencyRatio(small, i - 1) < rangeErLimit;
        const skip = inRange && config.rangeSkipShort && pending.side === -1;
        const exposureFraction = inRange && config.rangeHalf ? 0.5 : 1;
        const qty = skip ? 0 : sharedQuantity ?? size(entry, b.o, b.t, stop, pending.side, initialRisk * fraction, cash, 0, exposureFraction);
        if (qty > 0) {
          const fees = entry * qty * config.fee;
          if (!shared) maximumExposure = Math.max(maximumExposure, entry * qty / cash);
          cash -= fees;
          const signalHour = mid[hi];
          if (config.timeoutAtrMultiple && inRange && pending.side === -1
              && (!(signalHour?.atr > 0) || signalHour.t + 4 * bar > pending.signal)) {
            throw Error(`Missing closed 1h ATR at ${iso(pending.signal)}`);
          }
          const atrMovePct = config.timeoutAtrMultiple === undefined ? 0.004 : config.timeoutAtrMultiple * signalHour?.atr / entry;
          const minHoldHours = pending.setup === 'rsi_4h_extreme' ? (config.rsiMinHoldHours ?? 0) : 0;
          const softExitFrom = b.t + minHoldHours * 4 * bar;
          position = { timeoutMovePct: Math.min(atrMovePct, config.timeoutMoveCap ?? Infinity), ...pending, stop, entry, qty, firstEntry: entry, firstQty: qty, firstStop: stop, fees, funding: 0, initialRisk, riskOfR: fraction, opened: b.t, softExitFrom, inRange, hourFavorable: 0, added: 0, target: signalExit ? '' : entry + 2 * (entry - stop), favorable: 0 };
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
        if ((b.o - stop) * side <= 0) close(b.o, b.t, gapReason());
        else if (ladder) applyLadder(b);
        else if (config.takeProfitSteps) {
          const canReduce = b.t >= position.softExitFrom;
          if (canReduce) fillTakeProfits(b.o, b.t);
          if (position && (adverse - stop) * side <= 0) close(stop, b.t + bar, position.profitLocked ? 'profit_floor' : 'stop');
          else if (position && canReduce) fillTakeProfits(favorable, b.t + bar);
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
        if (ladder && !ladderOverlay) {
          if (config.ladderMaxHours && time - position.opened >= config.ladderMaxHours * 4 * bar) {
            pending = { type: 'exit', reason: 'ladder_time_cap' };
          }
          continue;
        }
        if (time < position.softExitFrom) continue;
        if (config.profitExit && !position.profitConfirmed && position.tpFills?.length
            && (b.c - position.entry) * position.side >= position.entry * 0.02) {
          position.profitConfirmed = true;
          if (config.profitExit !== 'profit_hour_only') {
            position.stop = position.entry * (1 + position.side * 0.01);
            position.profitLocked = true;
          }
        }
        if (position.runnerExitAt) {
          if (time >= position.runnerExitAt) pending = { type: 'exit', reason: 'profit_runner_hour' };
          else if (b.structure === -position.side) pending = { type: 'exit', reason: '15m_structure_flip' };
          continue;
        }
        const crossover = reversalExit(small, i, position.side, config.shortExitBars, config.crossoverOnly);
        const rangeTimeout = position.inRange && config.rangeTimeout && (!config.timeoutShortOnly || position.side === -1)
          && time - position.opened === 4 * bar && position.hourFavorable < position.timeoutMovePct;
        const reason = crossover ?? (config.exitOnTrendFlip && b.structure === -position.side ? '15m_structure_flip' : rangeTimeout ? 'er_1h_timeout' : undefined);
        if (config.diagnose && position.side === -1 && prev.histogram < 0 && b.histogram > prev.histogram) position.earlyExitPending = true;
        const exit = fill(b.c, -position.side);
        const netAtClose = position.qty * ((exit - position.entry) * position.side - exit * config.fee) - position.fees - position.funding;
        if (reason && (!config.profitOnly || netAtClose > 0)) {
          const hour = mid[hi];
          const extend = (config.profitExit === 'profit_runner' || config.profitExit === 'profit_hour_only')
            && reason === 'ma5_ma30_cross' && position.profitConfirmed
            && b.structure !== -position.side && hour && hour.structure !== -position.side
            && (hour.c - hour.averages[2]) * position.side > 0;
          if (extend) position.runnerExitAt = (Math.floor(time / (4 * bar)) + 1) * 4 * bar;
          else pending = { type: 'exit', reason };
        }
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
        const originalSignal = entryOnTime && macdConfirmed && wider && maSpreadDown
          && (!config.strictShortExpansion || downwardExpansion(b, prev));
        const maCrossDown = prev.ma5 >= prev.ma20 && b.ma5 < b.ma20;
        const shorts = entryFunnel.short;
        shorts.flatDecisionBars++;
        if (peakSetup) shorts.peakSetup++;
        if (macdConfirmed) {
          shorts.macdConfirmed++;
          if (wider) {
            shorts.wider++;
            if (maSpreadDown) shorts.maSpreadDown++;
          }
        }
        const shortSignal = config.supportShortEntry === 'ma_cross' ? maCrossDown : originalSignal;
        if (shortSignal && config.isolatedSide !== 'LONG') {
          const support = mid[hi]?.bottom;
          const distance = (b.c - support) / b.c;
          const supportDistance = config.supportDistance ?? 0.008;
          const nearSupport = Math.abs(distance) <= supportDistance && (config.allowNearBelow || distance >= 0);
          const volumeException = distance < -supportDistance && config.volumeExceptionBars
            && b.c < small[i - config.volumeExceptionBars].c
            && small.slice(i - config.volumeExceptionBars + 1, i + 1).some(row => row.downVolume);
          if (config.supportShortEntry) {
            supportShortChecks.candidates++;
            if (!Number.isFinite(support)) supportShortChecks.noSupport++;
            else if (distance < 0 && !config.allowNearBelow) supportShortChecks.belowSupport++;
            else if (volumeException) supportShortChecks.volumeException++;
            else if (!nearSupport) supportShortChecks.tooFar++;
            else supportShortChecks.nearSupport++;
          }
          if (!config.supportShortEntry || nearSupport || volumeException) {
            entryFunnel.short.distanceOrVolume++;
            const setup = config.supportShortEntry === 'ma_cross' ? 'ma5_ma20_cross_near_support' : 'peak_ma5_ma20_macd_death';
            pending = { type: 'entry', side: -1, fraction: 0.5, setup, resonance: resonanceFor(-1), signal: time, trend4, support, volumeException: Boolean(volumeException) };
          }
          peakSetup = undefined;
        }
        if (!config.zeroEntry) continue;
      }

      if (config.zeroEntry) {
        if (zone && (i - zone.index > 8 || b.c < zone.low)) zone = undefined;
        const freshEarlyMacd = config.allowFreshEarlyMacd && zone && lastZeroUp >= 0
          && lastZeroUp <= zone.firstIndex && zone.firstIndex - lastZeroUp <= 4 && mid[hi]?.structure === 1;
        const crossIsValid = config.allowMacdCrossBeforeSqueeze ? lastZeroUp >= 0
          : lastZeroUp > zone?.firstIndex || freshEarlyMacd;
        const zeroConfirmed = config.zeroEntry === 'none' || (zone && crossIsValid && b[config.zeroEntry] > 0);
        const priceConfirmed = config.skipSqueezeHighBreakout || b.c > zone?.high;
        const longs = entryFunnel.long;
        if (zone) {
          longs.zone++;
          if (side === 1) {
            longs.bullishTrigger++;
            if (lastBullishOrder > zone.firstIndex) {
              longs.goldenTriangle++;
              if (zeroConfirmed) {
                longs.macdConfirmed++;
                if (priceConfirmed) longs.priceBreakout++;
              }
            }
          }
        }
        if (zone && side === 1 && lastBullishOrder > zone.firstIndex && zeroConfirmed && priceConfirmed) {
          const resistance = mid[hi]?.top;
          const support = mid[hi]?.bottom;
          const distance = (b.c - resistance) / b.c;
          const nearResistance = Math.abs(distance) <= 0.01;
          const upVolumeBreakout = distance > 0.01 && b.c > small[i - 4].c
            && small.slice(i - 3, i + 1).some(row => row.upVolume);
          const weakDownReclaim = config.allowWeakDownReclaim && Number.isFinite(support) && b.c > support
            && small.slice(i - 3, i).some(row => row.weakDown && b.c > row.h);
          const longEntryGate = nearResistance ? 'nearResistance'
            : upVolumeBreakout ? 'upVolumeBreakout' : weakDownReclaim ? 'weakDownReclaim' : 'blocked';
          if (config.resistanceLongEntry) {
            resistanceLongChecks.candidates++;
            resistanceLongChecks[longEntryGate]++;
          }
          if (config.isolatedSide !== 'SHORT' && (!config.resistanceLongEntry || longEntryGate !== 'blocked')) {
            entryFunnel.long.distanceOrVolume++;
            pending = pending?.side === -1 ? undefined : { type: 'entry', side: 1, stop: zone.low, fraction: 0.5,
              setup: 'squeeze_triangle_macd_zero', resonance: resonanceFor(1), signal: time,
              resistance, longEntryGate: config.resistanceLongEntry ? longEntryGate : undefined,
              crossAtOrBeforeSqueeze: lastZeroUp <= zone.firstIndex, noHighBreakout: b.c <= zone.high,
              macdLeadMinutes: (zone.firstIndex - lastZeroUp) * 15, macdAgeMinutes: (i - lastZeroUp) * 15,
              hourlyStructure: mid[hi]?.structure ?? 0 };
          }
          zone = undefined;
        } else if (spread(b) <= config.squeeze * b.atr) {
          const window = small.slice(i - 3, i + 1);
          const firstIndex = zone?.index === i - 1 ? zone.firstIndex : i;
          zone = { high: Math.max(...window.map(x => x.h)), low: Math.min(...window.map(x => x.l)), index: i, firstIndex };
        }
        if (policySchedule && marketEntryPolicy === 'countertrend_gate') {
          const hour = Math.floor(time / (4 * bar)) * 4 * bar;
          if (pending && policySchedule[hour] === -pending.side) pending = undefined;
        } else if (policySchedule && !pending && policySchedule[time]) {
          const direction = policySchedule[time];
          const volumeConfirms = direction === 1 ? b.upVolume : b.downVolume;
          if (marketEntryPolicy !== 'range_breakout_volume' || volumeConfirms) {
            pending = { type: 'entry', side: direction, fraction: 0.5, setup: 'squeeze_continuation',
              resonance: resonanceFor(direction), signal: time, trend4 };
          }
        }
        if (!position && config.rsi4hPeriod && big[bi]?.t + 16 * bar === time) {
          const rsi = big[bi].rsi;
          const direction = rsi < 20 ? 1 : rsi > 80 ? -1 : 0;
          const conflict = direction !== 0 && pending?.side === -direction;
          const candidate = direction !== 0 && (!pending || (conflict && config.rsi4hPriority));
          const entryEr20 = config.rsiRangeOnly && direction ? rangeEfficiencyRatio(small, i) : undefined;
          const passesRange = !config.rsiRangeOnly || entryEr20 < rangeErLimit;
          const useRsi = candidate && passesRange;
          if (config.rsiRangeOnly && candidate) rsiRangeGate[passesRange ? 'allowed' : 'blocked']++;
          if (conflict && passesRange) rsi4hConflicts.push({ time: iso(time), rsi, originalSide: pending.side, rsiSide: direction,
            chosenSide: useRsi ? direction : pending.side });
          if (useRsi) pending = { type: 'entry', side: direction, fraction: 0.5, setup: 'rsi_4h_extreme',
            resonance: resonanceFor(direction), signal: time, trend4, entryRsi4h: rsi, entryEr20 };
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
  return { config, endingEquity: cash, drawdown, peak, lowEquity, yearlyEquity, ...(config.reportWindow ? { windowDrawdown } : {}), maximumExposure, rejected, rejectedAdds, coverage, years, months, overall: statistics(trades), byResonance: by('resonance'), bySetup: by('setup'), bySide: by('side'), byExit: by('reason'), diagnostics, entryFunnel, ...(config.supportShortEntry ? { supportShortChecks } : {}), ...(config.resistanceLongEntry ? { resistanceLongChecks } : {}), ...(config.rsi4hPeriod ? { rsi4hConflicts } : {}), ...(config.rsiRangeOnly ? { rsiRangeGate } : {}), ...(ladder ? { ladderAudit } : {}), trades, balances };
}

function backtest(config) {
  return simulate(config).next().value;
}

function backtestShared(btcConfig, ethConfig) {
  const ethStart = Date.parse(ethSince);
  if (!ethSource || !Number.isFinite(ethStart) || ethStart < start || ethStart >= end || ethStart % bar) {
    throw Error('Expected an ETH data path and a 15-minute ETH start within the portfolio window');
  }
  const ethMarket = loadMarket(ethSource, ethStart);
  const accounts = [
    { asset: 'BTC', config: btcConfig, firstTradeAt: start, history: segments },
    { asset: 'ETH', config: ethConfig, firstTradeAt: ethStart, history: ethMarket.segments },
  ].map(account => {
    const stream = simulate(account.config, { history: account.history, firstTradeAt: account.firstTradeAt, shared: true });
    return { ...account, stream, open: stream.next() };
  });
  const grossLimit = 5;
  const reserve = 1 + 2 * grossLimit * btcConfig.fee;
  for (let time = start; time < end; time += bar) {
    const active = accounts.filter(account => account.firstTradeAt <= time);
    if (active.some(({ open }) => open.done || open.value.time !== time)) throw Error(`Missing portfolio bar at ${iso(time)}`);
    const orders = active.filter(({ open }) => open.value.order);
    // Each strategy ledger starts at the same seed to track its own contribution.
    const equity = sum(active.map(({ open }) => open.value.equity)) - (active.length - 1) * startingEquity;
    const existing = sum(active.map(({ open }) => open.value.gross));
    const grossPerOrder = orders.length ? (grossLimit * equity - existing) / reserve / orders.length : 0;
    for (const account of active) {
      const { order } = account.open.value;
      let quantity = 0;
      if (order) {
        const { leverage, quantityStep = minQty, minOrderNotional } = account.config;
        const notional = Math.min(leverage * equity / reserve, grossPerOrder);
        quantity = roundOrder(notional / order.entry, order.reference, quantityStep, minOrderNotional);
      }
      account.open = account.stream.next(quantity);
    }
  }
  if (accounts.some(({ open }) => !open.done)) throw Error('Unexpected bars after portfolio cutoff');
  return accounts.map(({ asset, open }) => [asset, open.value]);
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
const supportShortBase = atrTimeoutReview.find(([name]) => name.endsWith('_capped'));
const supportShortReview = [
  supportShortBase,
  ['original_short_near_support', { ...supportShortBase[1], supportShortEntry: 'original' }],
  ['ma_cross_short_near_support', { ...supportShortBase[1], supportShortEntry: 'ma_cross' }],
  ['original_short_either_side_of_support', { ...supportShortBase[1], supportShortEntry: 'original', allowNearBelow: true }],
  ['ma_cross_short_either_side_of_support', { ...supportShortBase[1], supportShortEntry: 'ma_cross', allowNearBelow: true }],
];
const supportVolumeSettings = { ...supportShortBase[1], supportShortEntry: 'original', allowNearBelow: true, supportDistance: 0.01 };
const supportVolumeReview = [
  supportShortBase,
  supportShortReview.find(([name]) => name === 'original_short_either_side_of_support'),
  ['support_1pct', supportVolumeSettings],
  ['support_1pct_or_volume_15m', { ...supportVolumeSettings, volumeExceptionBars: 1 }],
  ['support_1pct_or_volume_1h', { ...supportVolumeSettings, volumeExceptionBars: 4 }],
];
const twoSideVolumeBase = supportVolumeReview.find(([name]) => name === 'support_1pct_or_volume_1h');
const twoSideVolumeReview = [
  supportShortBase,
  twoSideVolumeBase,
  ['both_sides_volume', { ...twoSideVolumeBase[1], resistanceLongEntry: true }],
  ['both_sides_volume_and_weak_down', { ...twoSideVolumeBase[1], resistanceLongEntry: true, allowWeakDownReclaim: true }],
];
const relaxedLongBase = twoSideVolumeReview.find(([name]) => name === 'both_sides_volume');
const relaxedLongReview = [
  relaxedLongBase,
  ['long_without_high_breakout', { ...relaxedLongBase[1], skipSqueezeHighBreakout: true }],
  ['long_macd_before_squeeze', { ...relaxedLongBase[1], allowMacdCrossBeforeSqueeze: true }],
  ['long_both_relaxed', { ...relaxedLongBase[1], skipSqueezeHighBreakout: true, allowMacdCrossBeforeSqueeze: true }],
];
const robustnessReview = [
  relaxedLongBase,
  ['cost_only', { ...relaxedLongBase[1], fee: 0.00055 }],
  ['fresh_early_macd_with_cost', { ...relaxedLongBase[1], fee: 0.00055, allowFreshEarlyMacd: true }],
  ['relaxed_both_with_cost', { ...relaxedLongBase[1], skipSqueezeHighBreakout: true, allowMacdCrossBeforeSqueeze: true, fee: 0.00055 }],
];
const userFeeReview = [
  ['actual_fee_5x_cap', { ...relaxedLongBase[1], fee: 0.0005 }],
];
// Match the 2.5x single-asset portfolio replay, including its 5x fee reserve.
const btcSingleAsset = { ...userFeeReview[0][1], leverage: 2.5, feeReserveLeverage: 5, minOrderNotional: 100 };
const marketEntryModes = ['countertrend_gate', 'confirmed_breakout', 'developing_breakout', 'range_breakout', 'range_breakout_volume'];
const profitExitModes = ['profit_close_lock', 'profit_runner', 'profit_hour_only'];
const marketEntryConfig = (config, asset, policy) => ({ ...config, marketEntryAsset: asset, marketEntryPolicy: policy });
for (const mode of marketEntryModes) {
  scenarioSets[`btc_${mode}`] = [['BTC', marketEntryConfig(btcSingleAsset, 'BTC', mode)]];
}
for (const mode of profitExitModes) scenarioSets[`btc_${mode}`] = [['BTC', { ...btcSingleAsset, profitExit: mode }]];
const ladderConfig = (config, asset, maxHours, overlay = false) => ({ ...config,
  ...(overlay ? { ladderOverlay: true } : { takeProfitSteps: undefined, rangeTimeout: false }),
  ladderAsset: asset, ladderScale: asset === 'BTC' ? 10 : 100, ladderMaxHours: maxHours });
const btcLadderReview = {
  btc_ladder: [['BTC', ladderConfig(btcSingleAsset, 'BTC', 0)]],
  btc_ladder_72h: [['BTC', ladderConfig(btcSingleAsset, 'BTC', 72)]],
  btc_ladder_overlay: [['BTC', ladderConfig(btcSingleAsset, 'BTC', 0, true)]],
};
Object.assign(scenarioSets, btcLadderReview);
const btcRsi4h = { ...btcSingleAsset, rsi4hPeriod: 6 };
const btcRsiPriority = { ...btcRsi4h, rsi4hPriority: true };
const btcRsiHoldConfigs = Array.from({ length: 24 }, (_, index) => index + 1).flatMap(hours => {
  const config = { ...btcRsiPriority, rsiMinHoldHours: hours };
  return [[`hold${hours}h`, config], [`range_hold${hours}h`, { ...config, rsiRangeOnly: true }]];
});
const btcRsi4hReview = {
  btc_rsi_4h_control: [['original', btcSingleAsset]],
  btc_rsi_4h_add: [['with_rsi_4h', btcRsi4h]],
  btc_rsi_4h_priority: [['rsi_4h_priority', btcRsiPriority]],
};
for (const [hold, config] of btcRsiHoldConfigs) {
  btcRsi4hReview[`btc_rsi_4h_${hold}`] = [[`rsi_4h_${hold}`, config]];
}
Object.assign(scenarioSets, btcRsi4hReview);
const ethContract = { quantityStep: 0.01, minOrderNotional: 5 };
const ethReview = [
  ['eth_current_strategy', { ...userFeeReview[0][1], ...ethContract }],
  ['eth_without_price_and_volume_gates', { ...supportShortBase[1], ...ethContract, fee: 0.0005 }],
  ['eth_finer_lot_diagnostic', { ...userFeeReview[0][1], ...ethContract, quantityStep: 0.001 }],
];
const btcSideReview = ['LONG', 'SHORT'].map(side => [
  'btc_' + side.toLowerCase() + '_only', { ...userFeeReview[0][1], isolatedSide: side },
]);
const ethSideReview = ['LONG', 'SHORT'].map(side => [
  'eth_' + side.toLowerCase() + '_only', { ...ethReview[0][1], isolatedSide: side },
]);
const scenarios = experiment === 'btc_side_review' ? btcSideReview : experiment === 'eth_side_review' ? ethSideReview : experiment === 'eth_review' ? ethReview : experiment === 'user_fee_review' ? userFeeReview : experiment === 'robustness_review' ? robustnessReview : experiment === 'relaxed_long_review' ? relaxedLongReview : experiment === 'two_side_volume_review' ? twoSideVolumeReview : experiment === 'support_volume_review' ? supportVolumeReview : experiment === 'support_short_review' ? supportShortReview : experiment === 'atr_timeout_review' ? atrTimeoutReview : experiment === 'confirmation_8h_only' ? [selectedShort8h] : experiment === 'combined_review' ? combinedReview : scenarioSets[experiment] ?? legacyScenarios;
const sharedBtcConfigs = {
  btc_eth_shared_control: btcSingleAsset,
  btc_eth_shared_ladder: btcLadderReview.btc_ladder[0][1],
  btc_eth_shared_ladder_72h: btcLadderReview.btc_ladder_72h[0][1],
  btc_eth_shared_ladder_overlay: btcLadderReview.btc_ladder_overlay[0][1],
  btc_eth_shared_original_priority: btcRsi4h,
  btc_eth_shared_rsi: btcRsiPriority,
};
for (const [hold, config] of btcRsiHoldConfigs) sharedBtcConfigs[`btc_eth_shared_rsi_${hold}`] = config;
for (const mode of marketEntryModes) sharedBtcConfigs[`btc_eth_shared_${mode}`] = marketEntryConfig(btcSingleAsset, 'BTC', mode);
for (const mode of profitExitModes) sharedBtcConfigs[`btc_eth_shared_${mode}`] = { ...btcSingleAsset, profitExit: mode };
const sharedPortfolio = Object.hasOwn(sharedBtcConfigs, experiment);
const sharedBtc = sharedBtcConfigs[experiment];
const ethSingleAsset = { ...btcSingleAsset, ...ethContract, profitExit: sharedBtc?.profitExit };
const sharedEth = sharedBtc?.marketEntryPolicy
  ? marketEntryConfig(ethSingleAsset, 'ETH', sharedBtc.marketEntryPolicy) : ethSingleAsset;
const results = sharedPortfolio
  ? backtestShared(sharedBtc, sharedBtc.ladderScale === undefined ? sharedEth
    : ladderConfig(sharedEth, 'ETH', sharedBtc.ladderMaxHours, sharedBtc.ladderOverlay))
  : scenarios.map(([label, config]) => [label, backtest(config)]);

const summaries = {};
const tradeRows = [];
for (const [label, { trades, balances, ...summary }] of results) {
  summaries[label] = summary;
  const exportScenarios = experiment === 'take_profit_review' ? ['take_profit_5_steps_actual', 'take_profit_5_steps_ideal'] : experiment === 'long_exit_review' ? ['long_only_half_r', 'long_only_ma_cross_15m'] : experiment === 'resonance_sizing' ? ['base_15m', 'triple_double_risk', 'triple_double_squeeze_only'] : experiment === 'signal_exit'
    ? ['roi_stop_2pct_full_r', 'roi_stop_2pct_profit_only', 'roi_stop_2pct_fractional', 'price_stop_2pct_fractional']
    : experiment === 'short' ? ['order_limits', 'max_2h', 'max_2h_macd_with_higher', '15m_macd_2h'] : ['base', 'order_limits', 'triple_only', 'one_x', 'order_limits_stress'];
  if (sharedPortfolio || summary.config.marketEntryPolicy || summary.config.profitExit || Object.hasOwn(btcRsi4hReview, experiment) || Object.hasOwn(btcLadderReview, experiment) || experiment === 'btc_side_review' || experiment === 'eth_side_review' || experiment === 'eth_review' || experiment === 'user_fee_review' || experiment === 'robustness_review' || experiment === 'relaxed_long_review' || experiment === 'two_side_volume_review' || experiment === 'support_volume_review' || experiment === 'support_short_review' || experiment === 'atr_timeout_review' || exportScenarios.includes(label) || (['one_cut_review', 'full_exposure_review', 'zero_entry_review', 'near_zero_review', 'above_zero_review', 'no_leverage_review', 'below_zero_review', 'fixed_dif_review', 'selected_atr_review', 'peak_short_review', 'immediate_peak_review', 'confirmation_peak_review', 'confirmation_8h_only', 'combined_review', 'er_review'].includes(experiment) && summary.config.takeProfitFraction)) {
    tradeRows.push(...trades.map(trade => ({ scenario: label, ...trade })));
  }
  if (label === 'base' || experiment === 'confirmation_8h_only') {
    writeFileSync(`${output}_equity.csv`, ['time,equity', ...balances.map(row => `${row.time},${row.equity}`)].join('\n') + '\n');
  }
}
if (tradeRows.length) {
  const columns = [...new Set(tradeRows.flatMap(Object.keys))];
  writeFileSync(`${output}_trades.csv`, [columns.join(','), ...tradeRows.map(row => columns.map(k => row[k]).join(','))].join('\n') + '\n');
}
const inWindow = input.filter(b => b.t >= start).length;
const expected = (end - start) / bar;
const result = { since: iso(start), until: iso(end), observedCandles: inWindow, expectedCandles: expected, continuous: inWindow === expected, summaries };
writeFileSync(`${output}_summary.json`, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));

