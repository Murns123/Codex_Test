import { nabtradeBrokerageAud, executionPrice, fxToAudWithSpread } from "@/lib/broker";
import { tradingConfig } from "@/lib/config";
import { buyPosition, getPortfolio, recordRun, sellPosition, updateMark } from "@/lib/db";
import { getHistory, getQuote, getSentiment, getUsdAud, marketFromSymbol, screenMarket } from "@/lib/eodhd";
import { calculateIndicators } from "@/lib/indicators";
import { choiceProbability, evaluateWithJev, noul } from "@/lib/jev";
import { evaluateEntryRisk, shouldExit } from "@/lib/risk";
import type { Market } from "@/lib/types";

async function evaluateSymbol(symbol: string) {
  const market = marketFromSymbol(symbol);
  const [quote, bars, sentiment] = await Promise.all([
    getQuote(symbol),
    getHistory(symbol),
    getSentiment(symbol).catch(() => null),
  ]);
  const indicators = calculateIndicators(bars);
  const portfolio = await getPortfolio();
  const existing = portfolio.positions.find((p) => p.symbol === symbol);
  const spotFx = market === "US" ? await getUsdAud() : 1;

  const state = {
    timestamp: new Date().toISOString(),
    symbol,
    market,
    quote,
    indicators,
    news_sentiment_7d: sentiment,
    portfolio: {
      cash_aud: portfolio.cashAud,
      total_value_aud: portfolio.totalValueAud,
      open_positions: portfolio.positions.length,
      max_positions: tradingConfig.maxPositions,
      max_position_pct: tradingConfig.maxPositionPct,
    },
    existing_position: existing ?? null,
    constraints: {
      long_only: true,
      no_leverage: true,
      minimum_share_price: tradingConfig.minSharePrice,
    },
  };

  const evaluation = await evaluateWithJev(state);
  return { market, quote, indicators, sentiment, portfolio, existing, spotFx, evaluation, state };
}

export async function runSymbol(symbol: string, execute = false) {
  const ctx = await evaluateSymbol(symbol);
  const { market, quote, portfolio, existing, spotFx, evaluation } = ctx;

  await updateMark(symbol, quote.close, spotFx);

  if (existing) {
    const exit = shouldExit(evaluation, quote.close, existing.avgPriceNative);
    if (exit.exit && execute && tradingConfig.paperTradingEnabled) {
      const px = executionPrice("SELL", quote.close);
      const fx = fxToAudWithSpread(market, spotFx, "SELL");
      const grossAud = existing.quantity * px * fx;
      await sellPosition({
        symbol,
        priceNative: px,
        fxToAud: fx,
        brokerageAud: nabtradeBrokerageAud(market, grossAud),
        reason: exit.reason,
        jevSellProbability: choiceProbability(evaluation, "sell"),
      });
      await recordRun(market, symbol, "SOLD", exit.reason, evaluation);
      return { action: "SELL", executed: true, reason: exit.reason, evaluation };
    }
    await recordRun(market, symbol, "HOLD", exit.reason, evaluation);
    return { action: "HOLD", executed: false, reason: exit.reason, evaluation };
  }

  const entry = evaluateEntryRisk(portfolio, evaluation, quote.close, spotFx);
  if (!entry.allowed) {
    await recordRun(market, symbol, "REJECTED", entry.reason, evaluation);
    return { action: "REJECT", executed: false, reason: entry.reason, evaluation };
  }

  const buyPx = executionPrice("BUY", quote.close);
  const fx = fxToAudWithSpread(market, spotFx, "BUY");
  const approxShareAud = buyPx * fx;
  const quantity = Math.floor(entry.targetAud / approxShareAud);

  if (quantity < 1) {
    const reason = "Target allocation cannot buy one whole share";
    await recordRun(market, symbol, "REJECTED", reason, evaluation);
    return { action: "REJECT", executed: false, reason, evaluation };
  }

  const grossAud = quantity * buyPx * fx;
  const brokerageAud = nabtradeBrokerageAud(market, grossAud);

  if (execute && tradingConfig.paperTradingEnabled) {
    await buyPosition({
      symbol,
      market,
      quantity,
      priceNative: buyPx,
      fxToAud: fx,
      brokerageAud,
      reason: entry.reason,
      jevBuyProbability: choiceProbability(evaluation, "buy"),
      jevAttractiveEntry: noul(evaluation, "attractive_entry"),
      jevDownsideRisk: noul(evaluation, "downside_risk_high"),
    });
    await recordRun(market, symbol, "BOUGHT", entry.reason, evaluation);
    return { action: "BUY", executed: true, quantity, priceNative: buyPx, evaluation };
  }

  await recordRun(market, symbol, "BUY_CANDIDATE", entry.reason, evaluation);
  return { action: "BUY", executed: false, quantity, priceNative: buyPx, evaluation };
}

export async function scanAndRun(market: Market, execute = false) {
  const candidates = await screenMarket(market, tradingConfig.candidatesPerMarket);
  const suffix = market === "AU" ? ".AU" : ".US";
  const results = [];

  for (const candidate of candidates) {
    const code = String(candidate.code ?? "").trim();
    if (!code) continue;
    const symbol = code.includes(".") ? code : `${code}${suffix}`;
    try {
      results.push({ symbol, result: await runSymbol(symbol, execute) });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await recordRun(market, symbol, "ERROR", message);
      results.push({ symbol, error: message });
    }
  }

  return { market, count: results.length, execute, results };
}
