"use client";

import { CalendarOff, CircleAlert, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusChip } from "@/components/rooms/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { addDays, formatStayDate } from "@/lib/dates";
import type { MaintenanceTicket } from "@/lib/types";

const PRIORITY = {
  urgent: { label: "Urgent", className: "bg-danger-tint text-danger ring-danger/40", Icon: CircleAlert },
  normal: { label: "Normal", className: "bg-mist text-forest ring-teal/40", Icon: CircleAlert },
  low: { label: "Low", className: "bg-cloud text-muted ring-line", Icon: CircleAlert },
} as const;

const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function MaintenanceBoard({
  propertyId,
  tickets,
  rooms,
  canWork,
  currentUserId,
  today,
  showClosed,
}: {
  propertyId: string;
  tickets: MaintenanceTicket[];
  rooms: { id: string; number: string }[];
  canWork: boolean;
  currentUserId: string;
  today: string;
  showClosed: boolean;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<{ kind: "report" } | { kind: "resolve" | "block"; ticket: MaintenanceTicket } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const done = () => {
    setDialog(null);
    router.refresh();
  };

  async function update(ticket: MaintenanceTicket, body: Record<string, unknown>, key: string) {
    setBusy(key);
    setError(null);
    try {
      await api(`/api/v1/maintenance/tickets/${ticket.id}`, { method: "PATCH", body });
      router.refresh();
    } catch (err) {
      setError(errorText(err, "Could not update the ticket."));
    } finally {
      setBusy(null);
    }
  }

  async function release(blockId: string) {
    setBusy(blockId);
    setError(null);
    try {
      await api(`/api/v1/room-blocks/${blockId}/release`, { method: "POST" });
      router.refresh();
    } catch (err) {
      setError(errorText(err, "Could not release the room."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {!showClosed ? (
        <div>
          <Button onClick={() => setDialog({ kind: "report" })}>
            <Plus aria-hidden />
            Report a problem
          </Button>
        </div>
      ) : null}
      {error ? <Alert tone="error">{error}</Alert> : null}

      {tickets.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">
          {showClosed ? "No closed tickets." : "Nothing reported. All good."}
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {tickets.map((t) => {
            const activeBlocks = t.blocks.filter((b) => b.status === "active");
            return (
              <li key={t.id} className="flex flex-col gap-2 px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-forest">{t.title}</p>
                    <p className="text-sm text-muted">
                      {t.room_number ? `Room ${t.room_number}` : t.location} · reported by {t.reported_by_name}
                      {t.assigned_to_name ? ` · with ${t.assigned_to_name}` : ""}
                      {t.status === "in_progress" ? " · in progress" : ""}
                    </p>
                  </div>
                  <StatusChip {...PRIORITY[t.priority]} />
                </div>
                {t.description ? <p className="text-sm whitespace-pre-wrap">{t.description}</p> : null}
                {t.resolution ? <p className="text-sm text-success">Done: {t.resolution}</p> : null}
                {activeBlocks.map((b) => (
                  <p key={b.id} className="flex flex-wrap items-center gap-2 rounded-md bg-warning-tint px-3 py-1.5 text-[13px] text-charcoal">
                    <CalendarOff className="size-3.5" aria-hidden />
                    Out of sale {formatStayDate(b.start_date)} to {formatStayDate(addDays(b.end_date, -1))} (back {formatStayDate(b.end_date)})
                    {canWork ? (
                      <Button variant="ghost" size="sm" className="ml-auto h-7" loading={busy === b.id} onClick={() => release(b.id)}>
                        Release now
                      </Button>
                    ) : null}
                  </p>
                ))}
                {canWork && !showClosed ? (
                  <div className="flex flex-wrap gap-2">
                    {t.status === "open" ? (
                      <Button size="sm" variant="secondary" loading={busy === `start-${t.id}`} onClick={() => update(t, { status: "in_progress", assigned_to: t.assigned_to ?? currentUserId }, `start-${t.id}`)}>
                        Start work
                      </Button>
                    ) : null}
                    {t.assigned_to !== currentUserId ? (
                      <Button size="sm" variant="ghost" loading={busy === `take-${t.id}`} onClick={() => update(t, { assigned_to: currentUserId }, `take-${t.id}`)}>
                        Assign to me
                      </Button>
                    ) : null}
                    {t.room_id ? (
                      <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: "block", ticket: t })}>
                        Take room out of sale
                      </Button>
                    ) : null}
                    <Button size="sm" onClick={() => setDialog({ kind: "resolve", ticket: t })}>Mark as fixed</Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {dialog?.kind === "report" ? <ReportDialog propertyId={propertyId} rooms={rooms} onClose={() => setDialog(null)} onDone={done} /> : null}
      {dialog?.kind === "resolve" ? <ResolveDialog ticket={dialog.ticket} onClose={() => setDialog(null)} onDone={done} /> : null}
      {dialog?.kind === "block" ? <BlockDialog ticket={dialog.ticket} today={today} onClose={() => setDialog(null)} onDone={done} /> : null}
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
      setError(errorText(err, fallback));
      setBusy(false);
    }
  }
  return { error, setError, busy, run };
}

function ReportDialog({ propertyId, rooms, onClose, onDone }: { propertyId: string; rooms: { id: string; number: string }[]; onClose: () => void; onDone: () => void }) {
  const [roomId, setRoomId] = useState(rooms[0]?.id ?? "");
  const [location, setLocation] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("normal");
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title="Report a problem" description="The maintenance team sees it straight away.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim().length < 3) return s.setError("Describe the problem in a few words.");
            if (!roomId && !location.trim()) return s.setError("Choose a room or name the area.");
            void s.run(
              () =>
                api(`/api/v1/properties/${propertyId}/maintenance/tickets`, {
                  method: "POST",
                  body: { room_id: roomId || null, location: roomId ? null : location.trim(), title: title.trim(), description: description.trim() || null, priority },
                }),
              "Could not report the problem.",
            );
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="report-room" label="Where">
              <Select id="report-room" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>Room {r.number}</option>
                ))}
                <option value="">Another area</option>
              </Select>
            </Field>
            {roomId ? null : (
              <Field id="report-location" label="Area">
                <Input id="report-location" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Kitchen, pool, generator" maxLength={100} />
              </Field>
            )}
          </div>
          <Field id="report-title" label="What is wrong?">
            <Input id="report-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Shower drain blocked" />
          </Field>
          <Field id="report-details" label="Details (optional)">
            <textarea id="report-details" rows={3} maxLength={4000} value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
          </Field>
          <fieldset className="flex flex-wrap gap-2">
            <legend className="mb-1 text-sm font-medium text-forest">How urgent?</legend>
            {(["low", "normal", "urgent"] as const).map((p) => (
              <label key={p} className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
                <input type="radio" name="priority" value={p} checked={priority === p} onChange={() => setPriority(p)} className="accent-forest" />
                {PRIORITY[p].label}
              </label>
            ))}
          </fieldset>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Report problem</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResolveDialog({ ticket, onClose, onDone }: { ticket: MaintenanceTicket; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState("");
  const s = useSubmit(onDone);
  const blocked = ticket.blocks.some((b) => b.status === "active");
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={`Fixed: ${ticket.title}`} description={blocked ? "The room goes back on sale straight away." : undefined}>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (note.trim().length < 3) return s.setError("Say briefly what was done.");
            void s.run(() => api(`/api/v1/maintenance/tickets/${ticket.id}`, { method: "PATCH", body: { status: "resolved", resolution: note.trim() } }), "Could not close the ticket.");
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <Field id="resolve-note" label="What was done?">
            <textarea id="resolve-note" rows={3} maxLength={4000} value={note} onChange={(e) => setNote(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Mark as fixed</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function BlockDialog({ ticket, today, onClose, onDone }: { ticket: MaintenanceTicket; today: string; onClose: () => void; onDone: () => void }) {
  const [from, setFrom] = useState(today);
  const [back, setBack] = useState(addDays(today, 1));
  const s = useSubmit(onDone);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={`Take room ${ticket.room_number} out of sale`} description="No bookings can use it on these nights. Refused if guests are in the room or it would leave too few rooms.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (back <= from) return s.setError("The room must come back after it goes out.");
            void s.run(() => api(`/api/v1/maintenance/tickets/${ticket.id}/blocks`, { method: "POST", body: { start_date: from, end_date: back } }), "Could not take the room out of sale.");
          }}
        >
          {s.error ? <Alert tone="error">{s.error}</Alert> : null}
          <div className="grid grid-cols-2 gap-3">
            <Field id="block-from" label="First night out">
              <Input id="block-from" type="date" value={from} onChange={(e) => { setFrom(e.target.value); if (e.target.value >= back) setBack(addDays(e.target.value, 1)); }} />
            </Field>
            <Field id="block-back" label="Back on sale">
              <Input id="block-back" type="date" value={back} min={addDays(from, 1)} onChange={(e) => setBack(e.target.value)} />
            </Field>
          </div>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={s.busy}>Take out of sale</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
