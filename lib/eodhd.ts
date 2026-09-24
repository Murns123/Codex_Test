import { requiredEnv } from "@/lib/config";
import type { Bar, Candidate, Market, Quote } from "@/lib/types";

const BASE = "https://eodhd.com/api/";

async function call<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const token = requiredEnv("EODHD_API_TOKEN");
  const url = new URL(path, BASE);
  url.searchParams.set("api_token", token);
  url.searchParams.set("fmt", "json");

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`EODHD ${response.status}: ${body.slice(0, 500)}`);
  }
  return response.json() as Promise<T>;
}

export async function getEodhdAccount() {
  return call<Record<string, unknown>>("user");
}

export async function getQuote(symbol: string): Promise<Quote> {
  const raw = await call<Record<string, unknown>>(`real-time/${encodeURIComponent(symbol)}`);
  const close = Number(raw.close ?? raw.previousClose ?? 0);
  return {
    code: String(raw.code ?? symbol),
    timestamp: raw.timestamp == null ? null : Number(raw.timestamp),
    close,
    previousClose: raw.previousClose == null ? null : Number(raw.previousClose),
    changePct: raw.change_p == null ? null : Number(raw.change_p),
    volume: raw.volume == null ? null : Number(raw.volume),
  };
}

export async function getHistory(symbol: string, days = 420): Promise<Bar[]> {
  const from = new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
  const rows = await call<Array<Record<string, unknown>>>(`eod/${encodeURIComponent(symbol)}`, {
    from,
    period: "d",
    order: "a",
  });

  return rows
    .map((row) => ({
      date: String(row.date),
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
      adjustedClose: Number(row.adjusted_close ?? row.close),
      volume: Number(row.volume ?? 0),
    }))
    .filter((row) => Number.isFinite(row.adjustedClose) && row.adjustedClose > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export async function getSentiment(symbol: string): Promise<number | null> {
  const from = new Date(Date.now() - 7 * 86_400_000).toISOString().slice(0, 10);
  const to = new Date().toISOString().slice(0, 10);
  const raw = await call<unknown>("sentiments", { s: symbol, from, to });

  const values: number[] = [];
  const walk = (value: unknown) => {
    if (Array.isArray(value)) return value.forEach(walk);
    if (value && typeof value === "object") {
      for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
        if ((key === "normalized" || key === "sentiment") && typeof child === "number") values.push(child);
        else walk(child);
      }
    }
  };
  walk(raw);

  if (!values.length) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export async function getUsdAud(): Promise<number> {
  const quote = await getQuote("USDAUD.FOREX");
  if (!quote.close || quote.close <= 0) throw new Error("Could not resolve USD/AUD FX rate");
  return quote.close;
}

export async function screenMarket(market: Market, limit = 8): Promise<Candidate[]> {
  const filters =
    market === "US"
      ? [["exchange", "=", "us"], ["adjusted_close", ">", 1], ["market_capitalization", ">", 300000000], ["avgvol_200d", ">", 500000]]
      : [["exchange", "=", "au"], ["adjusted_close", ">", 1], ["market_capitalization", ">", 200000000], ["avgvol_200d", ">", 100000]];

  const raw = await call<{ data?: Candidate[] }>("screener", {
    filters: JSON.stringify(filters),
    sort: "refund_1d_p.desc",
    limit,
    offset: 0,
  });

  return Array.isArray(raw.data) ? raw.data : [];
}

export function marketFromSymbol(symbol: string): Market {
  return symbol.toUpperCase().endsWith(".AU") ? "AU" : "US";
}
