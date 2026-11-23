"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { FreeRoom } from "@/lib/types";

const HK: Record<string, string> = { dirty: "dirty", clean: "clean", inspected: "inspected" };

/** Pick, change or remove the physical room for one booked room. */
export function AssignRoom({ reservationRoomId, roomNumber, label }: { reservationRoomId: string; roomNumber: string | null; label: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [rooms, setRooms] = useState<FreeRoom[] | null>(null);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setOpen(true);
    setError(null);
    try {
      const free = await api<FreeRoom[]>(`/api/v1/reservation-rooms/${reservationRoomId}/free-rooms`);
      setRooms(free);
      setChoice(free[0]?.id ?? "");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load free rooms.");
    }
  }

  async function save(roomId: string | null) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/reservation-rooms/${reservationRoomId}/assign`, { method: "POST", body: { room_id: roomId } });
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not assign the room.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button variant={roomNumber ? "ghost" : "secondary"} size="sm" onClick={start} aria-label={`${roomNumber ? "Change" : "Assign"} room for ${label}`}>
        {roomNumber ? "Change room" : "Assign room"}
      </Button>
    );
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md bg-cloud p-2">
      {rooms === null && !error ? <span className="text-sm text-muted">Finding free rooms…</span> : null}
      {rooms && rooms.length === 0 ? <span className="text-sm text-danger">No room of this type is free for all these nights.</span> : null}
      {rooms && rooms.length ? (
        <>
          <label className="sr-only" htmlFor={`assign-${reservationRoomId}`}>Room for {label}</label>
          <Select id={`assign-${reservationRoomId}`} value={choice} onChange={(e) => setChoice(e.target.value)} className="h-9 w-auto">
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>
                Room {r.number}{r.building_name ? ` · ${r.building_name}` : ""} · {HK[r.housekeeping_status] ?? r.housekeeping_status}
              </option>
            ))}
          </Select>
          <Button size="sm" onClick={() => save(choice)} loading={busy}>Assign</Button>
        </>
      ) : null}
      {roomNumber ? <Button size="sm" variant="ghost" onClick={() => save(null)} disabled={busy}>Remove room</Button> : null}
      <Button size="sm" variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Close</Button>
      {error ? <span className="w-full text-sm text-danger" role="alert">{error}</span> : null}
    </div>
  );
}
