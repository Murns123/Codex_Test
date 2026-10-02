"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCity, type City } from "@/lib/cities";
import { buildInsights } from "@/lib/insights";
import { isThemeId, resolveTheme, type SkyPhase, type ThemeId } from "@/lib/themes";
import { clockParts, fmtAgo, fmtDateLong } from "@/lib/time";
import type { CitySummary, WeatherData } from "@/lib/types";
import { wmoKind, wmoLabel } from "@/lib/wmo";
import { AnalogClock } from "./AnalogClock";
import { CityStrip } from "./CityStrip";
import { CommandPalette } from "./CommandPalette";
import { DailyForecast } from "./DailyForecast";
import { HourlyTimeline } from "./HourlyTimeline";
import { IconPin, IconRefresh, IconSearch, IconSpark } from "./Icons";
import { Metrics } from "./Metrics";
import { Sky } from "./Sky";
import { SunMoonCard } from "./SunMoonCard";
import { ThemePicker } from "./ThemePicker";
import { useNow } from "./useNow";
import { WeatherIcon } from "./WeatherIcon";

const REFRESH_MS = 10 * 60 * 1000;
const STORAGE = { city: "mhwa.city", theme: "mhwa.theme" };

const store = {
  get(key: string) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* storage unavailable (private mode etc.) */
    }
  },
};

function skyPhase(d: WeatherData): SkyPhase {
  const t = d.current.time;
  const today = d.daily[0];
  if (today && (Math.abs(t - today.sunrise) < 2700 || Math.abs(t - today.sunset) < 2700)) return "golden";
  return d.current.isDay ? "day" : "night";
}

