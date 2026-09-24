import { runSymbol } from "@/lib/strategy";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const symbol = String(body.symbol ?? "").trim().toUpperCase();
    if (!symbol) return NextResponse.json({ error: "symbol is required, e.g. BHP.AU or AAPL.US" }, { status: 400 });
    return NextResponse.json(await runSymbol(symbol, false));
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
