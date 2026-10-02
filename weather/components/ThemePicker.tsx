"use client";

import { useEffect, useRef, useState } from "react";
import { THEME_OPTIONS, type ThemeId } from "@/lib/themes";
import { IconPalette } from "./Icons";

export function ThemePicker({ value, onChange }: { value: ThemeId; onChange: (id: ThemeId) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = THEME_OPTIONS.find((o) => o.id === value);

  return (
    <div className="theme-picker" ref={root}>
      <button type="button" className="icon-btn" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <IconPalette />
        <span className="hide-sm">{current?.label}</span>
      </button>
      {open && (
        <div className="popover" role="menu" aria-label="Theme">
          {THEME_OPTIONS.map((o) => (
            <button
              key={o.id}
              type="button"
              role="menuitemradio"
              aria-checked={o.id === value}
              className={`theme-option${o.id === value ? " is-active" : ""}`}
              onClick={() => {
                onChange(o.id);
                setOpen(false);
              }}
            >
              <span className="swatch" style={{ background: `conic-gradient(${o.swatch.map((c, i) => `${c} ${(i * 360) / o.swatch.length}deg ${((i + 1) * 360) / o.swatch.length}deg`).join(",")})` }} />
              <span>
                {o.label}
                {o.hint && <small>{o.hint}</small>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
