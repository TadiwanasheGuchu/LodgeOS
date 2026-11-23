import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ReservationStatusBadge } from "@/components/reservations/status-badge";
import { accessOf } from "@/lib/access";
import { formatStayDate, todayIn } from "@/lib/dates";
import { formatDateTime } from "@/lib/format";
import { formatMoney, formatPercent } from "@/lib/money";
import { apiGet, requireOrganisation, ServerApiError } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import { BOOKING_SOURCE_LABELS, RESERVATION_STATUS_LABELS, type InvoicePayments, type InvoiceSummary, type Payment, type ReservationDetail } from "@/lib/types";
import { InvoiceStatusChip } from "../../invoices/status";
import { BookingPayments } from "./booking-payments";
import { CreateInvoice } from "./create-invoice";
import { AssignRoom } from "./assign-room";
import { ReservationActions } from "./reservation-actions";

export const metadata: Metadata = { title: "Reservation" };

export default async function ReservationPage({ params }: PageProps<"/reservations/[id]">) {
  const { id } = await params;
  const me = await requireOrganisation();
  let r: ReservationDetail;
  try {
    r = await apiGet<ReservationDetail>(`/api/v1/reservations/${id}`);
  } catch (err) {
    if (err instanceof ServerApiError && (err.status === 404 || err.status === 422)) notFound();
    throw err;
  }
  const property = await loadProperty(r.property_id);
  const access = accessOf(me);
  const canManage = access.canAt("reservations.manage", r.property_id);
  const canInvoice = access.canAt("invoices.manage", r.property_id);
  const invoices = access.canAt("invoices.view", r.property_id)
    ? await apiGet<InvoiceSummary[]>(`/api/v1/properties/${r.property_id}/invoices?reservation_id=${r.id}`)
    : null;
  const payments = access.canAt("payments.view", r.property_id)
    ? await apiGet<Payment[]>(`/api/v1/properties/${r.property_id}/payments?reservation_id=${r.id}`)
    : null;
  const openInvoices = payments && invoices
    ? (
        await Promise.all(
          invoices
            .filter((i) => i.status === "issued")
            .map(async (i) => ({ i, m: await apiGet<InvoicePayments>(`/api/v1/invoices/${i.id}/payments`) })),
        )
      )
        .filter(({ m }) => m.balance !== "0.00" && !m.balance.startsWith("-"))
        .map(({ i, m }) => ({ id: i.id, number: i.number ?? "", balance: m.balance }))
    : [];
  const long = { weekday: "short", day: "numeric", month: "short", year: "numeric" } as const;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted">
            <Link href={`/reservations?property=${r.property_id}`} className="underline-offset-2 hover:underline">Reservations</Link> · {property.name}
          </p>
          <h1 className="mt-1 flex flex-wrap items-center gap-3 text-lg font-semibold text-forest">
            <span className="font-mono">{r.reference}</span>
            <ReservationStatusBadge status={r.status} />
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            {r.guest_name} · {formatStayDate(r.check_in, long)} to {formatStayDate(r.check_out, long)} · {r.nights} {r.nights === 1 ? "night" : "nights"}
          </p>
        </div>
        {canManage ? <ReservationActions reservation={r} today={todayIn(property.timezone)} /> : null}
      </div>

      {r.status === "cancelled" && r.cancellation_reason ? (
        <p className="rounded-md border border-danger/30 bg-danger-tint px-4 py-3 text-sm text-danger">Cancelled: {r.cancellation_reason}</p>
      ) : null}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section aria-labelledby="rooms-heading" className="rounded-lg border border-line bg-white">
          <h2 id="rooms-heading" className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">
            {r.room_count} {r.room_count === 1 ? "room" : "rooms"}
          </h2>
          <ul className="divide-y divide-line">
            {r.rooms.map((room) => (
              <li key={room.id} className="px-5 py-4 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-forest">
                    {room.room_type_name}
                    <span className="ml-2 font-normal text-muted">{room.room_number ? `Room ${room.room_number}` : "Room not assigned yet"}</span>
                  </p>
                  {canManage && ["provisional", "confirmed", "checked_in"].includes(r.status) ? (
                    <AssignRoom reservationRoomId={room.id} roomNumber={room.room_number} label={room.room_type_name} />
                  ) : null}
                  <p className="text-muted">
                    {room.price_snapshot.rate_plan} · {room.adults} {room.adults === 1 ? "adult" : "adults"}
                    {room.children ? `, ${room.children} ${room.children === 1 ? "child" : "children"}` : ""}
                  </p>
                </div>
                <table className="mt-2 w-full">
                  <caption className="sr-only">Price per night as booked</caption>
                  <tbody>
                    {room.price_snapshot.nights.map((n) => (
                      <tr key={n.date}>
                        <td className="py-0.5 text-muted">
                          {formatStayDate(n.date)}
                          {n.season ? ` · ${n.season}` : n.weekend ? " · weekend" : ""}
                        </td>
                        <td className="py-0.5 text-right font-mono">{formatMoney(n.amount, room.price_snapshot.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </li>
            ))}
          </ul>
          <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-t border-line px-5 py-3 text-sm">
            {r.rooms.flatMap((room) => room.price_snapshot.taxes).length ? (
              <>
                <dt className="text-muted">Of which tax</dt>
                <dd className="text-right font-mono">{formatMoney(r.tax_amount, r.currency)}</dd>
              </>
            ) : null}
            <dt className="font-semibold text-forest">Total</dt>
            <dd className="text-right font-mono font-semibold text-forest">{formatMoney(r.total_amount, r.currency)}</dd>
          </dl>
          {r.rooms[0]?.price_snapshot.taxes.length ? (
            <p className="border-t border-line px-5 py-2 text-[12px] text-muted">
              Taxes: {r.rooms[0].price_snapshot.taxes.map((t) => `${t.name} ${formatPercent(t.rate_percent)}`).join(", ")}. Prices are kept as booked, even if rates change later.
            </p>
          ) : null}
        </section>

        <div className="flex flex-col gap-6">
          <section aria-labelledby="guest-heading" className="rounded-lg border border-line bg-white px-5 py-4 text-sm">
            <h2 id="guest-heading" className="text-sm font-semibold text-forest">Guest</h2>
            <p className="mt-2 font-medium text-forest">{r.guest.first_name} {r.guest.last_name}</p>
            {r.guest.email ? <p><a href={`mailto:${r.guest.email}`} className="text-teal underline-offset-2 hover:underline">{r.guest.email}</a></p> : null}
            {r.guest.phone ? <p><a href={`tel:${r.guest.phone}`} className="text-teal underline-offset-2 hover:underline">{r.guest.phone}</a></p> : null}
            <p className="mt-2 text-muted">Booked by {BOOKING_SOURCE_LABELS[r.source].toLowerCase()}</p>
            {r.notes ? <p className="mt-2 whitespace-pre-wrap">{r.notes}</p> : null}
          </section>

          {invoices ? (
            <section aria-labelledby="invoices-heading" className="rounded-lg border border-line bg-white px-5 py-4 text-sm">
              <h2 id="invoices-heading" className="text-sm font-semibold text-forest">Invoices</h2>
              {invoices.length > 0 ? (
                <ul className="mt-2 flex flex-col gap-2">
                  {invoices.map((inv) => (
                    <li key={inv.id} className="flex items-center justify-between gap-2">
                      <Link href={`/invoices/${inv.id}`} className="font-mono text-forest underline-offset-2 hover:underline">{inv.number ?? "Draft"}</Link>
                      <span className="font-mono tabular">{formatMoney(inv.total, inv.currency)}</span>
                      <InvoiceStatusChip status={inv.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-muted">Not invoiced yet.</p>
              )}
              {canInvoice && r.status !== "cancelled" && r.status !== "no_show" ? <CreateInvoice reservationId={r.id} propertyId={r.property_id} /> : null}
            </section>
          ) : null}

          {payments ? (
            <BookingPayments
              propertyId={r.property_id}
              reservationId={r.id}
              currency={r.currency}
              payments={payments}
              openInvoices={openInvoices}
              canRecord={access.canAt("payments.manage", r.property_id) && r.status !== "cancelled"}
              today={todayIn(property.timezone)}
            />
          ) : null}

          <section aria-labelledby="history-heading" className="rounded-lg border border-line bg-white px-5 py-4 text-sm">
            <h2 id="history-heading" className="text-sm font-semibold text-forest">History</h2>
            <ol className="mt-2 flex flex-col gap-2">
              {r.history.map((h, i) => (
                <li key={i}>
                  <p>{RESERVATION_STATUS_LABELS[h.to_status]}{h.changed_by_name ? ` by ${h.changed_by_name}` : ""}</p>
                  <p className="text-[12px] text-muted">{formatDateTime(h.changed_at, property.timezone)}</p>
                  {h.reason ? <p className="text-[13px] text-muted">{h.reason}</p> : null}
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
