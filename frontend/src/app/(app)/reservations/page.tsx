import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { ReservationStatusBadge } from "@/components/reservations/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { accessOf } from "@/lib/access";
import { addDays, formatStayDate, isIsoDate, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { PropertySummary, ReservationSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Reservations" };

export default async function ReservationsPage({ searchParams }: PageProps<"/reservations">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("reservations.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) =>
    access.canAt("reservations.view", p.id),
  );
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Reservations" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const from = isIsoDate(sp.from) ? sp.from : todayIn(current.timezone);
  const to = addDays(from, 14);
  const reservations = await apiGet<ReservationSummary[]>(
    `/api/v1/properties/${current.id}/reservations?from=${from}&to=${to}`,
  );
  const link = (params: Record<string, string>) =>
    `/reservations?${new URLSearchParams({ property: current.id, from, ...params })}`;

  return (
    <>
      <PageHeader
        title="Reservations"
        description={`${current.name} · stays from ${formatStayDate(from, { day: "numeric", month: "short" })} to ${formatStayDate(to, { day: "numeric", month: "short", year: "numeric" })}`}
        actions={
          access.canAt("reservations.manage", current.id) ? (
            <Button asChild>
              <Link href={`/reservations/new?property=${current.id}`}>
                <Plus aria-hidden />
                New booking
              </Link>
            </Button>
          ) : null
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5">
            {properties.map((p) => (
              <Link
                key={p.id}
                href={`/reservations?property=${p.id}`}
                aria-current={p.id === current.id ? "page" : undefined}
                className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white"
              >
                {p.name}
              </Link>
            ))}
          </nav>
        ) : null}
        <nav aria-label="Dates" className="ml-auto flex gap-1.5">
          <Button asChild variant="secondary" size="sm">
            <Link href={link({ from: addDays(from, -14) })}>Previous 2 weeks</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href={`/reservations?property=${current.id}`}>Today</Link>
          </Button>
          <Button asChild variant="secondary" size="sm">
            <Link href={link({ from: to })}>Next 2 weeks</Link>
          </Button>
        </nav>
      </div>

      {reservations.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">No bookings in these two weeks.</p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {reservations.map((r) => (
            <li key={r.id}>
              <Link href={`/reservations/${r.id}`} className="grid gap-x-4 gap-y-1 px-4 py-3 hover:bg-mist sm:grid-cols-[7rem_minmax(0,1fr)_12rem_8rem_9rem] sm:items-center">
                <span className="font-mono text-[13px] text-forest">{r.reference}</span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-forest">{r.guest_name}</span>
                  <span className="block text-[13px] text-muted">
                    {r.room_count} {r.room_count === 1 ? "room" : "rooms"} · {r.nights} {r.nights === 1 ? "night" : "nights"}
                  </span>
                </span>
                <span className="text-sm">
                  {formatStayDate(r.check_in)} – {formatStayDate(r.check_out)}
                </span>
                <span><ReservationStatusBadge status={r.status} /></span>
                <span className="font-mono text-sm sm:text-right">{formatMoney(r.total_amount, r.currency)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
