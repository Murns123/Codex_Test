import type { WeatherData } from "./types";
import { fmtHour } from "./time";
import { isWet, wmoLabel } from "./wmo";

export type Insight = { tone: "info" | "rain" | "warn"; text: string };

export function buildInsights(d: WeatherData, tz: string): Insight[] {
  const out: Insight[] = [];
  const next = d.hourly.slice(1);

  if (isWet(d.current.code) || d.current.precip > 0.1) {
    const dry = next.find((h) => !isWet(h.code) && h.pop < 40);
    out.push(
      dry
        ? { tone: "rain", text: `Rain easing around ${fmtHour(dry.time, tz)}` }
        : { tone: "rain", text: "Wet weather continuing through the next 24 hours" },
    );
  } else {
    const wet = next.slice(0, 12).find((h) => h.pop >= 50 || isWet(h.code));
    out.push(
      wet
        ? { tone: "rain", text: `Rain likely from ${fmtHour(wet.time, tz)} (${wet.pop}%)` }
        : { tone: "info", text: "No rain expected in the next 12 hours" },
    );
  }

  const today = d.daily[0];
  if (d.yesterday && today) {
    const diff = Math.round(today.max - d.yesterday.max);
    if (Math.abs(diff) >= 2) {
      out.push({ tone: "info", text: `${Math.abs(diff)}° ${diff > 0 ? "warmer" : "cooler"} than yesterday` });
    }
  }

  const gust = Math.max(d.current.gusts, ...next.slice(0, 12).map((h) => h.wind));
  if (gust >= 50) out.push({ tone: "warn", text: `Strong gusts up to ${Math.round(gust)} km/h` });

  if (today && today.uvMax >= 8) {
    out.push({ tone: "warn", text: `Very high UV (${Math.round(today.uvMax)}) around midday — sun protection recommended` });
  }

  return out.slice(0, 3);
}

export function headline(d: WeatherData) {
  const t = d.daily[0];
  return `${wmoLabel(d.current.code)}${t ? ` · High ${Math.round(t.max)}° · Low ${Math.round(t.min)}°` : ""}`;
}
