import { getPortfolio, recentTrades } from "@/lib/db";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    portfolio: await getPortfolio(),
    trades: await recentTrades(50),
  });
}
