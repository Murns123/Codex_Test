export type Market = "AU" | "US";

export type Quote = {
  code: string;
  timestamp: number | null;
  close: number;
  previousClose: number | null;
  changePct: number | null;
  volume: number | null;
};

export type Bar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adjustedClose: number;
  volume: number;
};

export type Indicators = {
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  rsi14: number | null;
  atr14: number | null;
  macd: number | null;
  macdSignal: number | null;
  macdHistogram: number | null;
  return20dPct: number | null;
  volumeRatio20: number | null;
  high52w: number | null;
  low52w: number | null;
};

export type JevAnswer =
  | { type: "noul"; noul: number }
  | { type: "choice"; choice: string; confidence: number; probabilities: Record<string, number> }
  | { type: "score"; score: number; confidence: number; legend: Record<string, unknown>; probabilities: Record<string, number> };

export type JevEvaluation = {
  model: string;
  answers: Record<string, JevAnswer>;
  usage: { input_tokens: number; output_tokens: number };
};

export type Position = {
  symbol: string;
  market: Market;
  quantity: number;
  avgPriceNative: number;
  costBasisAud: number;
  lastPriceNative: number;
  lastFxToAud: number;
  openedAt: string;
  updatedAt: string;
};

export type Portfolio = {
  cashAud: number;
  holdingsAud: number;
  totalValueAud: number;
  startingCashAud: number;
  totalReturnAud: number;
  totalReturnPct: number;
  positions: Position[];
};

export type RiskDecision = {
  allowed: boolean;
  reason: string;
  targetAud: number;
};

export type Candidate = {
  code: string;
  name?: string;
  exchange?: string;
  adjusted_close?: number;
  market_capitalization?: number;
  avgvol_200d?: number;
  refund_1d_p?: number;
};
