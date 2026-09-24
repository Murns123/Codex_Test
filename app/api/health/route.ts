import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "jev-eodhd-paper-trader",
    timestamp: new Date().toISOString(),
    env: {
      eodhd: Boolean(process.env.EODHD_API_TOKEN),
      jev: Boolean(process.env.JEV_API_KEY),
      database: Boolean(process.env.DATABASE_URL),
      paperTradingEnabled: process.env.PAPER_TRADING_ENABLED === "true",
    },
  });
}
