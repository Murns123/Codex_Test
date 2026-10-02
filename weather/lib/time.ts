// Manual formatting from numeric parts keeps server and browser output identical
// (ICU versions disagree on spacing in localised times, which breaks hydration).

export const DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const DAY_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
export const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export type ZonedParts = { year: number; month: number; day: number; hour: number; minute: number; second: number; weekday: number };

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(tz: string) {
  let f = formatters.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hourCycle: "h23",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      weekday: "short",
    });
    formatters.set(tz, f);
  }
  return f;
}

export function zoned(ms: number, tz: string): ZonedParts {
  const out: Record<string, string> = {};
  for (const p of formatter(tz).formatToParts(new Date(ms))) out[p.type] = p.value;
  return {
    year: Number(out.year),
    month: Number(out.month),
    day: Number(out.day),
    hour: Number(out.hour) % 24,
    minute: Number(out.minute),
    second: Number(out.second),
    weekday: DAY_SHORT.indexOf(out.weekday),
  };
}

/** Milliseconds to add to UTC to get the wall-clock time in `tz`. */
export function tzOffsetMs(tz: string, ms = Date.now()): number {
  const z = zoned(ms, tz);
  const wall = Date.UTC(z.year, z.month - 1, z.day, z.hour, z.minute, z.second);
  return wall - (ms - (ms % 1000));
}

const pad = (n: number) => String(n).padStart(2, "0");
const h12 = (h: number) => (h % 12 === 0 ? 12 : h % 12);
const ampm = (h: number) => (h < 12 ? "am" : "pm");

/** "3 pm" */
export function fmtHour(sec: number, tz: string) {
  const z = zoned(sec * 1000, tz);
  return `${h12(z.hour)} ${ampm(z.hour)}`;
}

/** "6:42 am" */
export function fmtTime(sec: number, tz: string) {
  const z = zoned(sec * 1000, tz);
  return `${h12(z.hour)}:${pad(z.minute)} ${ampm(z.hour)}`;
}

/** { hm: "6:42", s: "13", period: "PM" } */
export function clockParts(ms: number, tz: string) {
  const z = zoned(ms, tz);
  return { hm: `${h12(z.hour)}:${pad(z.minute)}`, s: pad(z.second), period: z.hour < 12 ? "AM" : "PM" };
}

/** "Friday 2 October" */
export function fmtDateLong(ms: number, tz: string) {
  const z = zoned(ms, tz);
  return `${DAY_LONG[z.weekday]} ${z.day} ${MONTH_LONG[z.month - 1]}`;
}

export function fmtWeekday(sec: number, tz: string) {
  return DAY_SHORT[zoned(sec * 1000, tz).weekday];
}

/** "11h 42m" */
export function fmtDuration(sec: number) {
  const m = Math.round(Math.abs(sec) / 60);
  return `${Math.floor(m / 60)}h ${pad(m % 60)}m`;
}

export function fmtAgo(ms: number, now: number) {
  const m = Math.round((now - ms) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  return `${Math.floor(m / 60)} h ago`;
}
