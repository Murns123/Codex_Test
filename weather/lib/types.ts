export type PressureTrend = "rising" | "falling" | "steady";

export type Current = {
  time: number;
  temp: number;
  feels: number;
  humidity: number;
  dewPoint: number;
  isDay: boolean;
  code: number;
  cloud: number;
  pressure: number;
  pressureTrend: PressureTrend;
  wind: number;
  windDir: number;
  gusts: number;
  precip: number;
  uv: number;
  visibility: number;
};

export type Hour = {
  time: number;
  temp: number;
  pop: number;
  precip: number;
  code: number;
  isDay: boolean;
  wind: number;
};

export type Day = {
  time: number;
  code: number;
  max: number;
  min: number;
  pop: number;
  precip: number;
  sunrise: number;
  sunset: number;
  uvMax: number;
  windMax: number;
  windDir: number;
};

export type AirQuality = { usAqi: number; pm25: number; pm10: number };

export type WeatherData = {
  cityId: string;
  fetchedAt: number;
  current: Current;
  /** Current hour plus the next 24 hours. */
  hourly: Hour[];
  /** Today plus the next 6 days. */
  daily: Day[];
  yesterday: { max: number; min: number; daylight: number } | null;
  air: AirQuality | null;
};

export type CitySummary = {
  id: string;
  temp: number;
  code: number;
  isDay: boolean;
  max: number;
  min: number;
};
