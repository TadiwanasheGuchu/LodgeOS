import Link from "next/link";
import { ReservationStatusBadge } from "@/components/reservations/status-badge";
import { formatStayDate } from "@/lib/dates";
import type { ReservationSummary, TodayData } from "@/lib/types";

function List({ title, items, empty }: { title: string; items: ReservationSummary[]; empty: string }) {
  return (
    <div>
      <h3 className="px-5 pt-3 pb-1 text-[13px] font-semibold tracking-wide text-muted uppercase">
        {title} <span className="tabular font-normal">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="px-5 pb-3 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((r) => (
            <li key={r.id}>
              <Link href={`/reservations/${r.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-2.5 text-sm hover:bg-mist">
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-forest">{r.guest_name}</span>
                  <span className="block text-[12px] text-muted">
                    <span className="font-mono">{r.reference}</span> · {r.room_count} {r.room_count === 1 ? "room" : "rooms"} · {r.nights}{" "}
                    {r.nights === 1 ? "night" : "nights"}
                  </span>
                </span>
                <ReservationStatusBadge status={r.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Today's arrivals and departures for one property, in the property's own date. */
export function TodayPanel({ propertyName, data }: { propertyName: string; data: TodayData }) {
  if (data.arrivals.length === 0 && data.departures.length === 0) {
    return (
      <p className="flex flex-wrap justify-between gap-2 rounded-lg border border-line bg-white px-5 py-3 text-sm">
        <span>
          <span className="font-semibold text-forest">Today at {propertyName}</span>
          <span className="text-muted"> · no arrivals or departures</span>
        </span>
        <span className="text-[13px] text-muted">{data.in_house} in house</span>
      </p>
    );
  }
  return (
    <section aria-labelledby={`today-${data.date}-${propertyName}`} className="rounded-lg border border-line bg-white">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-5 py-3">
        <h2 id={`today-${data.date}-${propertyName}`} className="text-sm font-semibold text-forest">
          Today at {propertyName} · {formatStayDate(data.date, { weekday: "long", day: "numeric", month: "long" })}
        </h2>
        <span className="text-[13px] text-muted">{data.in_house} in house</span>
      </div>
      {data.unassigned_arrivals > 0 ? (
        <p className="border-b border-warning bg-warning-tint px-5 py-2 text-[13px] text-charcoal">
          {data.unassigned_arrivals} arriving {data.unassigned_arrivals === 1 ? "room has" : "rooms have"} no room number yet.{" "}
          <Link href="/calendar" className="font-medium underline underline-offset-2">Open the calendar</Link>
        </p>
      ) : null}
      <div className="grid divide-line sm:grid-cols-2 sm:divide-x">
        <List title="Arriving" items={data.arrivals} empty="No arrivals today." />
        <List title="Leaving" items={data.departures} empty="No departures today." />
      </div>
    </section>
  );
}
