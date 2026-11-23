"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { addDays } from "@/lib/dates";
import type { ReservationDetail } from "@/lib/types";

type Action = "confirm" | "check-in" | "check-out" | "no-show" | "cancel";

/** The actions that fit the booking's status. The server checks every rule again. */
export function ReservationActions({ reservation, today }: { reservation: ReservationDetail; today: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<Action | "dates" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"cancel" | "dates" | null>(null);
  const [reason, setReason] = useState("");
  const [checkIn, setCheckIn] = useState(reservation.check_in);
  const [checkOut, setCheckOut] = useState(reservation.check_out);

  async function act(action: Action, body: Record<string, unknown> = {}) {
    setBusy(action);
    setError(null);
    try {
      await api(`/api/v1/reservations/${reservation.id}/${action}`, { method: "POST", body });
      setDialog(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the booking.");
    } finally {
      setBusy(null);
    }
  }

  async function changeDates(e: React.FormEvent) {
    e.preventDefault();
    if (checkOut <= checkIn) return setError("Departure must be after arrival.");
    setBusy("dates");
    setError(null);
    try {
      await api(`/api/v1/reservations/${reservation.id}/dates`, { method: "PATCH", body: { check_in: checkIn, check_out: checkOut } });
      setDialog(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the dates.");
    } finally {
      setBusy(null);
    }
  }

  const s = reservation.status;
  const arrived = today >= reservation.check_in;
  const open = s === "provisional" || s === "confirmed";
  if (!open && s !== "checked_in") return null;

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap justify-end gap-2">
        {s === "provisional" ? <Button onClick={() => act("confirm")} loading={busy === "confirm"}>Confirm booking</Button> : null}
        {s === "confirmed" && arrived ? <Button onClick={() => act("check-in")} loading={busy === "check-in"}>Check in</Button> : null}
        {s === "checked_in" ? <Button onClick={() => act("check-out")} loading={busy === "check-out"}>Check out</Button> : null}
        {open ? <Button variant="secondary" onClick={() => { setError(null); setDialog("dates"); }}>Change dates</Button> : null}
        {open && arrived ? <Button variant="secondary" onClick={() => act("no-show")} loading={busy === "no-show"}>Mark no-show</Button> : null}
        {open ? <Button variant="ghost" onClick={() => { setError(null); setDialog("cancel"); }}>Cancel booking</Button> : null}
      </div>
      {error && !dialog ? <Alert tone="error">{error}</Alert> : null}

      {dialog === "cancel" ? (
        <Dialog open onOpenChange={(o) => (o ? null : setDialog(null))}>
          <DialogContent title={`Cancel ${reservation.reference}`} description="The rooms become available again. The booking and its history are kept.">
            <form method="post"
              noValidate
              className="flex flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (reason.trim().length < 3) return setError("Give a reason for the cancellation.");
                void act("cancel", { reason: reason.trim() });
              }}
            >
              {error ? <Alert tone="error">{error}</Alert> : null}
              <Field id="cancel-reason" label="Reason">
                <textarea id="cancel-reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
              </Field>
              <div className="border-t border-line pt-4">
                <Button type="submit" variant="danger" loading={busy === "cancel"}>Cancel booking</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      ) : null}

      {dialog === "dates" ? (
        <Dialog open onOpenChange={(o) => (o ? null : setDialog(null))}>
          <DialogContent title={`Change dates of ${reservation.reference}`} description="Availability is checked again and the stay is priced at current rates.">
            <form method="post" noValidate className="flex flex-col gap-4" onSubmit={changeDates}>
              {error ? <Alert tone="error">{error}</Alert> : null}
              <div className="grid grid-cols-2 gap-3">
                <Field id="new-check-in" label="Arrival">
                  <Input id="new-check-in" type="date" value={checkIn} onChange={(e) => { setCheckIn(e.target.value); if (e.target.value >= checkOut) setCheckOut(addDays(e.target.value, 1)); }} />
                </Field>
                <Field id="new-check-out" label="Departure">
                  <Input id="new-check-out" type="date" value={checkOut} min={addDays(checkIn, 1)} onChange={(e) => setCheckOut(e.target.value)} />
                </Field>
              </div>
              <div className="border-t border-line pt-4">
                <Button type="submit" loading={busy === "dates"}>Change dates</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}
