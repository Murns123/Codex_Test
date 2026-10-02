import type { Day } from "@/lib/types";
import { fmtWeekday } from "@/lib/time";
import { IconDrop } from "./Icons";
import { WeatherIcon } from "./WeatherIcon";

const STOPS: [number, string][] = [
  [-5, "#818CF8"],
  [5, "#60A5FA"],
  [12, "#34D399"],
  [20, "#FACC15"],
  [28, "#FB923C"],
  [36, "#EF4444"],
];

export function tempColor(t: number) {
  if (t <= STOPS[0][0]) return STOPS[0][1];
  for (let i = 1; i < STOPS.length; i++) if (t <= STOPS[i][0]) return STOPS[i][1];
  return STOPS[STOPS.length - 1][1];
}

export function DailyForecast({ days, tz, currentTemp }: { days: Day[]; tz: string; currentTemp: number }) {
  const lo = Math.min(...days.map((d) => d.min));
  const hi = Math.max(...days.map((d) => d.max));
  const span = Math.max(1, hi - lo);

  return (
    <ul className="daily">
      {days.map((d, i) => {
        const left = ((d.min - lo) / span) * 100;
        const width = ((d.max - d.min) / span) * 100;
        const nowPos = ((Math.min(Math.max(currentTemp, d.min), d.max) - lo) / span) * 100;
        return (
          <li key={d.time} className="daily-row">
            <span className="daily-day">{i === 0 ? "Today" : fmtWeekday(d.time, tz)}</span>
            <span className="daily-icon">
              <WeatherIcon code={d.code} size={30} animated={false} />
            </span>
            <span className="daily-pop">
              {d.pop >= 20 && (
                <>
                  <IconDrop size={12} />
                  {d.pop}%
                </>
              )}
            </span>
            <span className="daily-min">{Math.round(d.min)}°</span>
            <span className="range" aria-label={`Low ${Math.round(d.min)}°, high ${Math.round(d.max)}°`}>
              <span
                className="range-fill"
                style={{ left: `${left}%`, width: `${Math.max(width, 4)}%`, background: `linear-gradient(90deg, ${tempColor(d.min)}, ${tempColor(d.max)})` }}
              />
              {i === 0 && <span className="range-now" style={{ left: `${nowPos}%` }} />}
            </span>
            <span className="daily-max">{Math.round(d.max)}°</span>
          </li>
        );
      })}
    </ul>
  );
}
