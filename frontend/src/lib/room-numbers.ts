/**
 * Expands room-number input such as "101-105, 110, Tent 1" into a list.
 * Ranges work for plain numbers and for a shared prefix ("A1-A4").
 */
export function parseRoomNumbers(input: string): { numbers: string[]; error: string | null } {
  const parts = input
    .split(/[,\n]/)
    .map((p) => p.trim())
    .filter(Boolean);
  const numbers: string[] = [];
  for (const part of parts) {
    const range = part.match(/^([A-Za-z]*\s?)(\d+)\s*[-–]\s*\1?(\d+)$/);
    if (range) {
      const [, prefix, fromText, toText] = range;
      const from = Number(fromText);
      const to = Number(toText);
      if (to < from) return { numbers: [], error: `"${part}" counts backwards.` };
      if (to - from > 199) return { numbers: [], error: `"${part}" is more than 200 rooms.` };
      const width = fromText.length === toText.length && fromText.startsWith("0") ? fromText.length : 0;
      for (let n = from; n <= to; n++) numbers.push(`${prefix}${String(n).padStart(width, "0")}`);
    } else if (/^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,19}$/.test(part)) {
      numbers.push(part);
    } else {
      return { numbers: [], error: `"${part}" is not a valid room number.` };
    }
  }
  const seen = new Set<string>();
  const dupes = numbers.filter((n) => (seen.has(n) ? true : (seen.add(n), false)));
  if (dupes.length) return { numbers: [], error: `Listed more than once: ${[...new Set(dupes)].join(", ")}.` };
  if (numbers.length > 200) return { numbers: [], error: "Add at most 200 rooms at a time." };
  return { numbers, error: null };
}
