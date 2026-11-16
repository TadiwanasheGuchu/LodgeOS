"use client";

import { Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { parseRoomNumbers } from "@/lib/room-numbers";
import type { Building, Room, RoomType } from "@/lib/types";

export function RoomsManager({
  propertyId,
  rooms,
  roomTypes,
  buildings,
  canManage,
}: {
  propertyId: string;
  rooms: Room[];
  roomTypes: RoomType[];
  buildings: Building[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<"add" | Room | null>(null);
  const active = rooms.filter((r) => r.status === "active");
  const archived = rooms.filter((r) => r.status === "archived");
  const done = () => {
    setDialog(null);
    router.refresh();
  };

  if (roomTypes.length === 0) {
    return (
      <Alert tone="info">
        Add a room type before adding rooms.{" "}
        <Link href={`/properties/${propertyId}/room-types`} className="font-medium underline underline-offset-2">
          Go to room types
        </Link>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {active.length} active {active.length === 1 ? "room" : "rooms"}
          {archived.length ? `, ${archived.length} archived` : ""}.
        </p>
        {canManage ? (
          <Button onClick={() => setDialog("add")}>
            <Plus aria-hidden />
            Add rooms
          </Button>
        ) : null}
      </div>

      {rooms.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">No rooms yet.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line bg-cloud text-[13px] text-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-medium">Room</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Type</th>
                <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">Building</th>
                <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">Floor</th>
                {canManage ? <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th> : null}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {[...active, ...archived].map((r) => (
                <tr key={r.id} className={r.status === "archived" ? "text-muted" : undefined}>
                  <td className="tabular px-4 py-2.5 font-medium text-forest">
                    {r.number}
                    {r.status === "archived" ? <span className="ml-2 text-[12px] font-normal text-muted">Archived</span> : null}
                  </td>
                  <td className="px-4 py-2.5"><span className="font-mono text-[13px]">{r.room_type_code}</span></td>
                  <td className="hidden px-4 py-2.5 sm:table-cell">{r.building_name ?? "—"}</td>
                  <td className="hidden px-4 py-2.5 sm:table-cell">{r.floor ?? "—"}</td>
                  {canManage ? (
                    <td className="px-2 py-1 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setDialog(r)} aria-label={`Edit room ${r.number}`}>
                        <Pencil aria-hidden />
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog === "add" ? (
        <AddRoomsDialog propertyId={propertyId} roomTypes={roomTypes} buildings={buildings} onClose={() => setDialog(null)} onDone={done} />
      ) : dialog ? (
        <EditRoomDialog room={dialog} roomTypes={roomTypes} buildings={buildings} onClose={() => setDialog(null)} onDone={done} />
      ) : null}
    </div>
  );
}

function AddRoomsDialog({
  propertyId,
  roomTypes,
  buildings,
  onClose,
  onDone,
}: {
  propertyId: string;
  roomTypes: RoomType[];
  buildings: Building[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [numbersText, setNumbersText] = useState("");
  const [roomTypeId, setRoomTypeId] = useState(roomTypes[0]?.id ?? "");
  const [buildingId, setBuildingId] = useState("");
  const [floor, setFloor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const parsed = parseRoomNumbers(numbersText);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (parsed.error || parsed.numbers.length === 0) {
      setError(parsed.error ?? "Enter at least one room number.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/properties/${propertyId}/rooms/bulk`, {
        method: "POST",
        body: { numbers: parsed.numbers, room_type_id: roomTypeId, building_id: buildingId || null, floor: floor.trim() || null },
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the rooms.");
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title="Add rooms" description="Add several rooms of the same type at once.">
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Field
            id="room-numbers"
            label="Room numbers"
            hint={
              parsed.numbers.length && !parsed.error
                ? `${parsed.numbers.length} ${parsed.numbers.length === 1 ? "room" : "rooms"}: ${parsed.numbers.slice(0, 8).join(", ")}${parsed.numbers.length > 8 ? "…" : ""}`
                : "Separate with commas. Ranges work: 101-110, A1-A4, Tent 1"
            }
          >
            <Input
              id="room-numbers"
              aria-describedby="room-numbers-hint"
              value={numbersText}
              onChange={(e) => setNumbersText(e.target.value)}
              placeholder="101-110"
              autoComplete="off"
            />
          </Field>
          <Field id="room-type" label="Room type">
            <Select id="room-type" value={roomTypeId} onChange={(e) => setRoomTypeId(e.target.value)}>
              {roomTypes.map((t) => (
                <option key={t.id} value={t.id}>{t.code} · {t.name}</option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="room-building" label="Building">
              <Select id="room-building" value={buildingId} onChange={(e) => setBuildingId(e.target.value)}>
                <option value="">None</option>
                {buildings.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </Select>
            </Field>
            <Field id="room-floor" label="Floor (optional)">
              <Input id="room-floor" value={floor} onChange={(e) => setFloor(e.target.value)} maxLength={20} />
            </Field>
          </div>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>
              {parsed.numbers.length > 1 && !parsed.error ? `Add ${parsed.numbers.length} rooms` : "Add room"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditRoomDialog({
  room,
  roomTypes,
  buildings,
  onClose,
  onDone,
}: {
  room: Room;
  roomTypes: RoomType[];
  buildings: Building[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [number, setNumber] = useState(room.number);
  const [roomTypeId, setRoomTypeId] = useState(room.room_type_id);
  const [buildingId, setBuildingId] = useState(room.building_id ?? "");
  const [floor, setFloor] = useState(room.floor ?? "");
  const [notes, setNotes] = useState(room.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // An archived type is not in the list; keep the room's current one selectable.
  const typeOptions = roomTypes.some((t) => t.id === room.room_type_id)
    ? roomTypes
    : [{ id: room.room_type_id, code: room.room_type_code, name: room.room_type_name } as RoomType, ...roomTypes];

  async function patch(body: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/rooms/${room.id}`, { method: "PATCH", body });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the room.");
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const body: Record<string, unknown> = {};
    if (number.trim() !== room.number) body.number = number.trim();
    if (roomTypeId !== room.room_type_id) body.room_type_id = roomTypeId;
    if ((buildingId || null) !== room.building_id) body.building_id = buildingId || null;
    if ((floor.trim() || null) !== room.floor) body.floor = floor.trim() || null;
    if ((notes.trim() || null) !== room.notes) body.notes = notes.trim() || null;
    if (Object.keys(body).length === 0) return onClose();
    void patch(body);
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title={`Room ${room.number}`}>
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <div className="grid grid-cols-2 gap-3">
            <Field id="edit-number" label="Number">
              <Input id="edit-number" value={number} onChange={(e) => setNumber(e.target.value)} maxLength={20} />
            </Field>
            <Field id="edit-floor" label="Floor">
              <Input id="edit-floor" value={floor} onChange={(e) => setFloor(e.target.value)} maxLength={20} />
            </Field>
          </div>
          <Field id="edit-type" label="Room type">
            <Select id="edit-type" value={roomTypeId} onChange={(e) => setRoomTypeId(e.target.value)}>
              {typeOptions.map((t) => (
                <option key={t.id} value={t.id}>{t.code} · {t.name}</option>
              ))}
            </Select>
          </Field>
          <Field id="edit-building" label="Building">
            <Select id="edit-building" value={buildingId} onChange={(e) => setBuildingId(e.target.value)}>
              <option value="">None</option>
              {buildings.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </Select>
          </Field>
          <Field id="edit-notes" label="Notes for staff">
            <textarea id="edit-notes" rows={2} maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" />
          </Field>
          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            <Button type="submit" loading={busy}>Save</Button>
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => patch({ status: room.status === "active" ? "archived" : "active" })}
            >
              {room.status === "active" ? "Archive room" : "Restore room"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
