import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { accessOf } from "@/lib/access";
import { formatStayDate } from "@/lib/dates";
import { formatMoney, sumMoney } from "@/lib/money";
import { apiGet, requireOrganisation, ServerApiError } from "@/lib/server/api";
import type { Invoice, Tax } from "@/lib/types";
import { InvoiceStatusChip } from "../status";
import { InvoiceActions } from "./invoice-actions";

export const metadata: Metadata = { title: "Invoice" };

const longDate = (iso: string) => formatStayDate(iso, { day: "numeric", month: "long", year: "numeric" });

export default async function InvoicePage({ params }: PageProps<"/invoices/[id]">) {
  const { id } = await params;
  const me = await requireOrganisation();
  const access = accessOf(me);
  let inv: Invoice;
  try {
    inv = await apiGet<Invoice>(`/api/v1/invoices/${id}`);
  } catch (err) {
    if (err instanceof ServerApiError && [403, 404, 422].includes(err.status)) notFound();
    throw err;
  }
  const canManage = access.canAt("invoices.manage", inv.property_id);
  const canCredit = access.canAt("invoices.credit", inv.property_id);
  const taxes = inv.status === "draft" && canManage
    ? (await apiGet<Tax[]>(`/api/v1/properties/${inv.property_id}/taxes`)).filter((t) => t.status === "active")
    : [];
  const money = (a: string) => formatMoney(a, inv.currency);
  const balance = sumMoney([inv.total, `-${inv.credited}`]);
  const title = inv.status === "draft" ? "Draft invoice" : inv.seller.tax_number ? "Tax invoice" : "Invoice";

  return (
    <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
      <article aria-label={title} className="min-w-0 flex-1 rounded-lg border border-line bg-white px-5 py-6 sm:px-8 sm:py-8 print:border-0 print:p-0">
        <header className="flex flex-col gap-6 border-b border-line pb-6 sm:flex-row sm:justify-between">
          <div>
            <p className="font-display text-2xl text-forest">{inv.seller.legal_name ?? inv.seller.name}</p>
            {inv.seller.legal_name ? <p className="text-sm text-muted">{inv.seller.name}</p> : null}
            <address className="mt-2 text-sm not-italic text-charcoal">
              {inv.seller.address.map((line) => <span key={line} className="block">{line}</span>)}
              {inv.seller.phone ? <span className="block">{inv.seller.phone}</span> : null}
              {inv.seller.email ? <span className="block">{inv.seller.email}</span> : null}
            </address>
            {inv.seller.tax_number ? <p className="mt-2 text-sm">Tax number <span className="font-mono">{inv.seller.tax_number}</span></p> : null}
          </div>
          <div className="sm:text-right">
            <h1 className="text-lg font-semibold text-forest">{title}</h1>
            <p className="font-mono text-xl text-forest">{inv.number ?? "Not yet numbered"}</p>
            <dl className="mt-2 grid grid-cols-[auto_auto] justify-start gap-x-4 gap-y-0.5 text-sm sm:justify-end">
              {inv.issue_date ? (<><dt className="text-muted">Date</dt><dd className="tabular">{longDate(inv.issue_date)}</dd></>) : null}
              {inv.due_date ? (<><dt className="text-muted">Due</dt><dd className="tabular">{longDate(inv.due_date)}</dd></>) : null}
              {inv.reservation_reference ? (
                <>
                  <dt className="text-muted">Booking</dt>
                  <dd className="font-mono">
                    <Link href={`/reservations/${inv.reservation_id}`} className="underline-offset-2 hover:underline print:no-underline">{inv.reservation_reference}</Link>
                  </dd>
                </>
              ) : null}
            </dl>
            <div className="mt-2 print:hidden"><InvoiceStatusChip status={inv.status} fullyCredited={inv.status === "issued" && balance === "0.00"} /></div>
          </div>
        </header>

        <section aria-label="Bill to" className="border-b border-line py-5">
          <p className="text-[12px] font-medium text-muted uppercase">Bill to</p>
          <p className="font-medium">{inv.bill_to_name}</p>
          {inv.bill_to_details ? <p className="text-sm whitespace-pre-line">{inv.bill_to_details}</p> : null}
        </section>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="text-left text-[12px] text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-3 font-medium">Description</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Qty</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Net</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Tax</th>
                <th scope="col" className="py-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {inv.items.map((item) => (
                <tr key={item.id} className="align-top">
                  <td className="py-2.5 pr-3">
                    {item.description}
                    {item.credited_amount !== "0.00" ? <span className="block text-[12px] text-muted">Credited {money(item.credited_amount)}</span> : null}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular whitespace-nowrap">{item.quantity.replace(/\.00$/, "")}</td>
                  <td className="py-2.5 pr-3 text-right font-mono tabular whitespace-nowrap">{money(item.net_amount)}</td>
                  <td className="py-2.5 pr-3 text-right font-mono tabular whitespace-nowrap">{money(item.tax_amount)}</td>
                  <td className="py-2.5 text-right font-mono tabular whitespace-nowrap">{money(item.total_amount)}</td>
                </tr>
              ))}
              {inv.items.length === 0 ? (
                <tr><td colSpan={5} className="py-6 text-center text-muted">No lines yet.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <dl className="ml-auto mt-4 grid max-w-xs grid-cols-[1fr_auto] gap-x-6 gap-y-1 border-t border-line pt-4 text-sm">
          <dt className="text-muted">Net</dt>
          <dd className="text-right font-mono tabular whitespace-nowrap">{money(inv.net_total)}</dd>
          {inv.tax_summary.map((t) => (
            <div key={`${t.name}-${t.rate_percent}`} className="contents">
              <dt className="text-muted">{t.name} {Number(t.rate_percent)}%</dt>
              <dd className="text-right font-mono tabular whitespace-nowrap">{money(t.amount)}</dd>
            </div>
          ))}
          <dt className="font-semibold text-forest">Total</dt>
          <dd className="text-right font-mono font-semibold tabular text-forest">{money(inv.total)}</dd>
          {inv.credited !== "0.00" ? (
            <>
              <dt className="text-muted">Credited</dt>
              <dd className="text-right font-mono tabular whitespace-nowrap">−{money(inv.credited)}</dd>
              <dt className="font-semibold text-forest">Still owed</dt>
              <dd className="text-right font-mono font-semibold tabular text-forest">{money(balance)}</dd>
            </>
          ) : null}
        </dl>
        {inv.notes ? <p className="mt-6 border-t border-line pt-4 text-sm whitespace-pre-line">{inv.notes}</p> : null}

        {inv.credit_notes.length > 0 ? (
          <section aria-label="Credit notes" className="mt-6 border-t border-line pt-4">
            <h2 className="text-sm font-semibold text-forest">Credit notes</h2>
            <ul className="mt-2 divide-y divide-line text-sm">
              {inv.credit_notes.map((n) => (
                <li key={n.id} className="flex flex-wrap justify-between gap-2 py-2">
                  <span>
                    <span className="font-mono">{n.number}</span> · {longDate(n.issue_date)} · {n.reason}
                    <span className="block text-[12px] text-muted">by {n.issued_by_name}</span>
                  </span>
                  <span className="font-mono tabular">−{money(n.total)}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>

      <aside className="w-full shrink-0 xl:sticky xl:top-20 xl:w-72 print:hidden">
        <InvoiceActions invoice={inv} taxes={taxes} canManage={canManage} canCredit={canCredit} balance={balance} />
      </aside>
    </div>
  );
}
