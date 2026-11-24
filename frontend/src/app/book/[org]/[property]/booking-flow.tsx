"use client";

import { ArrowLeft, BedDouble, CalendarCheck, Clock } from "lucide-react";
import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { addDays, formatStayDate } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { MEAL_PLAN_LABELS, type MealPlan, type PublicBooking, type PublicProperty, type RoomTypeOffers } from "@/lib/types";

type Choice = { roomTypeId: string; roomType: string; ratePlanId: string; ratePlan: string; total: string };
type Search = { checkIn: string; checkOut: string; adults: number; children: number };

const long = { weekday: "short", day: "numeric", month: "short", year: "numeric" } as const;

export function BookingFlow({ org, slug, property }: { org: string; slug: string; property: PublicProperty }) {
  const base = `/api/v1/public/properties/${encodeURIComponent(org)}/${encodeURIComponent(slug)}`;
  const first = property.earliest_arrival;
  const [search, setSearch] = useState<Search>({ checkIn: first, checkOut: addDays(first, 1), adults: 2, children: 0 });
  const [results, setResults] = useState<RoomTypeOffers[] | null>(null);
  const [searched, setSearched] = useState<Search | null>(null);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [booking, setBooking] = useState<PublicBooking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const maxAdults = Math.max(1, ...property.room_types.map((t) => t.max_adults));
  const maxChildren = Math.max(0, ...property.room_types.map((t) => t.max_children));
  const money = (a: string) => formatMoney(a, property.currency);

  async function find(e: React.FormEvent) {
    e.preventDefault();
    if (search.checkOut <= search.checkIn) return setError("Departure must be after arrival.");
    setBusy(true);
    setError(null);
    setChoice(null);
    try {
      const q = new URLSearchParams({ check_in: search.checkIn, check_out: search.checkOut, adults: String(search.adults), children: String(search.children) });
      setResults(await api<RoomTypeOffers[]>(`${base}/offers?${q}`));
      setSearched(search);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not check availability. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  if (booking) return <Confirmation booking={booking} property={property} />;

  if (choice && searched) {
    return (
      <GuestDetails
        base={base}
        property={property}
        search={searched}
        choice={choice}
        onBack={() => setChoice(null)}
        onBooked={setBooking}
      />
    );
  }

  const available = results?.filter((r) => r.available > 0 && r.offers.length > 0) ?? [];
  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={find} noValidate className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-white p-4 sm:grid-cols-[1fr_1fr_auto_auto_auto] sm:items-end sm:p-5">
        <div className="col-span-2 sm:col-span-1">
        <Field id="arrival" label="Arrival">
          <Input
            id="arrival"
            type="date"
            min={property.earliest_arrival}
            max={property.latest_arrival}
            value={search.checkIn}
            onChange={(e) => {
              const v = e.target.value;
              setSearch((s) => ({ ...s, checkIn: v, checkOut: s.checkOut <= v ? addDays(v, 1) : s.checkOut }));
            }}
          />
        </Field>
        </div>
        <div className="col-span-2 sm:col-span-1">
        <Field id="departure" label="Departure">
          <Input id="departure" type="date" min={addDays(search.checkIn, 1)} value={search.checkOut} onChange={(e) => setSearch((s) => ({ ...s, checkOut: e.target.value }))} />
        </Field>
        </div>
        <Field id="adults" label="Adults">
          <Select id="adults" value={search.adults} onChange={(e) => setSearch((s) => ({ ...s, adults: Number(e.target.value) }))}>
            {Array.from({ length: maxAdults }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field id="children" label="Children">
          <Select id="children" value={search.children} disabled={maxChildren === 0} onChange={(e) => setSearch((s) => ({ ...s, children: Number(e.target.value) }))}>
            {Array.from({ length: maxChildren + 1 }, (_, i) => i).map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Button type="submit" size="lg" loading={busy} className="col-span-2 sm:col-span-1 sm:h-10">Check availability</Button>
      </form>
      {error ? <Alert tone="error">{error}</Alert> : null}

      {results && searched ? (
        available.length === 0 ? (
          <Alert tone="info">
            Nothing available for {formatStayDate(searched.checkIn, long)} to {formatStayDate(searched.checkOut, long)} for {searched.adults + searched.children} guest{searched.adults + searched.children === 1 ? "" : "s"}. Try other dates{property.phone ? ` or call us on ${property.phone}` : ""}.
          </Alert>
        ) : (
          <section aria-label="Available rooms" className="flex flex-col gap-3">
            <h2 className="text-sm text-muted">
              {formatStayDate(searched.checkIn, long)} to {formatStayDate(searched.checkOut, long)} · {searched.adults} adult{searched.adults === 1 ? "" : "s"}
              {searched.children ? `, ${searched.children} child${searched.children === 1 ? "" : "ren"}` : ""}
            </h2>
            {available.map((r) => {
              const info = property.room_types.find((t) => t.id === r.room_type_id);
              return (
                <article key={r.room_type_id} aria-label={r.name} className="rounded-lg border border-line bg-white">
                  <div className="border-b border-line px-4 py-3 sm:px-5">
                    <h3 className="flex items-center gap-2 font-semibold text-forest">
                      <BedDouble className="size-4" aria-hidden />
                      {r.name}
                    </h3>
                    <p className="text-[13px] text-muted">
                      {[info?.bed_configuration, `Sleeps ${info?.max_occupancy}`].filter(Boolean).join(" · ")}
                      {r.available <= 2 ? ` · ${r.available === 1 ? "Last room" : "2 left"}` : ""}
                    </p>
                    {info?.description ? <p className="mt-1 text-sm">{info.description}</p> : null}
                  </div>
                  <ul className="divide-y divide-line">
                    {r.offers.map((o) => (
                      <li key={o.rate_plan_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
                        <div>
                          <p className="font-medium">{o.name}</p>
                          {(() => {
                            const meal = MEAL_PLAN_LABELS[o.meal_plan as MealPlan] ?? o.meal_plan;
                            const detail = [meal !== o.name ? meal : null, o.description].filter(Boolean).join(" · ");
                            return detail ? <p className="text-[13px] text-muted">{detail}</p> : null;
                          })()}
                        </div>
                        <div className="flex items-center gap-3">
                          <p className="text-right">
                            <span className="block font-mono font-semibold whitespace-nowrap text-forest">{money(o.total)}</span>
                            <span className="text-[12px] text-muted">{o.nights} night{o.nights === 1 ? "" : "s"}, taxes included</span>
                          </p>
                          <Button onClick={() => setChoice({ roomTypeId: r.room_type_id, roomType: r.name, ratePlanId: o.rate_plan_id, ratePlan: o.name, total: o.total })}>
                            Book
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </article>
              );
            })}
          </section>
        )
      ) : null}
    </div>
  );
}

function GuestDetails({
  base,
  property,
  search,
  choice,
  onBack,
  onBooked,
}: {
  base: string;
  property: PublicProperty;
  search: Search;
  choice: Choice;
  onBack: () => void;
  onBooked: (b: PublicBooking) => void;
}) {
  const key = useMemo(() => crypto.randomUUID(), []);
  const [form, setForm] = useState({ first: "", last: "", email: "", phone: "", requests: "", website: "" });
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.first.trim()) errs.first = "Enter your first name.";
    if (!form.last.trim()) errs.last = "Enter your last name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) errs.email = "Enter a valid email address; your confirmation goes there.";
    setFieldErrors(errs);
    if (Object.keys(errs).length) return setError("Please check the highlighted fields.");
    if (!accepted) return setError("Please read and accept the booking terms.");
    setBusy(true);
    setError(null);
    try {
      const b = await api<PublicBooking>(`${base}/bookings`, {
        method: "POST",
        body: {
          check_in: search.checkIn,
          check_out: search.checkOut,
          rooms: [{ room_type_id: choice.roomTypeId, rate_plan_id: choice.ratePlanId, adults: search.adults, children: search.children }],
          guest: { first_name: form.first.trim(), last_name: form.last.trim(), email: form.email.trim(), phone: form.phone.trim() || null },
          special_requests: form.requests.trim() || null,
          accept_terms: accepted,
          website: form.website,
          idempotency_key: key,
        },
      });
      onBooked(b);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete the booking. Check your connection and try again; you will not be booked twice.");
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_16rem]">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4 rounded-lg border border-line bg-white p-4 sm:p-5">
        <button type="button" onClick={onBack} className="inline-flex items-center gap-1 self-start text-sm text-teal underline-offset-2 hover:underline">
          <ArrowLeft className="size-4" aria-hidden />
          Change room or dates
        </button>
        <h2 className="text-lg font-semibold text-forest">Your details</h2>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="first" label="First name" error={fieldErrors.first}>
            <Input id="first" autoComplete="given-name" value={form.first} onChange={set("first")} maxLength={100} />
          </Field>
          <Field id="last" label="Last name" error={fieldErrors.last}>
            <Input id="last" autoComplete="family-name" value={form.last} onChange={set("last")} maxLength={100} />
          </Field>
        </div>
        <Field id="email" label="Email" error={fieldErrors.email}>
          <Input id="email" type="email" autoComplete="email" value={form.email} onChange={set("email")} maxLength={320} />
        </Field>
        <Field id="phone" label="Phone or WhatsApp (optional)">
          <Input id="phone" type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} maxLength={40} />
        </Field>
        <Field id="requests" label="Special requests (optional)" hint="Arrival time, dietary needs, anything we should know.">
          <textarea id="requests" rows={3} maxLength={1000} value={form.requests} onChange={set("requests")} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
        </Field>
        {/* Left empty by people; bots that fill every field are turned away. */}
        <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
          <label htmlFor="website">Website</label>
          <input id="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={set("website")} />
        </div>
        <div className="rounded-md border border-line bg-cloud p-3">
          <p className="text-sm font-medium text-forest">Booking terms</p>
          <p className="mt-1 max-h-40 overflow-y-auto text-[13px] whitespace-pre-line">{property.booking_terms}</p>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-forest" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
            I accept the booking terms
          </label>
        </div>
        <Button type="submit" size="lg" loading={busy}>
          {property.booking_mode === "instant" ? `Book now · ${formatMoney(choice.total, property.currency)}` : "Send booking request"}
        </Button>
        <p className="text-[12px] text-muted">
          {property.booking_mode === "instant" ? "Your booking is confirmed immediately. You pay at the property." : "We hold the room and confirm by email. You pay at the property."}
        </p>
      </form>
      <aside aria-label="Your stay" className="h-fit rounded-lg border border-line bg-white p-4 text-sm">
        <p className="font-semibold text-forest">{choice.roomType}</p>
        <p className="text-muted">{choice.ratePlan}</p>
        <p className="mt-3">{formatStayDate(search.checkIn, long)}<br />to {formatStayDate(search.checkOut, long)}</p>
        <p className="mt-1 text-muted">{search.adults} adult{search.adults === 1 ? "" : "s"}{search.children ? `, ${search.children} child${search.children === 1 ? "" : "ren"}` : ""}</p>
        <p className="mt-3 border-t border-line pt-3 font-mono text-base font-semibold text-forest">{formatMoney(choice.total, property.currency)}</p>
        <p className="text-[12px] text-muted">Taxes included</p>
      </aside>
    </div>
  );
}

function Confirmation({ booking, property }: { booking: PublicBooking; property: PublicProperty }) {
  const request = booking.status === "provisional";
  return (
    <section aria-label="Booking received" className="rounded-lg border border-line bg-white p-5 sm:p-6">
      <p className="flex items-center gap-2 text-sm font-medium text-success">
        {request ? <Clock className="size-4" aria-hidden /> : <CalendarCheck className="size-4" aria-hidden />}
        {request ? "Request received" : "Booking confirmed"}
      </p>
      <h2 className="mt-2 text-xl font-semibold text-forest">Thank you, {booking.guest_name}</h2>
      <p className="mt-1 text-sm">
        {request
          ? `${property.name} will confirm your booking by email to ${booking.email}. Your room is held until then.`
          : `Your booking is confirmed. A confirmation is on its way to ${booking.email}.`}
      </p>
      <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted">Reference</dt>
        <dd className="font-mono text-base font-semibold text-forest">{booking.reference}</dd>
        <dt className="text-muted">Stay</dt>
        <dd>{formatStayDate(booking.check_in, long)} to {formatStayDate(booking.check_out, long)} ({booking.nights} night{booking.nights === 1 ? "" : "s"})</dd>
        {booking.rooms.map((r, i) => (
          <div key={i} className="contents">
            <dt className="text-muted">Room</dt>
            <dd>{r.room_type} · {r.rate_plan}</dd>
          </div>
        ))}
        <dt className="text-muted">Total</dt>
        <dd className="font-mono font-semibold">{formatMoney(booking.total, booking.currency)}</dd>
      </dl>
      <p className="mt-5 text-[13px] text-muted">Keep your reference. To change or cancel, reply to the email{property.phone ? ` or call ${property.phone}` : ""}.</p>
    </section>
  );
}
