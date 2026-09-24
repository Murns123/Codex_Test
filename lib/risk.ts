import { tradingConfig } from "@/lib/config";
import { choiceProbability, noul } from "@/lib/jev";
import type { JevEvaluation, Portfolio, RiskDecision } from "@/lib/types";

export function evaluateEntryRisk(
  portfolio: Portfolio,
  evaluation: JevEvaluation,
  nativePrice: number,
  fxToAud: number,
): RiskDecision {
  if (!Number.isFinite(nativePrice) || nativePrice < tradingConfig.minSharePrice) {
    return { allowed: false, reason: "Below minimum share price", targetAud: 0 };
  }

  const buyProbability = choiceProbability(evaluation, "buy");
  const attractive = noul(evaluation, "attractive_entry");
  const downside = noul(evaluation, "downside_risk_high");
  const overextended = noul(evaluation, "overextended");

  if (buyProbability < tradingConfig.entryConfidence) {
    return { allowed: false, reason: `JEV buy probability ${buyProbability.toFixed(2)} below threshold`, targetAud: 0 };
  }
  if (attractive < tradingConfig.minAttractiveEntry) {
    return { allowed: false, reason: `Entry quality ${attractive.toFixed(2)} below threshold`, targetAud: 0 };
  }
  if (downside > tradingConfig.maxDownsideRisk) {
    return { allowed: false, reason: `Downside risk ${downside.toFixed(2)} above threshold`, targetAud: 0 };
  }
  if (overextended > 0.70) {
    return { allowed: false, reason: `Overextension risk ${overextended.toFixed(2)}`, targetAud: 0 };
  }
  if (portfolio.positions.length >= tradingConfig.maxPositions) {
    return { allowed: false, reason: "Maximum open positions reached", targetAud: 0 };
  }

  const targetAud = Math.min(
    portfolio.totalValueAud * tradingConfig.maxPositionPct,
    portfolio.cashAud * 0.98,
  );
  const oneShareAud = nativePrice * fxToAud;
  if (targetAud < oneShareAud) {
    return { allowed: false, reason: "Insufficient cash for one whole share", targetAud: 0 };
  }

  return { allowed: true, reason: "Passed deterministic risk gates", targetAud };
}

export function shouldExit(
  evaluation: JevEvaluation,
  currentNativePrice: number,
  avgNativePrice: number,
): { exit: boolean; reason: string } {
  const returnPct = avgNativePrice > 0 ? currentNativePrice / avgNativePrice - 1 : 0;
  const sellProbability = choiceProbability(evaluation, "sell");

  if (returnPct <= -tradingConfig.stopLossPct) {
    return { exit: true, reason: `Stop loss triggered at ${(returnPct * 100).toFixed(2)}%` };
  }
  if (returnPct >= tradingConfig.takeProfitPct && sellProbability >= 0.50) {
    return { exit: true, reason: `Take-profit review triggered at ${(returnPct * 100).toFixed(2)}%` };
  }
  if (sellProbability >= tradingConfig.sellConfidence) {
    return { exit: true, reason: `JEV sell probability ${sellProbability.toFixed(2)}` };
  }
  return { exit: false, reason: "Hold" };
}
