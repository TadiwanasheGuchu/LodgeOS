"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatMoney, parseMoneyInput } from "@/lib/money";
import type { PosItem, PosOutlet, Tax } from "@/lib/types";

const box = "rounded-lg border border-line bg-white px-5 py-5 sm:px-6";

export function Catalogue({ propertyId, currency, outlets, items, taxes }: { propertyId: string; currency: string; outlets: PosOutlet[]; items: PosItem[]; taxes: Tax[] }) {
  const router = useRouter();
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [outletName, setOutletName] = useState("");
  const active = outlets.filter((o) => o.status === "active");
  const [form, setForm] = useState({ outlet: active[0]?.id ?? "", name: "", category: "", price: "", includeTax: true, taxIds: taxes.map((t) => t.id) });

  async function run(key: string, fn: () => Promise<unknown>, ok: string) {
    setBusy(key);
    setNotice(null);
    try {
      await fn();
      setNotice({ tone: "success", text: ok });
      router.refresh();
      return true;
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof ApiError ? err.message : "Could not save." });
      return false;
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      {notice ? <Alert tone={notice.tone}>{notice.text}</Alert> : null}

      <section aria-label="Outlets" className={box}>
        <h2 className="text-sm font-semibold text-forest">Outlets</h2>
        <p className="mt-1 text-[13px] text-muted">Where you sell: bar, restaurant, curio shop, activities desk.</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {outlets.map((o) => (
            <li key={o.id} className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm">
              <span className={o.status === "archived" ? "text-muted line-through" : ""}>{o.name}</span>
              <button className="text-[12px] text-teal underline-offset-2 hover:underline" onClick={() => void run(o.id, () => api(`/api/v1/pos/outlets/${o.id}`, { method: "PATCH", body: { status: o.status === "active" ? "archived" : "active" } }), "Saved.")}>
                {o.status === "active" ? "Close" : "Reopen"}
              </button>
            </li>
          ))}
        </ul>
        <form
          className="mt-3 flex flex-wrap items-end gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (outletName.trim().length < 2) return setNotice({ tone: "error", text: "Name the outlet." });
            if (await run("outlet", () => api(`/api/v1/properties/${propertyId}/pos/outlets`, { method: "POST", body: { name: outletName.trim() } }), "Outlet added.")) setOutletName("");
          }}
        >
          <Field id="outlet-name" label="New outlet">
            <Input id="outlet-name" value={outletName} onChange={(e) => setOutletName(e.target.value)} placeholder="Bar" maxLength={100} />
          </Field>
          <Button type="submit" variant="secondary" loading={busy === "outlet"}><Plus aria-hidden />Add outlet</Button>
        </form>
      </section>

      {active.length > 0 ? (
        <section aria-label="Add an item" className={box}>
          <h2 className="text-sm font-semibold text-forest">Add an item</h2>
          <form
            className="mt-3 grid gap-3 sm:grid-cols-2"
            onSubmit={async (e) => {
              e.preventDefault();
              const price = parseMoneyInput(form.price);
              const outlet = active.some((o) => o.id === form.outlet) ? form.outlet : active[0]?.id;
              if (form.name.trim().length < 2) return setNotice({ tone: "error", text: "Name the item." });
              if (!price || price === "0.00") return setNotice({ tone: "error", text: "Enter a price, for example 45.00." });
              const ok = await run(
                "item",
                () => api(`/api/v1/properties/${propertyId}/pos/items`, { method: "POST", body: { outlet_id: outlet, name: form.name.trim(), category: form.category.trim() || null, price, prices_include_tax: form.includeTax, tax_ids: form.taxIds } }),
                `${form.name.trim()} added.`,
              );
              if (ok) setForm((f) => ({ ...f, name: "", price: "" }));
            }}
          >
            <Field id="item-outlet" label="Outlet">
              <Select id="item-outlet" value={active.some((o) => o.id === form.outlet) ? form.outlet : active[0]?.id} onChange={(e) => setForm({ ...form, outlet: e.target.value })}>
                {active.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </Select>
            </Field>
            <Field id="item-category" label="Category (optional)">
              <Input id="item-category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Beer, Mains, Activities" maxLength={60} />
            </Field>
            <Field id="item-name" label="Item">
              <Input id="item-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />
            </Field>
            <Field id="item-price" label={`Price (${currency})`}>
              <Input id="item-price" inputMode="decimal" className="font-mono" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
            </Field>
            {taxes.length ? (
              <fieldset className="flex flex-col gap-1.5 sm:col-span-2">
                <legend className="mb-1 text-sm font-medium text-forest">Taxes</legend>
                {taxes.map((t) => (
                  <label key={t.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" className="size-4 accent-forest" checked={form.taxIds.includes(t.id)} onChange={(e) => setForm({ ...form, taxIds: e.target.checked ? [...form.taxIds, t.id] : form.taxIds.filter((x) => x !== t.id) })} />
                    {t.name} {Number(t.rate_percent)}%
                  </label>
                ))}
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="size-4 accent-forest" checked={form.includeTax} onChange={(e) => setForm({ ...form, includeTax: e.target.checked })} />
                  The price includes these taxes
                </label>
              </fieldset>
            ) : null}
            <div className="sm:col-span-2"><Button type="submit" loading={busy === "item"}><Plus aria-hidden />Add item</Button></div>
          </form>
        </section>
      ) : null}

      {outlets.map((o) => {
        const list = items.filter((i) => i.outlet_id === o.id);
        if (!list.length) return null;
        return (
          <section key={o.id} aria-label={`${o.name} items`} className={box}>
            <h2 className="text-sm font-semibold text-forest">{o.name}</h2>
            <ul className="mt-2 divide-y divide-line text-sm">
              {list.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span className={i.status === "archived" ? "text-muted line-through" : ""}>
                    {i.name}{i.category ? <span className="text-muted"> · {i.category}</span> : null}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="font-mono tabular">{formatMoney(i.price, currency)}{i.prices_include_tax ? "" : " + tax"}</span>
                    <button className="text-[12px] text-teal underline-offset-2 hover:underline" onClick={() => void run(i.id, () => api(`/api/v1/pos/items/${i.id}`, { method: "PATCH", body: { status: i.status === "active" ? "archived" : "active" } }), "Saved.")}>
                      {i.status === "active" ? "Stop selling" : "Sell again"}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
