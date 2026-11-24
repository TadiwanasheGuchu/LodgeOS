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
  "housekeeping.assign": "Assigned a room for cleaning",
  "housekeeping.start": "Started cleaning a room",
  "housekeeping.done": "Finished cleaning a room",
  "housekeeping.decline": "Recorded service declined",
  "housekeeping.reopen": "Sent a room back for cleaning",
  "invoice.drafted": "Started an invoice",
  "invoice.issued": "Issued an invoice",
  "invoice.discarded": "Discarded a draft invoice",
  "invoice.credited": "Issued a credit note",
  "payment.recorded": "Recorded a payment",
  "payment.allocated": "Applied a payment to an invoice",
  "payment.released": "Took a payment off an invoice",
  "payment.refunded": "Refunded money",
  "payment.reversed": "Reversed a payment",
  "notification.queued": "Emailed a guest",
  "reservation.guest_link_created": "Created a guest link",
  "reservation.guest_links_revoked": "Withdrew guest links",
  "reservation.guest_updated": "Guest sent arrival details",
  "reservation.cancellation_requested": "Guest asked to cancel",
  "reservation.cancellation_request_dismissed": "Kept a booking after a cancellation request",
  "pos.sale": "Rang up a sale",
  "maintenance.reported": "Reported a maintenance problem",
  "maintenance.updated": "Updated a maintenance ticket",
  "maintenance.room_blocked": "Took a room out of sale",
  "maintenance.room_released": "Put a room back on sale",
  "reservation.created": "Made a booking",
  "reservation.confirmed": "Confirmed a booking",
  "reservation.cancelled": "Cancelled a booking",
  "reservation.room_assigned": "Assigned a room",
  "reservation.checked_in": "Checked in a guest",
  "reservation.checked_out": "Checked out a guest",
  "reservation.no_show": "Marked a no-show",
  "reservation.dates_changed": "Changed booking dates",
  "guest.updated": "Updated guest details",
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
  if (entry.action.startsWith("housekeeping.") && d.room) {
    return [`Room ${String(d.room)}, ${String(d.date)}`];
  }
  if (entry.action === "invoice.credited") {
    return [`${String(d.number)} against ${String(d.invoice)}: ${String(d.total)}`];
  }
  if (entry.action.startsWith("invoice.") && d.bill_to) {
    return [d.number ? `${String(d.number)} to ${String(d.bill_to)}: ${String(d.total)}` : `For ${String(d.bill_to)}`];
  }
  if (entry.action.startsWith("payment.") && d.amount) {
    const amount = `${String(d.currency)} ${String(d.amount)}`;
    if (entry.action === "payment.refunded") return [`${String(d.currency)} ${String(d.refunded)}: ${String(d.reason)}`];
    if (entry.action === "payment.reversed") return [`${amount}: ${String(d.reason)}`];
    if (entry.action === "payment.allocated") return [`${String(d.currency)} ${String(d.to)} to ${String(d.invoice)}`];
    if (entry.action === "payment.released") return [`${String(d.currency)} ${String(d.released)} from ${String(d.invoice)}`];
    return [d.payer ? `${amount} from ${String(d.payer)}` : amount];
  }
  if (entry.action === "notification.queued" && d.title) {
    return [String(d.title)];
  }
  if (entry.action === "maintenance.reported" && d.title) {
    return [String(d.title)];
  }
  if (entry.action === "maintenance.room_blocked") {
    return [`Room ${String(d.room)}: ${String(d.from)} until ${String(d.to)}`];
  }
  if (!entry.action.endsWith(".updated")) return [];
  const before = (entry.data.before ?? {}) as Record<string, unknown>;
  const after = (entry.data.after ?? {}) as Record<string, unknown>;
  return Object.keys(after)
    .filter((k) => before[k] !== after[k])
    .map((k) => `${FIELD_LABELS[k] ?? k}: ${String(before[k] ?? "—")} → ${String(after[k] ?? "—")}`);
}
