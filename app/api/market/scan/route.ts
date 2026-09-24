import { screenMarket } from "@/lib/eodhd";
import { NextRequest, NextResponse } from "next/server";
import type { Market } from "@/lib/types";

export async function GET(request: NextRequest) {
  try {
    const market = (request.nextUrl.searchParams.get("market") ?? "AU").toUpperCase() as Market;
    if (market !== "AU" && market !== "US") return NextResponse.json({ error: "market must be AU or US" }, { status: 400 });
    const data = await screenMarket(market, 20);
    return NextResponse.json({ market, data });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
