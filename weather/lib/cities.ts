export type CountryCode = "AU" | "ZA" | "NL" | "MY";

export type City = {
  id: string;
  name: string;
  region: string;
  country: CountryCode;
  countryName: string;
  tz: string;
  lat: number;
  lon: number;
};

export const CITIES: City[] = [
  { id: "clyde", name: "Clyde", region: "Victoria", country: "AU", countryName: "Australia", tz: "Australia/Melbourne", lat: -38.1297, lon: 145.3267 },
  { id: "berwick", name: "Berwick", region: "Victoria", country: "AU", countryName: "Australia", tz: "Australia/Melbourne", lat: -38.0293, lon: 145.343 },
  { id: "melbourne", name: "Melbourne", region: "Victoria", country: "AU", countryName: "Australia", tz: "Australia/Melbourne", lat: -37.8136, lon: 144.9631 },
  { id: "brisbane", name: "Brisbane", region: "Queensland", country: "AU", countryName: "Australia", tz: "Australia/Brisbane", lat: -27.4698, lon: 153.0251 },
  { id: "chintsa", name: "Chintsa", region: "Eastern Cape", country: "ZA", countryName: "South Africa", tz: "Africa/Johannesburg", lat: -32.8325, lon: 28.1188 },
  { id: "east-london", name: "East London", region: "Eastern Cape", country: "ZA", countryName: "South Africa", tz: "Africa/Johannesburg", lat: -33.0292, lon: 27.8546 },
  { id: "kempton-park", name: "Kempton Park", region: "Gauteng", country: "ZA", countryName: "South Africa", tz: "Africa/Johannesburg", lat: -26.1087, lon: 28.2322 },
  { id: "cape-town", name: "Cape Town", region: "Western Cape", country: "ZA", countryName: "South Africa", tz: "Africa/Johannesburg", lat: -33.9249, lon: 18.4241 },
  { id: "the-hague", name: "The Hague", region: "South Holland", country: "NL", countryName: "Netherlands", tz: "Europe/Amsterdam", lat: 52.0705, lon: 4.3007 },
  { id: "kuala-lumpur", name: "Kuala Lumpur", region: "Federal Territory", country: "MY", countryName: "Malaysia", tz: "Asia/Kuala_Lumpur", lat: 3.139, lon: 101.6869 },
];

export const DEFAULT_CITY_ID = "clyde";

export function getCity(id: string | null | undefined): City | undefined {
  return id ? CITIES.find((c) => c.id === id) : undefined;
}
