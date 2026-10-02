"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CITIES } from "@/lib/cities";
import type { CitySummary } from "@/lib/types";
import { IconCheck, IconSearch } from "./Icons";
import { WeatherIcon } from "./WeatherIcon";

export function CommandPalette({ open, onClose, onSelect, selected, summaries }: {
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  selected: string;
  summaries: CitySummary[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const byId = useMemo(() => new Map(summaries.map((s) => [s.id, s])), [summaries]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? CITIES.filter((c) => `${c.name} ${c.region} ${c.countryName}`.toLowerCase().includes(q)) : CITIES;
  }, [query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(Math.max(0, CITIES.findIndex((c) => c.id === selected)));
      requestAnimationFrame(() => input.current?.focus());
    }
  }, [open, selected]);

  if (!open) return null;

  const choose = (id: string) => {
    onSelect(id);
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(results.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter" && results[active]) choose(results[active].id);
  };

  return (
    <div className="overlay" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Choose a city" onMouseDown={(e) => e.stopPropagation()} onKeyDown={onKeyDown}>
        <div className="palette-input">
          <IconSearch />
          <input
            ref={input}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            placeholder="Search cities…"
            aria-label="Search cities"
          />
          <kbd>Esc</kbd>
        </div>
        <ul className="palette-list" role="listbox">
          {results.length === 0 && <li className="palette-empty">No matching cities</li>}
          {results.map((c, i) => {
            const s = byId.get(c.id);
            return (
              <li
                key={c.id}
                role="option"
                aria-selected={i === active}
                className={`palette-item${i === active ? " is-active" : ""}`}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(c.id)}
              >
                <span className="palette-icon">{s ? <WeatherIcon code={s.code} isDay={s.isDay} size={28} animated={false} /> : null}</span>
                <span className="palette-name">
                  {c.name}
                  <small>
                    {c.region}, {c.countryName}
                  </small>
                </span>
                {s && <span className="palette-temp">{Math.round(s.temp)}°</span>}
                {c.id === selected && <IconCheck className="palette-check" />}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
