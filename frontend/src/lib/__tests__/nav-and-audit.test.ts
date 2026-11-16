import { describe, expect, it } from "vitest";
import { navFor } from "@/components/shell/nav";
import { describeAction, describeChanges } from "@/lib/audit";
import type { AuditLogEntry } from "@/lib/types";

describe("navFor", () => {
  it("shows only screens the role may open", () => {
    expect(navFor(["organisation.view"]).map((i) => i.href)).toEqual(["/", "/settings"]);
    expect(navFor(["organisation.view", "members.view", "audit.view"]).map((i) => i.href)).toEqual([
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
