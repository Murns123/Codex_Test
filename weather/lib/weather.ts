import "server-only";
import { CITIES, type City } from "./cities";
import { mockSummaries, mockWeather } from "./mock";
import type { AirQuality, CitySummary, Day, Hour, PressureTrend, WeatherData } from "./types";

const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality";
const REVALIDATE_SECONDS = 600;

const useMock = () => process.env.WEATHER_MOCK === "1";

type Series = Record<string, number[]>;
type ForecastResponse = {
  current: Record<string, number>;
  hourly: Series & { time: number[] };
  daily: Series & { time: number[] };
};

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
  if (!res.ok) throw new Error(`Open-Meteo ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function forecastUrl(city: City) {
  const q = new URLSearchParams({
    latitude: String(city.lat),
    longitude: String(city.lon),
    timezone: city.tz,
    timeformat: "unixtime",
    wind_speed_unit: "kmh",
    past_days: "1",
    forecast_days: "8",
    current: [
      "temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature", "is_day",
      "precipitation", "weather_code", "cloud_cover", "pressure_msl",
      "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    ].join(","),
    hourly: [
      "temperature_2m", "precipitation_probability", "precipitation", "weather_code", "is_day",
      "wind_speed_10m", "uv_index", "visibility", "pressure_msl",
    ].join(","),
    daily: [
      "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max",
      "precipitation_sum", "sunrise", "sunset", "uv_index_max", "wind_speed_10m_max",
      "wind_direction_10m_dominant",
    ].join(","),
  });
  return `${FORECAST_URL}?${q}`;
}

async function getAir(city: City): Promise<AirQuality | null> {
  try {
    const q = new URLSearchParams({
      latitude: String(city.lat),
      longitude: String(city.lon),
      timezone: city.tz,
      current: "us_aqi,pm2_5,pm10",
    });
    const r = await getJson<{ current: Record<string, number> }>(`${AIR_URL}?${q}`);
    if (r.current?.us_aqi == null) return null;
    return { usAqi: r.current.us_aqi, pm25: r.current.pm2_5, pm10: r.current.pm10 };
  } catch {
    return null; // Air quality is a nice-to-have; never fail the page for it.
  }
}

const n = (v: number | null | undefined, fallback = 0) => (typeof v === "number" && Number.isFinite(v) ? v : fallback);

function lastIndexAtOrBefore(times: number[], t: number) {
  let idx = 0;
  for (let i = 0; i < times.length; i++) if (times[i] <= t) idx = i;
  return idx;
}

export function normalize(cityId: string, f: ForecastResponse, air: AirQuality | null): WeatherData {
  const c = f.current;
  const H = f.hourly;
  const D = f.daily;
  const now = n(c.time, Math.floor(Date.now() / 1000));

  const h0 = lastIndexAtOrBefore(H.time, now);
  const hourly: Hour[] = [];
  for (let i = h0; i < Math.min(H.time.length, h0 + 25); i++) {
    hourly.push({
      time: H.time[i],
      temp: n(H.temperature_2m[i]),
      pop: Math.round(n(H.precipitation_probability[i])),
      precip: n(H.precipitation[i]),
      code: n(H.weather_code[i]),
      isDay: n(H.is_day[i]) === 1,
      wind: n(H.wind_speed_10m[i]),
    });
  }

  const pNow = n(H.pressure_msl[h0], n(c.pressure_msl));
  const pPast = n(H.pressure_msl[Math.max(0, h0 - 3)], pNow);
  const delta = pNow - pPast;
  const pressureTrend: PressureTrend = delta > 0.8 ? "rising" : delta < -0.8 ? "falling" : "steady";

  const d0 = lastIndexAtOrBefore(D.time, now);
  const day = (i: number): Day => ({
    time: D.time[i],
    code: n(D.weather_code[i]),
    max: n(D.temperature_2m_max[i]),
    min: n(D.temperature_2m_min[i]),
    pop: Math.round(n(D.precipitation_probability_max[i])),
    precip: n(D.precipitation_sum[i]),
    sunrise: n(D.sunrise[i]),
    sunset: n(D.sunset[i]),
    uvMax: n(D.uv_index_max[i]),
    windMax: n(D.wind_speed_10m_max[i]),
    windDir: n(D.wind_direction_10m_dominant[i]),
  });
  const daily: Day[] = [];
  for (let i = d0; i < Math.min(D.time.length, d0 + 7); i++) daily.push(day(i));
  const y = d0 > 0 ? day(d0 - 1) : null;

  return {
    cityId,
    fetchedAt: Date.now(),
    current: {
      time: now,
      temp: n(c.temperature_2m),
      feels: n(c.apparent_temperature),
      humidity: n(c.relative_humidity_2m),
      dewPoint: n(c.dew_point_2m),
      isDay: n(c.is_day) === 1,
      code: n(c.weather_code),
      cloud: n(c.cloud_cover),
      pressure: n(c.pressure_msl),
      pressureTrend,
      wind: n(c.wind_speed_10m),
      windDir: n(c.wind_direction_10m),
      gusts: n(c.wind_gusts_10m),
      precip: n(c.precipitation),
      uv: n(H.uv_index[h0]),
      visibility: n(H.visibility[h0], 10000),
    },
    hourly,
    daily,
    yesterday: y ? { max: y.max, min: y.min, daylight: y.sunset - y.sunrise } : null,
    air,
  };
}

export async function getWeather(city: City): Promise<WeatherData> {
  if (useMock()) return mockWeather(city);
  const [forecast, air] = await Promise.all([getJson<ForecastResponse>(forecastUrl(city)), getAir(city)]);
  return normalize(city.id, forecast, air);
}

/** Current conditions for every city in a single multi-location request. */
export async function getSummaries(): Promise<CitySummary[]> {
  if (useMock()) return mockSummaries();
  const q = new URLSearchParams({
    latitude: CITIES.map((c) => c.lat).join(","),
    longitude: CITIES.map((c) => c.lon).join(","),
    timezone: "auto",
    forecast_days: "1",
    current: "temperature_2m,weather_code,is_day",
    daily: "temperature_2m_max,temperature_2m_min",
  });
  const raw = await getJson<unknown>(`${FORECAST_URL}?${q}`);
  const list = (Array.isArray(raw) ? raw : [raw]) as Array<{ current: Record<string, number>; daily: Series }>;
  return CITIES.map((city, i) => {
    const r = list[i];
    return {
      id: city.id,
      temp: n(r?.current?.temperature_2m),
      code: n(r?.current?.weather_code),
      isDay: n(r?.current?.is_day) === 1,
      max: n(r?.daily?.temperature_2m_max?.[0]),
      min: n(r?.daily?.temperature_2m_min?.[0]),
    };
  });
}
