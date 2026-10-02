import type { Hour } from "@/lib/types";
import { fmtHour } from "@/lib/time";
import { WeatherIcon } from "./WeatherIcon";

const COL = 68;
const CURVE_H = 96;
const PAD = 22;

function smoothPath(pts: [number, number][]) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${p2[0]} ${p2[1].toFixed(1)}`;
  }
  return d;
}

export function HourlyTimeline({ hours, tz }: { hours: Hour[]; tz: string }) {
  const width = hours.length * COL;
  const temps = hours.map((h) => h.temp);
  const max = Math.max(...temps);
  const min = Math.min(...temps);
  const span = Math.max(1, max - min);
  const pts: [number, number][] = hours.map((h, i) => [i * COL + COL / 2, PAD + ((max - h.temp) / span) * (CURVE_H - PAD * 1.6)]);
  const line = smoothPath(pts);
  const area = `${line} L${pts[pts.length - 1][0]} ${CURVE_H} L${pts[0][0]} ${CURVE_H} Z`;

  return (
    <div className="hourly-scroll" tabIndex={0} aria-label="Hourly forecast for the next 24 hours">
      <div className="hourly" style={{ width }}>
        <div className="hourly-row">
          {hours.map((h, i) => (
            <div key={h.time} className="hourly-cell">
              <span className={`hourly-time${i === 0 ? " is-now" : ""}`}>{i === 0 ? "Now" : fmtHour(h.time, tz)}</span>
              <WeatherIcon code={h.code} isDay={h.isDay} size={34} animated={i === 0} />
            </div>
          ))}
        </div>
        <svg width={width} height={CURVE_H} className="hourly-curve" role="img" aria-label={`Temperatures from ${Math.round(min)}° to ${Math.round(max)}°`}>
          <defs>
            <linearGradient id="temp-area" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" style={{ stopColor: "var(--accent)", stopOpacity: 0.35 }} />
              <stop offset="100%" style={{ stopColor: "var(--accent)", stopOpacity: 0 }} />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#temp-area)" />
          <path d={line} fill="none" style={{ stroke: "var(--accent)" }} strokeWidth="2.5" strokeLinecap="round" />
          {pts.map(([x, y], i) => (
            <g key={i}>
              <circle cx={x} cy={y} r={i === 0 ? 5 : 3} style={{ fill: i === 0 ? "var(--accent)" : "var(--fg)" }} />
              <text x={x} y={y - 10} textAnchor="middle" className="hourly-temp">
                {Math.round(hours[i].temp)}°
              </text>
            </g>
          ))}
        </svg>
        <div className="hourly-row hourly-rain">
          {hours.map((h) => (
            <div key={h.time} className="hourly-cell" title={`${h.pop}% chance of rain`}>
              <div className="rain-track">
                <div className="rain-bar" style={{ height: `${Math.max(h.pop, 2)}%`, opacity: h.pop < 10 ? 0.25 : 1 }} />
              </div>
              <span className="rain-pct">{h.pop >= 10 ? `${h.pop}%` : ""}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
