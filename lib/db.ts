import postgres from "postgres";
import { tradingConfig } from "@/lib/config";
import type { Market, Portfolio, Position } from "@/lib/types";

let sql: ReturnType<typeof postgres> | null = null;

function client() {
  if (!process.env.DATABASE_URL) return null;
  if (!sql) sql = postgres(process.env.DATABASE_URL, { ssl: "require", max: 1, idle_timeout: 20 });
  return sql;
}

export async function ensureSchema() {
  const db = client();
  if (!db) return false;

  await db`
    create table if not exists paper_account (
      id integer primary key,
      cash_aud numeric not null,
      starting_cash_aud numeric not null,
      updated_at timestamptz not null default now()
    )
  `;

  await db`
    create table if not exists paper_positions (
      symbol text primary key,
      market text not null,
      quantity numeric not null,
      avg_price_native numeric not null,
      cost_basis_aud numeric not null,
      last_price_native numeric not null,
      last_fx_to_aud numeric not null,
      opened_at timestamptz not null,
      updated_at timestamptz not null default now()
    )
  `;

  await db`
    create table if not exists paper_trades (
      id bigserial primary key,
      created_at timestamptz not null default now(),
      symbol text not null,
      market text not null,
      side text not null,
      quantity numeric not null,
      price_native numeric not null,
      fx_to_aud numeric not null,
      brokerage_aud numeric not null,
      gross_aud numeric not null,
      net_aud numeric not null,
      reason text,
      jev_buy_probability numeric,
      jev_sell_probability numeric,
      jev_attractive_entry numeric,
      jev_downside_risk numeric,
      strategy_version text not null default 'v1'
    )
  `;

  await db`
    create table if not exists strategy_runs (
      id bigserial primary key,
      created_at timestamptz not null default now(),
      market text not null,
      symbol text,
      status text not null,
      message text,
      payload jsonb
    )
  `;

  await db`
    insert into paper_account (id, cash_aud, starting_cash_aud)
    values (1, ${tradingConfig.startingCashAud}, ${tradingConfig.startingCashAud})
    on conflict (id) do nothing
  `;

  return true;
}

export async function getPortfolio(): Promise<Portfolio> {
  const db = client();
  if (!db) {
    return {
      cashAud: tradingConfig.startingCashAud,
      holdingsAud: 0,
      totalValueAud: tradingConfig.startingCashAud,
      startingCashAud: tradingConfig.startingCashAud,
      totalReturnAud: 0,
      totalReturnPct: 0,
      positions: [],
    };
  }

  await ensureSchema();
  const [account] = await db`select cash_aud, starting_cash_aud from paper_account where id = 1`;
  const rows = await db`
    select symbol, market, quantity, avg_price_native, cost_basis_aud,
           last_price_native, last_fx_to_aud, opened_at, updated_at
    from paper_positions
    order by opened_at asc
  `;

  const positions: Position[] = rows.map((r) => ({
    symbol: String(r.symbol),
    market: String(r.market) as Market,
    quantity: Number(r.quantity),
    avgPriceNative: Number(r.avg_price_native),
    costBasisAud: Number(r.cost_basis_aud),
    lastPriceNative: Number(r.last_price_native),
    lastFxToAud: Number(r.last_fx_to_aud),
    openedAt: new Date(r.opened_at).toISOString(),
    updatedAt: new Date(r.updated_at).toISOString(),
  }));

  const holdingsAud = positions.reduce((sum, p) => sum + p.quantity * p.lastPriceNative * p.lastFxToAud, 0);
  const cashAud = Number(account.cash_aud);
  const startingCashAud = Number(account.starting_cash_aud);
  const totalValueAud = cashAud + holdingsAud;
  const totalReturnAud = totalValueAud - startingCashAud;

  return {
    cashAud,
    holdingsAud,
    totalValueAud,
    startingCashAud,
    totalReturnAud,
    totalReturnPct: startingCashAud ? totalReturnAud / startingCashAud : 0,
    positions,
  };
}

export async function updateMark(symbol: string, priceNative: number, fxToAud: number) {
  const db = client();
  if (!db) return;
  await ensureSchema();
  await db`
    update paper_positions
    set last_price_native = ${priceNative},
        last_fx_to_aud = ${fxToAud},
        updated_at = now()
    where symbol = ${symbol}
  `;
}

export async function recordRun(market: Market, symbol: string | null, status: string, message: string, payload?: unknown) {
  const db = client();
  if (!db) return;
  await ensureSchema();
  await db`
    insert into strategy_runs (market, symbol, status, message, payload)
    values (${market}, ${symbol}, ${status}, ${message}, ${payload ? JSON.stringify(payload) : null})
  `;
}

