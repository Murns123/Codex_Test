"use client";

import { CITIES } from "@/lib/cities";
import type { CitySummary } from "@/lib/types";
import { clockParts } from "@/lib/time";
import { useNow } from "./useNow";
import { WeatherIcon } from "./WeatherIcon";

export function CityStrip({ summaries, selected, onSelect }: { summaries: CitySummary[]; selected: string; onSelect: (id: string) => void }) {
  const now = useNow(15_000);
  const byId = new Map(summaries.map((s) => [s.id, s]));

  return (
    <nav className="strip" aria-label="Your cities">
      {CITIES.map((c) => {
        const s = byId.get(c.id);
        const t = now == null ? null : clockParts(now, c.tz);
        return (
          <button key={c.id} type="button" className={`chip${c.id === selected ? " is-active" : ""}`} onClick={() => onSelect(c.id)} aria-pressed={c.id === selected}>
            <span className="chip-top">
              <span className="chip-name">{c.name}</span>
              <span className="chip-time">{t ? `${t.hm} ${t.period.toLowerCase()}` : " "}</span>
            </span>
            <span className="chip-bottom">
              {s ? (
                <>
                  <WeatherIcon code={s.code} isDay={s.isDay} size={26} animated={false} />
                  <span className="chip-temp">{Math.round(s.temp)}°</span>
                  <span className="chip-range">
                    {Math.round(s.max)}° / {Math.round(s.min)}°
                  </span>
                </>
              ) : (
                <span className="chip-range">{c.countryName}</span>
              )}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
