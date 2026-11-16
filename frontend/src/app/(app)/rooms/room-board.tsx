"use client";

import { Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import { HOUSEKEEPING, HousekeepingChip, MaintenanceChip } from "@/components/rooms/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { HousekeepingStatus, MaintenanceStatus, Room } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | HousekeepingStatus | "attention";

const FILTERS: { id: Filter; label: string; match: (r: Room) => boolean }[] = [
  { id: "all", label: "All", match: () => true },
  { id: "dirty", label: "Dirty", match: (r) => r.housekeeping_status === "dirty" },
  { id: "clean", label: "Clean", match: (r) => r.housekeeping_status === "clean" },
  { id: "inspected", label: "Inspected", match: (r) => r.housekeeping_status === "inspected" },
  { id: "attention", label: "Maintenance", match: (r) => r.maintenance_status !== "none" },
];

const HK_ORDER: HousekeepingStatus[] = ["dirty", "clean", "inspected"];

function timeAt(iso: string | null, timeZone: string) {
  if (!iso) return null;
  return new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" }).format(
    new Date(iso),
  );
}

export function RoomBoard({
  rooms: initial,
  timeZone,
  canHousekeep,
  canMaintain,
}: {
  rooms: Room[];
  timeZone: string;
  canHousekeep: boolean;
  canMaintain: boolean;
}) {
  const [rooms, setRooms] = useState(initial);
  const [filter, setFilter] = useState<Filter>("all");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [issueRoom, setIssueRoom] = useState<Room | null>(null);

  const replace = (updated: Room) => setRooms((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));

  async function setHousekeeping(room: Room, status: HousekeepingStatus) {
    if (room.housekeeping_status === status) return;
    setPending(room.id);
    setError(null);
    try {
      replace(await api<Room>(`/api/v1/rooms/${room.id}/housekeeping`, { method: "POST", body: { housekeeping_status: status } }));
    } catch (err) {
      setError(err instanceof ApiError ? `Room ${room.number}: ${err.message}` : "Could not update the room.");
    } finally {
      setPending(null);
    }
  }

  const visible = rooms.filter(FILTERS.find((f) => f.id === filter)!.match);
  const groups = useMemo(() => {
    const map = new Map<string, Room[]>();
    for (const r of visible) {
      const key = r.building_name ?? "";
      map.set(key, [...(map.get(key) ?? []), r]);
    }
    return [...map.entries()];
  }, [visible]);

  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label="Filter rooms" className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => {
          const count = rooms.filter(f.match).length;
          return (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
              className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line bg-white px-3 text-sm text-forest hover:bg-mist aria-pressed:border-forest aria-pressed:bg-forest aria-pressed:text-white"
            >
              {f.label}
              <span className="tabular text-[13px] opacity-80">{count}</span>
            </button>
          );
        })}
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {visible.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">No rooms match this filter.</p>
      ) : (
        groups.map(([building, list]) => (
          <section key={building || "none"} aria-label={building || "Rooms"}>
            {building ? <h2 className="mb-2 text-[13px] font-semibold tracking-wide text-muted uppercase">{building}</h2> : null}
            <ul className="divide-y divide-line rounded-lg border border-line bg-white">
              {list.map((room) => (
                <li key={room.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <span className="tabular w-14 shrink-0 text-lg font-semibold text-forest">{room.number}</span>
                    <div className="min-w-0">
                      <p className="text-sm text-charcoal">
                        <span className="font-mono text-[13px]">{room.room_type_code}</span> · {room.room_type_name}
                        {room.floor ? <span className="text-muted"> · Floor {room.floor}</span> : null}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        {/* The segmented control already shows the status to people who can change it. */}
                        {canHousekeep ? null : <HousekeepingChip status={room.housekeeping_status} />}
                        <MaintenanceChip status={room.maintenance_status} />
                        {room.housekeeping_updated_at ? (
                          <span className="text-[12px] text-muted">updated {timeAt(room.housekeeping_updated_at, timeZone)}</span>
                        ) : null}
                      </div>
                      {room.maintenance_reason ? <p className="mt-1 text-[13px] text-muted">{room.maintenance_reason}</p> : null}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                    {canHousekeep ? (
                      <div role="group" aria-label={`Room ${room.number} cleaning status`} className="flex w-full rounded-md border border-control sm:inline-flex sm:w-auto">
                        {HK_ORDER.map((s) => (
                          <button
                            key={s}
                            type="button"
                            aria-pressed={room.housekeeping_status === s}
                            disabled={pending === room.id}
                            onClick={() => setHousekeeping(room, s)}
                            className={cn(
                              "h-11 flex-1 px-3 text-sm first:rounded-l-md last:rounded-r-md disabled:opacity-60 sm:h-10 sm:min-w-[4.75rem] sm:flex-none",
                              room.housekeeping_status === s ? "bg-forest font-medium text-white" : "bg-white text-forest hover:bg-mist",
                            )}
                          >
                            {HOUSEKEEPING[s].label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {canMaintain ? (
                      <Button variant="secondary" size="md" className="w-full sm:w-auto" onClick={() => setIssueRoom(room)} aria-label={`Maintenance for room ${room.number}`}>
                        <Wrench aria-hidden />
                        {room.maintenance_status === "none" ? "Report issue" : "Update"}
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}

      {issueRoom ? (
        <MaintenanceDialog
          room={issueRoom}
          onClose={() => setIssueRoom(null)}
          onSaved={(r) => {
            replace(r);
            setIssueRoom(null);
          }}
        />
      ) : null}
    </div>
  );
}

function MaintenanceDialog({ room, onClose, onSaved }: { room: Room; onClose: () => void; onSaved: (r: Room) => void }) {
  const [status, setStatus] = useState<Exclude<MaintenanceStatus, "none">>(
    room.maintenance_status === "none" ? "out_of_service" : room.maintenance_status,
  );
  const [reason, setReason] = useState(room.maintenance_reason ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(next: MaintenanceStatus) {
    if (next !== "none" && !reason.trim()) {
      setError("Describe the problem so the team knows what to fix.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onSaved(
        await api<Room>(`/api/v1/rooms/${room.id}/maintenance`, {
          method: "POST",
          body: { maintenance_status: next, reason: next === "none" ? null : reason.trim() },
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title={`Room ${room.number} maintenance`} description={`${room.room_type_name}`}>
        <div className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium text-forest">How serious is it?</legend>
            {(
              [
                ["out_of_service", "Out of service", "Minor problem. The room stays bookable but should not be given to guests until fixed."],
                ["out_of_order", "Out of order", "The room cannot be used. It is removed from sale until fixed."],
              ] as const
            ).map(([value, label, help]) => (
              <label
                key={value}
                className="flex cursor-pointer gap-3 rounded-md border border-line p-3 has-[:checked]:border-forest has-[:checked]:bg-mist"
              >
                <input
                  type="radio"
                  name="maintenance"
                  value={value}
                  checked={status === value}
                  onChange={() => setStatus(value)}
                  className="mt-1 accent-forest"
                />
                <span>
                  <span className="block text-sm font-medium text-forest">{label}</span>
                  <span className="block text-[13px] text-muted">{help}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <Field id="maintenance-reason" label="What is wrong?">
            <textarea
              id="maintenance-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              rows={3}
              className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]"
            />
          </Field>
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <Button onClick={() => save(status)} loading={busy}>
              Save
            </Button>
            {room.maintenance_status !== "none" ? (
              <Button variant="secondary" onClick={() => save("none")} disabled={busy}>
                Mark as fixed
              </Button>
            ) : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
