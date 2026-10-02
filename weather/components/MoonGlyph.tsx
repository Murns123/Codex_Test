/** Moon disc with the lit portion drawn from the phase fraction (0 new, 0.5 full). */
export function MoonGlyph({ fraction, southern, size = 56 }: { fraction: number; southern: boolean; size?: number }) {
  const r = 24;
  const cx = 28;
  const cy = 28;
  const rx = Math.abs(Math.cos(2 * Math.PI * fraction)) * r;
  const waxing = fraction < 0.5;
  const crescent = fraction < 0.25 || fraction > 0.75;
  // Northern-hemisphere view: waxing is lit on the right. Mirrored for the southern hemisphere.
  const outerSweep = waxing ? 1 : 0;
  const termSweep = waxing ? (crescent ? 0 : 1) : crescent ? 1 : 0;
  const lit = `M${cx} ${cy - r} A${r} ${r} 0 0 ${outerSweep} ${cx} ${cy + r} A${rx} ${r} 0 0 ${termSweep} ${cx} ${cy - r} Z`;

  return (
    <svg viewBox="0 0 56 56" width={size} height={size} aria-hidden="true">
      <defs>
        <radialGradient id="moon-lit" cx="40%" cy="35%" r="80%">
          <stop offset="0%" stopColor="#FFFDF2" />
          <stop offset="100%" stopColor="#D9DCE6" />
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r} fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)" />
      <g transform={southern ? `translate(56 0) scale(-1 1)` : undefined}>
        <path d={lit} fill="url(#moon-lit)" style={{ filter: "drop-shadow(0 0 6px rgba(255,250,220,0.45))" }} />
      </g>
    </svg>
  );
}
