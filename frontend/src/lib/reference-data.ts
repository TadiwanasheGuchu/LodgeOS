/** Currencies offered in settings. The API accepts any ISO 4217 code. */
export const CURRENCIES: { code: string; name: string }[] = [
  { code: "NAD", name: "Namibian dollar" },
  { code: "ZAR", name: "South African rand" },
  { code: "USD", name: "US dollar" },
  { code: "BWP", name: "Botswana pula" },
  { code: "ZMW", name: "Zambian kwacha" },
  { code: "ZWG", name: "Zimbabwe Gold" },
  { code: "EUR", name: "Euro" },
  { code: "GBP", name: "Pound sterling" },
];

/** Countries listed first; others can be added as markets open. */
export const COUNTRIES: { code: string; name: string }[] = [
  { code: "NA", name: "Namibia" },
  { code: "ZW", name: "Zimbabwe" },
  { code: "ZA", name: "South Africa" },
  { code: "BW", name: "Botswana" },
  { code: "ZM", name: "Zambia" },
  { code: "MZ", name: "Mozambique" },
  { code: "AO", name: "Angola" },
  { code: "MW", name: "Malawi" },
  { code: "TZ", name: "Tanzania" },
  { code: "KE", name: "Kenya" },
];

/** Timezones in the browser's IANA database, regional ones first. */
export function timezones(current: string): string[] {
  const all: string[] =
    typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [current];
  const africa = all.filter((tz) => tz.startsWith("Africa/"));
  const rest = all.filter((tz) => !tz.startsWith("Africa/"));
  const list = [...africa, ...rest];
  return list.includes(current) ? list : [current, ...list];
}
