import { describe, expect, it } from "vitest";
import { Access } from "@/lib/access";

describe("Access", () => {
  const a = new Access({
    permissions: ["organisation.view"],
    property_permissions: { A: ["properties.view", "rooms.view", "rooms.housekeeping_update"] },
  });

  it("separates organisation-wide and per-property permissions", () => {
    expect(a.can("organisation.view")).toBe(true);
    expect(a.can("rooms.view")).toBe(false);
    expect(a.canAnywhere("rooms.view")).toBe(true);
    expect(a.canAt("rooms.view", "A")).toBe(true);
    expect(a.canAt("rooms.view", "B")).toBe(false);
    expect(a.canAnywhere("rooms.manage")).toBe(false);
  });
});
