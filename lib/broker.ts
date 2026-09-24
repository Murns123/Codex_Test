import { tradingConfig } from "@/lib/config";
import type { Market } from "@/lib/types";

export function nabtradeBrokerageAud(market: Market, tradeValueAud: number): number {
  if (market === "AU") {
    if (tradeValueAud <= 1_000) return 9.95;
    if (tradeValueAud <= 5_000) return 14.95;
    if (tradeValueAud <= 20_000) return 19.95;
    return tradeValueAud * 0.0011;
  }

  if (tradeValueAud <= 1_000) return 9.95;
  if (tradeValueAud <= 5_000) return 14.95;
  if (tradeValueAud <= 20_000) return 19.95;
  return tradeValueAud * 0.0011;
}

export function executionPrice(side: "BUY" | "SELL", quoted: number): number {
  return side === "BUY"
    ? quoted * (1 + tradingConfig.slippagePct)
    : quoted * (1 - tradingConfig.slippagePct);
}

export function fxToAudWithSpread(market: Market, spotFxToAud: number, side: "BUY" | "SELL"): number {
  if (market === "AU") return 1;
  const spread = tradingConfig.nabtradeFxSpreadPct;
  return side === "BUY" ? spotFxToAud * (1 + spread) : spotFxToAud * (1 - spread);
}
