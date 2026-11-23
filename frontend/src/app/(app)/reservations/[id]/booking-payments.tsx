"use client";

import { Banknote } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RecordPaymentDialog } from "@/components/payments/payment-dialogs";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import { formatStayDate } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { PAYMENT_METHOD_LABELS, type Payment } from "@/lib/types";

/** Smaller of two decimal strings, compared in whole cents. */
function minMoney(a: string, b: string): string {
  const cents = (x: string) => {
    const [w, f = ""] = x.split(".");
    return BigInt(w) * BigInt(100) + BigInt((f + "00").slice(0, 2));
  };
  return cents(a) <= cents(b) ? a : b;
}

export function BookingPayments({
  propertyId,
  reservationId,
  currency,
  payments,
  openInvoices,
  canRecord,
  today,
}: {
  propertyId: string;
  reservationId: string;
  currency: string;
  payments: Payment[];
  /** Issued invoices of this booking that still owe money. */
  openInvoices: { id: string; number: string; balance: string }[];
  canRecord: boolean;
  today: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fmt = (a: string) => formatMoney(a, currency);
  const target = openInvoices[0];

  async function apply(p: Payment) {
    if (!target) return;
    setBusy(p.id);
    setError(null);
    try {
      await api(`/api/v1/payments/${p.id}/allocations`, { method: "POST", body: { invoice_id: target.id, amount: minMoney(p.unallocated, target.balance) } });
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not apply the payment.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby="payments-heading" className="rounded-lg border border-line bg-white px-5 py-4 text-sm">
      <h2 id="payments-heading" className="text-sm font-semibold text-forest">Payments</h2>
      {error ? <div className="mt-2"><Alert tone="error">{error}</Alert></div> : null}
      {payments.length === 0 ? (
        <p className="mt-2 text-muted">No payments yet.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {payments.map((p) => (
            <li key={p.id} className={p.reversed_at ? "text-muted line-through" : undefined}>
              <div className="flex items-center justify-between gap-2">
                <span>{formatStayDate(p.received_on, { day: "numeric", month: "short" })} · {PAYMENT_METHOD_LABELS[p.method]}</span>
                <span className="font-mono tabular whitespace-nowrap">{fmt(p.amount)}</span>
              </div>
              {!p.reversed_at && p.unallocated !== "0.00" ? (
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-[12px] text-muted no-underline">
                  <span>{fmt(p.unallocated)} not yet on an invoice</span>
                  {canRecord && target ? (
                    <Button size="sm" variant="secondary" className="h-7" loading={busy === p.id} onClick={() => apply(p)}>
                      Apply to {target.number}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {canRecord ? (
        <Button className="mt-3" size="sm" variant="secondary" onClick={() => setOpen(true)}>
          <Banknote aria-hidden />
          {target ? "Take a payment" : "Take a deposit"}
        </Button>
      ) : null}
      {open ? (
        <RecordPaymentDialog
          propertyId={propertyId}
          currency={currency}
          suggested={target?.balance ?? null}
          invoiceId={target?.id}
          reservationId={reservationId}
          title={target ? `Payment for ${target.number}` : "Deposit for this booking"}
          description={target ? `Balance due ${fmt(target.balance)}.` : "Kept on the booking until it is invoiced."}
          today={today}
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false);
            router.refresh();
          }}
        />
      ) : null}
    </section>
  );
}
