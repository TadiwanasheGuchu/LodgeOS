import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { accessOf } from "@/lib/access";
import { addDays, formatStayDate, isIsoDate, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { PAYMENT_METHOD_LABELS, type CashUp, type MethodTotal, type PropertySummary } from "@/lib/types";
import { WalkInPayment } from "./walk-in-payment";

export const metadata: Metadata = { title: "Payments" };

const pill =
  "rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white";

function TotalsTable({ totals, caption }: { totals: MethodTotal[]; caption: string }) {
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="text-left text-[12px] text-muted">
        <tr className="border-b border-line">
          <th scope="col" className="py-2 pr-3 font-medium">Method</th>
          <th scope="col" className="py-2 pr-3 text-right font-medium">Payments</th>
          <th scope="col" className="py-2 pr-3 text-right font-medium">Received</th>
          <th scope="col" className="py-2 pr-3 text-right font-medium">Refunded</th>
          <th scope="col" className="py-2 text-right font-medium">Net</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {totals.map((t) => (
          <tr key={`${t.method}-${t.currency}`}>
            <th scope="row" className="py-2 pr-3 text-left font-medium">{PAYMENT_METHOD_LABELS[t.method]}</th>
            <td className="py-2 pr-3 text-right tabular">{t.count}</td>
            <td className="py-2 pr-3 text-right font-mono tabular whitespace-nowrap">{formatMoney(t.received, t.currency)}</td>
            <td className="py-2 pr-3 text-right font-mono tabular whitespace-nowrap">{t.refunded === "0.00" ? "—" : formatMoney(t.refunded, t.currency)}</td>
            <td className="py-2 text-right font-mono font-semibold tabular whitespace-nowrap text-forest">{formatMoney(t.net, t.currency)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function PaymentsPage({ searchParams }: PageProps<"/payments">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("payments.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("payments.view", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Payments" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const today = todayIn(current.timezone);
  const from = isIsoDate(sp.from) ? sp.from : today;
  const to = isIsoDate(sp.to) && sp.to >= from ? sp.to : from;
  const data = await apiGet<CashUp>(`/api/v1/properties/${current.id}/cash-up?from=${from}&to=${to}`);
  const day = (iso: string) => formatStayDate(iso, { weekday: "short", day: "numeric", month: "short" });
  const range = (f: string, t: string) => `/payments?${new URLSearchParams({ property: current.id, from: f, to: t })}`;
  const single = from === to;

  return (
    <>
      <PageHeader
        title="Payments"
        description={`${current.name} · ${single ? day(from) : `${day(from)} to ${day(to)}`}`}
        actions={access.canAt("payments.manage", current.id) ? <WalkInPayment propertyId={current.id} currency={current.currency} today={today} /> : null}
      />
      <div className="mb-4 flex flex-wrap items-end gap-3 print:hidden">
        <nav aria-label="Period" className="flex gap-1.5">
          <Link href={range(today, today)} aria-current={single && from === today ? "page" : undefined} className={pill}>Today</Link>
          <Link href={range(addDays(today, -1), addDays(today, -1))} aria-current={single && from === addDays(today, -1) ? "page" : undefined} className={pill}>Yesterday</Link>
          <Link href={range(addDays(today, -6), today)} aria-current={from === addDays(today, -6) && to === today ? "page" : undefined} className={pill}>Last 7 days</Link>
        </nav>
        <form method="get" action="/payments" className="flex flex-wrap items-end gap-2">
          <input type="hidden" name="property" value={current.id} />
          <label className="text-[12px] text-muted">From<Input type="date" name="from" defaultValue={from} max={today} className="mt-0.5 h-9 w-40" /></label>
          <label className="text-[12px] text-muted">To<Input type="date" name="to" defaultValue={to} max={today} className="mt-0.5 h-9 w-40" /></label>
          <Button type="submit" size="sm" variant="secondary" className="h-9">Show</Button>
        </form>
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5 sm:ml-auto">
            {properties.map((p) => (
              <Link key={p.id} href={`/payments?property=${p.id}`} aria-current={p.id === current.id ? "page" : undefined} className={pill}>{p.name}</Link>
            ))}
          </nav>
        ) : null}
      </div>

      <section aria-label="Cash-up" className="rounded-lg border border-line bg-white px-5 py-4">
        <h2 className="text-sm font-semibold text-forest">Takings by method</h2>
        <p className="text-[13px] text-muted">Count the drawer and check the card machine against these totals. Reversed payments are left out.</p>
        {data.totals.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No money received or refunded in this period.</p>
        ) : (
          <div className="mt-2 overflow-x-auto"><TotalsTable totals={data.totals} caption="Totals for the period" /></div>
        )}
        {!single && data.days.length > 1
          ? data.days.map((d) => (
              <details key={d.date} className="mt-3 border-t border-line pt-2">
                <summary className="cursor-pointer text-sm font-medium text-forest">{day(d.date)}</summary>
                <div className="overflow-x-auto"><TotalsTable totals={d.totals} caption={`Totals for ${d.date}`} /></div>
              </details>
            ))
          : null}
      </section>

      <section aria-label="Payments received" className="mt-4 rounded-lg border border-line bg-white">
        <h2 className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">Payments received</h2>
        {data.payments.length === 0 ? (
          <p className="px-5 py-4 text-sm text-muted">None.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {data.payments.map((p) => (
              <li key={p.id} className="flex flex-wrap items-start justify-between gap-2 px-5 py-2.5">
                <span className={p.reversed_at ? "text-muted line-through" : undefined}>
                  {single ? null : <>{day(p.received_on)} · </>}
                  {PAYMENT_METHOD_LABELS[p.method]} · {p.payer_name}
                  {p.reservation_reference ? (
                    <> · <Link href={`/reservations/${p.reservation_id}`} className="font-mono text-forest underline-offset-2 hover:underline">{p.reservation_reference}</Link></>
                  ) : null}
                  {p.allocations.filter((a) => a.amount.charAt(0) !== "-").map((a) => (
                    <span key={`${a.invoice_id}-${a.created_at}`}> · <Link href={`/invoices/${a.invoice_id}`} className="font-mono text-forest underline-offset-2 hover:underline">{a.invoice_number}</Link></span>
                  ))}
                  {p.reference ? <span className="font-mono text-muted"> · {p.reference}</span> : null}
                  <span className="block text-[12px] text-muted no-underline">
                    by {p.recorded_by_name}
                    {p.reversed_at ? ` · reversed: ${p.reversal_reason}` : p.unallocated !== "0.00" ? ` · ${formatMoney(p.unallocated, p.currency)} on account` : ""}
                  </span>
                </span>
                <span className="font-mono tabular whitespace-nowrap">{formatMoney(p.amount, p.currency)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.refunds.length > 0 ? (
        <section aria-label="Refunds" className="mt-4 rounded-lg border border-line bg-white">
          <h2 className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">Refunds</h2>
          <ul className="divide-y divide-line text-sm">
            {data.refunds.map((r) => (
              <li key={r.id} className="flex flex-wrap justify-between gap-2 px-5 py-2.5">
                <span>{single ? null : <>{day(r.refunded_on)} · </>}{PAYMENT_METHOD_LABELS[r.method]} · {r.reason}</span>
                <span className="font-mono tabular whitespace-nowrap">−{formatMoney(r.amount, r.currency)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
