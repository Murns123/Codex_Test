const numberEnv = (name: string, fallback: number) => {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const tradingConfig = {
  startingCashAud: numberEnv("STARTING_CASH_AUD", 10_000),
  maxPositions: numberEnv("MAX_POSITIONS", 5),
  maxPositionPct: numberEnv("MAX_POSITION_PCT", 0.20),
  minSharePrice: numberEnv("MIN_SHARE_PRICE", 1),
  slippagePct: numberEnv("SLIPPAGE_PCT", 0.001),
  entryConfidence: numberEnv("ENTRY_CONFIDENCE", 0.75),
  minAttractiveEntry: numberEnv("MIN_ATTRACTIVE_ENTRY", 0.70),
  maxDownsideRisk: numberEnv("MAX_DOWNSIDE_RISK", 0.35),
  sellConfidence: numberEnv("SELL_CONFIDENCE", 0.70),
  stopLossPct: numberEnv("STOP_LOSS_PCT", 0.06),
  takeProfitPct: numberEnv("TAKE_PROFIT_PCT", 0.15),
  nabtradeFxSpreadPct: numberEnv("NABTRADE_FX_SPREAD_PCT", 0.0065),
  usSecFeeRate: numberEnv("US_SEC_FEE_RATE", 0.000000229),
  candidatesPerMarket: numberEnv("CANDIDATES_PER_MARKET", 8),
  paperTradingEnabled: process.env.PAPER_TRADING_ENABLED === "true",
  jevModel: process.env.JEV_MODEL || "jev-latest",
};

export function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}
