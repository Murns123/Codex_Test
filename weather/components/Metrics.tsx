import type { AirQuality, Current, Day, Hour } from "@/lib/types";
import { fmtHour } from "@/lib/time";
import {
  IconArrowDown, IconArrowUp, IconDrop, IconEye, IconGauge, IconLeaf, IconMinus, IconSun, IconThermo, IconUmbrella, IconWind,
} from "./Icons";

const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const compass = (deg: number) => COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];

function beaufort(kmh: number) {
  if (kmh < 2) return "Calm";
  if (kmh < 12) return "Light breeze";
  if (kmh < 29) return "Moderate breeze";
  if (kmh < 39) return "Fresh breeze";
  if (kmh < 50) return "Strong breeze";
  if (kmh < 62) return "Near gale";
  if (kmh < 75) return "Gale";
  return "Storm-force";
}

function uvLabel(uv: number) {
  if (uv < 3) return "Low";
  if (uv < 6) return "Moderate";
  if (uv < 8) return "High";
  if (uv < 11) return "Very high";
  return "Extreme";
}

function aqiLabel(aqi: number) {
  if (aqi <= 50) return "Good";
  if (aqi <= 100) return "Moderate";
  if (aqi <= 150) return "Unhealthy for sensitive groups";
  if (aqi <= 200) return "Unhealthy";
  return "Very unhealthy";
}

function Tile({ icon, label, children, note }: { icon: React.ReactNode; label: string; children: React.ReactNode; note?: React.ReactNode }) {
  return (
    <section className="card tile">
      <h3 className="card-title">
        {icon} {label}
      </h3>
      <div className="tile-body">{children}</div>
      {note && <p className="tile-note">{note}</p>}
    </section>
  );
}

function Scale({ value, max, gradient }: { value: number; max: number; gradient: string }) {
  return (
    <div className="scale" style={{ background: gradient }}>
      <span className="scale-dot" style={{ left: `${Math.min(100, Math.max(0, (value / max) * 100))}%` }} />
    </div>
  );
}

export function Metrics({ current, today, hours, air, tz }: { current: Current; today: Day; hours: Hour[]; air: AirQuality | null; tz: string }) {
  const feelsDiff = current.feels - current.temp;
  const nextRain = hours.slice(1).find((h) => h.pop >= 40);
  const precipNext24 = hours.slice(1).reduce((a, h) => a + h.precip, 0);
  const TrendIcon = current.pressureTrend === "rising" ? IconArrowUp : current.pressureTrend === "falling" ? IconArrowDown : IconMinus;
  const pressureAngle = ((Math.min(1050, Math.max(970, current.pressure)) - 970) / 80) * 180 - 90;

  return (
    <>
      <Tile
        icon={<IconThermo />}
        label="Feels like"
        note={
          feelsDiff <= -2 ? "Wind makes it feel cooler." : feelsDiff >= 2 ? "Humidity makes it feel warmer." : "Similar to the actual temperature."
        }
      >
        <span className="big-value">{Math.round(current.feels)}°</span>
      </Tile>

      <Tile icon={<IconWind />} label="Wind" note={`${beaufort(current.wind)} · gusts ${Math.round(current.gusts)} km/h`}>
        <div className="wind">
          <div>
            <span className="big-value">{Math.round(current.wind)}</span>
            <span className="unit">km/h</span>
            <p className="muted small">from {compass(current.windDir)}</p>
          </div>
          <svg viewBox="0 0 80 80" width="74" height="74" aria-hidden="true" className="compass">
            <circle cx="40" cy="40" r="36" fill="none" style={{ stroke: "var(--fg)" }} strokeOpacity="0.2" />
            {["N", "E", "S", "W"].map((l, i) => (
              <text key={l} x={40 + 27 * Math.sin((i * Math.PI) / 2)} y={44 - 27 * Math.cos((i * Math.PI) / 2)} textAnchor="middle" className="compass-label">
                {l}
              </text>
            ))}
            {/* Arrow points where the wind is blowing to. */}
            <g transform={`rotate(${current.windDir + 180} 40 40)`}>
              <line x1="40" y1="58" x2="40" y2="20" style={{ stroke: "var(--accent)" }} strokeWidth="2.5" strokeLinecap="round" />
              <path d="M34 26 L40 16 L46 26 Z" style={{ fill: "var(--accent)" }} />
            </g>
          </svg>
        </div>
      </Tile>

      <Tile icon={<IconDrop />} label="Humidity" note={`Dew point is ${Math.round(current.dewPoint)}° right now.`}>
        <span className="big-value">{Math.round(current.humidity)}%</span>
        <div className="meter">
          <span style={{ width: `${current.humidity}%` }} />
        </div>
      </Tile>

      <Tile
        icon={<IconUmbrella />}
        label="Precipitation"
        note={nextRain ? `${nextRain.pop}% chance from ${fmtHour(nextRain.time, tz)}.` : "No significant rain expected in 24 h."}
      >
        <span className="big-value">{precipNext24.toFixed(precipNext24 < 10 ? 1 : 0)}</span>
        <span className="unit">mm next 24 h</span>
      </Tile>

      <Tile icon={<IconGauge />} label="Pressure" note={`${current.pressureTrend[0].toUpperCase()}${current.pressureTrend.slice(1)} over the last 3 hours.`}>
        <div className="pressure">
          <div>
            <span className="big-value">{Math.round(current.pressure)}</span>
            <span className="unit">hPa</span>
          </div>
          <svg viewBox="0 0 80 48" width="78" height="47" aria-hidden="true">
            <path d="M8 44 A32 32 0 0 1 72 44" fill="none" style={{ stroke: "var(--fg)" }} strokeOpacity="0.2" strokeWidth="6" strokeLinecap="round" />
            <g transform={`rotate(${pressureAngle} 40 44)`}>
              <line x1="40" y1="44" x2="40" y2="18" style={{ stroke: "var(--accent)" }} strokeWidth="2.5" strokeLinecap="round" />
            </g>
            <circle cx="40" cy="44" r="3.5" style={{ fill: "var(--accent)" }} />
          </svg>
          <TrendIcon size={18} className="trend" />
        </div>
      </Tile>

      <Tile icon={<IconSun />} label="UV index" note={`Peak today ${Math.round(today.uvMax)} (${uvLabel(today.uvMax)}).`}>
        <span className="big-value">{Math.round(current.uv)}</span>
        <span className="unit">{uvLabel(current.uv)}</span>
        <Scale value={current.uv} max={12} gradient="linear-gradient(90deg,#22c55e,#facc15,#fb923c,#ef4444,#a855f7)" />
      </Tile>

      <Tile icon={<IconEye />} label="Visibility" note={current.visibility >= 10000 ? "Clear views." : current.visibility >= 4000 ? "Slightly hazy." : "Reduced visibility."}>
        <span className="big-value">{(current.visibility / 1000).toFixed(current.visibility < 10000 ? 1 : 0)}</span>
        <span className="unit">km</span>
      </Tile>

      {air && (
        <Tile icon={<IconLeaf />} label="Air quality" note={`PM2.5 ${air.pm25.toFixed(1)} µg/m³ · PM10 ${air.pm10.toFixed(1)} µg/m³`}>
          <span className="big-value">{Math.round(air.usAqi)}</span>
          <span className="unit">{aqiLabel(air.usAqi)}</span>
          <Scale value={air.usAqi} max={250} gradient="linear-gradient(90deg,#22c55e,#facc15 25%,#fb923c 45%,#ef4444 65%,#a855f7 85%,#7f1d1d)" />
        </Tile>
      )}
    </>
  );
}
