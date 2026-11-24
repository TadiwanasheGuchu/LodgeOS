"use client";

import { Check, DoorOpen, Play, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { HousekeepingChip } from "@/components/rooms/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { HousekeepingBoard, HousekeepingRoom } from "@/lib/types";
import { cn } from "@/lib/utils";

type Step = { action: "assign"; assigned_to: string | null } | { action: "start" | "done" | "reopen" } | { action: "decline"; note: string };

/** What the room needs, in the words a housekeeper uses, and how soon. */
function describe(r: HousekeepingRoom): { title: string; detail: string | null; rank: number; waiting?: boolean } {
  const people = r.guests === 1 ? "1 guest" : `${r.guests} guests`;
  switch (r.kind) {
    case "departure":
      if (!r.guest_left) return { title: "Departure clean", detail: r.arriving ? "Guest not checked out yet · new guest arriving" : "Guest not checked out yet", rank: 3, waiting: true };
      return { title: "Departure clean", detail: r.arriving ? "Guest left · new guest arriving today" : "Guest left", rank: r.arriving ? 0 : 2 };
    case "arrival":
      return { title: "Prepare for arrival", detail: `Arriving today · ${people}`, rank: 1 };
    case "stayover":
      return { title: "Stay-over service", detail: people, rank: 4 };
    case "vacant":
      return { title: "Vacant, needs cleaning", detail: null, rank: 5 };
    default:
      return { title: "", detail: null, rank: 9 };
  }
}

const finished = (r: HousekeepingRoom) => r.task?.status === "done" || r.task?.status === "declined";

export function DayList({
  propertyId,
  timezone,
  board,
  canWork,
  currentUserId,
}: {
  propertyId: string;
  timezone: string;
  board: HousekeepingBoard;
  canWork: boolean;
  currentUserId: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mineOnly, setMineOnly] = useState(false);
  const [declining, setDeclining] = useState<HousekeepingRoom | null>(null);
  const isToday = board.date === board.today;
  const time = (iso: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: timezone }).format(new Date(iso));

  async function step(room: HousekeepingRoom, body: Step) {
    setBusy(`${room.room_id}-${body.action}`);
    setError(null);
    try {
      await api(`/api/v1/properties/${propertyId}/housekeeping/${board.date}/rooms/${room.room_id}`, { method: "POST", body });
      router.refresh();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save. Check your connection and try again.");
      return false;
    } finally {
      setBusy(null);
    }
  }

  const work = board.rooms.filter((r) => r.kind !== null);
  const idle = board.rooms.filter((r) => r.kind === null);
  const visible = work
    .filter((r) => !mineOnly || r.task?.assigned_to === currentUserId)
    .sort((a, b) => Number(finished(a)) - Number(finished(b)) || describe(a).rank - describe(b).rank || a.number.localeCompare(b.number, undefined, { numeric: true }));
  const done = work.filter(finished).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="text-sm text-charcoal" aria-live="polite">
          <span className="font-semibold text-forest">{done} of {work.length}</span> rooms finished
        </p>
        <div className="h-2 w-32 overflow-hidden rounded-full bg-mist" aria-hidden>
          <div className="h-full bg-teal" style={{ width: `${work.length ? (done / work.length) * 100 : 0}%` }} />
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm text-charcoal">
          <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} className="size-4 accent-forest" />
          Only my rooms
        </label>
      </div>
      {!isToday ? <Alert tone="info">Planning ahead: rooms can be assigned now and worked on the day.</Alert> : null}
      {error ? <Alert tone="error">{error}</Alert> : null}

      {visible.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">
          {mineOnly ? "No rooms assigned to you." : "No rooms need housekeeping."}
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white" aria-label="Rooms to do">
          {visible.map((r) => {
            const d = describe(r);
            const t = r.task;
            const key = (a: string) => busy === `${r.room_id}-${a}`;
            return (
              <li key={r.room_id} aria-label={`Room ${r.number}`} className={cn("flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:px-5", finished(r) && "bg-cloud")}>
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="w-14 shrink-0">
                    <p className="text-lg leading-tight font-semibold text-forest">{r.number}</p>
                    <p className="text-[11px] text-muted">{r.room_type_code}{r.floor ? ` · fl ${r.floor}` : ""}</p>
                  </div>
                  <div className="min-w-0">
                    <p className={cn("font-medium", finished(r) ? "text-muted" : "text-charcoal")}>{d.title}</p>
                    {d.detail ? (
                      <p className={cn("text-[13px]", d.waiting ? "mt-0.5 inline-flex items-center gap-1 rounded-sm bg-warning-tint px-1.5 py-0.5 text-charcoal" : d.rank === 0 ? "font-medium text-teal" : "text-muted")}>
                        {d.waiting ? <DoorOpen className="size-3.5" aria-hidden /> : null}
                        {d.detail}
                      </p>
                    ) : null}
                    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted">
                      <HousekeepingChip status={r.housekeeping_status} />
                      {r.maintenance_status !== "none" || r.blocked ? <span className="text-danger">Maintenance issue</span> : null}
                      {t?.status === "in_progress" ? <span className="font-medium text-teal">In progress</span> : null}
                      {t?.assigned_to_name && !finished(r) ? <span>{t.assigned_to === currentUserId ? "Yours" : t.assigned_to_name}</span> : null}
                      {t?.status === "done" && t.completed_at ? <span>Done by {t.completed_by_name} at {time(t.completed_at)}</span> : null}
                      {t?.status === "declined" ? <span>Service declined: {t.note}</span> : null}
                      {t?.status !== "declined" && t?.note ? <span>Note: {t.note}</span> : null}
                    </p>
                  </div>
                </div>
                {canWork ? (
                  <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                    {!isToday ? (
                      <div className="w-full sm:w-48">
                        <label htmlFor={`assign-${r.room_id}`} className="sr-only">Assign room {r.number}</label>
                        <Select
                          id={`assign-${r.room_id}`}
                          value={t?.assigned_to ?? ""}
                          disabled={busy !== null}
                          onChange={(e) => void step(r, { action: "assign", assigned_to: e.target.value || null })}
                        >
                          <option value="">Not assigned</option>
                          {board.assignees.map((a) => (
                            <option key={a.user_id} value={a.user_id}>{a.name}</option>
                          ))}
                        </Select>
                      </div>
                    ) : finished(r) ? (
                      <Button size="sm" variant="ghost" loading={key("reopen")} onClick={() => void step(r, { action: "reopen" })}>
                        <RotateCcw aria-hidden />
                        Reopen
                      </Button>
                    ) : (
                      <>
                        {r.kind === "stayover" ? (
                          <Button size="sm" variant="ghost" onClick={() => setDeclining(r)}>Declined</Button>
                        ) : null}
                        {t?.status !== "in_progress" ? (
                          <Button size="sm" variant="secondary" disabled={d.waiting} loading={key("start")} onClick={() => void step(r, { action: "start" })}>
                            <Play aria-hidden />
                            Start
                          </Button>
                        ) : null}
                        <Button size="sm" disabled={d.waiting} loading={key("done")} onClick={() => void step(r, { action: "done" })}>
                          <Check aria-hidden />
                          Done
                        </Button>
                      </>
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {idle.length > 0 && !mineOnly ? (
        <p className="text-[13px] text-muted">
          Nothing needed: {idle.length === 1 ? "room" : "rooms"} {idle.map((r) => r.number).join(", ")}.
        </p>
      ) : null}

      {declining ? (
        <DeclineDialog
          room={declining}
          onClose={() => setDeclining(null)}
          onSave={async (note) => {
            if (await step(declining, { action: "decline", note })) setDeclining(null);
          }}
        />
      ) : null}
    </div>
  );
}

function DeclineDialog({ room, onClose, onSave }: { room: HousekeepingRoom; onClose: () => void; onSave: (note: string) => Promise<void> }) {
  const [note, setNote] = useState("Do not disturb sign");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={`Room ${room.number}: service declined`} description="The room stays on today's record as not serviced.">
        <form method="post"
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!note.trim()) return;
            setBusy(true);
            await onSave(note.trim());
            setBusy(false);
          }}
        >
          <Field id="decline-note" label="Reason">
            <Input id="decline-note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} list="decline-reasons" />
            <datalist id="decline-reasons">
              <option value="Do not disturb sign" />
              <option value="Guest declined service" />
              <option value="Guest asked for later" />
            </datalist>
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy} disabled={!note.trim()}>Save</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
