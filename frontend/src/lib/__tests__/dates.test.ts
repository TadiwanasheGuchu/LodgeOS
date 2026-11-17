import { describe, expect, it } from "vitest";
import { addDays, formatStayDate, isIsoDate } from "@/lib/dates";

describe("stay dates", () => {
  it("adds days across month and year ends without time zone drift", () => {
    expect(addDays("2026-12-30", 3)).toBe("2027-01-02");
    expect(addDays("2028-02-28", 1)).toBe("2028-02-29");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
  it("formats and validates", () => {
    expect(formatStayDate("2026-12-18")).toBe("Fri 18 Dec");
    expect(isIsoDate("2026-12-18")).toBe(true);
    expect(isIsoDate("18/12/2026")).toBe(false);
    expect(isIsoDate(undefined)).toBe(false);
  });
});
