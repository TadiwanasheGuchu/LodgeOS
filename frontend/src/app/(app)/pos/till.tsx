"use client";

import { BedDouble, Banknote, Minus, Plus, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatMoney, sumMoney } from "@/lib/money";
import { PAYMENT_METHOD_LABELS, type InHouseGuest, type PaymentMethod, type PosItem, type PosOutlet, type PosSale } from "@/lib/types";

const METHODS = Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[];

/** price × whole quantity, exact in cents. */
const times = (price: string, qty: number) => sumMoney(Array.from({ length: qty }, () => price));

export function Till({
  propertyId,
  currency,
  outlets,
  items,
  guests,
  sales,
  canManage,
  itemsLink,
}: {
  propertyId: string;
  currency: string;
  outlets: PosOutlet[];
  items: PosItem[];
  guests: InHouseGuest[];
  sales: PosSale[];
  canManage: boolean;
  itemsLink: string;
}) {
  const router = useRouter();
  const [outletId, setOutletId] = useState(outlets[0]?.id ?? "");
  const [basket, setBasket] = useState<Record<string, number>>({});
  const [settle, setSettle] = useState<"room" | "paid">(guests.length ? "room" : "paid");
  const [guestId, setGuestId] = useState(guests[0]?.reservation_id ?? "");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const money = (a: string) => formatMoney(a, currency);

  const outletItems = items.filter((i) => i.outlet_id === outletId);
  const groups = useMemo(() => {
    const m = new Map<string, PosItem[]>();
    for (const i of outletItems) m.set(i.category ?? "Other", [...(m.get(i.category ?? "Other") ?? []), i]);
    return [...m.entries()];
  }, [outletItems]);
  const lines = Object.entries(basket)
    .filter(([, q]) => q > 0)
    .map(([id, q]) => ({ item: items.find((i) => i.id === id)!, qty: q }))
    .filter((l) => l.item);
  const total = sumMoney(lines.map((l) => times(l.item.price, l.qty)));
  const exclusive = lines.some((l) => !l.item.prices_include_tax);

  const add = (id: string, d: number) => setBasket((b) => ({ ...b, [id]: Math.max(0, (b[id] ?? 0) + d) }));

  if (outlets.length === 0) {
    return (
      <Alert tone="info">
        No outlets yet.{" "}
        {canManage ? <Link href={itemsLink} className="font-medium underline underline-offset-2">Set up a bar or restaurant and its items</Link> : "Ask a manager to set up the bar and its items."}
      </Alert>
    );
  }

  async function ringUp() {
    if (lines.length === 0) return;
    if (settle === "room" && !guestId) return setNotice({ tone: "error", text: "Choose the guest's room." });
    setBusy(true);
    setNotice(null);
    try {
      const sale = await api<PosSale>(`/api/v1/properties/${propertyId}/pos/sales`, {
        method: "POST",
        body: {
          outlet_id: outletId,
          lines: lines.map((l) => ({ service_id: l.item.id, quantity: String(l.qty) })),
          settlement: settle,
          reservation_id: settle === "room" ? guestId : null,
          method: settle === "paid" ? method : null,
          idempotency_key: key,
        },
      });
      setNotice({
        tone: "success",
        text: sale.settlement === "room" ? `${money(sale.total)} charged to room ${sale.room_label ?? ""}.` : `${money(sale.total)} paid by ${PAYMENT_METHOD_LABELS[method].toLowerCase()} (${sale.invoice_number}).`,
      });
      setBasket({});
      setKey(crypto.randomUUID());
      router.refresh();
    } catch (err) {
      // Keep the same key: retrying after a dropped connection must not charge twice.
      setNotice({ tone: "error", text: err instanceof ApiError ? err.message : "The sale did not go through. Check the connection and try again; it will not be charged twice." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <section aria-label="Items" className="flex flex-col gap-4">
          {outlets.length > 1 ? (
            <div role="tablist" aria-label="Outlet" className="flex flex-wrap gap-1.5">
              {outlets.map((o) => (
                <button key={o.id} role="tab" aria-selected={o.id === outletId} onClick={() => { setOutletId(o.id); setBasket({}); }} className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest aria-selected:border-forest aria-selected:bg-forest aria-selected:text-white">
                  {o.name}
                </button>
              ))}
            </div>
          ) : null}
          {outletItems.length === 0 ? <p className="text-sm text-muted">No items at this outlet yet.</p> : null}
          {groups.map(([category, list]) => (
            <div key={category}>
              <h2 className="mb-2 text-[12px] font-medium text-muted uppercase">{category}</h2>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                {list.map((i) => (
                  <button
                    key={i.id}
                    onClick={() => add(i.id, 1)}
                    className="flex min-h-16 flex-col items-start justify-between rounded-md border border-line bg-white px-3 py-2 text-left hover:border-teal hover:bg-mist focus-visible:border-teal"
                  >
                    <span className="text-sm font-medium text-charcoal">{i.name}</span>
                    <span className="font-mono text-[13px] text-forest">{money(i.price)}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </section>

        <aside aria-label="Basket" className="flex flex-col gap-3 rounded-lg border border-line bg-white p-4 lg:sticky lg:top-20">
          <h2 className="text-sm font-semibold text-forest">Basket</h2>
          {lines.length === 0 ? (
            <p className="text-sm text-muted">Tap items to add them.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {lines.map((l) => (
                <li key={l.item.id} className="flex items-center gap-2 text-sm">
                  <span className="min-w-0 flex-1 truncate">{l.item.name}</span>
                  <Button size="icon" variant="ghost" className="size-8" onClick={() => add(l.item.id, -1)}><Minus aria-hidden /><span className="sr-only">One less {l.item.name}</span></Button>
                  <span className="w-6 text-center tabular">{l.qty}</span>
                  <Button size="icon" variant="ghost" className="size-8" onClick={() => add(l.item.id, 1)}><Plus aria-hidden /><span className="sr-only">One more {l.item.name}</span></Button>
                  <span className="w-24 text-right font-mono tabular whitespace-nowrap">{money(times(l.item.price, l.qty))}</span>
                </li>
              ))}
            </ul>
          )}
          {lines.length > 0 ? (
            <>
              <p className="flex justify-between border-t border-line pt-2 text-sm font-semibold text-forest">
                <span>Total</span>
                <span className="font-mono">{money(total)}{exclusive ? " + tax" : ""}</span>
              </p>
              <button className="self-start text-[12px] text-muted underline-offset-2 hover:underline" onClick={() => setBasket({})}><X className="mr-1 inline size-3" aria-hidden />Clear</button>
            </>
          ) : null}

          <fieldset className="flex gap-2">
            <legend className="sr-only">Settle</legend>
            <label className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line px-2 py-2 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist has-[:disabled]:opacity-50">
              <input type="radio" name="settle" className="sr-only" checked={settle === "room"} disabled={guests.length === 0} onChange={() => setSettle("room")} />
              <BedDouble className="size-4" aria-hidden />Charge to room
            </label>
            <label className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line px-2 py-2 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
              <input type="radio" name="settle" className="sr-only" checked={settle === "paid"} onChange={() => setSettle("paid")} />
              <Banknote className="size-4" aria-hidden />Paid now
            </label>
          </fieldset>
          {settle === "room" ? (
            <Field id="pos-guest" label="Room">
              <Select id="pos-guest" value={guestId} onChange={(e) => setGuestId(e.target.value)}>
                {guests.map((g) => (
                  <option key={g.reservation_id} value={g.reservation_id}>{g.rooms.length ? `Room ${g.rooms.join(", ")}` : "No room"} · {g.guest_name}</option>
                ))}
              </Select>
            </Field>
          ) : (
            <Field id="pos-method" label="Paid by">
              <Select id="pos-method" value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
                {METHODS.map((m) => <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>)}
              </Select>
            </Field>
          )}
          {notice ? <Alert tone={notice.tone}>{notice.text}</Alert> : null}
          <Button size="lg" disabled={lines.length === 0} loading={busy} onClick={ringUp}>
            {settle === "room" ? "Charge to room" : "Take payment"}
          </Button>
        </aside>
      </div>

      <section aria-label="Today's sales" className="rounded-lg border border-line bg-white">
        <h2 className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">Today&apos;s sales</h2>
        {sales.length === 0 ? (
          <p className="px-5 py-4 text-sm text-muted">None yet.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {sales.map((s) => (
              <li key={s.id} className="flex flex-wrap justify-between gap-2 px-5 py-2.5">
                <span>
                  {new Date(s.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })} · {s.outlet} · {s.items.map((i) => `${Number(i.quantity)}× ${i.name}`).join(", ")}
                  <span className="block text-[12px] text-muted">
                    {s.settlement === "room" ? `Room ${s.room_label ?? "?"} · ${s.reservation_reference}` : `Paid · ${s.invoice_number}`} · {s.sold_by}
                  </span>
                </span>
                <Link href={`/invoices/${s.invoice_id}`} className="font-mono tabular text-forest underline-offset-2 hover:underline">{money(s.total)}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
