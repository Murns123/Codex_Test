# MHWA Weather 2.0

A rebuilt version of the weather and world-clock dashboard (originally `mhwav2.vercel.app`),
with a modern look, server-side data fetching and no exposed API keys.

## Highlights

- **Live sky theme**: the background follows current conditions and time of day (day, golden hour
  or night), with rain, snow, cloud or star particles.
- **Theme presets**: Home flag (follows the selected city's country), South Africa, Australia,
  Netherlands, Malaysia, Christmas, New Year, Construction, Midnight and Aurora.
- **Hero panel**: current conditions, a smooth analogue clock in the city's timezone, and
  generated highlights ("Rain likely from 7 pm", "3° warmer than yesterday", UV and gust warnings).
- **24-hour timeline**: temperature curve plus rain-probability bars.
- **7-day forecast**: range bars on a shared scale, with a marker for the current temperature.
- **Sun & moon**: daylight arc showing the sun's current position, daylight change versus yesterday,
  and the moon phase (correctly mirrored for the southern hemisphere).
- **Detail tiles**: feels like, wind compass and Beaufort scale, humidity and dew point,
  precipitation, pressure and its trend, UV index, visibility, and air quality (US AQI, PM2.5, PM10).
- **City strip and ⌘K / Ctrl+K search**: live local time and temperature for all 10 cities.
- Responsive from phone to wide desktop. Respects `prefers-reduced-motion`. City and theme
  choices are remembered, and `?city=cape-town` links straight to a city.

## Data

Weather comes from [Open-Meteo](https://open-meteo.com/) (forecast and air-quality APIs). It needs
no API key, so there are no secrets to manage. Responses are fetched on the server, normalised
in `lib/weather.ts` and cached for 10 minutes.

The previous version shipped an OpenWeatherMap key in its client JavaScript. **Rotate that key**
in your OpenWeatherMap account.

## Develop

```bash
cd weather
npm install
npm run dev                      # live data
WEATHER_MOCK=1 npm run dev       # generated demo data, works offline
```

## Deploy on Vercel

Create a new Vercel project from this repository and set **Root Directory** to `weather`.
No environment variables are required. To replace the old site, point the `mhwav2`
domain at the new project.
