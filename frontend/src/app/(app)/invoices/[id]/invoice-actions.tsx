"use client";

import { FileCheck2, Plus, Printer, Trash2, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatMoney, parseMoneyInput, sumMoney } from "@/lib/money";
import type { Invoice, Tax } from "@/lib/types";

type DialogKind = "line" | "details" | "issue" | "credit" | null;

const message = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function InvoiceActions({
  invoice,
  taxes,
  canManage,
  canCredit,
  balance,
}: {
  invoice: Invoice;
  taxes: Tax[];
  canManage: boolean;
  canCredit: boolean;
  balance: string;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const draft = invoice.status === "draft";
  const close = () => setDialog(null);
  const done = () => {
    setDialog(null);
    router.refresh();
  };

  async function run(key: string, fn: () => Promise<unknown>, fallback: string) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      router.refresh();
    } catch (err) {
      setError(message(err, fallback));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-white p-4">
      {error ? <Alert tone="error">{error}</Alert> : null}
      {draft && canManage ? (
        <>
          <p className="text-sm text-muted">Drafts can be changed. Issuing gives the invoice its number and locks it.</p>
          <Button onClick={() => setDialog("issue")} disabled={invoice.items.length === 0}>
            <FileCheck2 aria-hidden />
            Issue invoice
          </Button>
          <Button variant="secondary" onClick={() => setDialog("line")}>
            <Plus aria-hidden />
            Add a line
          </Button>
          <Button variant="ghost" onClick={() => setDialog("details")}>Edit bill-to and notes</Button>
          {invoice.items.length > 0 ? (
            <div className="border-t border-line pt-3">
              <p className="mb-1 text-[12px] font-medium text-muted">Remove a line</p>
              <ul className="flex flex-col gap-1">
                {invoice.items.map((item) => (
                  <li key={item.id} className="flex items-center gap-2 text-[13px]">
                    <span className="min-w-0 flex-1 truncate">{item.description}</span>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8"
                      loading={busy === item.id}
                      onClick={() => run(item.id, () => api(`/api/v1/invoices/${invoice.id}/items/${item.id}`, { method: "DELETE" }), "Could not remove the line.")}
                    >
                      <Trash2 aria-hidden />
                      <span className="sr-only">Remove {item.description}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <Button
            variant="ghost"
            className="text-danger"
            loading={busy === "discard"}
            onClick={() => run("discard", () => api(`/api/v1/invoices/${invoice.id}/discard`, { method: "POST" }), "Could not discard the draft.")}
          >
            Discard draft
          </Button>
        </>
      ) : null}
      {invoice.status === "issued" ? (
        <>
          <Button variant="secondary" onClick={() => window.print()}>
            <Printer aria-hidden />
            Print or save as PDF
          </Button>
          {canCredit && balance !== "0.00" ? (
            <Button variant="ghost" onClick={() => setDialog("credit")}>
              <Undo2 aria-hidden />
              Credit note
            </Button>
          ) : null}
          {!canCredit ? <p className="text-[13px] text-muted">Mistakes are corrected with a credit note by a manager or accountant.</p> : null}
        </>
      ) : null}
      {invoice.status === "discarded" ? <p className="text-sm text-muted">This draft was discarded. It is kept for the record.</p> : null}

      {dialog === "line" ? <LineDialog invoice={invoice} taxes={taxes} onClose={close} onDone={done} /> : null}
      {dialog === "details" ? <DetailsDialog invoice={invoice} onClose={close} onDone={done} /> : null}
      {dialog === "issue" ? <IssueDialog invoice={invoice} onClose={close} onDone={done} /> : null}
      {dialog === "credit" ? <CreditDialog invoice={invoice} onClose={close} onDone={done} /> : null}
    </div>
  );
}

function useSubmit(onDone: () => void) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
    } catch (err) {
      setError(message(err, fallback));
      setBusy(false);
    }
  }
  return { error, setError, busy, run };
}

const textarea = "w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]";

function LineDialog({ invoice, taxes, onClose, onDone }: { invoice: Invoice; taxes: Tax[]; onClose: () => void; onDone: () => void }) {
  const [description, setDescription] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState("");
  const [includeTax, setIncludeTax] = useState(true);
  const [taxIds, setTaxIds] = useState<string[]>(taxes.map((t) => t.id));
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title="Add a line" description="Meals, drinks, activities, transfers or other charges.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const amount = parseMoneyInput(unit);
            const qty = parseMoneyInput(quantity);
            if (description.trim().length < 2) return s.setError("Describe the charge.");
            if (!qty || qty === "0.00") return s.setError("Enter a quantity.");
            if (!amount || amount === "0.00") return s.setError("Enter a price, for example 185.50.");
            void s.run(
              () =>
                api(`/api/v1/invoices/${invoice.id}/items`, {
                  method: "POST",
                  body: { description: description.trim(), quantity: qty, unit_amount: amount, prices_include_tax: includeTax, tax_ids: taxIds },
                }),
              "Could not add the line.",
            );
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <Field id="line-description" label="Description">
            <Input id="line-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} placeholder="Dinner, 2 guests" />
          </Field>
          <div className="grid grid-cols-[6rem_1fr] gap-3">
            <Field id="line-qty" label="Quantity">
              <Input id="line-qty" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="tabular" />
            </Field>
            <Field id="line-unit" label={`Price each (${invoice.currency})`}>
              <Input id="line-unit" inputMode="decimal" value={unit} onChange={(e) => setUnit(e.target.value)} className="font-mono tabular" />
            </Field>
          </div>
          {taxes.length > 0 ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-sm font-medium text-forest">Taxes</legend>
              {taxes.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="size-4 accent-forest"
                    checked={taxIds.includes(t.id)}
                    onChange={(e) => setTaxIds(e.target.checked ? [...taxIds, t.id] : taxIds.filter((x) => x !== t.id))}
                  />
                  {t.name} {Number(t.rate_percent)}%
                </label>
              ))}
              <label className="mt-1 flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-forest" checked={includeTax} onChange={(e) => setIncludeTax(e.target.checked)} />
                The price includes these taxes
              </label>
            </fieldset>
          ) : (
            <p className="text-[13px] text-muted">This property has no taxes set up, so the line has none.</p>
          )}
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Add line</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DetailsDialog({ invoice, onClose, onDone }: { invoice: Invoice; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(invoice.bill_to_name);
  const [details, setDetails] = useState(invoice.bill_to_details ?? "");
  const [notes, setNotes] = useState(invoice.notes ?? "");
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title="Bill-to and notes">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length < 2) return s.setError("Say who the invoice is for.");
            void s.run(
              () => api(`/api/v1/invoices/${invoice.id}`, { method: "PATCH", body: { bill_to_name: name.trim(), bill_to_details: details.trim() || null, notes: notes.trim() || null } }),
              "Could not save.",
            );
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <Field id="bill-name" label="Bill to">
            <Input id="bill-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </Field>
          <Field id="bill-details" label="Address, VAT or order number (optional)">
            <textarea id="bill-details" rows={3} maxLength={1000} value={details} onChange={(e) => setDetails(e.target.value)} className={textarea} />
          </Field>
          <Field id="bill-notes" label="Note on the invoice (optional)">
            <textarea id="bill-notes" rows={2} maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} className={textarea} placeholder="Banking details, thank-you note" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Save</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function IssueDialog({ invoice, onClose, onDone }: { invoice: Invoice; onClose: () => void; onDone: () => void }) {
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={`Issue invoice for ${formatMoney(invoice.total, invoice.currency)}?`} description="It gets the next invoice number and can no longer be changed. Mistakes are then corrected with a credit note.">
        {s.error ? <Alert tone="error">{s.error}</Alert> : null}
        <div className="flex gap-2 border-t border-line pt-4">
          <Button loading={s.busy} onClick={() => void s.run(() => api(`/api/v1/invoices/${invoice.id}/issue`, { method: "POST" }), "Could not issue the invoice.")}>
            Issue invoice
          </Button>
          <Button variant="ghost" onClick={onClose}>Not yet</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CreditDialog({ invoice, onClose, onDone }: { invoice: Invoice; onClose: () => void; onDone: () => void }) {
  const open = invoice.items
    .map((i) => ({ item: i, remaining: sumMoney([i.total_amount, `-${i.credited_amount}`]) }))
    .filter((x) => x.remaining !== "0.00");
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const s = useSubmit(onDone);
  const money = (a: string) => formatMoney(a, invoice.currency);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={`Credit note for ${invoice.number}`} description="Enter how much to credit on each line. Leave a line empty to credit nothing on it.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (reason.trim().length < 3) return s.setError("Give a reason; it is printed on the credit note.");
            const lines: { invoice_item_id: string; amount?: string }[] = [];
            for (const { item, remaining } of open) {
              const raw = (amounts[item.id] ?? "").trim();
              if (!raw) continue;
              const amount = parseMoneyInput(raw);
              if (!amount || amount === "0.00") return s.setError(`Enter an amount like 250.00 for “${item.description}”.`);
              // Crediting exactly what remains is sent without an amount, so the line nets to zero.
              lines.push(amount === remaining ? { invoice_item_id: item.id } : { invoice_item_id: item.id, amount });
            }
            if (lines.length === 0) return s.setError("Enter an amount on at least one line.");
            void s.run(() => api(`/api/v1/invoices/${invoice.id}/credit-notes`, { method: "POST", body: { reason: reason.trim(), lines } }), "Could not issue the credit note.");
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <ul className="flex flex-col gap-3">
            {open.map(({ item, remaining }) => (
              <li key={item.id} className="grid grid-cols-[1fr_8rem] items-end gap-3">
                <div className="min-w-0 text-sm">
                  <p className="truncate">{item.description}</p>
                  <button type="button" className="text-[12px] text-teal underline-offset-2 hover:underline" onClick={() => setAmounts({ ...amounts, [item.id]: remaining })}>
                    Credit all {money(remaining)}
                  </button>
                </div>
                <Field id={`credit-${item.id}`} label="Amount">
                  <Input id={`credit-${item.id}`} inputMode="decimal" className="font-mono tabular" value={amounts[item.id] ?? ""} onChange={(e) => setAmounts({ ...amounts, [item.id]: e.target.value })} />
                </Field>
              </li>
            ))}
          </ul>
          <Field id="credit-reason" label="Reason">
            <Input id="credit-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} placeholder="Guest left a night early" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Issue credit note</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
