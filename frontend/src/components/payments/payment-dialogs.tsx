"use client";

import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatMoney, parseMoneyInput } from "@/lib/money";
import { PAYMENT_METHOD_LABELS, type Payment, type PaymentMethod } from "@/lib/types";

const METHODS = Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[];
const message = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

/** One key per dialog: a double-click or a retry after a dropped connection records once. */
function useIdempotencyKey() {
  return useMemo(() => crypto.randomUUID(), []);
}

function MethodPicker({ value, onChange, name }: { value: PaymentMethod; onChange: (m: PaymentMethod) => void; name: string }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-forest">Method</legend>
      <div className="flex flex-wrap gap-2">
        {METHODS.map((m) => (
          <label key={m} className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
            <input type="radio" name={name} value={m} checked={value === m} onChange={() => onChange(m)} className="accent-forest" />
            {PAYMENT_METHOD_LABELS[m]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function RecordPaymentDialog({
  propertyId,
  currency,
  suggested,
  invoiceId,
  reservationId,
  title,
  description,
  askPayer = false,
  today,
  onClose,
  onDone,
}: {
  propertyId: string;
  currency: string;
  suggested: string | null;
  invoiceId?: string;
  reservationId?: string;
  title: string;
  description?: string;
  askPayer?: boolean;
  today: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const key = useIdempotencyKey();
  const [method, setMethod] = useState<PaymentMethod>("card");
  const [amount, setAmount] = useState(suggested ?? "");
  const [receivedOn, setReceivedOn] = useState(today);
  const [reference, setReference] = useState("");
  const [payer, setPayer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={title} description={description}>
        <form method="post"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const value = parseMoneyInput(amount);
            if (!value || value === "0.00") return setError("Enter the amount received, for example 1500.00.");
            if (askPayer && payer.trim().length < 2) return setError("Say who paid.");
            setBusy(true);
            setError(null);
            try {
              await api(`/api/v1/properties/${propertyId}/payments`, {
                method: "POST",
                body: {
                  method,
                  amount: value,
                  received_on: receivedOn,
                  reference: reference.trim() || null,
                  payer_name: askPayer ? payer.trim() : null,
                  invoice_id: invoiceId ?? null,
                  reservation_id: reservationId ?? null,
                  idempotency_key: key,
                },
              });
              onDone();
            } catch (err) {
              setError(message(err, "Could not record the payment. Check your connection and try again."));
              setBusy(false);
            }
          }}
        >
          {error ? <Alert tone="error">{error}</Alert> : null}
          <MethodPicker value={method} onChange={setMethod} name="payment-method" />
          {askPayer ? (
            <Field id="pay-payer" label="Paid by">
              <Input id="pay-payer" value={payer} onChange={(e) => setPayer(e.target.value)} maxLength={200} />
            </Field>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="pay-amount" label={`Amount (${currency})`}>
              <Input id="pay-amount" inputMode="decimal" className="font-mono tabular" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </Field>
            <Field id="pay-date" label="Received on">
              <Input id="pay-date" type="date" max={today} value={receivedOn} onChange={(e) => setReceivedOn(e.target.value)} />
            </Field>
          </div>
          <Field id="pay-reference" label="Reference (optional)" hint="Card slip, EFT or mobile money reference. Never a card number.">
            <Input id="pay-reference" value={reference} onChange={(e) => setReference(e.target.value)} maxLength={100} />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>Record payment</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function RefundDialog({
  payment,
  amount,
  releaseFromInvoiceId,
  onClose,
  onDone,
}: {
  payment: Payment;
  amount: string;
  releaseFromInvoiceId?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const key = useIdempotencyKey();
  const [method, setMethod] = useState<PaymentMethod>(payment.method);
  const [value, setValue] = useState(amount);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title="Refund" description={`From ${payment.payer_name}'s ${formatMoney(payment.amount, payment.currency)} payment of ${payment.received_on}.`}>
        <form method="post"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const v = parseMoneyInput(value);
            if (!v || v === "0.00") return setError("Enter the amount to refund.");
            if (reason.trim().length < 3) return setError("Give a reason for the refund.");
            setBusy(true);
            setError(null);
            try {
              await api(`/api/v1/payments/${payment.id}/refunds`, {
                method: "POST",
                body: { amount: v, method, reason: reason.trim(), release_from_invoice_id: releaseFromInvoiceId ?? null, idempotency_key: key },
              });
              onDone();
            } catch (err) {
              setError(message(err, "Could not record the refund."));
              setBusy(false);
            }
          }}
        >
          {error ? <Alert tone="error">{error}</Alert> : null}
          <MethodPicker value={method} onChange={setMethod} name="refund-method" />
          <Field id="refund-amount" label={`Amount (${payment.currency})`}>
            <Input id="refund-amount" inputMode="decimal" className="font-mono tabular" value={value} onChange={(e) => setValue(e.target.value)} />
          </Field>
          <Field id="refund-reason" label="Reason">
            <Input id="refund-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} placeholder="Night credited after early departure" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>Record refund</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ReverseDialog({ payment, onClose, onDone }: { payment: Payment; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent
        title={`Reverse ${formatMoney(payment.amount, payment.currency)} from ${payment.payer_name}?`}
        description="Only for a payment recorded by mistake, when no money was received. It stays on record as reversed and is taken off its invoices."
      >
        <form method="post"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (reason.trim().length < 3) return setError("Say what went wrong.");
            setBusy(true);
            setError(null);
            try {
              await api(`/api/v1/payments/${payment.id}/reverse`, { method: "POST", body: { reason: reason.trim() } });
              onDone();
            } catch (err) {
              setError(message(err, "Could not reverse the payment."));
              setBusy(false);
            }
          }}
        >
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Field id="reverse-reason" label="Reason">
            <Input id="reverse-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} placeholder="Recorded twice" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" variant="danger" loading={busy}>Reverse payment</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
