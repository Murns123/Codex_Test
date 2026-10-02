type P = { size?: number; className?: string };

function base(size: number, className: string | undefined, children: React.ReactNode) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

export const IconPin = ({ size = 18, className }: P) =>
  base(size, className, <><path d="M12 21s-7-6.1-7-11.5A7 7 0 0 1 19 9.5C19 14.9 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></>);
export const IconSearch = ({ size = 18, className }: P) =>
  base(size, className, <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>);
export const IconPalette = ({ size = 18, className }: P) =>
  base(size, className, <><path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.7-.9 1.4-1.8-.4-1.2.4-2.2 1.6-2.2H17a4 4 0 0 0 4-4c0-5.5-4-10-9-10z" /><circle cx="7.5" cy="11" r="1.2" /><circle cx="10.5" cy="7" r="1.2" /><circle cx="15" cy="7.5" r="1.2" /></>);
export const IconRefresh = ({ size = 18, className }: P) =>
  base(size, className, <><path d="M20 11a8 8 0 0 0-14.6-4.5M4 4v4h4" /><path d="M4 13a8 8 0 0 0 14.6 4.5M20 20v-4h-4" /></>);
export const IconThermo = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M14 14.8V5a2 2 0 1 0-4 0v9.8a4 4 0 1 0 4 0z" /><path d="M12 9v6" /></>);
export const IconWind = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M3 8h11a3 3 0 1 0-3-3" /><path d="M3 12h16a3 3 0 1 1-3 3" /><path d="M3 16h7" /></>);
export const IconDrop = ({ size = 16, className }: P) =>
  base(size, className, <path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11z" />);
export const IconGauge = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M4 17a8 8 0 1 1 16 0" /><path d="m12 17 4-5" /></>);
export const IconSun = ({ size = 16, className }: P) =>
  base(size, className, <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>);
export const IconEye = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>);
export const IconLeaf = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M5 19c0-9 6-14 15-14 0 9-5 15-14 15" /><path d="M5 19 14 10" /></>);
export const IconUmbrella = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M3 12a9 9 0 0 1 18 0z" /><path d="M12 12v7a2 2 0 0 1-4 0" /></>);
export const IconSunrise = ({ size = 16, className }: P) =>
  base(size, className, <><path d="M17 18a5 5 0 0 0-10 0" /><path d="M12 2v6M4.2 10.2l1.4 1.4M2 18h2M20 18h2M18.4 11.6l1.4-1.4M23 22H1M8 6l4-4 4 4" /></>);
export const IconArrowUp = ({ size = 14, className }: P) => base(size, className, <path d="M12 19V5M5 12l7-7 7 7" />);
export const IconArrowDown = ({ size = 14, className }: P) => base(size, className, <path d="M12 5v14M19 12l-7 7-7-7" />);
export const IconMinus = ({ size = 14, className }: P) => base(size, className, <path d="M5 12h14" />);
export const IconCheck = ({ size = 16, className }: P) => base(size, className, <path d="M20 6 9 17l-5-5" />);
export const IconSpark = ({ size = 14, className }: P) =>
  base(size, className, <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" />);
