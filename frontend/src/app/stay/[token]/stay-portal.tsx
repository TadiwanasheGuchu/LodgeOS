"use client";

import { CalendarDays, Clock, Mail, MessageSquare, Phone } from "lucide-react";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatStayDate } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import type { PortalBooking } from "@/lib/types";

const STATUS: Record<string, string> = {
  provisional: "Request received: waiting for the property to confirm",
  confirmed: "Confirmed",
  checked_in: "Checked in. Enjoy your stay",
  checked_out: "Checked out. Thank you for staying",
  cancelled: "Cancelled",
  no_show: "Not arrived",
};
const long = { weekday: "long", day: "numeric", month: "long", year: "numeric" } as const;
const box = "rounded-lg border border-line bg-white px-4 py-4 sm:px-5";

export function StayPortal({ token, initial }: { token: string; initial: PortalBooking }) {
  const [b, setB] = useState(initial);
  const [arrival, setArrival] = useState(initial.arrival_time ?? "");
  const [message, setMessage] = useState(initial.message ?? "");
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const money = (a: string) => formatMoney(a, b.currency);
  const base = `/api/v1/stay/${encodeURIComponent(token)}`;
  const owed = b.invoices.reduce((n, i) => n + (i.balance !== "0.00" ? 1 : 0), 0);

  async function send(key: string, path: string, body: unknown, done: string) {
    setBusy(key);
    setNotice(null);
    try {
      setB(await api<PortalBooking>(`${base}/${path}`, { method: "POST", body }));
      setNotice({ tone: "success", text: done });
      setAsking(false);
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof ApiError ? err.message : "Could not send. Check your connection and try again." });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Booking" className={box}>
        <p className="text-sm text-muted">Booking for {b.guest_name}</p>
        <p className="font-mono text-xl font-semibold text-forest">{b.reference}</p>
        <p className={b.status === "cancelled" ? "mt-1 text-sm font-medium text-danger" : "mt-1 text-sm font-medium text-success"}>{STATUS[b.status] ?? b.status}</p>
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-5 gap-y-2 text-sm">
          <dt className="flex items-center gap-1.5 text-muted"><CalendarDays className="size-4" aria-hidden />Arrive</dt>
          <dd>{formatStayDate(b.check_in, long)}, from {b.property.check_in_time.slice(0, 5)}</dd>
          <dt className="flex items-center gap-1.5 text-muted"><CalendarDays className="size-4" aria-hidden />Leave</dt>
          <dd>{formatStayDate(b.check_out, long)}, by {b.property.check_out_time.slice(0, 5)}</dd>
          {b.rooms.map((r, i) => (
            <div key={i} className="contents">
              <dt className="text-muted">Room</dt>
              <dd>{r.room_type} · {r.rate_plan} · {r.adults} adult{r.adults === 1 ? "" : "s"}{r.children ? `, ${r.children} child${r.children === 1 ? "" : "ren"}` : ""}</dd>
            </div>
          ))}
          <dt className="text-muted">Total</dt>
          <dd className="font-mono font-semibold">{money(b.total)} <span className="font-sans text-[12px] font-normal text-muted">taxes included</span></dd>
          {b.paid !== "0.00" ? (<><dt className="text-muted">Paid</dt><dd className="font-mono">{money(b.paid)}</dd></>) : null}
        </dl>
      </section>

      {b.invoices.length > 0 ? (
        <section aria-label="Invoices" className={box}>
          <h2 className="text-sm font-semibold text-forest">Invoices</h2>
          <ul className="mt-2 divide-y divide-line text-sm">
            {b.invoices.map((i) => (
              <li key={i.number} className="flex flex-wrap justify-between gap-2 py-2">
                <span><span className="font-mono">{i.number}</span> · {formatStayDate(i.issue_date, { day: "numeric", month: "short", year: "numeric" })}</span>
                <span className="text-right">
                  <span className="block font-mono">{money(i.total)}</span>
                  <span className={i.balance === "0.00" ? "text-[12px] text-success" : "text-[12px] text-charcoal"}>{i.balance === "0.00" ? "Paid" : `${money(i.balance)} still due`}</span>
                </span>
              </li>
            ))}
          </ul>
          {owed > 0 ? <p className="mt-2 text-[13px] text-muted">Pay at the property, or ask them for banking details.</p> : null}
        </section>
      ) : null}

      {notice ? <Alert tone={notice.tone}>{notice.text}</Alert> : null}

      {b.can_update ? (
        <section aria-label="Your arrival" className={box}>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold text-forest"><Clock className="size-4" aria-hidden />Your arrival</h2>
          <form
            className="mt-3 flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void send("arrival", "arrival", { arrival_time: arrival || null, message: message.trim() || null }, "Thank you. The property has your details.");
            }}
          >
            <Field id="arrival-time" label="Expected arrival time">
              <Input id="arrival-time" type="time" value={arrival} onChange={(e) => setArrival(e.target.value)} className="w-40" />
            </Field>
            <Field id="guest-message" label="Message to the property (optional)" hint="Flight or transfer details, dietary needs, celebrations.">
              <textarea id="guest-message" rows={3} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
            </Field>
            <div><Button type="submit" loading={busy === "arrival"}>Send to the property</Button></div>
          </form>
        </section>
      ) : null}

      {b.cancellation_requested ? (
        <Alert tone="info">You asked to cancel ({b.cancellation_reason}). The property will reply by email.</Alert>
      ) : b.can_update && b.status !== "checked_in" ? (
        <section aria-label="Cancel" className={box}>
          {asking ? (
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (reason.trim().length < 3) return setNotice({ tone: "error", text: "Please give a short reason." });
                void send("cancel", "cancellation-request", { reason: reason.trim() }, "Your request was sent. The property will confirm by email.");
              }}
            >
              <p className="text-sm">The property decides under its booking terms{b.property.booking_terms ? " below" : ""}. Nothing is cancelled until they confirm.</p>
              <Field id="cancel-reason" label="Reason">
                <Input id="cancel-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
              </Field>
              <div className="flex gap-2">
                <Button type="submit" variant="danger" loading={busy === "cancel"}>Ask to cancel</Button>
                <Button type="button" variant="ghost" onClick={() => setAsking(false)}>Keep my booking</Button>
              </div>
            </form>
          ) : (
            <button type="button" className="text-sm text-teal underline-offset-2 hover:underline" onClick={() => setAsking(true)}>
              Need to cancel?
            </button>
          )}
        </section>
      ) : null}

      <section aria-label="Contact" className={`${box} text-sm`}>
        <h2 className="text-sm font-semibold text-forest">Contact {b.property.name}</h2>
        <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
          {b.property.phone ? <a href={`tel:${b.property.phone}`} className="flex items-center gap-1.5 text-teal"><Phone className="size-4" aria-hidden />{b.property.phone}</a> : null}
          {b.property.phone ? <a href={`https://wa.me/${b.property.phone.replace(/\D/g, "")}`} className="flex items-center gap-1.5 text-teal" rel="noopener"><MessageSquare className="size-4" aria-hidden />WhatsApp</a> : null}
          {b.property.email ? <a href={`mailto:${b.property.email}`} className="flex items-center gap-1.5 text-teal"><Mail className="size-4" aria-hidden />{b.property.email}</a> : null}
        </p>
        {b.property.booking_terms ? (
          <details className="mt-3">
            <summary className="cursor-pointer text-muted">Booking terms</summary>
            <p className="mt-2 whitespace-pre-line text-[13px]">{b.property.booking_terms}</p>
          </details>
        ) : null}
        <p className="mt-3 text-[12px] text-muted">This page is private to your booking. Do not share the link.</p>
      </section>
    </div>
  );
}
