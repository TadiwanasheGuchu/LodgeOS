import { describe, expect, it } from "vitest";
import { formatMoney, formatPercent, parseMoneyInput, sumMoney } from "@/lib/money";

describe("money helpers", () => {
  it("formats decimal strings without floating point", () => {
    expect(formatMoney("1250.5", "NAD")).toBe("NAD 1 250.50");
    expect(formatMoney("9999999999.99", "USD")).toBe("USD 9 999 999 999.99");
    expect(formatMoney("0.10", "ZAR")).toBe("ZAR 0.10");
    expect(formatMoney("-12.00", "NAD")).toBe("NAD -12.00");
  });
  it("parses staff input to a canonical string", () => {
    expect(parseMoneyInput("1 250.5")).toBe("1250.50");
    expect(parseMoneyInput("1,250")).toBe("1250.00");
    expect(parseMoneyInput("007")).toBe("7.00");
    expect(parseMoneyInput("12.345")).toBeNull();
    expect(parseMoneyInput("-5")).toBeNull();
    expect(parseMoneyInput("abc")).toBeNull();
  });
  it("formats tax rates", () => {
    expect(formatPercent("15.0000")).toBe("15%");
    expect(formatPercent("7.5000")).toBe("7.5%");
  });
});

describe("sumMoney", () => {
  it("adds exactly in cents", () => {
    // 0.1 + 0.2 is 0.30000000000000004 in floating point.
    expect(sumMoney(["0.10", "0.20"])).toBe("0.30");
    expect(sumMoney(["9999999999.99", "0.01"])).toBe("10000000000.00");
    expect(sumMoney(["1500.00", "-0.05"])).toBe("1499.95");
    expect(sumMoney([])).toBe("0.00");
  });
});
