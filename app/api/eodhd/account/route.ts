import { getEodhdAccount } from "@/lib/eodhd";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    return NextResponse.json(await getEodhdAccount());
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
