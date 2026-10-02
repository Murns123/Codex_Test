"use client";

import { useEffect, useRef } from "react";
import { tzOffsetMs } from "@/lib/time";

export function AnalogClock({ tz, size = 176 }: { tz: string; size?: number }) {
  const hour = useRef<SVGGElement>(null);
  const minute = useRef<SVGGElement>(null);
  const second = useRef<SVGGElement>(null);

  useEffect(() => {
    let offset = tzOffsetMs(tz);
    let offsetAt = Date.now();
    let raf = 0;
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const tick = () => {
      const now = Date.now();
      if (now - offsetAt > 60_000) {
        offset = tzOffsetMs(tz, now);
        offsetAt = now;
      }
      const local = new Date(now + offset);
      const s = local.getUTCSeconds() + (smooth ? local.getUTCMilliseconds() / 1000 : 0);
      const m = local.getUTCMinutes() + s / 60;
      const h = (local.getUTCHours() % 12) + m / 60;
      second.current?.setAttribute("transform", `rotate(${s * 6} 100 100)`);
      minute.current?.setAttribute("transform", `rotate(${m * 6} 100 100)`);
      hour.current?.setAttribute("transform", `rotate(${h * 30} 100 100)`);
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [tz]);

  return (
    <svg viewBox="0 0 200 200" width={size} height={size} className="clock" aria-hidden="true">
      <defs>
        <radialGradient id="clock-face" cx="50%" cy="35%" r="75%">
          <stop offset="0%" style={{ stopColor: "var(--glass-strong)" }} />
          <stop offset="100%" style={{ stopColor: "var(--glass)" }} />
        </radialGradient>
      </defs>
      <circle cx="100" cy="100" r="96" fill="url(#clock-face)" style={{ stroke: "var(--glass-border)" }} strokeWidth="1.5" />
      <circle cx="100" cy="100" r="88" fill="none" style={{ stroke: "var(--accent)" }} strokeOpacity="0.25" strokeWidth="1" />
      {Array.from({ length: 60 }, (_, i) => {
        const major = i % 5 === 0;
        return (
          <line
            key={i}
            x1="100"
            y1={major ? 14 : 16}
            x2="100"
            y2={major ? 26 : 21}
            style={{ stroke: "var(--fg)" }}
            strokeOpacity={major ? 0.9 : 0.35}
            strokeWidth={major ? 3 : 1.4}
            strokeLinecap="round"
            transform={`rotate(${i * 6} 100 100)`}
          />
        );
      })}
      <g ref={hour}>
        <line x1="100" y1="108" x2="100" y2="54" style={{ stroke: "var(--fg)" }} strokeWidth="6" strokeLinecap="round" />
      </g>
      <g ref={minute}>
        <line x1="100" y1="112" x2="100" y2="32" style={{ stroke: "var(--fg)" }} strokeWidth="3.5" strokeLinecap="round" />
      </g>
      <g ref={second}>
        <line x1="100" y1="120" x2="100" y2="22" style={{ stroke: "var(--accent)" }} strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="100" cy="22" r="3" style={{ fill: "var(--accent)" }} />
      </g>
      <circle cx="100" cy="100" r="5.5" style={{ fill: "var(--accent)" }} />
      <circle cx="100" cy="100" r="2" style={{ fill: "var(--fg)" }} />
    </svg>
  );
}
