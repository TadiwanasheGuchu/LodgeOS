"use client";

import { Plus, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { addDays } from "@/lib/dates";
import { formatMoney, sumMoney } from "@/lib/money";
import {
  BOOKING_SOURCE_LABELS,
  type BookingSource,
  type Guest,
  type PropertySummary,
  type Quote,
  type RatePlan,
  type ReservationDetail,
  type RoomTypeAvailability,
} from "@/lib/types";

type Line = { key: number; roomTypeId: string; ratePlanId: string; adults: string; children: string };
const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function BookingForm({ property, plans, today }: { property: PropertySummary; plans: RatePlan[]; today: string }) {
  const router = useRouter();
  const [checkIn, setCheckIn] = useState(today);
  const [checkOut, setCheckOut] = useState(addDays(today, 1));
  const [availability, setAvailability] = useState<RoomTypeAvailability[] | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [quotes, setQuotes] = useState<Record<number, Quote | string>>({});
  const [guest, setGuest] = useState<Guest | null>(null);
  const [newGuest, setNewGuest] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [source, setSource] = useState<BookingSource>("phone");
  const [provisional, setProvisional] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const datesValid = checkIn && checkOut && checkOut > checkIn;

  // Availability for the chosen dates.
  useEffect(() => {
    if (!datesValid) return;
    let stale = false;
    api<RoomTypeAvailability[]>(`/api/v1/properties/${property.id}/availability?check_in=${checkIn}&check_out=${checkOut}`)
      .then((a) => !stale && setAvailability(a))
      .catch((err) => !stale && setError(errorText(err, "Could not load availability.")));
    return () => {
      stale = true;
    };
  }, [property.id, checkIn, checkOut, datesValid]);

  // A live price for each room line.
  useEffect(() => {
    if (!datesValid) return;
    let stale = false;
    for (const line of lines) {
      api<Quote>(`/api/v1/properties/${property.id}/quote`, {
        method: "POST",
        body: {
          rate_plan_id: line.ratePlanId,
          room_type_id: line.roomTypeId,
          check_in: checkIn,
          check_out: checkOut,
          adults: Number(line.adults) || 0,
          children: Number(line.children) || 0,
        },
      })
        .then((q) => !stale && setQuotes((prev) => ({ ...prev, [line.key]: q })))
        .catch((err) => !stale && setQuotes((prev) => ({ ...prev, [line.key]: errorText(err, "Cannot price this room.") })));
    }
    return () => {
      stale = true;
    };
  }, [lines, checkIn, checkOut, property.id, datesValid]);

  function addLine(roomTypeId: string) {
    setLines((prev) => [...prev, { key: Date.now(), roomTypeId, ratePlanId: plans[0].id, adults: "2", children: "0" }]);
  }
  const updateLine = (key: number, patch: Partial<Line>) => setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const priced = lines.map((l) => quotes[l.key]).filter((q): q is Quote => typeof q === "object");
  const allPriced = lines.length > 0 && priced.length === lines.length;
  const currency = priced[0]?.currency ?? property.currency;

  async function submit() {
    setError(null);
    if (!datesValid) return setError("Check-out must be after check-in.");
    if (lines.length === 0) return setError("Add at least one room.");
    if (!guest && (!newGuest.first_name.trim() || !newGuest.last_name.trim())) return setError("Choose a returning guest or enter the guest's first and last name.");
    setBusy(true);
    try {
      const created = await api<ReservationDetail>(`/api/v1/properties/${property.id}/reservations`, {
        method: "POST",
        body: {
          check_in: checkIn,
          check_out: checkOut,
          ...(guest
            ? { guest_id: guest.id }
            : {
                guest: {
                  first_name: newGuest.first_name.trim(),
                  last_name: newGuest.last_name.trim(),
                  email: newGuest.email.trim() || null,
                  phone: newGuest.phone.trim() || null,
                },
              }),
          rooms: lines.map((l) => ({ room_type_id: l.roomTypeId, rate_plan_id: l.ratePlanId, adults: Number(l.adults), children: Number(l.children) })),
          source,
          status: provisional ? "provisional" : "confirmed",
          notes: notes.trim() || null,
        },
      });
      router.push(`/reservations/${created.id}`);
      router.refresh();
    } catch (err) {
      setError(errorText(err, "Could not create the booking."));
      setBusy(false);
    }
  }

  const nights = datesValid ? Math.round((Date.parse(checkOut) - Date.parse(checkIn)) / 86_400_000) : 0;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="flex min-w-0 flex-col gap-6">
        <section aria-labelledby="stay-heading" className="rounded-lg border border-line bg-white px-5 py-4">
          <h2 id="stay-heading" className="mb-3 text-sm font-semibold text-forest">Stay</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field id="check-in" label="Arrival">
              <Input id="check-in" type="date" value={checkIn} onChange={(e) => { setCheckIn(e.target.value); if (e.target.value >= checkOut) setCheckOut(addDays(e.target.value, 1)); }} />
            </Field>
            <Field id="check-out" label="Departure">
              <Input id="check-out" type="date" value={checkOut} min={addDays(checkIn, 1)} onChange={(e) => setCheckOut(e.target.value)} />
            </Field>
            <p className="self-end pb-2 text-sm text-muted">{nights > 0 ? `${nights} ${nights === 1 ? "night" : "nights"}` : "Departure must be after arrival"}</p>
          </div>
        </section>

        <section aria-labelledby="rooms-heading" className="rounded-lg border border-line bg-white">
          <h2 id="rooms-heading" className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">Rooms</h2>
          {availability === null ? (
            <p className="px-5 py-4 text-sm text-muted">Loading availability…</p>
          ) : (
            <ul className="divide-y divide-line">
              {availability.map((a) => {
                const chosen = lines.filter((l) => l.roomTypeId === a.room_type_id).length;
                const left = a.free - chosen;
                return (
                  <li key={a.room_type_id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                    <span className="min-w-0 flex-1">
                      <span className="font-mono text-[13px]">{a.room_type_code}</span> <span className="font-medium text-forest">{a.room_type_name}</span>
                      <span className="block text-[13px] text-muted">Up to {a.max_occupancy} guests</span>
                    </span>
                    <span className={left > 0 ? "text-sm text-success" : "text-sm text-danger"}>
                      {left > 0 ? `${left} free` : "None free"}
                    </span>
                    <Button variant="secondary" size="sm" disabled={left <= 0} onClick={() => addLine(a.room_type_id)} aria-label={`Add a ${a.room_type_name}`}>
                      <Plus aria-hidden />
                      Add
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
          {lines.length ? (
            <ul className="divide-y divide-line border-t border-line bg-cloud">
              {lines.map((l, i) => {
                const type = availability?.find((a) => a.room_type_id === l.roomTypeId);
                const q = quotes[l.key];
                return (
                  <li key={l.key} className="grid gap-3 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_5rem_5rem_auto] sm:items-end">
                    <p className="text-sm font-medium text-forest sm:pb-2">Room {i + 1}: {type?.room_type_name}</p>
                    <Field id={`plan-${l.key}`} label="Rate plan">
                      <Select id={`plan-${l.key}`} value={l.ratePlanId} onChange={(e) => updateLine(l.key, { ratePlanId: e.target.value })}>
                        {plans.map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </Select>
                    </Field>
                    <Field id={`adults-${l.key}`} label="Adults">
                      <Input id={`adults-${l.key}`} type="number" min={1} inputMode="numeric" value={l.adults} onChange={(e) => updateLine(l.key, { adults: e.target.value })} />
                    </Field>
                    <Field id={`children-${l.key}`} label="Children">
                      <Input id={`children-${l.key}`} type="number" min={0} inputMode="numeric" value={l.children} onChange={(e) => updateLine(l.key, { children: e.target.value })} />
                    </Field>
                    <Button variant="ghost" size="icon" onClick={() => setLines((prev) => prev.filter((x) => x.key !== l.key))} aria-label={`Remove room ${i + 1}`}>
                      <Trash2 aria-hidden />
                    </Button>
                    <p className="text-sm sm:col-span-5">
                      {q === undefined ? <span className="text-muted">Pricing…</span> : typeof q === "string" ? <span className="text-danger">{q}</span> : (
                        <span>
                          <span className="font-mono">{formatMoney(q.total, q.currency)}</span>
                          <span className="text-muted"> for {q.nights.length} {q.nights.length === 1 ? "night" : "nights"}{q.prices_include_tax ? ", tax included" : ""}</span>
                        </span>
                      )}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </section>

        <GuestSection guest={guest} setGuest={setGuest} newGuest={newGuest} setNewGuest={setNewGuest} />
      </div>

      <aside className="flex flex-col gap-4 rounded-lg border border-line bg-white px-5 py-4 lg:sticky lg:top-4">
        <h2 className="text-sm font-semibold text-forest">Booking</h2>
        <Field id="source" label="How did they book?">
          <Select id="source" value={source} onChange={(e) => setSource(e.target.value as BookingSource)}>
            {Object.entries(BOOKING_SOURCE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </Select>
        </Field>
        <label className="flex items-start gap-2.5 text-sm">
          <input type="checkbox" checked={provisional} onChange={(e) => setProvisional(e.target.checked)} className="mt-0.5 size-4 accent-forest" />
          <span>
            <span className="font-medium text-forest">Provisional</span>
            <span className="block text-[13px] text-muted">Hold the rooms until the guest confirms.</span>
          </span>
        </label>
        <Field id="notes" label="Notes (optional)">
          <textarea id="notes" rows={3} maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
        </Field>
        <div className="border-t border-line pt-3">
          <p className="flex items-baseline justify-between text-sm">
            <span className="text-muted">Total</span>
            <span className="font-mono text-lg font-semibold text-forest" aria-live="polite">
              {allPriced
                ? formatMoney(sumMoney(priced.map((q) => q.total)), currency)
                : "—"}
            </span>
          </p>
          <p className="mt-1 text-[12px] text-muted">The final price is calculated again when you book.</p>
        </div>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Button size="lg" onClick={submit} loading={busy} disabled={!allPriced}>
          Book {lines.length > 1 ? `${lines.length} rooms` : "room"}
        </Button>
      </aside>
    </div>
  );
}

function GuestSection({
  guest,
  setGuest,
  newGuest,
  setNewGuest,
}: {
  guest: Guest | null;
  setGuest: (g: Guest | null) => void;
  newGuest: { first_name: string; last_name: string; email: string; phone: string };
  setNewGuest: (g: { first_name: string; last_name: string; email: string; phone: string }) => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Guest[]>([]);

  useEffect(() => {
    if (q.trim().length < 2) return;
    let stale = false;
    const t = setTimeout(() => {
      api<Guest[]>(`/api/v1/guests?q=${encodeURIComponent(q.trim())}`)
        .then((r) => !stale && setResults(r))
        .catch(() => !stale && setResults([]));
    }, 250);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <section aria-labelledby="guest-heading" className="rounded-lg border border-line bg-white px-5 py-4">
      <h2 id="guest-heading" className="mb-3 text-sm font-semibold text-forest">Guest</h2>
      {guest ? (
        <div className="flex items-center justify-between gap-3 rounded-md bg-mist px-3 py-2.5">
          <span>
            <span className="font-medium text-forest">{guest.first_name} {guest.last_name}</span>
            <span className="block text-[13px] text-muted">{[guest.email, guest.phone].filter(Boolean).join(" · ") || "No contact details"}</span>
          </span>
          <Button variant="ghost" size="sm" onClick={() => setGuest(null)}>Change</Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <Field id="guest-search" label="Returning guest">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
              <Input id="guest-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, email or phone" className="pl-9" autoComplete="off" />
            </div>
          </Field>
          {q.trim().length >= 2 && results.length ? (
            <ul className="divide-y divide-line rounded-md border border-line">
              {results.map((g) => (
                <li key={g.id}>
                  <button type="button" onClick={() => setGuest(g)} className="w-full px-3 py-2 text-left text-sm hover:bg-mist">
                    <span className="font-medium text-forest">{g.first_name} {g.last_name}</span>
                    <span className="block text-[13px] text-muted">{[g.email, g.phone].filter(Boolean).join(" · ")}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="text-[13px] text-muted">Or enter a new guest:</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="first-name" label="First name">
              <Input id="first-name" value={newGuest.first_name} onChange={(e) => setNewGuest({ ...newGuest, first_name: e.target.value })} autoComplete="off" />
            </Field>
            <Field id="last-name" label="Last name">
              <Input id="last-name" value={newGuest.last_name} onChange={(e) => setNewGuest({ ...newGuest, last_name: e.target.value })} autoComplete="off" />
            </Field>
            <Field id="guest-email" label="Email (optional)">
              <Input id="guest-email" type="email" value={newGuest.email} onChange={(e) => setNewGuest({ ...newGuest, email: e.target.value })} autoComplete="off" />
            </Field>
            <Field id="guest-phone" label="Phone (optional)">
              <Input id="guest-phone" type="tel" value={newGuest.phone} onChange={(e) => setNewGuest({ ...newGuest, phone: e.target.value })} autoComplete="off" />
            </Field>
          </div>
        </div>
      )}
    </section>
  );
}
