import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { accessOf } from "@/lib/access";
import { addDays, formatStayDate, isIsoDate, todayIn } from "@/lib/dates";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { CalendarData, CalendarStay, PropertySummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Calendar" };

const DAYS = 14;
const STATUS_BAR: Record<string, string> = {
  provisional: "border-warning bg-warning-tint text-charcoal border-dashed",
  confirmed: "border-teal bg-mist text-forest",
  checked_in: "border-success bg-success-tint text-success",
};

function nightsBetween(a: string, b: string) {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
}

/** Grid column placement of a stay within the visible window (1-based, clipped). */
function placement(stay: CalendarStay, start: string) {
  const from = Math.max(0, nightsBetween(start, stay.check_in));
  const to = Math.min(DAYS, nightsBetween(start, stay.check_out));
  return { column: from + 2, span: Math.max(1, to - from), clippedStart: nightsBetween(start, stay.check_in) < 0, clippedEnd: nightsBetween(start, stay.check_out) > DAYS };
}

function StayBar({ stay, start, row }: { stay: CalendarStay; start: string; row: number }) {
  const p = placement(stay, start);
  return (
    <Link
      href={`/reservations/${stay.reservation_id}`}
      style={{ gridColumn: `${p.column} / span ${p.span}`, gridRow: row }}
      className={cn(
        "relative z-10 my-1 flex min-w-0 items-center truncate rounded-sm border px-2 text-[12px] font-medium hover:brightness-95",
        STATUS_BAR[stay.status],
        p.clippedStart && "rounded-l-none border-l-0",
        p.clippedEnd && "rounded-r-none border-r-0",
      )}
      title={`${stay.reference} · ${stay.guest_name} · ${stay.check_in} to ${stay.check_out}`}
    >
      <span className="truncate">{stay.guest_name}</span>
    </Link>
  );
}

export default async function CalendarPage({ searchParams }: PageProps<"/calendar">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("reservations.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("reservations.view", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Calendar" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const today = todayIn(current.timezone);
  const start = isIsoDate(sp.start) ? sp.start : addDays(today, -1);
  const data = await apiGet<CalendarData>(`/api/v1/properties/${current.id}/calendar?start=${start}&days=${DAYS}`);
  const dates = Array.from({ length: DAYS }, (_, i) => addDays(start, i));
  const link = (s: string) => `/calendar?${new URLSearchParams({ property: current.id, start: s })}`;

  // Rows: each room; after each room type's rooms, one row per unassigned stay of that type.
  type Row = { key: string; label: string; sub?: string; stays: CalendarStay[]; unassigned?: boolean };
  const rows: Row[] = [];
  const typeOrder = [...new Set(data.rooms.map((r) => r.room_type_id))];
  for (const typeId of typeOrder) {
    for (const room of data.rooms.filter((r) => r.room_type_id === typeId)) {
      rows.push({
        key: room.id,
        label: room.number,
        sub: room.room_type_code + (room.maintenance_status === "out_of_order" ? " · out of order" : ""),
        stays: data.stays.filter((s) => s.room_id === room.id),
      });
    }
    const code = data.rooms.find((r) => r.room_type_id === typeId)?.room_type_code ?? "";
    for (const stay of data.stays.filter((s) => s.room_type_id === typeId && !s.room_id)) {
      rows.push({ key: stay.reservation_room_id, label: "No room", sub: code, stays: [stay], unassigned: true });
    }
  }

  return (
    <>
      <PageHeader
        title="Calendar"
        description={`${current.name} · ${formatStayDate(dates[0], { day: "numeric", month: "short" })} to ${formatStayDate(dates[DAYS - 1], { day: "numeric", month: "short", year: "numeric" })}`}
        actions={
          <nav aria-label="Dates" className="flex gap-1.5">
            <Button asChild variant="secondary" size="sm"><Link href={link(addDays(start, -7))}>Previous week</Link></Button>
            <Button asChild variant="ghost" size="sm"><Link href={`/calendar?property=${current.id}`}>Today</Link></Button>
            <Button asChild variant="secondary" size="sm"><Link href={link(addDays(start, 7))}>Next week</Link></Button>
          </nav>
        }
      />
      {properties.length > 1 ? (
        <nav aria-label="Property" className="mb-4 flex flex-wrap gap-1.5">
          {properties.map((p) => (
            <Link key={p.id} href={`/calendar?property=${p.id}`} aria-current={p.id === current.id ? "page" : undefined}
              className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white">
              {p.name}
            </Link>
          ))}
        </nav>
      ) : null}

      {data.rooms.length === 0 ? (
        <Alert tone="info">{current.name} has no rooms yet.</Alert>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white" role="region" aria-label="Booking calendar" tabIndex={0}>
          <div className="grid min-w-[60rem]" style={{ gridTemplateColumns: `6.5rem repeat(${DAYS}, minmax(3.5rem, 1fr))` }}>
            <div className="sticky left-0 z-20 border-r border-b border-line bg-cloud" />
            {dates.map((d) => {
              const weekend = current.weekend_nights.includes(((new Date(`${d}T00:00:00Z`).getUTCDay() + 6) % 7) + 1);
              return (
                <div key={d} className={cn("border-b border-l border-line px-1 py-1.5 text-center text-[12px]", d === today ? "bg-forest text-white" : weekend ? "bg-mist text-forest" : "bg-cloud text-muted")}>
                  <span className="block">{formatStayDate(d, { weekday: "short" })}</span>
                  <span className="block font-semibold">{formatStayDate(d, { day: "numeric" })}</span>
                </div>
              );
            })}
            {rows.map((row, i) => (
              <div key={row.key} className="contents">
                <div style={{ gridRow: i + 2 }} className={cn("sticky left-0 z-20 border-r border-b border-line bg-white px-2 py-1.5", row.unassigned && "bg-warning-tint")}>
                  <span className={cn("block text-sm font-semibold", row.unassigned ? "text-charcoal" : "text-forest")}>{row.label}</span>
                  <span className="block text-[11px] text-muted">{row.sub}</span>
                </div>
                {dates.map((d, j) => (
                  <div key={d} style={{ gridRow: i + 2, gridColumn: j + 2 }} className={cn("border-b border-l border-line", d === today && "bg-mist/60")} />
                ))}
                {row.stays.map((s) => (
                  <StayBar key={s.reservation_room_id} stay={s} start={start} row={i + 2} />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
        <span><span className="mr-1 inline-block size-3 rounded-sm border border-teal bg-mist align-middle" />Confirmed</span>
        <span><span className="mr-1 inline-block size-3 rounded-sm border border-dashed border-warning bg-warning-tint align-middle" />Provisional</span>
        <span><span className="mr-1 inline-block size-3 rounded-sm border border-success bg-success-tint align-middle" />Checked in</span>
        <span>Yellow rows are bookings without a room yet. Open a booking to assign one.</span>
      </p>
    </>
  );
}
