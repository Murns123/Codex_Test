"use client";

import { useMemo } from "react";
import type { SkyPhase } from "@/lib/themes";
import type { WxKind } from "@/lib/wmo";

/** Ambient particle layer: rain, snow, drifting clouds or stars, depending on conditions. */
export function Sky({ kind, phase, intensity = 1 }: { kind: WxKind; phase: SkyPhase; intensity?: number }) {
  const particles = useMemo(() => {
    // Deterministic pseudo-random layout so server and client markup match.
    const r = (i: number, k: number) => {
      const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453;
      return x - Math.floor(x);
    };
    if (kind === "rain" || kind === "drizzle" || kind === "storm") {
      const count = kind === "drizzle" ? 40 : 90;
      return Array.from({ length: count }, (_, i) => ({
        cls: "p-rain",
        style: {
          left: `${r(i, 1) * 100}%`,
          animationDelay: `${-r(i, 2) * 2}s`,
          animationDuration: `${(kind === "drizzle" ? 1.4 : 0.7) + r(i, 3) * 0.5}s`,
          opacity: 0.25 + r(i, 4) * 0.45,
        },
      }));
    }
    if (kind === "snow") {
      return Array.from({ length: 70 }, (_, i) => ({
        cls: "p-snow",
        style: {
          left: `${r(i, 1) * 100}%`,
          animationDelay: `${-r(i, 2) * 12}s`,
          animationDuration: `${8 + r(i, 3) * 8}s`,
          width: `${3 + r(i, 4) * 4}px`,
          height: `${3 + r(i, 4) * 4}px`,
        },
      }));
    }
    if (phase === "night" && (kind === "clear" || kind === "partly")) {
      return Array.from({ length: 110 }, (_, i) => ({
        cls: "p-star",
        style: {
          left: `${r(i, 1) * 100}%`,
          top: `${r(i, 2) * 70}%`,
          animationDelay: `${-r(i, 3) * 5}s`,
          width: `${1 + r(i, 4) * 2}px`,
          height: `${1 + r(i, 4) * 2}px`,
        },
      }));
    }
    if (kind === "cloudy" || kind === "partly" || kind === "fog") {
      return Array.from({ length: kind === "partly" ? 4 : 7 }, (_, i) => ({
        cls: "p-cloud",
        style: {
          top: `${r(i, 1) * 55}%`,
          animationDelay: `${-r(i, 2) * 120}s`,
          animationDuration: `${90 + r(i, 3) * 80}s`,
          width: `${280 + r(i, 4) * 340}px`,
          opacity: kind === "fog" ? 0.22 : 0.1 + r(i, 5) * 0.12,
        },
      }));
    }
    return [];
  }, [kind, phase]);

  return (
    <div className="sky" aria-hidden="true" style={{ opacity: intensity }}>
      {phase === "day" && kind === "clear" && <div className="sun-glow" />}
      {kind === "storm" && <div className="lightning" />}
      {particles.map((p, i) => (
        <span key={i} className={p.cls} style={p.style} />
      ))}
    </div>
  );
}
