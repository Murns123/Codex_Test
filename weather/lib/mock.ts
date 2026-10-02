// Deterministic demo data so the UI can be developed offline (WEATHER_MOCK=1).
import { CITIES, type City } from "./cities";
import type { CitySummary, Day, Hour, WeatherData } from "./types";
import { tzOffsetMs } from "./time";

function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const hash = (str: string) => [...str].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) % 2147483647, 7);

const CODES = [0, 1, 2, 3, 61, 80, 2, 1, 95, 63, 3, 45];

function baseTemp(city: City) {
  return city.country === "MY" ? 31 : city.country === "NL" ? 13 : city.country === "ZA" ? 22 : 18;
}

export function mockWeather(city: City): WeatherData {
  const rand = seeded(hash(city.id));
  const nowSec = Math.floor(Date.now() / 1000);
  const offset = tzOffsetMs(city.tz) / 1000;
  const localMidnight = Math.floor((nowSec + offset) / 86400) * 86400 - offset;
  const hourStart = nowSec - (nowSec % 3600);
  const base = baseTemp(city);

  const daily: Day[] = Array.from({ length: 7 }, (_, i) => {
    const max = base + 4 + rand() * 6 - i * 0.4;
    const code = CODES[Math.floor(rand() * CODES.length)];
    return {
      time: localMidnight + i * 86400,
      code,
      max,
      min: max - 7 - rand() * 4,
      pop: code >= 61 ? 60 + Math.round(rand() * 35) : Math.round(rand() * 25),
      precip: code >= 61 ? rand() * 12 : 0,
      sunrise: localMidnight + i * 86400 + 6 * 3600 + 20 * 60 + i * 60,
      sunset: localMidnight + i * 86400 + 18 * 3600 + 40 * 60 + i * 90,
      uvMax: 3 + rand() * 8,
      windMax: 12 + rand() * 30,
      windDir: Math.round(rand() * 360),
    };
  });

  const hourly: Hour[] = Array.from({ length: 25 }, (_, i) => {
    const t = hourStart + i * 3600;
    const localHour = ((t + offset) % 86400) / 3600;
    const diurnal = Math.sin(((localHour - 9) / 24) * 2 * Math.PI);
    const rainy = i >= 5 && i <= 9;
    return {
      time: t,
      temp: base + diurnal * 5 + rand() * 0.8,
      pop: rainy ? 55 + Math.round(rand() * 35) : Math.round(rand() * 20),
      precip: rainy ? rand() * 2 : 0,
      code: rainy ? (i === 7 ? 63 : 61) : i < 5 ? 1 : 2,
      isDay: localHour > 6.3 && localHour < 18.7,
      wind: 10 + rand() * 20,
    };
  });

  const h = hourly[0];
  return {
    cityId: city.id,
    fetchedAt: Date.now(),
    current: {
      time: nowSec,
      temp: h.temp,
      feels: h.temp - 1.6,
      humidity: 58 + Math.round(rand() * 30),
      dewPoint: h.temp - 6,
      isDay: h.isDay,
      code: 2,
      cloud: 40,
      pressure: 1008 + Math.round(rand() * 14),
      pressureTrend: "falling",
      wind: h.wind,
      windDir: 225,
      gusts: h.wind + 14,
      precip: 0,
      uv: h.isDay ? 4.2 : 0,
      visibility: 24000,
    },
    hourly,
    daily,
    yesterday: { max: daily[0].max - 3.2, min: daily[0].min - 1, daylight: daily[0].sunset - daily[0].sunrise - 120 },
    air: { usAqi: 38, pm25: 7.4, pm10: 14.1 },
  };
}

export function mockSummaries(): CitySummary[] {
  return CITIES.map((c) => {
    const w = mockWeather(c);
    return { id: c.id, temp: w.current.temp, code: w.hourly[0].code, isDay: w.current.isDay, max: w.daily[0].max, min: w.daily[0].min };
  });
}
