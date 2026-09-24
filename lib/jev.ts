import { requiredEnv, tradingConfig } from "@/lib/config";
import type { JevEvaluation } from "@/lib/types";

const JEV_BASE = "https://api.typesafe.ai";

export async function listJevModels() {
  const response = await fetch(`${JEV_BASE}/v1/models`, {
    headers: { Authorization: `Bearer ${requiredEnv("JEV_API_KEY")}` },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`JEV models ${response.status}: ${await response.text()}`);
  return response.json();
}

export async function evaluateWithJev(state: Record<string, unknown>): Promise<JevEvaluation> {
  const response = await fetch(`${JEV_BASE}/v1/systemone`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${requiredEnv("JEV_API_KEY")}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: tradingConfig.jevModel,
      state,
      questions: {
        momentum_positive: {
          type: "noul",
          instructions: "Is short-term price momentum convincingly positive given the supplied price, moving-average, MACD, RSI and volume data?",
        },
        overextended: {
          type: "noul",
          instructions: "Is the instrument currently overextended enough that initiating or adding to a long position has poor near-term timing?",
        },
        news_favourable: {
          type: "noul",
          instructions: "Is the supplied news/sentiment environment favourable for a long position?",
        },
        downside_risk_high: {
          type: "noul",
          instructions: "Is downside risk unusually high relative to the potential reward for a long-only paper trade?",
        },
        attractive_entry: {
          type: "noul",
          instructions: "Is the current price an attractive entry for a short-to-medium-term long position?",
        },
        action: {
          type: "choice",
          instructions: "Choose the most appropriate action for a long-only paper portfolio.",
          criteria: {
            buy: "Evidence supports initiating or adding to a long position now.",
            hold: "Evidence is mixed or neutral; do not initiate a new trade and retain an existing position if present.",
            sell: "Risk/reversal evidence supports closing or reducing an existing long position; do not open a new one.",
          },
        },
      },
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`JEV ${response.status}: ${body.slice(0, 1000)}`);
  }
  return response.json() as Promise<JevEvaluation>;
}

export function noul(evaluation: JevEvaluation, key: string): number {
  const answer = evaluation.answers[key];
  return answer?.type === "noul" ? answer.noul : 0;
}

export function choiceProbability(evaluation: JevEvaluation, choice: string): number {
  const answer = evaluation.answers.action;
  if (!answer || answer.type !== "choice") return 0;
  return answer.probabilities[choice] ?? 0;
}
