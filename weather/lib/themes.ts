import type { CountryCode } from "./cities";
import type { WxKind } from "./wmo";

export type ThemeVars = {
  bg: string;
  fg: string;
  fgMuted: string;
  glass: string;
  glassStrong: string;
  glassBorder: string;
  accent: string;
  accent2: string;
};

export type ThemeId =
  | "live" | "country" | "southAfrica" | "australia" | "netherlands" | "malaysia"
  | "christmas" | "newYear" | "construction" | "midnight" | "aurora";

type Preset = { id: ThemeId; label: string; swatch: string[]; vars: ThemeVars };

const glassDark = {
  fg: "#ffffff",
  fgMuted: "rgba(255,255,255,0.68)",
  glass: "rgba(255,255,255,0.08)",
  glassStrong: "rgba(255,255,255,0.14)",
  glassBorder: "rgba(255,255,255,0.14)",
};

export const PRESETS: Preset[] = [
  {
    id: "southAfrica", label: "South Africa", swatch: ["#007A4D", "#FCB514", "#E03C31"],
    vars: { ...glassDark, accent: "#FCB514", accent2: "#E03C31",
      bg: "radial-gradient(120% 80% at 85% 0%, rgba(252,181,20,0.22), transparent 55%), radial-gradient(90% 70% at 0% 100%, rgba(224,60,49,0.18), transparent 60%), linear-gradient(160deg, #004d33 0%, #007A4D 48%, #062a1f 100%)" },
  },
  {
    id: "australia", label: "Australia", swatch: ["#012169", "#FFCD00", "#00843D"],
    vars: { ...glassDark, accent: "#FFCD00", accent2: "#00843D",
      bg: "radial-gradient(100% 70% at 90% 10%, rgba(255,205,0,0.16), transparent 55%), radial-gradient(90% 60% at 0% 100%, rgba(0,132,61,0.25), transparent 60%), linear-gradient(165deg, #001a52 0%, #012169 50%, #000d2e 100%)" },
  },
  {
    id: "netherlands", label: "Netherlands", swatch: ["#AE1C28", "#FF7A00", "#21468B"],
    vars: { ...glassDark, accent: "#FF7A00", accent2: "#ffffff",
      bg: "radial-gradient(110% 80% at 80% 0%, rgba(255,122,0,0.28), transparent 55%), linear-gradient(170deg, #8f1520 0%, #5a2a55 50%, #21468B 100%)" },
  },
  {
    id: "malaysia", label: "Malaysia", swatch: ["#010066", "#FFCC00", "#CC0001"],
    vars: { ...glassDark, accent: "#FFCC00", accent2: "#CC0001",
      bg: "radial-gradient(100% 70% at 85% 5%, rgba(255,204,0,0.2), transparent 55%), radial-gradient(80% 60% at 5% 95%, rgba(204,0,1,0.22), transparent 60%), linear-gradient(165deg, #02024d 0%, #010066 50%, #00002e 100%)" },
  },
  {
    id: "christmas", label: "Christmas", swatch: ["#14532d", "#E63946", "#F1C40F"],
    vars: { ...glassDark, accent: "#F1C40F", accent2: "#E63946",
      bg: "radial-gradient(100% 70% at 85% 0%, rgba(230,57,70,0.25), transparent 55%), radial-gradient(70% 50% at 10% 100%, rgba(241,196,15,0.12), transparent 60%), linear-gradient(165deg, #0b2e1a 0%, #14532d 55%, #071c10 100%)" },
  },
  {
    id: "newYear", label: "New Year", swatch: ["#0b1340", "#FFD700", "#FF6EC7"],
    vars: { ...glassDark, accent: "#FFD700", accent2: "#FF6EC7",
      bg: "radial-gradient(90% 60% at 80% 0%, rgba(255,110,199,0.25), transparent 55%), radial-gradient(80% 60% at 0% 100%, rgba(255,215,0,0.15), transparent 60%), linear-gradient(170deg, #0b1340 0%, #1B3F8B 60%, #070b26 100%)" },
  },
  {
    id: "construction", label: "Construction", swatch: ["#F7BD03", "#262624", "#E8590C"],
    vars: {
      fg: "#1c1c1a", fgMuted: "rgba(28,28,26,0.66)", glass: "rgba(255,255,255,0.28)", glassStrong: "rgba(255,255,255,0.42)",
      glassBorder: "rgba(28,28,26,0.14)", accent: "#262624", accent2: "#E8590C",
      bg: "repeating-linear-gradient(135deg, rgba(0,0,0,0.035) 0 22px, transparent 22px 44px), linear-gradient(165deg, #FFD43B 0%, #F7BD03 50%, #F59F00 100%)" },
  },
  {
    id: "midnight", label: "Midnight", swatch: ["#121212", "#BB86FC", "#03DAC6"],
    vars: { ...glassDark, glass: "rgba(255,255,255,0.05)", accent: "#BB86FC", accent2: "#03DAC6",
      bg: "radial-gradient(80% 60% at 85% 0%, rgba(187,134,252,0.18), transparent 60%), linear-gradient(170deg, #121212 0%, #1b1b1f 60%, #0a0a0b 100%)" },
  },
  {
    id: "aurora", label: "Aurora", swatch: ["#020617", "#38BDF8", "#A78BFA"],
    vars: { ...glassDark, glass: "rgba(148,163,184,0.08)", accent: "#38BDF8", accent2: "#A78BFA",
      bg: "radial-gradient(70% 55% at 15% 0%, rgba(56,189,248,0.28), transparent 60%), radial-gradient(60% 50% at 90% 15%, rgba(167,139,250,0.28), transparent 60%), radial-gradient(70% 50% at 50% 100%, rgba(45,212,191,0.14), transparent 60%), linear-gradient(180deg, #020617 0%, #0F172A 100%)" },
  },
];

