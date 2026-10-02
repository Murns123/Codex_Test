import { Dashboard } from "@/components/Dashboard";
import { DEFAULT_CITY_ID, getCity } from "@/lib/cities";
import { getSummaries, getWeather } from "@/lib/weather";

export default async function Page({ searchParams }: { searchParams: Promise<{ city?: string }> }) {
  const { city: requested } = await searchParams;
  const fromUrl = getCity(requested);
  const city = fromUrl ?? getCity(DEFAULT_CITY_ID)!;

  const [weather, summaries] = await Promise.allSettled([getWeather(city), getSummaries()]);

  return (
    <Dashboard
      initialCityId={city.id}
      cityFromUrl={Boolean(fromUrl)}
      initialWeather={weather.status === "fulfilled" ? weather.value : null}
      initialSummaries={summaries.status === "fulfilled" ? summaries.value : []}
    />
  );
}
