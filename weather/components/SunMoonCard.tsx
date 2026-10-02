"use client";

import type { Day } from "@/lib/types";
import { moonInfo } from "@/lib/moon";
import { fmtDuration, fmtTime } from "@/lib/time";
import { IconSunrise } from "./Icons";
import { MoonGlyph } from "./MoonGlyph";
import { useNow } from "./useNow";

export function SunMoonCard({ today, tomorrow, tz, southern, yesterdayDaylight }: {
  today: Day;
  tomorrow?: Day;
  tz: string;
  southern: boolean;
  yesterdayDaylight: number | null;
}) {
  const nowMs = useNow(60_000);
  const now = nowMs == null ? today.sunrise + (today.sunset - today.sunrise) / 2 : nowMs / 1000;
  const p = Math.min(1, Math.max(0, (now - today.sunrise) / (today.sunset - today.sunrise)));
  const isUp = now >= today.sunrise && now <= today.sunset;
  const theta = Math.PI * (1 - p);
  const x = 120 + 100 * Math.cos(theta);
  const y = 100 - 78 * Math.sin(theta);
  const daylight = today.sunset - today.sunrise;
  const delta = yesterdayDaylight ? Math.round((daylight - yesterdayDaylight) / 60) : null;
  const moon = moonInfo(nowMs ?? today.sunrise * 1000);

  let status: string;
  if (now < today.sunrise) status = `Sunrise in ${fmtDuration(today.sunrise - now)}`;
  else if (isUp) status = `Sunset in ${fmtDuration(today.sunset - now)}`;
  else status = tomorrow ? `Sunrise in ${fmtDuration(tomorrow.sunrise - now)}` : "After sunset";

  return (
    <section className="card sunmoon">
      <h2 className="card-title">
        <IconSunrise /> Sun & Moon
      </h2>
      <div className="sunmoon-body">
        <div className="sun-arc">
          <svg viewBox="0 0 240 118" width="100%" role="img" aria-label={status}>
            <defs>
              <radialGradient id="sun-dot">
                <stop offset="0%" stopColor="#FFF3B0" />
                <stop offset="100%" stopColor="#FFB020" />
              </radialGradient>
            </defs>
            <path d="M20 100 A100 78 0 0 1 220 100" fill="none" style={{ stroke: "var(--fg)" }} strokeOpacity="0.25" strokeDasharray="3 5" strokeWidth="1.5" />
            {p > 0 && (
              <path d={`M20 100 A100 78 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`} fill="none" style={{ stroke: "var(--accent)" }} strokeWidth="2.5" strokeLinecap="round" />
            )}
            <line x1="8" y1="100" x2="232" y2="100" style={{ stroke: "var(--fg)" }} strokeOpacity="0.3" />
            {isUp && <circle cx={x} cy={y} r="16" fill="#FFD166" opacity="0.18" />}
            <circle cx={x} cy={y} r="8" fill={isUp ? "url(#sun-dot)" : "rgba(255,255,255,0.35)"} />
          </svg>
          <div className="sun-times">
            <span>
              <small>Sunrise</small>
              {fmtTime(today.sunrise, tz)}
            </span>
            <span className="sun-status">{status}</span>
            <span className="align-end">
              <small>Sunset</small>
              {fmtTime(today.sunset, tz)}
            </span>
          </div>
          <p className="muted small">
            {fmtDuration(daylight)} of daylight
            {delta != null && delta !== 0 && ` · ${delta > 0 ? "+" : "−"}${Math.abs(delta)} min vs yesterday`}
          </p>
        </div>
        <div className="moon">
          <MoonGlyph fraction={moon.fraction} southern={southern} size={64} />
          <div>
            <strong>{moon.name}</strong>
            <p className="muted small">{Math.round(moon.illumination * 100)}% illuminated</p>
            <p className="muted small">
              {moon.daysToFull < 1 ? "Full moon tonight" : `Full moon in ${Math.round(moon.daysToFull)} days`}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