export const THEME_OPTIONS: { id: ThemeId; label: string; swatch: string[]; hint?: string }[] = [
  { id: "live", label: "Live sky", swatch: ["#1e3a8a", "#38bdf8", "#fbbf24"], hint: "Follows the weather and time of day" },
  { id: "country", label: "Home flag", swatch: ["#007A4D", "#012169", "#AE1C28"], hint: "Matches the selected city's country" },
  ...PRESETS,
];

const COUNTRY_THEME: Record<CountryCode, ThemeId> = {
  AU: "australia",
  ZA: "southAfrica",
  NL: "netherlands",
  MY: "malaysia",
};

export type SkyPhase = "day" | "golden" | "night";

const SKY: Record<SkyPhase, Record<WxKind, string>> = {
  day: {
    clear: "linear-gradient(180deg, #1d6fd8 0%, #3b9cf0 45%, #8fd0ff 100%)",
    partly: "linear-gradient(180deg, #2a6cbf 0%, #5a9bdc 50%, #a9cdee 100%)",
    cloudy: "linear-gradient(180deg, #51637a 0%, #7489a3 55%, #a3b3c6 100%)",
    fog: "linear-gradient(180deg, #6f7c8b 0%, #98a3ae 55%, #c3cad1 100%)",
    drizzle: "linear-gradient(180deg, #3f5670 0%, #5d7690 55%, #8a9fb4 100%)",
    rain: "linear-gradient(180deg, #2c3e55 0%, #4a6079 55%, #6f8399 100%)",
    snow: "linear-gradient(180deg, #7f9bbd 0%, #b4c8dd 55%, #e3ecf5 100%)",
    storm: "linear-gradient(180deg, #1a2233 0%, #2f3a4f 55%, #4a5468 100%)",
  },
  golden: {
    clear: "linear-gradient(180deg, #2b3a7a 0%, #b4558f 45%, #ff9a5a 80%, #ffd27a 100%)",
    partly: "linear-gradient(180deg, #33406f 0%, #a4588a 50%, #f39a6b 100%)",
    cloudy: "linear-gradient(180deg, #3a4157 0%, #7a6378 55%, #c08a7c 100%)",
    fog: "linear-gradient(180deg, #4f5566 0%, #8d7f87 55%, #c7a99a 100%)",
    drizzle: "linear-gradient(180deg, #2f3850 0%, #5f5b70 55%, #9b7f80 100%)",
    rain: "linear-gradient(180deg, #252c40 0%, #4b4a5e 55%, #7c6a6f 100%)",
    snow: "linear-gradient(180deg, #5c6b95 0%, #b29ab8 55%, #f2d3c9 100%)",
    storm: "linear-gradient(180deg, #161a28 0%, #3a3346 55%, #5d4a52 100%)",
  },
  night: {
    clear: "radial-gradient(80% 50% at 70% 0%, rgba(99,102,241,0.25), transparent 60%), linear-gradient(180deg, #050a1f 0%, #0c1638 55%, #1a2a5c 100%)",
    partly: "linear-gradient(180deg, #070d24 0%, #141f45 55%, #26355f 100%)",
    cloudy: "linear-gradient(180deg, #0e131f 0%, #1d2535 55%, #2e384b 100%)",
    fog: "linear-gradient(180deg, #151a24 0%, #262d39 55%, #3a414e 100%)",
    drizzle: "linear-gradient(180deg, #0c1220 0%, #1a2436 55%, #2a364b 100%)",
    rain: "linear-gradient(180deg, #080d18 0%, #142033 55%, #22304a 100%)",
    snow: "linear-gradient(180deg, #121a33 0%, #27355c 55%, #44547f 100%)",
    storm: "linear-gradient(180deg, #05070d 0%, #10141f 55%, #1d2232 100%)",
  },
};

const SKY_ACCENT: Record<SkyPhase, [string, string]> = {
  day: ["#FFD166", "#7DD3FC"],
  golden: ["#FFB86B", "#F9A8D4"],
  night: ["#A5B4FC", "#7DD3FC"],
};

export function resolveTheme(id: ThemeId, ctx: { country: CountryCode; kind: WxKind; phase: SkyPhase }): ThemeVars {
  if (id === "live") {
    const [accent, accent2] = SKY_ACCENT[ctx.phase];
    const light = ctx.phase === "day" && (ctx.kind === "snow" || ctx.kind === "fog");
    return {
      ...glassDark,
      glass: light ? "rgba(15,23,42,0.16)" : "rgba(255,255,255,0.1)",
      glassStrong: light ? "rgba(15,23,42,0.24)" : "rgba(255,255,255,0.16)",
      glassBorder: "rgba(255,255,255,0.18)",
      accent,
      accent2,
      bg: SKY[ctx.phase][ctx.kind],
    };
  }
  const target = id === "country" ? COUNTRY_THEME[ctx.country] : id;
  return (PRESETS.find((p) => p.id === target) ?? PRESETS[0]).vars;
}

export function isThemeId(v: unknown): v is ThemeId {
  return typeof v === "string" && THEME_OPTIONS.some((o) => o.id === v);
}
