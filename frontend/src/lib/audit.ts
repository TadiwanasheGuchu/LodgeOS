import type { AuditLogEntry } from "@/lib/types";

const LABELS: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.logout": "Signed out",
  "auth.organisation_switched": "Switched to this organisation",
  "organisation.updated": "Changed organisation details",
  "organisation.bootstrapped": "Organisation created",
  "member.added": "Added a team member",
};

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  default_currency: "Currency",
  default_timezone: "Timezone",
  country_code: "Country",
};

export function describeAction(entry: AuditLogEntry): string {
  return LABELS[entry.action] ?? entry.action;
}

/** "Currency: NAD → ZAR" lines for an organisation.updated entry. */
export function describeChanges(entry: AuditLogEntry): string[] {
  if (entry.action !== "organisation.updated") return [];
  const before = (entry.data.before ?? {}) as Record<string, unknown>;
  const after = (entry.data.after ?? {}) as Record<string, unknown>;
  return Object.keys(after)
    .filter((k) => before[k] !== after[k])
    .map((k) => `${FIELD_LABELS[k] ?? k}: ${String(before[k] ?? "—")} → ${String(after[k] ?? "—")}`);
}
