import { NextResponse, type NextRequest } from "next/server";
import { getCity } from "@/lib/cities";
import { getSummaries, getWeather } from "@/lib/weather";

const CACHE = "public, s-maxage=600, stale-while-revalidate=1800";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  try {
    if (params.get("scope") === "summary") {
      return NextResponse.json(await getSummaries(), { headers: { "Cache-Control": CACHE } });
    }
    const city = getCity(params.get("city"));
    if (!city) return NextResponse.json({ error: "Unknown city" }, { status: 400 });
    return NextResponse.json(await getWeather(city), { headers: { "Cache-Control": CACHE } });
  } catch (e) {
    console.error("weather api", e);
    return NextResponse.json({ error: "The weather service is not responding. Please try again shortly." }, { status: 502 });
  }
}
