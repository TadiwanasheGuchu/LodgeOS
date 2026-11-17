/**
 * Display helpers for money. The API sends decimal strings; the browser only formats them
 * and never calculates with them (totals come from the server).
 */

/** "1250.5" or "1250.50" -> "1 250.50" with a currency code, e.g. "NAD 1 250.50". */
export function formatMoney(amount: string, currency: string): string {
  const negative = amount.startsWith("-");
  const [whole, fraction = ""] = amount.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${currency} ${negative ? "-" : ""}${grouped}.${fraction.padEnd(2, "0").slice(0, 2)}`;
}

/** Accepts "1250", "1 250.5", "1,250.50"; returns a canonical "1250.50" or null if invalid. */
export function parseMoneyInput(raw: string): string | null {
  const cleaned = raw.replace(/[\s ,]/g, "");
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, fraction = ""] = cleaned.split(".");
  return `${String(Number(whole))}.${fraction.padEnd(2, "0")}`;
}

/** "15.0000" -> "15", "7.5000" -> "7.5" */
export function formatPercent(rate: string): string {
  return `${rate.replace(/\.?0+$/, "")}%`;
}

/**
 * Exact sum of decimal-string amounts for previews, using whole cents (BigInt), never
 * floating point. The server's total remains the authoritative figure.
 */
export function sumMoney(amounts: string[]): string {
  const ZERO = BigInt(0);
  const HUNDRED = BigInt(100);
  let cents = ZERO;
  for (const a of amounts) {
    const negative = a.startsWith("-");
    const [whole, fraction = ""] = a.replace("-", "").split(".");
    const value = BigInt(whole || "0") * HUNDRED + BigInt((fraction + "00").slice(0, 2));
    cents += negative ? -value : value;
  }
  const sign = cents < ZERO ? "-" : "";
  const abs = cents < ZERO ? -cents : cents;
  return `${sign}${abs / HUNDRED}.${(abs % HUNDRED).toString().padStart(2, "0")}`;
}
