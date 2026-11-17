"use client";

import { Calculator, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatMoney, formatPercent, parseMoneyInput } from "@/lib/money";
import {
  MEAL_PLAN_LABELS,
  RATE_PLAN_KIND_LABELS,
  type MealPlan,
  type PriceSet,
  type Property,
  type Quote,
  type RatePlan,
  type RatePlanDetail,
  type RatePlanKind,
  type RoomType,
  type Season,
  type Tax,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);
const shortDate = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));

export function RatesManager({
  property,
  taxes,
  plans,
  plan,
  roomTypes,
  canManage,
}: {
  property: Property;
  taxes: Tax[];
  plans: RatePlan[];
  plan: RatePlanDetail | null;
  roomTypes: RoomType[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<
    | { kind: "tax"; tax: Tax | null }
    | { kind: "plan"; plan: RatePlan | null }
    | { kind: "price"; roomType: RoomType }
    | { kind: "season"; season: Season | null }
    | null
  >(null);
  const done = () => {
    setDialog(null);
    router.refresh();
  };

  if (roomTypes.length === 0) {
    return (
      <Alert tone="info">
        Add room types before setting rates.{" "}
        <Link href={`/properties/${property.id}/room-types`} className="font-medium underline underline-offset-2">
          Go to room types
        </Link>
      </Alert>
    );
  }

  const activeTaxes = taxes.filter((t) => t.status === "active");

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="flex min-w-0 flex-col gap-6">
        {/* Rate plans */}
        <section aria-labelledby="plans-heading" className="rounded-lg border border-line bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
            <h2 id="plans-heading" className="text-sm font-semibold text-forest">Rate plans</h2>
            {canManage ? (
              <Button size="sm" variant="secondary" onClick={() => setDialog({ kind: "plan", plan: null })}>
                <Plus aria-hidden />
                Add rate plan
              </Button>
            ) : null}
          </div>
          {plans.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted">No rate plans yet. Start with your standard rate.</p>
          ) : (
            <nav aria-label="Rate plans" className="flex flex-wrap gap-1.5 px-5 py-3">
              {plans.map((p) => (
                <Link
                  key={p.id}
                  href={`/properties/${property.id}/rates?plan=${p.id}`}
                  aria-current={plan?.id === p.id ? "page" : undefined}
                  className={cn(
                    "rounded-md border border-line px-3 py-1.5 text-sm hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white",
                    p.status === "archived" && "text-muted line-through",
                  )}
                >
                  <span className="font-mono text-[12px]">{p.code}</span> {p.name}
                </Link>
              ))}
            </nav>
          )}
        </section>

        {plan ? (
          <section aria-labelledby="plan-heading" className="rounded-lg border border-line bg-white">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <h2 id="plan-heading" className="font-semibold text-forest">
                  {plan.name} <span className="font-mono text-[13px] font-normal text-muted">{plan.code}</span>
                </h2>
                <p className="mt-0.5 text-sm text-muted">
                  {RATE_PLAN_KIND_LABELS[plan.kind]} · {MEAL_PLAN_LABELS[plan.meal_plan]} ·{" "}
                  {plan.prices_include_tax ? "Prices include tax" : "Tax added to prices"} · Minimum {plan.min_stay_nights}{" "}
                  {plan.min_stay_nights === 1 ? "night" : "nights"}
                  {plan.stay_from || plan.stay_to
                    ? ` · Stays ${plan.stay_from ? `from ${shortDate(plan.stay_from)}` : ""}${plan.stay_to ? ` to ${shortDate(plan.stay_to)}` : ""}`
                    : ""}
                  {plan.status === "archived" ? " · Archived" : ""}
                </p>
              </div>
              {canManage ? (
                <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: "plan", plan })}>
                  <Pencil aria-hidden />
                  Edit plan
                </Button>
              ) : null}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <caption className="sr-only">Nightly prices in {plan.currency}</caption>
                <thead className="border-b border-line bg-cloud text-[13px] text-muted">
                  <tr>
                    <th scope="col" className="px-5 py-2.5 font-medium">Room type</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Per night</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Weekend</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Extra adult</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Extra child</th>
                    {canManage ? <th scope="col" className="px-3 py-2.5"><span className="sr-only">Edit</span></th> : null}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {roomTypes.map((rt) => {
                    const p = plan.prices.find((x) => x.room_type_id === rt.id);
                    return (
                      <tr key={rt.id}>
                        <td className="px-5 py-2.5">
                          <span className="font-mono text-[13px]">{rt.code}</span> {rt.name}
                          <span className="block text-[12px] text-muted">{rt.base_occupancy} guests included</span>
                        </td>
                        {p ? (
                          <>
                            <td className="px-3 py-2.5 text-right font-mono">{formatMoney(p.base_price, plan.currency)}</td>
                            <td className="px-3 py-2.5 text-right font-mono">{p.weekend_price ? formatMoney(p.weekend_price, plan.currency) : "—"}</td>
                            <td className="px-3 py-2.5 text-right font-mono">{formatMoney(p.extra_adult_price, plan.currency)}</td>
                            <td className="px-3 py-2.5 text-right font-mono">{formatMoney(p.extra_child_price, plan.currency)}</td>
                          </>
                        ) : (
                          <td colSpan={4} className="px-3 py-2.5 text-right text-[13px] text-danger">No price set: this room type cannot be quoted</td>
                        )}
                        {canManage ? (
                          <td className="px-2 py-1 text-right">
                            <Button variant="ghost" size="sm" onClick={() => setDialog({ kind: "price", roomType: rt })} aria-label={`Set prices for ${rt.name}`}>
                              <Pencil aria-hidden />
                            </Button>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="border-t border-line px-5 py-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-forest">Seasons</h3>
                {canManage ? (
                  <Button size="sm" variant="secondary" onClick={() => setDialog({ kind: "season", season: null })}>
                    <Plus aria-hidden />
                    Add season
                  </Button>
                ) : null}
              </div>
              {plan.seasons.length === 0 ? (
                <p className="text-sm text-muted">No seasons. Normal prices apply all year.</p>
              ) : (
                <ul className="divide-y divide-line text-sm">
                  {plan.seasons.map((s) => {
                    const rt = roomTypes.find((r) => r.id === s.room_type_id);
                    return (
                      <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2">
                        <span className="min-w-0 flex-1">
                          <span className="font-medium text-forest">{s.name}</span>{" "}
                          <span className="text-muted">
                            {rt ? `${rt.code} · ` : ""}
                            {shortDate(s.start_date)} to {shortDate(s.end_date)}
                          </span>
                        </span>
                        <span className="font-mono">{formatMoney(s.base_price, plan.currency)}</span>
                        {canManage ? (
                          <span className="flex">
                            <Button variant="ghost" size="sm" onClick={() => setDialog({ kind: "season", season: s })} aria-label={`Edit ${s.name}`}>
                              <Pencil aria-hidden />
                            </Button>
                            <DeleteSeason season={s} onDone={done} />
                          </span>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>
        ) : null}

        {/* Taxes */}
        <section aria-labelledby="taxes-heading" className="rounded-lg border border-line bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
            <h2 id="taxes-heading" className="text-sm font-semibold text-forest">Taxes on accommodation</h2>
            {canManage ? (
              <Button size="sm" variant="secondary" onClick={() => setDialog({ kind: "tax", tax: null })}>
                <Plus aria-hidden />
                Add tax
              </Button>
            ) : null}
          </div>
          {taxes.length === 0 ? (
            <p className="px-5 py-4 text-sm text-muted">No taxes set. Add the taxes this property charges, such as VAT or a tourism levy.</p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {taxes.map((t) => (
                <li key={t.id} className={cn("flex items-center gap-4 px-5 py-2.5", t.status === "archived" && "text-muted")}>
                  <span className="flex-1">
                    {t.name}
                    {t.status === "archived" ? <span className="ml-2 text-[12px]">Not charged</span> : null}
                  </span>
                  <span className="font-mono">{formatPercent(t.rate_percent)}</span>
                  {canManage ? (
                    <Button variant="ghost" size="sm" onClick={() => setDialog({ kind: "tax", tax: t })} aria-label={`Edit ${t.name}`}>
                      <Pencil aria-hidden />
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <QuotePanel property={property} plans={plans.filter((p) => p.status === "active")} roomTypes={roomTypes} selectedPlanId={plan?.id ?? null} taxCount={activeTaxes.length} />

      {dialog?.kind === "tax" ? <TaxDialog propertyId={property.id} tax={dialog.tax} onClose={() => setDialog(null)} onDone={done} /> : null}
      {dialog?.kind === "plan" ? (
        <PlanDialog
          propertyId={property.id}
          plan={dialog.plan}
          onClose={() => setDialog(null)}
          onDone={(id) => {
            setDialog(null);
            router.push(`/properties/${property.id}/rates?plan=${id}`);
            router.refresh();
          }}
        />
      ) : null}
      {dialog?.kind === "price" && plan ? (
        <PriceDialog plan={plan} roomType={dialog.roomType} onClose={() => setDialog(null)} onDone={done} />
      ) : null}
      {dialog?.kind === "season" && plan ? (
        <SeasonDialog plan={plan} season={dialog.season} roomTypes={roomTypes} onClose={() => setDialog(null)} onDone={done} />
      ) : null}
    </div>
  );
}

/* --- money inputs ------------------------------------------------------------------- */

function MoneyField({
  id,
  label,
  currency,
  value,
  onChange,
  optional,
}: {
  id: string;
  label: string;
  currency: string;
  value: string;
  onChange: (v: string) => void;
  optional?: boolean;
}) {
  return (
    <Field id={id} label={`${label}${optional ? " (optional)" : ""}`}>
      <div className="relative">
        <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 font-mono text-[13px] text-muted">{currency}</span>
        <Input id={id} inputMode="decimal" autoComplete="off" value={value} onChange={(e) => onChange(e.target.value)} className="pl-12 text-right font-mono" />
      </div>
    </Field>
  );
}

function usePriceForm(initial: Partial<PriceSet> | undefined) {
  const [base, setBase] = useState(initial?.base_price ?? "");
  const [weekend, setWeekend] = useState(initial?.weekend_price ?? "");
  const [adult, setAdult] = useState(initial?.extra_adult_price ?? "0.00");
  const [child, setChild] = useState(initial?.extra_child_price ?? "0.00");
  function values(): { ok: true; body: PriceSet } | { ok: false; error: string } {
    const b = parseMoneyInput(base);
    if (!b) return { ok: false, error: "Enter the nightly price, for example 1250.00." };
    const w = weekend.trim() ? parseMoneyInput(weekend) : null;
    if (weekend.trim() && !w) return { ok: false, error: "Enter a valid weekend price, or leave it empty." };
    const a = parseMoneyInput(adult || "0");
    const c = parseMoneyInput(child || "0");
    if (!a || !c) return { ok: false, error: "Enter valid extra guest prices (0 for none)." };
    return { ok: true, body: { base_price: b, weekend_price: w, extra_adult_price: a, extra_child_price: c } };
  }
  return { base, setBase, weekend, setWeekend, adult, setAdult, child, setChild, values };
}

function PriceFields({ f, currency }: { f: ReturnType<typeof usePriceForm>; currency: string }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <MoneyField id="price-base" label="Per night" currency={currency} value={f.base} onChange={f.setBase} />
      <MoneyField id="price-weekend" label="Weekend night" currency={currency} value={f.weekend} onChange={f.setWeekend} optional />
      <MoneyField id="price-adult" label="Extra adult" currency={currency} value={f.adult} onChange={f.setAdult} />
      <MoneyField id="price-child" label="Extra child" currency={currency} value={f.child} onChange={f.setChild} />
    </div>
  );
}

/* --- dialogs ------------------------------------------------------------------------ */

function useSubmit(onDone: () => void) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>, fallback = "Could not save.") {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
    } catch (err) {
      setError(errorText(err, fallback));
      setBusy(false);
    }
  }
  return { error, setError, busy, run };
}

function PriceDialog({ plan, roomType, onClose, onDone }: { plan: RatePlanDetail; roomType: RoomType; onClose: () => void; onDone: () => void }) {
  const existing = plan.prices.find((p) => p.room_type_id === roomType.id);
  const f = usePriceForm(existing);
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent
        title={`${roomType.name} · ${plan.name}`}
        description={`Per night for ${roomType.base_occupancy} guests, ${plan.prices_include_tax ? "including" : "before"} tax. Seasons override these prices.`}
      >
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const v = f.values();
            if (!v.ok) return s.setError(v.error);
            void s.run(() => api(`/api/v1/rate-plans/${plan.id}/prices/${roomType.id}`, { method: "PUT", body: v.body }));
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <PriceFields f={f} currency={plan.currency} />
          <div className="flex gap-2 border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Save prices</Button>
            {existing ? (
              <Button type="button" variant="ghost" disabled={s.busy} onClick={() => s.run(() => api(`/api/v1/rate-plans/${plan.id}/prices/${roomType.id}`, { method: "DELETE" }))}>
                Clear prices
              </Button>
            ) : null}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SeasonDialog({
  plan,
  season,
  roomTypes,
  onClose,
  onDone,
}: {
  plan: RatePlanDetail;
  season: Season | null;
  roomTypes: RoomType[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [name, setName] = useState(season?.name ?? "");
  const [roomTypeId, setRoomTypeId] = useState(season?.room_type_id ?? roomTypes[0]?.id ?? "");
  const [start, setStart] = useState(season?.start_date ?? "");
  const [end, setEnd] = useState(season?.end_date ?? "");
  const f = usePriceForm(season ?? undefined);
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={season ? `Edit ${season.name}` : "Add season"} description="Prices for these nights replace the normal prices. The last night is included.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length < 2) return s.setError("Name the season, for example Festive.");
            if (!start || !end) return s.setError("Choose the first and last night.");
            if (end < start) return s.setError("The last night must be on or after the first.");
            const v = f.values();
            if (!v.ok) return s.setError(v.error);
            const body = { name: name.trim(), start_date: start, end_date: end, ...v.body };
            void s.run(() =>
              season
                ? api(`/api/v1/seasons/${season.id}`, { method: "PATCH", body })
                : api(`/api/v1/rate-plans/${plan.id}/seasons`, { method: "POST", body: { ...body, room_type_id: roomTypeId } }),
            );
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="season-name" label="Name">
              <Input id="season-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Festive" />
            </Field>
            <Field id="season-room-type" label="Room type">
              <Select id="season-room-type" value={roomTypeId} disabled={Boolean(season)} onChange={(e) => setRoomTypeId(e.target.value)}>
                {roomTypes.map((r) => (
                  <option key={r.id} value={r.id}>{r.code} · {r.name}</option>
                ))}
              </Select>
            </Field>
            <Field id="season-start" label="First night">
              <Input id="season-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field id="season-end" label="Last night">
              <Input id="season-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
          <PriceFields f={f} currency={plan.currency} />
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>{season ? "Save season" : "Add season"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteSeason({ season, onDone }: { season: Season; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      loading={busy}
      aria-label={`Delete ${season.name}`}
      onClick={async () => {
        setBusy(true);
        try {
          await api(`/api/v1/seasons/${season.id}`, { method: "DELETE" });
          onDone();
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? null : <Trash2 aria-hidden />}
    </Button>
  );
}

function TaxDialog({ propertyId, tax, onClose, onDone }: { propertyId: string; tax: Tax | null; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(tax?.name ?? "");
  const [rate, setRate] = useState(tax ? tax.rate_percent.replace(/\.?0+$/, "") : "");
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={tax ? `Edit ${tax.name}` : "Add tax"} description="Charged on accommodation at this property. Confirm rates with your accountant.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length < 2) return s.setError("Name the tax, for example VAT.");
            if (!/^\d{1,2}(\.\d{1,4})?$/.test(rate.trim()) || Number(rate) <= 0) return s.setError("Enter a rate between 0 and 100, for example 15.");
            const body = { name: name.trim(), rate_percent: rate.trim() };
            void s.run(() => (tax ? api(`/api/v1/taxes/${tax.id}`, { method: "PATCH", body }) : api(`/api/v1/properties/${propertyId}/taxes`, { method: "POST", body })));
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
            <Field id="tax-name" label="Name">
              <Input id="tax-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="VAT" />
            </Field>
            <Field id="tax-rate" label="Rate (%)">
              <Input id="tax-rate" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} className="text-right font-mono" />
            </Field>
          </div>
          <div className="flex gap-2 border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>{tax ? "Save" : "Add tax"}</Button>
            {tax ? (
              <Button
                type="button"
                variant="ghost"
                disabled={s.busy}
                onClick={() => s.run(() => api(`/api/v1/taxes/${tax.id}`, { method: "PATCH", body: { status: tax.status === "active" ? "archived" : "active" } }))}
              >
                {tax.status === "active" ? "Stop charging" : "Charge again"}
              </Button>
            ) : null}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PlanDialog({ propertyId, plan, onClose, onDone }: { propertyId: string; plan: RatePlan | null; onClose: () => void; onDone: (id: string) => void }) {
  const [name, setName] = useState(plan?.name ?? "");
  const [code, setCode] = useState(plan?.code ?? "");
  const [kind, setKind] = useState<RatePlanKind>(plan?.kind ?? "standard");
  const [meal, setMeal] = useState<MealPlan>(plan?.meal_plan ?? "room_only");
  const [includesTax, setIncludesTax] = useState(plan?.prices_include_tax ?? true);
  const [minStay, setMinStay] = useState(String(plan?.min_stay_nights ?? 1));
  const [from, setFrom] = useState(plan?.stay_from ?? "");
  const [to, setTo] = useState(plan?.stay_to ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(body: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      const saved = plan
        ? await api<RatePlan>(`/api/v1/rate-plans/${plan.id}`, { method: "PATCH", body })
        : await api<RatePlan>(`/api/v1/properties/${propertyId}/rate-plans`, { method: "POST", body });
      onDone(saved.id);
    } catch (err) {
      setError(errorText(err, "Could not save the rate plan."));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={plan ? `Edit ${plan.name}` : "Add rate plan"}>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const c = code.trim().toUpperCase();
            if (name.trim().length < 2) return setError("Name the rate plan.");
            if (!/^[A-Z0-9][A-Z0-9-]{0,15}$/.test(c)) return setError("Use a short code of letters and digits, for example BB.");
            const n = Number(minStay);
            if (!Number.isInteger(n) || n < 1) return setError("Minimum stay must be at least 1 night.");
            if (from && to && to < from) return setError("The last night must be on or after the first.");
            void save({ name: name.trim(), code: c, kind, meal_plan: meal, prices_include_tax: includesTax, min_stay_nights: n, stay_from: from || null, stay_to: to || null });
          }}
        >
          {error ? <Alert tone="error">{error}</Alert> : null}
          <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
            <Field id="plan-name" label="Name">
              <Input id="plan-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Bed and breakfast" />
            </Field>
            <Field id="plan-code" label="Code">
              <Input id="plan-code" value={code} onChange={(e) => setCode(e.target.value)} className="font-mono uppercase" placeholder="BB" />
            </Field>
            <Field id="plan-kind" label="Kind">
              <Select id="plan-kind" value={kind} onChange={(e) => setKind(e.target.value as RatePlanKind)}>
                {Object.entries(RATE_PLAN_KIND_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </Select>
            </Field>
            <Field id="plan-min" label="Min. nights">
              <Input id="plan-min" type="number" min={1} inputMode="numeric" value={minStay} onChange={(e) => setMinStay(e.target.value)} />
            </Field>
          </div>
          <Field id="plan-meal" label="Meals included">
            <Select id="plan-meal" value={meal} onChange={(e) => setMeal(e.target.value as MealPlan)}>
              {Object.entries(MEAL_PLAN_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </Select>
          </Field>
          <label className="flex items-start gap-2.5 text-sm">
            <input type="checkbox" checked={includesTax} onChange={(e) => setIncludesTax(e.target.checked)} className="mt-0.5 size-4 accent-forest" />
            <span>
              <span className="font-medium text-forest">Prices include tax</span>
              <span className="block text-[13px] text-muted">Usual for guest-facing prices. If unticked, taxes are added on top.</span>
            </span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <Field id="plan-from" label="Valid from (optional)">
              <Input id="plan-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field id="plan-to" label="Last night (optional)">
              <Input id="plan-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </Field>
          </div>
          <div className="flex gap-2 border-t border-line pt-4">
            <Button type="submit" loading={busy}>{plan ? "Save" : "Add rate plan"}</Button>
            {plan ? (
              <Button type="button" variant="ghost" disabled={busy} onClick={() => save({ status: plan.status === "active" ? "archived" : "active" })}>
                {plan.status === "active" ? "Archive" : "Restore"}
              </Button>
            ) : null}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* --- quote ------------------------------------------------------------------------------ */

function QuotePanel({
  property,
  plans,
  roomTypes,
  selectedPlanId,
  taxCount,
}: {
  property: Property;
  plans: RatePlan[];
  roomTypes: RoomType[];
  selectedPlanId: string | null;
  taxCount: number;
}) {
  const [chosenPlanId, setPlanId] = useState(selectedPlanId ?? plans[0]?.id ?? "");
  const [chosenRoomTypeId, setRoomTypeId] = useState(roomTypes[0]?.id ?? "");
  // Plans and room types can be added or archived after this panel first rendered; never
  // keep a selection that is no longer offered.
  const planId = plans.some((p) => p.id === chosenPlanId) ? chosenPlanId : (selectedPlanId ?? plans[0]?.id ?? "");
  const roomTypeId = roomTypes.some((r) => r.id === chosenRoomTypeId) ? chosenRoomTypeId : (roomTypes[0]?.id ?? "");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState("2");
  const [children, setChildren] = useState("0");
  const [result, setResult] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!checkIn || !checkOut) return setError("Choose arrival and departure dates.");
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api<Quote>(`/api/v1/properties/${property.id}/quote`, {
          method: "POST",
          body: { rate_plan_id: planId, room_type_id: roomTypeId, check_in: checkIn, check_out: checkOut, adults: Number(adults), children: Number(children) },
        }),
      );
    } catch (err) {
      const fields = err instanceof ApiError ? Object.entries(err.fieldErrors) : [];
      setError(fields.length ? fields.map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" ") : errorText(err, "Could not calculate the price."));
    } finally {
      setBusy(false);
    }
  }

  if (plans.length === 0) return null;

  return (
    <section aria-labelledby="quote-heading" className="rounded-lg border border-line bg-white px-5 py-4 xl:sticky xl:top-4">
      <h2 id="quote-heading" className="flex items-center gap-2 text-sm font-semibold text-forest">
        <Calculator className="size-4" aria-hidden />
        Price a stay
      </h2>
      <form onSubmit={run} noValidate className="mt-3 flex flex-col gap-3">
        <Field id="q-plan" label="Rate plan">
          <Select id="q-plan" value={planId} onChange={(e) => setPlanId(e.target.value)}>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </Select>
        </Field>
        <Field id="q-room" label="Room type">
          <Select id="q-room" value={roomTypeId} onChange={(e) => setRoomTypeId(e.target.value)}>
            {roomTypes.map((r) => (
              <option key={r.id} value={r.id}>{r.code} · {r.name}</option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field id="q-in" label="Arrival">
            <Input id="q-in" type="date" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
          </Field>
          <Field id="q-out" label="Departure">
            <Input id="q-out" type="date" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
          </Field>
          <Field id="q-adults" label="Adults">
            <Input id="q-adults" type="number" min={1} inputMode="numeric" value={adults} onChange={(e) => setAdults(e.target.value)} />
          </Field>
          <Field id="q-children" label="Children">
            <Input id="q-children" type="number" min={0} inputMode="numeric" value={children} onChange={(e) => setChildren(e.target.value)} />
          </Field>
        </div>
        <Button type="submit" variant="secondary" loading={busy}>Calculate</Button>
      </form>
      {taxCount === 0 ? <p className="mt-3 text-[13px] text-muted">No taxes are set for this property.</p> : null}
      {error ? <Alert tone="error" className="mt-3">{error}</Alert> : null}
      {result ? (
        <div className="mt-4 border-t border-line pt-3 text-sm" aria-live="polite">
          <table className="w-full">
            <caption className="sr-only">Price per night</caption>
            <tbody>
              {result.nights.map((n) => (
                <tr key={n.date}>
                  <td className="py-0.5 text-muted">
                    {new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${n.date}T00:00:00Z`))}
                    {n.season ? ` · ${n.season}` : n.weekend ? " · weekend" : ""}
                  </td>
                  <td className="py-0.5 text-right font-mono">{formatMoney(n.amount, result.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-t border-line pt-2">
            <dt className="text-muted">Before tax</dt>
            <dd className="text-right font-mono">{formatMoney(result.net_total, result.currency)}</dd>
            {result.taxes.map((t) => (
              <div key={t.name} className="contents">
                <dt className="text-muted">{t.name} ({formatPercent(t.rate_percent)})</dt>
                <dd className="text-right font-mono">{formatMoney(t.amount, result.currency)}</dd>
              </div>
            ))}
            <dt className="mt-1 font-semibold text-forest">Total</dt>
            <dd className="mt-1 text-right font-mono font-semibold text-forest">{formatMoney(result.total, result.currency)}</dd>
          </dl>
        </div>
      ) : null}
    </section>
  );
}
