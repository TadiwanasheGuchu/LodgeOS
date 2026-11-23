"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { describedBy, Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { RoomType } from "@/lib/types";

const count = (label: string, min: number) =>
  z.coerce.number({ message: `Enter ${label}.` }).int().min(min, `Must be at least ${min}.`).max(50, "Must be 50 or fewer.");

const schema = z
  .object({
    name: z.string().trim().min(2, "Enter at least 2 characters.").max(100),
    code: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z0-9][A-Z0-9-]{0,9}$/, "Up to 10 letters, digits or dashes, e.g. DBL."),
    bed_configuration: z.string().trim().max(200),
    description: z.string().trim().max(2000),
    base_occupancy: count("a number", 1),
    max_occupancy: count("a number", 1),
    max_adults: count("a number", 1),
    max_children: count("a number", 0),
  })
  .superRefine((v, ctx) => {
    if (v.max_occupancy < v.base_occupancy)
      ctx.addIssue({ code: "custom", path: ["max_occupancy"], message: "Must be at least the guests included in the rate." });
    if (v.max_adults > v.max_occupancy)
      ctx.addIssue({ code: "custom", path: ["max_adults"], message: "Cannot exceed maximum guests." });
    if (v.max_children > v.max_occupancy)
      ctx.addIssue({ code: "custom", path: ["max_children"], message: "Cannot exceed maximum guests." });
  });
type Input = z.input<typeof schema>;
type Values = z.output<typeof schema>;

export function RoomTypesManager({
  propertyId,
  initial,
  canManage,
}: {
  propertyId: string;
  initial: RoomType[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState<RoomType | "new" | null>(null);
  const active = initial.filter((t) => t.status === "active");
  const archived = initial.filter((t) => t.status === "archived");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Room types are what guests book. Each physical room belongs to one type.
        </p>
        {canManage ? (
          <Button onClick={() => setEditing("new")}>
            <Plus aria-hidden />
            Add room type
          </Button>
        ) : null}
      </div>

      {active.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">No room types yet.</p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {[...active, ...archived].map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3.5">
              <span className="font-mono w-14 text-[13px] text-forest">{t.code}</span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-forest">
                  {t.name}
                  {t.status === "archived" ? <span className="ml-2 text-[13px] font-normal text-muted">Archived</span> : null}
                </span>
                <span className="block text-sm text-muted">
                  {t.bed_configuration ? `${t.bed_configuration} · ` : ""}
                  {t.base_occupancy} included, up to {t.max_occupancy} guests
                  {t.max_children ? ` (max ${t.max_children} children)` : ""}
                </span>
              </span>
              <span className="tabular text-sm">
                {t.room_count} {t.room_count === 1 ? "room" : "rooms"}
              </span>
              {canManage ? (
                <Button variant="ghost" size="sm" onClick={() => setEditing(t)} aria-label={`Edit ${t.name}`}>
                  <Pencil aria-hidden />
                  Edit
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {editing ? (
        <RoomTypeDialog
          propertyId={propertyId}
          roomType={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

function RoomTypeDialog({
  propertyId,
  roomType,
  onClose,
  onSaved,
}: {
  propertyId: string;
  roomType: RoomType | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Input, unknown, Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: roomType?.name ?? "",
      code: roomType?.code ?? "",
      bed_configuration: roomType?.bed_configuration ?? "",
      description: roomType?.description ?? "",
      base_occupancy: roomType?.base_occupancy ?? 2,
      max_occupancy: roomType?.max_occupancy ?? 2,
      max_adults: roomType?.max_adults ?? 2,
      max_children: roomType?.max_children ?? 0,
    },
  });

  async function onSubmit(values: Values) {
    setError(null);
    const body = { ...values, bed_configuration: values.bed_configuration || null, description: values.description || null };
    try {
      if (roomType) await api(`/api/v1/room-types/${roomType.id}`, { method: "PATCH", body });
      else await api(`/api/v1/properties/${propertyId}/room-types`, { method: "POST", body });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    }
  }

  async function toggleArchive() {
    if (!roomType) return;
    setArchiving(true);
    setError(null);
    try {
      await api(`/api/v1/room-types/${roomType.id}`, {
        method: "PATCH",
        body: { status: roomType.status === "active" ? "archived" : "active" },
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the room type.");
      setArchiving(false);
    }
  }

  const err = (k: keyof Input) => errors[k]?.message;

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title={roomType ? `Edit ${roomType.name}` : "Add room type"}>
        <form method="post" onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
            <Field id="rt-name" label="Name" error={err("name")}>
              <Input placeholder="Double Room" {...describedBy("rt-name", err("name"))} {...register("name")} />
            </Field>
            <Field id="rt-code" label="Code" error={err("code")}>
              <Input className="font-mono uppercase" placeholder="DBL" {...describedBy("rt-code", err("code"))} {...register("code")} />
            </Field>
          </div>
          <Field id="rt-beds" label="Beds (optional)" error={err("bed_configuration")}>
            <Input placeholder="1 queen bed" {...describedBy("rt-beds", err("bed_configuration"))} {...register("bed_configuration")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="rt-base" label="Guests in base rate" error={err("base_occupancy")}>
              <Input type="number" inputMode="numeric" min={1} {...describedBy("rt-base", err("base_occupancy"))} {...register("base_occupancy")} />
            </Field>
            <Field id="rt-max" label="Maximum guests" error={err("max_occupancy")}>
              <Input type="number" inputMode="numeric" min={1} {...describedBy("rt-max", err("max_occupancy"))} {...register("max_occupancy")} />
            </Field>
            <Field id="rt-adults" label="Maximum adults" error={err("max_adults")}>
              <Input type="number" inputMode="numeric" min={1} {...describedBy("rt-adults", err("max_adults"))} {...register("max_adults")} />
            </Field>
            <Field id="rt-children" label="Maximum children" error={err("max_children")}>
              <Input type="number" inputMode="numeric" min={0} {...describedBy("rt-children", err("max_children"))} {...register("max_children")} />
            </Field>
          </div>
          <Field id="rt-desc" label="Description (optional)" error={err("description")}>
            <textarea id="rt-desc" rows={2} className="w-full rounded-md border border-control bg-white px-3 py-2 text-[15px]" {...register("description")} />
          </Field>
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <Button type="submit" loading={isSubmitting}>{roomType ? "Save changes" : "Add room type"}</Button>
            {roomType ? (
              <Button type="button" variant="ghost" onClick={toggleArchive} loading={archiving}>
                {roomType.status === "active" ? "Archive" : "Restore"}
              </Button>
            ) : null}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
