import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { accessOf } from "@/lib/access";
import { formatStayDate } from "@/lib/dates";
import { formatMoney, sumMoney } from "@/lib/money";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { InvoiceSummary, PropertySummary } from "@/lib/types";
import { NewInvoice } from "./new-invoice";
import { InvoiceStatusChip } from "./status";

export const metadata: Metadata = { title: "Invoices" };

const pill =
  "rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white";
const VIEWS = { issued: "Issued", draft: "Drafts" } as const;

export default async function InvoicesPage({ searchParams }: PageProps<"/invoices">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("invoices.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("invoices.view", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Invoices" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const view = sp.view === "draft" ? "draft" : "issued";
  const invoices = await apiGet<InvoiceSummary[]>(`/api/v1/properties/${current.id}/invoices?status=${view}&limit=100`);
  const link = (q: Record<string, string>) => `/invoices?${new URLSearchParams({ property: current.id, ...q })}`;

  return (
    <>
      <PageHeader
        title="Invoices"
        description={current.name}
        actions={
          access.canAt("invoices.manage", current.id) ? <NewInvoice propertyId={current.id} /> : null
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <nav aria-label="Invoice list" className="flex gap-1.5">
          {(Object.keys(VIEWS) as (keyof typeof VIEWS)[]).map((v) => (
            <Link key={v} href={link({ view: v })} aria-current={view === v ? "page" : undefined} className={pill}>{VIEWS[v]}</Link>
          ))}
        </nav>
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5 sm:ml-auto">
            {properties.map((p) => (
              <Link key={p.id} href={`/invoices?property=${p.id}&view=${view}`} aria-current={p.id === current.id ? "page" : undefined} className={pill}>{p.name}</Link>
            ))}
          </nav>
        ) : null}
      </div>
      {invoices.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">
          {view === "draft" ? "No drafts." : "No invoices issued yet. Open a booking and choose “Create invoice”."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="border-b border-line bg-cloud text-left text-[12px] text-muted">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Number</th>
                <th scope="col" className="px-4 py-2 font-medium">Bill to</th>
                <th scope="col" className="px-4 py-2 font-medium">Booking</th>
                <th scope="col" className="px-4 py-2 font-medium">Date</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Total</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Credited</th>
                <th scope="col" className="px-4 py-2 font-medium"><span className="sr-only">Status</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-cloud">
                  <td className="px-4 py-2.5">
                    <Link href={`/invoices/${inv.id}`} className="font-mono font-medium text-forest underline-offset-2 hover:underline">
                      {inv.number ?? "Draft"}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">{inv.bill_to_name}</td>
                  <td className="px-4 py-2.5 font-mono text-[13px]">{inv.reservation_reference ?? "—"}</td>
                  <td className="px-4 py-2.5 tabular">{inv.issue_date ? formatStayDate(inv.issue_date, { day: "numeric", month: "short", year: "numeric" }) : "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular whitespace-nowrap">{formatMoney(inv.total, inv.currency)}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular text-muted">{inv.credited === "0.00" ? "—" : formatMoney(inv.credited, inv.currency)}</td>
                  <td className="px-4 py-2.5"><InvoiceStatusChip status={inv.status} fullyCredited={inv.status === "issued" && sumMoney([inv.total, `-${inv.credited}`]) === "0.00"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