export async function buyPosition(input: {
  symbol: string;
  market: Market;
  quantity: number;
  priceNative: number;
  fxToAud: number;
  brokerageAud: number;
  reason: string;
  jevBuyProbability?: number;
  jevAttractiveEntry?: number;
  jevDownsideRisk?: number;
}) {
  const db = client();
  if (!db) throw new Error("DATABASE_URL is required for paper execution");
  await ensureSchema();

  const grossAud = input.quantity * input.priceNative * input.fxToAud;
  const netAud = grossAud + input.brokerageAud;

  await db.begin(async (tx) => {
    const [account] = await tx`select cash_aud from paper_account where id = 1 for update`;
    const cash = Number(account.cash_aud);
    if (cash < netAud) throw new Error("Insufficient paper cash");

    const existing = await tx`select * from paper_positions where symbol = ${input.symbol} for update`;

    if (existing.length) {
      const row = existing[0];
      const oldQty = Number(row.quantity);
      const newQty = oldQty + input.quantity;
      const oldNativeCost = oldQty * Number(row.avg_price_native);
      const newAvgNative = (oldNativeCost + input.quantity * input.priceNative) / newQty;
      const newCostBasisAud = Number(row.cost_basis_aud) + netAud;

      await tx`
        update paper_positions
        set quantity = ${newQty},
            avg_price_native = ${newAvgNative},
            cost_basis_aud = ${newCostBasisAud},
            last_price_native = ${input.priceNative},
            last_fx_to_aud = ${input.fxToAud},
            updated_at = now()
        where symbol = ${input.symbol}
      `;
    } else {
      await tx`
        insert into paper_positions
          (symbol, market, quantity, avg_price_native, cost_basis_aud, last_price_native, last_fx_to_aud, opened_at, updated_at)
        values
          (${input.symbol}, ${input.market}, ${input.quantity}, ${input.priceNative}, ${netAud},
           ${input.priceNative}, ${input.fxToAud}, now(), now())
      `;
    }

    await tx`update paper_account set cash_aud = ${cash - netAud}, updated_at = now() where id = 1`;
    await tx`
      insert into paper_trades
        (symbol, market, side, quantity, price_native, fx_to_aud, brokerage_aud, gross_aud, net_aud,
         reason, jev_buy_probability, jev_attractive_entry, jev_downside_risk)
      values
        (${input.symbol}, ${input.market}, 'BUY', ${input.quantity}, ${input.priceNative}, ${input.fxToAud},
         ${input.brokerageAud}, ${grossAud}, ${netAud}, ${input.reason},
         ${input.jevBuyProbability ?? null}, ${input.jevAttractiveEntry ?? null}, ${input.jevDownsideRisk ?? null})
    `;
  });
}

export async function sellPosition(input: {
  symbol: string;
  priceNative: number;
  fxToAud: number;
  brokerageAud: number;
  reason: string;
  jevSellProbability?: number;
}) {
  const db = client();
  if (!db) throw new Error("DATABASE_URL is required for paper execution");
  await ensureSchema();

  await db.begin(async (tx) => {
    const rows = await tx`select * from paper_positions where symbol = ${input.symbol} for update`;
    if (!rows.length) return;

    const row = rows[0];
    const quantity = Number(row.quantity);
    const grossAud = quantity * input.priceNative * input.fxToAud;
    const netAud = Math.max(0, grossAud - input.brokerageAud);

    const [account] = await tx`select cash_aud from paper_account where id = 1 for update`;
    const cash = Number(account.cash_aud);

    await tx`delete from paper_positions where symbol = ${input.symbol}`;
    await tx`update paper_account set cash_aud = ${cash + netAud}, updated_at = now() where id = 1`;
    await tx`
      insert into paper_trades
        (symbol, market, side, quantity, price_native, fx_to_aud, brokerage_aud, gross_aud, net_aud,
         reason, jev_sell_probability)
      values
        (${input.symbol}, ${String(row.market)}, 'SELL', ${quantity}, ${input.priceNative}, ${input.fxToAud},
         ${input.brokerageAud}, ${grossAud}, ${netAud}, ${input.reason}, ${input.jevSellProbability ?? null})
    `;
  });
}

export async function recentTrades(limit = 50) {
  const db = client();
  if (!db) return [];
  await ensureSchema();
  return db`
    select *
    from paper_trades
    order by created_at desc
    limit ${limit}
  `;
}
