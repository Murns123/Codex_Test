import { useId } from "react";
import { wmoKind, wmoLabel } from "@/lib/wmo";

type Props = { code: number; isDay?: boolean; size?: number; animated?: boolean; className?: string };

function Cloud({ fill, x = 0, y = 0, s = 1 }: { fill: string; x?: number; y?: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} fill={fill}>
      <circle cx="24" cy="36" r="10" />
      <circle cx="35" cy="29" r="13" />
      <circle cx="46" cy="37" r="9" />
      <rect x="14" y="36" width="41" height="10" rx="5" />
    </g>
  );
}

function Sun({ id, x = 32, y = 32, r = 11 }: { id: string; x?: number; y?: number; r?: number }) {
  return (
    <g>
      <g className="wx-spin" style={{ transformOrigin: `${x}px ${y}px` }} stroke="#FFC23D" strokeWidth="2.6" strokeLinecap="round">
        {Array.from({ length: 8 }, (_, i) => {
          const a = (i * Math.PI) / 4;
          return (
            <line key={i} x1={x + Math.cos(a) * (r + 5)} y1={y + Math.sin(a) * (r + 5)} x2={x + Math.cos(a) * (r + 10)} y2={y + Math.sin(a) * (r + 10)} />
          );
        })}
      </g>
      <circle cx={x} cy={y} r={r} fill={`url(#${id}-sun)`} />
    </g>
  );
}

function Moon({ x = 32, y = 30, r = 13 }: { x?: number; y?: number; r?: number }) {
  return (
    <path
      d={`M${x + r * 0.35} ${y - r} A${r} ${r} 0 1 0 ${x + r} ${y + r * 0.45} A${r * 0.85} ${r * 0.85} 0 0 1 ${x + r * 0.35} ${y - r} Z`}
      fill="#E8ECF8"
    />
  );
}

export function WeatherIcon({ code, isDay = true, size = 48, animated = true, className }: Props) {
  const id = useId().replace(/:/g, "");
  const kind = wmoKind(code);
  const cloud = isDay ? "#F4F7FB" : "#C9D2E3";
  const darkCloud = "#9AA6B8";

  let body: React.ReactNode;
  switch (kind) {
    case "clear":
      body = isDay ? <Sun id={id} /> : <Moon />;
      break;
    case "partly":
      body = (
        <>
          {isDay ? <Sun id={id} x={24} y={22} r={9} /> : <Moon x={24} y={20} r={10} />}
          <Cloud fill={cloud} x={4} y={4} s={0.95} />
        </>
      );
      break;
    case "cloudy":
      body = (
        <>
          <Cloud fill={darkCloud} x={-6} y={-8} s={0.85} />
          <Cloud fill={cloud} x={2} y={2} />
        </>
      );
      break;
    case "fog":
      body = (
        <>
          <Cloud fill={cloud} y={-6} />
          <g stroke={cloud} strokeWidth="3" strokeLinecap="round" className="wx-drift">
            <line x1="14" y1="48" x2="44" y2="48" />
            <line x1="20" y1="55" x2="52" y2="55" />
          </g>
        </>
      );
      break;
    case "storm":
      body = (
        <>
          <Cloud fill="#7D8AA0" y={-6} />
          <path d="M34 40 L26 52 L32 52 L28 62 L40 48 L34 48 L38 40 Z" fill="#FFD43B" className="wx-flash" />
        </>
      );
      break;
    case "snow":
      body = (
        <>
          <Cloud fill={cloud} y={-6} />
          {[20, 32, 44].map((x, i) => (
            <circle key={x} cx={x} cy={50} r="2.6" fill="#ffffff" className="wx-snow" style={{ animationDelay: `${i * 0.5}s` }} />
          ))}
        </>
      );
      break;
    default: {
      const heavy = kind === "rain";
      body = (
        <>
          <Cloud fill={heavy ? "#B7C3D4" : cloud} y={-6} />
          {[22, 32, 42].map((x, i) => (
            <line
              key={x}
              x1={x}
              y1={46}
              x2={x - 3}
              y2={heavy ? 54 : 50}
              stroke="#7CC4FF"
              strokeWidth="2.6"
              strokeLinecap="round"
              className="wx-drop"
              style={{ animationDelay: `${i * 0.25}s` }}
            />
          ))}
        </>
      );
    }
  }

  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      role="img"
      aria-label={wmoLabel(code)}
      className={`wx-icon${animated ? " is-animated" : ""}${className ? ` ${className}` : ""}`}
    >
      <defs>
        <radialGradient id={`${id}-sun`} cx="40%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#FFE58A" />
          <stop offset="100%" stopColor="#FFA41B" />
        </radialGradient>
      </defs>
      {body}
    </svg>
  );
}
