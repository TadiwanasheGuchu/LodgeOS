import type { AuditLogEntry } from "@/lib/types";

const LABELS: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.logout": "Signed out",
  "auth.organisation_switched": "Switched to this organisation",
  "organisation.updated": "Changed organisation details",
  "organisation.bootstrapped": "Organisation created",
  "member.added": "Added a team member",
  "property.created": "Added a property",
  "property.updated": "Changed property details",
  "building.created": "Added a building",
  "building.updated": "Changed a building",
  "room_type.created": "Added a room type",
  "room_type.updated": "Changed a room type",
  "room.created": "Added a room",
  "room.bulk_created": "Added rooms",
  "room.updated": "Changed a room",
  "room.housekeeping_changed": "Changed room cleaning status",
  "room.maintenance_changed": "Changed room maintenance status",
  "member.role_added": "Gave a role",
  "member.role_removed": "Removed a role",
  "member.disabled": "Turned off someone's access",
  "member.enabled": "Turned on someone's access",
  "invitation.created": "Invited someone",
  "invitation.revoked": "Withdrew an invitation",
  "invitation.accepted": "Accepted an invitation and joined",
  "tax.created": "Added a tax",
  "tax.updated": "Changed a tax",
  "rate_plan.created": "Added a rate plan",
  "rate_plan.updated": "Changed a rate plan",
  "rate_plan.price_set": "Set prices",
  "rate_plan.price_cleared": "Cleared prices",
  "season.created": "Added a season",
  "season.updated": "Changed a season",
  "season.deleted": "Deleted a season",
  "reservation.created": "Made a booking",
  "reservation.confirmed": "Confirmed a booking",
  "reservation.cancelled": "Cancelled a booking",
  "reservation.room_assigned": "Assigned a room",
};

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  status: "Status",
  timezone: "Timezone",
  currency: "Currency",
  check_in_time: "Check-in from",
  check_out_time: "Check-out by",
  number: "Number",
  floor: "Floor",
  default_currency: "Currency",
  default_timezone: "Timezone",
  country_code: "Country",
};

export function describeAction(entry: AuditLogEntry): string {
  return LABELS[entry.action] ?? entry.action;
}

/** "Currency: NAD → ZAR" lines for an organisation.updated entry. */
const STATUS_WORDS: Record<string, string> = {
  dirty: "dirty",
  clean: "clean",
  inspected: "inspected",
  none: "no issue",
  out_of_service: "out of service",
  out_of_order: "out of order",
};

export function describeChanges(entry: AuditLogEntry): string[] {
  const d = entry.data as Record<string, unknown>;
  if (entry.action === "room.housekeeping_changed" || entry.action === "room.maintenance_changed") {
    const line = `Room ${String(d.number)}: ${STATUS_WORDS[String(d.from)] ?? d.from} → ${STATUS_WORDS[String(d.to)] ?? d.to}`;
    return d.reason ? [line, `Reason: ${String(d.reason)}`] : [line];
  }
  if (entry.action === "room.bulk_created" && Array.isArray(d.numbers)) {
    return [`Rooms ${(d.numbers as string[]).join(", ")}`];
  }
  if (entry.action === "member.role_added" || entry.action === "member.role_removed") {
    return [String(d.role)];
  }
  if (entry.action.startsWith("invitation.") && d.email) {
    return [d.role ? `${String(d.email)} as ${String(d.role)}` : String(d.email)];
  }
  if (!entry.action.endsWith(".updated")) return [];
  const before = (entry.data.before ?? {}) as Record<string, unknown>;
  const after = (entry.data.after ?? {}) as Record<string, unknown>;
  return Object.keys(after)
    .filter((k) => before[k] !== after[k])
    .map((k) => `${FIELD_LABELS[k] ?? k}: ${String(before[k] ?? "—")} → ${String(after[k] ?? "—")}`);
}
