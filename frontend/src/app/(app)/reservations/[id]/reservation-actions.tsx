"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { ReservationDetail } from "@/lib/types";

export function ReservationActions({ reservation }: { reservation: ReservationDetail }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");

  async function act(path: "confirm" | "cancel", body: Record<string, unknown> = {}) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/reservations/${reservation.id}/${path}`, { method: "POST", body });
      setCancelling(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the booking.");
    } finally {
      setBusy(false);
    }
  }

  const canCancel = reservation.status === "provisional" || reservation.status === "confirmed";
  if (!canCancel) return null;

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex gap-2">
        {reservation.status === "provisional" ? <Button onClick={() => act("confirm")} loading={busy && !cancelling}>Confirm booking</Button> : null}
        <Button variant="secondary" onClick={() => setCancelling(true)}>Cancel booking</Button>
      </div>
      {error && !cancelling ? <Alert tone="error">{error}</Alert> : null}
      {cancelling ? (
        <Dialog open onOpenChange={(o) => (o ? null : setCancelling(false))}>
          <DialogContent title={`Cancel ${reservation.reference}`} description="The rooms become available again. The booking and its history are kept.">
            <form
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
                <Button type="submit" variant="danger" loading={busy}>Cancel booking</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}
