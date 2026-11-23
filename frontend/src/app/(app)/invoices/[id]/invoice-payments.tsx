"use client";

import { Banknote, RotateCcw, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EmailButton } from "@/components/notifications/email-button";
import { RecordPaymentDialog, RefundDialog, ReverseDialog } from "@/components/payments/payment-dialogs";
import { Button } from "@/components/ui/button";
import { formatStayDate } from "@/lib/dates";
import { formatMoney, sumMoney } from "@/lib/money";
import { PAYMENT_METHOD_LABELS, type InvoicePayments as Money, type Payment } from "@/lib/types";

/** Payments against an issued invoice: what was paid, what is owed, and the actions. */
export function InvoicePayments({
  invoiceId,
  invoiceNumber,
  propertyId,
  money,
  canRecord,
  canRefund,
  today,
}: {
  invoiceId: string;
  invoiceNumber: string;
  propertyId: string;
  money: Money;
  canRecord: boolean;
  canRefund: boolean;
  today: string;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<{ kind: "pay" } | { kind: "refund"; payment: Payment; amount: string } | { kind: "reverse"; payment: Payment } | null>(null);
  const fmt = (a: string) => formatMoney(a, money.currency);
  const owed = money.balance.startsWith("-") ? "0.00" : money.balance;
  const over = money.balance.startsWith("-") ? money.balance.slice(1) : null;
  // Refund an overpayment from the most recent payment that still has money on this invoice.
  const onInvoice = (p: Payment) => sumMoney(p.allocations.filter((a) => a.invoice_id === invoiceId).map((a) => a.amount));
  const source = [...money.payments].reverse().find((p) => !p.reversed_at && onInvoice(p) !== "0.00");
  const done = () => {
    setDialog(null);
    router.refresh();
  };

  return (
    <section aria-label="Payments" className="mt-6 border-t border-line pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-forest">Payments</h2>
        <div className="flex flex-wrap gap-2 print:hidden">
          {canRecord && owed !== "0.00" ? (
            <Button size="sm" onClick={() => setDialog({ kind: "pay" })}>
              <Banknote aria-hidden />
              Record payment
            </Button>
          ) : null}
          {canRefund && over && source ? (
            <Button size="sm" variant="secondary" onClick={() => setDialog({ kind: "refund", payment: source, amount: over })}>
              <Undo2 aria-hidden />
              Refund {fmt(over)}
            </Button>
          ) : null}
        </div>
      </div>
      {money.payments.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No payments yet.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line text-sm">
          {money.payments.map((p) => (
            <li key={p.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-0.5 py-2">
              <span className={p.reversed_at ? "text-muted line-through" : undefined}>
                {formatStayDate(p.received_on, { day: "numeric", month: "short", year: "numeric" })} · {PAYMENT_METHOD_LABELS[p.method]} · {p.payer_name}
                {p.reference ? <span className="font-mono"> · {p.reference}</span> : null}
              </span>
              <span className="flex items-center gap-2">
                <span className="font-mono tabular whitespace-nowrap">{fmt(onInvoice(p))}</span>
                {canRefund && !p.reversed_at && p.refunded === "0.00" ? (
                  <Button size="sm" variant="ghost" className="h-7 print:hidden" title="Reverse (recorded by mistake)" onClick={() => setDialog({ kind: "reverse", payment: p })}>
                    <RotateCcw aria-hidden />
                    <span className="sr-only">Reverse payment from {p.payer_name}</span>
                  </Button>
                ) : null}
              </span>
              {canRecord && !p.reversed_at ? (
                <span className="col-span-2 flex flex-wrap items-center gap-2 print:hidden">
                  <EmailButton
                    url={`/api/v1/payments/${p.id}/email-receipt`}
                    label="Email receipt"
                    title={`Receipt for ${fmt(p.amount)} from ${p.payer_name}`}
                    variant="ghost"
                    className="h-7 px-2 text-[13px]"
                  />
                </span>
              ) : null}
              {p.reversed_at ? <span className="col-span-2 text-[12px] text-muted no-underline">Reversed: {p.reversal_reason}</span> : null}
              {p.refunds.map((r) => (
                <span key={r.id} className="col-span-2 text-[12px] text-muted">
                  Refunded {fmt(r.amount)} by {PAYMENT_METHOD_LABELS[r.method].toLowerCase()} on {formatStayDate(r.refunded_on, { day: "numeric", month: "short" })}: {r.reason}
                </span>
              ))}
            </li>
          ))}
        </ul>
      )}
      <dl className="ml-auto mt-3 grid max-w-xs grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-sm">
        <dt className="text-muted">Paid</dt>
        <dd className="text-right font-mono tabular whitespace-nowrap">{fmt(money.paid)}</dd>
        <dt className="font-semibold text-forest">{over ? "Overpaid" : "Balance due"}</dt>
        <dd className="text-right font-mono font-semibold tabular whitespace-nowrap text-forest">{fmt(over ?? owed)}</dd>
      </dl>

      {dialog?.kind === "pay" ? (
        <RecordPaymentDialog
          propertyId={propertyId}
          currency={money.currency}
          suggested={owed}
          invoiceId={invoiceId}
          title={`Payment for ${invoiceNumber}`}
          description={`Balance due ${fmt(owed)}. More than the balance stays on the guest's account.`}
          today={today}
          onClose={() => setDialog(null)}
          onDone={done}
        />
      ) : null}
      {dialog?.kind === "refund" ? (
        <RefundDialog payment={dialog.payment} amount={dialog.amount} releaseFromInvoiceId={invoiceId} onClose={() => setDialog(null)} onDone={done} />
      ) : null}
      {dialog?.kind === "reverse" ? <ReverseDialog payment={dialog.payment} onClose={() => setDialog(null)} onDone={done} /> : null}
    </section>
  );
}
