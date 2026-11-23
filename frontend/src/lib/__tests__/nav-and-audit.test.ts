import { describe, expect, it } from "vitest";
import { navFor } from "@/components/shell/nav";
import { Access } from "@/lib/access";
import { describeAction, describeChanges } from "@/lib/audit";
import type { AuditLogEntry, Permission } from "@/lib/types";

describe("navFor", () => {
  it("shows only screens the role may open", () => {
    const only = (permissions: Permission[], property_permissions: Record<string, Permission[]> = {}) =>
      navFor(new Access({ permissions, property_permissions })).map((i) => i.href);
    expect(only(["organisation.view"])).toEqual(["/", "/settings"]);
    // A role at one property is enough to see the screen.
    expect(only(["organisation.view"], { A: ["rooms.view", "properties.view"] })).toEqual([
      "/",
      "/rooms",
      "/maintenance",
      "/properties",
      "/settings",
    ]);
    expect(only(["organisation.view", "members.view", "audit.view"])).toEqual([
      "/",
      "/team",
      "/activity",
      "/settings",
    ]);
  });
});

describe("audit descriptions", () => {
  const entry = (over: Partial<AuditLogEntry>): AuditLogEntry => ({
    id: "1",
    action: "organisation.updated",
    actor_user_id: null,
    actor_name: null,
    entity_type: null,
    entity_id: null,
    data: {},
    created_at: "2026-11-16T10:00:00Z",
    ...over,
  });

  it("lists only fields whose value changed", () => {
    const e = entry({ data: { before: { default_currency: "NAD", name: "A" }, after: { default_currency: "ZAR", name: "A" } } });
    expect(describeChanges(e)).toEqual(["Currency: NAD → ZAR"]);
  });

  it("falls back to the raw action for unknown events", () => {
    expect(describeAction(entry({ action: "something.new" }))).toBe("something.new");
    expect(describeAction(entry({ action: "auth.login" }))).toBe("Signed in");
  });
});
