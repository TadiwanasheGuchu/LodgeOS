"use client";

import { Check, Copy, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { MEAL_PLAN_LABELS, type MealPlan, type Property, type RatePlan } from "@/lib/types";

const textarea = "w-full rounded-md border border-control bg-white px-3 py-2 text-[15px] disabled:bg-cloud";

export function OnlineBookingSettings({
  property,
  plans,
  publicUrl,
  canManage,
  canManageRates,
}: {
  property: Property;
  plans: RatePlan[];
  publicUrl: string;
  canManage: boolean;
  canManageRates: boolean;
}) {
  const router = useRouter();
  const [enabled, setEnabled] = useState(property.booking_engine_enabled);
  const [mode, setMode] = useState(property.booking_mode);
  const [terms, setTerms] = useState(property.booking_terms ?? "");
  const [description, setDescription] = useState(property.public_description ?? "");
  const [lead, setLead] = useState(String(property.min_lead_days));
  const [advance, setAdvance] = useState(String(property.max_advance_days));
  const [hold, setHold] = useState(String(property.request_hold_hours));
  const [result, setResult] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Shown at once; reverted if the server refuses.
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const sells = (p: RatePlan) => overrides[p.id] ?? p.sell_online;
  const online = plans.filter(sells);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy("save");
    setResult(null);
    try {
      await api(`/api/v1/properties/${property.id}`, {
        method: "PATCH",
        body: {
          booking_engine_enabled: enabled,
          booking_mode: mode,
          booking_terms: terms.trim() || null,
          public_description: description.trim() || null,
          min_lead_days: Number(lead),
          max_advance_days: Number(advance),
          request_hold_hours: Number(hold),
        },
      });
      setResult({ tone: "success", message: enabled ? "Saved. Guests can book online." : "Saved." });
      router.refresh();
    } catch (err) {
      setResult({ tone: "error", message: err instanceof ApiError ? err.message : "Could not save." });
    } finally {
      setBusy(null);
    }
  }

  async function toggle(plan: RatePlan, value: boolean) {
    setOverrides((o) => ({ ...o, [plan.id]: value }));
    setBusy(plan.id);
    setResult(null);
    try {
      await api(`/api/v1/rate-plans/${plan.id}`, { method: "PATCH", body: { sell_online: value } });
      router.refresh();
    } catch (err) {
      setOverrides((o) => ({ ...o, [plan.id]: !value }));
      setResult({ tone: "error", message: err instanceof ApiError ? err.message : "Could not change the rate." });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <section aria-label="Booking page" className="rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        <h2 className="text-sm font-semibold text-forest">Your booking page</h2>
        <p className="mt-1 text-sm text-muted">
          {property.booking_engine_enabled
            ? "Live. Share this link on your website, social media and WhatsApp."
            : "Not live yet. Turn it on below once terms and an online rate are set."}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-md border border-line bg-cloud px-3 py-2 font-mono text-[13px]">{publicUrl}</code>
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await navigator.clipboard.writeText(publicUrl);
              setCopied(true);
            }}
          >
            {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
            {copied ? "Copied" : "Copy link"}
          </Button>
          {property.booking_engine_enabled ? (
            <Button asChild variant="ghost" size="sm">
              <a href={publicUrl} target="_blank" rel="noopener">
                <ExternalLink aria-hidden />
                Open
              </a>
            </Button>
          ) : null}
        </div>
      </section>

      <section aria-label="Rates sold online" className="rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        <h2 className="text-sm font-semibold text-forest">Rates sold online</h2>
        <p className="mt-1 text-sm text-muted">Only these rates appear on the booking page. Corporate and private rates should stay off.</p>
        {plans.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No active rate plans yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {plans.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span>
                  <span className="font-medium text-charcoal">{p.name}</span>
                  <span className="text-muted"> · {MEAL_PLAN_LABELS[p.meal_plan as MealPlan] ?? p.meal_plan}</span>
                </span>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-4 accent-forest"
                    checked={sells(p)}
                    disabled={!canManageRates || busy === p.id}
                    onChange={(e) => void toggle(p, e.target.checked)}
                  />
                  Sell online
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>

      <form onSubmit={save} noValidate className="flex flex-col gap-5 rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        {result ? <Alert tone={result.tone}>{result.message}</Alert> : null}
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-0.5 size-4 accent-forest" checked={enabled} disabled={!canManage} onChange={(e) => setEnabled(e.target.checked)} />
          <span>
            <span className="font-medium text-forest">Take bookings online</span>
            <span className="block text-muted">{online.length === 0 ? "Mark at least one rate to sell online first." : `${online.length} rate${online.length === 1 ? "" : "s"} offered.`}</span>
          </span>
        </label>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-forest">When a guest books</legend>
          <label className="flex items-start gap-3 rounded-md border border-line px-3 py-2.5 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
            <input type="radio" name="mode" className="mt-0.5 accent-forest" checked={mode === "request"} disabled={!canManage} onChange={() => setMode("request")} />
            <span>
              <span className="font-medium">Request: we confirm each booking</span>
              <span className="block text-muted">The rooms are held as provisional. Unconfirmed requests are cancelled after the hold time.</span>
            </span>
          </label>
          <label className="flex items-start gap-3 rounded-md border border-line px-3 py-2.5 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
            <input type="radio" name="mode" className="mt-0.5 accent-forest" checked={mode === "instant"} disabled={!canManage} onChange={() => setMode("instant")} />
            <span>
              <span className="font-medium">Instant: confirmed straight away</span>
              <span className="block text-muted">The guest pays on arrival until online payment is set up.</span>
            </span>
          </label>
        </fieldset>
        <Field id="booking-terms" label="Booking terms" hint="Cancellation, deposit and payment policy. Guests must accept these to book.">
          <textarea id="booking-terms" rows={5} maxLength={8000} value={terms} disabled={!canManage} onChange={(e) => setTerms(e.target.value)} className={textarea} />
        </Field>
        <Field id="public-description" label="About the property (optional)" hint="Shown at the top of the booking page.">
          <textarea id="public-description" rows={3} maxLength={4000} value={description} disabled={!canManage} onChange={(e) => setDescription(e.target.value)} className={textarea} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="min-lead" label="Earliest arrival (days ahead)">
            <Input id="min-lead" type="number" min={0} max={365} value={lead} disabled={!canManage} onChange={(e) => setLead(e.target.value)} className="tabular" />
          </Field>
          <Field id="max-advance" label="Latest arrival (days ahead)">
            <Input id="max-advance" type="number" min={1} max={730} value={advance} disabled={!canManage} onChange={(e) => setAdvance(e.target.value)} className="tabular" />
          </Field>
          <Field id="hold-hours" label="Hold requests for (hours)">
            <Input id="hold-hours" type="number" min={1} max={336} value={hold} disabled={!canManage || mode === "instant"} onChange={(e) => setHold(e.target.value)} className="tabular" />
          </Field>
        </div>
        {canManage ? (
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy === "save"}>Save</Button>
          </div>
        ) : null}
      </form>
    </div>
  );
}