export function Dashboard({ initialCityId, cityFromUrl, initialWeather, initialSummaries }: {
  initialCityId: string;
  cityFromUrl: boolean;
  initialWeather: WeatherData | null;
  initialSummaries: CitySummary[];
}) {
  const [cityId, setCityId] = useState(initialCityId);
  const [cache, setCache] = useState<Record<string, WeatherData>>(initialWeather ? { [initialWeather.cityId]: initialWeather } : {});
  const [summaries, setSummaries] = useState(initialSummaries);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeId>("live");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const inflight = useRef<AbortController | null>(null);
  const now = useNow(30_000);

  const city = getCity(cityId) as City;
  const data = cache[cityId] ?? null;

  const load = useCallback(async (id: string) => {
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/weather?city=${encodeURIComponent(id)}`, { signal: ctrl.signal });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error ?? `Request failed (${res.status})`);
      setCache((c) => ({ ...c, [id]: body as WeatherData }));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message || "Could not load weather");
    } finally {
      if (inflight.current === ctrl) setLoading(false);
    }
  }, []);

  const loadSummaries = useCallback(async () => {
    try {
      const res = await fetch("/api/weather?scope=summary");
      if (res.ok) setSummaries(await res.json());
    } catch {
      /* the strip simply keeps its previous values */
    }
  }, []);

  const select = useCallback(
    (id: string) => {
      if (!getCity(id)) return;
      setCityId(id);
      store.set(STORAGE.city, id);
      const url = new URL(window.location.href);
      url.searchParams.set("city", id);
      window.history.replaceState(null, "", url);
      const cached = cache[id];
      if (!cached || Date.now() - cached.fetchedAt > REFRESH_MS) load(id);
    },
    [cache, load],
  );

  // Restore preferences after mount.
  useEffect(() => {
    const t = store.get(STORAGE.theme);
    if (isThemeId(t)) setTheme(t);
    const saved = store.get(STORAGE.city);
    if (!cityFromUrl && saved && saved !== initialCityId && getCity(saved)) select(saved);
    else if (!initialWeather) load(initialCityId);
    if (initialSummaries.length === 0) loadSummaries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Background refresh.
  useEffect(() => {
    const id = setInterval(() => {
      load(cityId);
      loadSummaries();
    }, REFRESH_MS);
    return () => clearInterval(id);
  }, [cityId, load, loadSummaries]);

  // ⌘K / Ctrl+K / "/" opens the city search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest?.("input, textarea");
      if (((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") || (e.key === "/" && !typing)) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const changeTheme = (t: ThemeId) => {
    setTheme(t);
    store.set(STORAGE.theme, t);
  };

  const kind = data ? wmoKind(data.current.code) : "partly";
  const phase: SkyPhase = data ? skyPhase(data) : "day";
  const vars = resolveTheme(theme, { country: city.country, kind, phase });
  const insights = useMemo(() => (data ? buildInsights(data, city.tz) : []), [data, city.tz]);
  const clock = now == null ? null : clockParts(now, city.tz);

  const style = {
    "--bg": vars.bg,
    "--fg": vars.fg,
    "--fg-muted": vars.fgMuted,
    "--glass": vars.glass,
    "--glass-strong": vars.glassStrong,
    "--glass-border": vars.glassBorder,
    "--accent": vars.accent,
    "--accent-2": vars.accent2,
  } as React.CSSProperties;

  return (
    <div className="app" style={style}>
      <div className="backdrop" />
      <Sky kind={kind} phase={phase} intensity={theme === "live" ? 1 : 0.55} />
      {loading && <div className="progress" role="progressbar" aria-label="Loading" />}

      <div className="shell">
        <header className="topbar">
          <button type="button" className="location" onClick={() => setPaletteOpen(true)} aria-label={`Change city (currently ${city.name})`}>
            <IconPin className="accent" />
            <span className="location-text">
              <span className="location-name">{city.name}</span>
              <span className="location-sub">
                {city.region}, {city.countryName}
              </span>
            </span>
            <span className="kbd-hint">
              <IconSearch size={14} />
              <kbd>⌘K</kbd>
            </span>
          </button>
          <div className="topbar-actions">
            <span className="updated hide-sm" aria-live="polite">
              {data && now != null ? `Updated ${fmtAgo(data.fetchedAt, now)}` : ""}
            </span>
            <button type="button" className="icon-btn" onClick={() => { load(cityId); loadSummaries(); }} aria-label="Refresh" disabled={loading}>
              <IconRefresh className={loading ? "spin" : undefined} />
            </button>
            <ThemePicker value={theme} onChange={changeTheme} />
          </div>
        </header>

        {error && data && (
          <div className="toast" role="status">
            Couldn&apos;t refresh — showing the last forecast. <button onClick={() => load(cityId)}>Retry</button>
          </div>
        )}

        {!data ? (
          <section className="card empty">
            {error ? (
              <>
                <h2>Weather is unavailable right now</h2>
                <p className="muted">{error}</p>
                <button type="button" className="btn" onClick={() => load(cityId)}>
                  Try again
                </button>
              </>
            ) : (
              <div className="skeleton-stack">
                <div className="skeleton" style={{ width: "40%" }} />
                <div className="skeleton tall" />
                <div className="skeleton" style={{ width: "70%" }} />
              </div>
            )}
          </section>
        ) : (
          <main className={`content${loading ? " is-loading" : ""}`} key={cityId}>
            <section className="hero">
              <div className="hero-main">
                <div className="hero-condition">
                  <WeatherIcon code={data.current.code} isDay={data.current.isDay} size={72} />
                  <span>{wmoLabel(data.current.code)}</span>
                </div>
                <div className="hero-temp">
                  {Math.round(data.current.temp)}
                  <span className="deg">°</span>
                </div>
                <p className="hero-sub">
                  Feels like {Math.round(data.current.feels)}° · H {Math.round(data.daily[0]?.max ?? data.current.temp)}° · L{" "}
                  {Math.round(data.daily[0]?.min ?? data.current.temp)}°
                </p>
                <ul className="insights" aria-label="Highlights">
                  {insights.map((i) => (
                    <li key={i.text} className={`insight tone-${i.tone}`}>
                      <IconSpark />
                      {i.text}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="hero-clock">
                <AnalogClock tz={city.tz} />
                <div className="digital" aria-live="off">
                  {clock ? (
                    <>
                      <span className="digital-hm">{clock.hm}</span>
                      <span className="digital-period">{clock.period}</span>
                    </>
                  ) : (
                    <span className="digital-hm">&nbsp;</span>
                  )}
                </div>
                <div className="muted small">{now != null ? fmtDateLong(now, city.tz) : " "}</div>
              </div>
            </section>

            <CityStrip summaries={summaries} selected={cityId} onSelect={select} />

            <section className="card">
              <h2 className="card-title">Next 24 hours</h2>
              <HourlyTimeline hours={data.hourly} tz={city.tz} />
            </section>

            <div className="grid">
              <section className="card daily-card">
                <h2 className="card-title">7-day forecast</h2>
                <DailyForecast days={data.daily} tz={city.tz} currentTemp={data.current.temp} />
              </section>
              <div className="tiles">
                {data.daily[0] && (
                  <SunMoonCard
                    today={data.daily[0]}
                    tomorrow={data.daily[1]}
                    tz={city.tz}
                    southern={city.lat < 0}
                    yesterdayDaylight={data.yesterday?.daylight ?? null}
                  />
                )}
                {data.daily[0] && <Metrics current={data.current} today={data.daily[0]} hours={data.hourly} air={data.air} tz={city.tz} />}
              </div>
            </div>
          </main>
        )}

        <footer className="footer">
          Weather data by{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
            Open-Meteo.com
          </a>{" "}
          (CC BY 4.0) · Times shown in {city.name} local time
        </footer>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onSelect={select} selected={cityId} summaries={summaries} />
    </div>
  );
}
