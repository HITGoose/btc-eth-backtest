export function ladderOnCandle(entry, side, state, { o, h, l, c }, favorableFirst, tickScale) {
  const favorable = side === 1 ? h : l;
  const adverse = side === 1 ? l : h;
  const path = favorableFirst ? [o, favorable, adverse, c] : [o, adverse, favorable, c];
  return ladderAlongPrices(entry, side, state, path, tickScale);
}

export function ladderAlongPrices(entry, side, state, path, tickScale) {
  let { stop, rung } = state;
  for (const price of path) {
    if ((price - stop) * side <= 0) return { stop, rung, hit: true };
    const movePct = 100 * (price - entry) * side / entry;
    const nextRung = Math.min(5, Math.floor(movePct + 1e-10) - 1);
    if (nextRung > rung) {
      rung = nextRung;
      stop = lockPrice(entry, side, rung, tickScale);
    }
  }
  return { stop, rung, hit: false };
}

function lockPrice(entry, side, rung, tickScale) {
  return Math.round(entry * (1 + side * rung * 0.01) * tickScale) / tickScale;
}

export function ladderCandleIsAmbiguous(entry, side, state, candle, first, second, tickScale) {
  if (first.stop !== second.stop || first.rung !== second.rung || first.hit !== second.hit) return true;
  if (first.rung < 2 || !first.hit) return false;
  const atOpen = ladderAlongPrices(entry, side, state, [candle.o], tickScale);
  if (atOpen.hit || first.rung - atOpen.rung < 2) return false;
  // Both extreme orders can exit at the highest rung even when an earlier
  // reversal could have stopped out at a lower rung on the way there.
  const intermediateStop = lockPrice(entry, side, first.rung - 1, tickScale);
  const adverse = side === 1 ? candle.l : candle.h;
  return (adverse - intermediateStop) * side <= 0;
}
