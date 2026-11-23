import { formatDateTime } from "@/lib/format";
import type { NotificationRecord } from "@/lib/types";

const STATUS: Record<NotificationRecord["status"], string> = {
  queued: "Waiting to send",
  sent: "Sent",
  failed: "Could not be delivered",
};

/** Emails sent about one booking, invoice or payment, newest first. */
export function EmailLog({ items, timezone }: { items: NotificationRecord[]; timezone: string }) {
  if (items.length === 0) return null;
  return (
    <ul aria-label="Emails" className="mt-2 flex flex-col gap-2 text-[13px]">
      {items.map((n) => (
        <li key={n.id} className="rounded-md border border-line px-3 py-2">
          <p className="font-medium text-charcoal">{n.title}</p>
          <p className="text-muted">
            To {n.recipient} · {formatDateTime(n.created_at, timezone)}
          </p>
          <p className={n.status === "failed" ? "text-danger" : n.status === "sent" ? "text-success" : "text-charcoal"}>
            {STATUS[n.status]}
            {n.status === "sent" && n.provider === "mock" ? " (test mode: not delivered to the guest)" : ""}
            {n.status === "queued" && n.attempts > 0 ? `, retrying after ${n.attempts} attempt${n.attempts === 1 ? "" : "s"}` : ""}
          </p>
          {n.last_error ? <p className="font-mono text-[12px] text-muted">{n.last_error}</p> : null}
        </li>
      ))}
    </ul>
  );
}
