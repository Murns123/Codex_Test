const SYNODIC_DAYS = 29.530588853;
const KNOWN_NEW_MOON_MS = Date.UTC(2000, 0, 6, 18, 14);

export type MoonInfo = {
  /** 0 = new, 0.5 = full */
  fraction: number;
  illumination: number;
  name: string;
  daysToFull: number;
  daysToNew: number;
};

export function moonInfo(ms: number): MoonInfo {
  const days = (ms - KNOWN_NEW_MOON_MS) / 86_400_000;
  const age = ((days % SYNODIC_DAYS) + SYNODIC_DAYS) % SYNODIC_DAYS;
  const f = age / SYNODIC_DAYS;
  const name =
    f < 0.0339 ? "New Moon"
    : f < 0.216 ? "Waxing Crescent"
    : f < 0.284 ? "First Quarter"
    : f < 0.466 ? "Waxing Gibbous"
    : f < 0.534 ? "Full Moon"
    : f < 0.716 ? "Waning Gibbous"
    : f < 0.784 ? "Last Quarter"
    : f < 0.966 ? "Waning Crescent"
    : "New Moon";
  return {
    fraction: f,
    illumination: (1 - Math.cos(2 * Math.PI * f)) / 2,
    name,
    daysToFull: (((0.5 - f) % 1) + 1) % 1 * SYNODIC_DAYS,
    daysToNew: (1 - f) * SYNODIC_DAYS,
  };
}
