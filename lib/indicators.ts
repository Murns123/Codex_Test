import type { Bar, Indicators } from "@/lib/types";

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function sma(values: number[], period: number): number | null {
  if (values.length < period) return null;
  return average(values.slice(-period));
}

function emaSeries(values: number[], period: number): number[] {
  if (!values.length) return [];
  const k = 2 / (period + 1);
  const output = [values[0]];
  for (let i = 1; i < values.length; i++) {
    output.push(values[i] * k + output[i - 1] * (1 - k));
  }
  return output;
}

function rsi(values: number[], period = 14): number | null {
  if (values.length <= period) return null;
  const changes = values.slice(-(period + 1)).slice(1).map((v, i) => v - values.slice(-(period + 1))[i]);
  const gains = changes.map((v) => Math.max(v, 0));
  const losses = changes.map((v) => Math.max(-v, 0));
  const avgGain = average(gains) ?? 0;
  const avgLoss = average(losses) ?? 0;
  if (avgLoss === 0) return avgGain > 0 ? 100 : 50;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

function atr(bars: Bar[], period = 14): number | null {
  if (bars.length <= period) return null;
  const recent = bars.slice(-(period + 1));
  const tr: number[] = [];
  for (let i = 1; i < recent.length; i++) {
    const current = recent[i];
    const prevClose = recent[i - 1].adjustedClose;
    tr.push(Math.max(current.high - current.low, Math.abs(current.high - prevClose), Math.abs(current.low - prevClose)));
  }
  return average(tr);
}

export function calculateIndicators(bars: Bar[]): Indicators {
  const closes = bars.map((b) => b.adjustedClose);
  const volumes = bars.map((b) => b.volume);

  const ema12 = emaSeries(closes, 12);
  const ema26 = emaSeries(closes, 26);
  const macdSeries = closes.map((_, i) => (ema12[i] ?? 0) - (ema26[i] ?? 0));
  const signalSeries = emaSeries(macdSeries, 9);
  const macd = macdSeries.at(-1) ?? null;
  const macdSignal = signalSeries.at(-1) ?? null;

  const latest = closes.at(-1) ?? null;
  const twentyAgo = closes.length > 20 ? closes.at(-21)! : null;
  const recent52w = closes.slice(-252);
  const avgVolume20 = sma(volumes.slice(0, -1), 20);
  const latestVolume = volumes.at(-1) ?? null;

  return {
    sma20: sma(closes, 20),
    sma50: sma(closes, 50),
    sma200: sma(closes, 200),
    rsi14: rsi(closes, 14),
    atr14: atr(bars, 14),
    macd,
    macdSignal,
    macdHistogram: macd != null && macdSignal != null ? macd - macdSignal : null,
    return20dPct: latest != null && twentyAgo ? ((latest / twentyAgo) - 1) * 100 : null,
    volumeRatio20: latestVolume != null && avgVolume20 ? latestVolume / avgVolume20 : null,
    high52w: recent52w.length ? Math.max(...recent52w) : null,
    low52w: recent52w.length ? Math.min(...recent52w) : null,
  };
}
