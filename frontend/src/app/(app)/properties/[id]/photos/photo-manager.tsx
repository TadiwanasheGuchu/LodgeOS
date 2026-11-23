"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError, uploadImage } from "@/lib/api-client";
import type { MediaAsset } from "@/lib/types";

type Target = { kind: "logo" } | { kind: "property_photo" } | { kind: "room_type_photo"; roomTypeId: string };

function Thumb({ asset, canManage, onDelete, busy }: { asset: MediaAsset; canManage: boolean; onDelete: () => void; busy: boolean }) {
  return (
    <li className="w-40 overflow-hidden rounded-md border border-line bg-white">
      {/* eslint-disable-next-line @next/next/no-img-element -- small pre-sized thumbnail */}
      <img src={asset.urls.sm} alt={asset.alt_text ?? "Logo"} loading="lazy" className={asset.kind === "logo" ? "h-24 w-full bg-cloud object-contain p-2" : "h-24 w-full object-cover"} />
      <div className="flex items-start justify-between gap-1 px-2 py-1.5">
        <p className="line-clamp-2 text-[12px] text-charcoal">{asset.alt_text ?? "Logo"}</p>
        {canManage ? (
          <Button size="icon" variant="ghost" className="size-7 shrink-0" loading={busy} onClick={onDelete}>
            <Trash2 aria-hidden />
            <span className="sr-only">Delete {asset.alt_text ?? "logo"}</span>
          </Button>
        ) : null}
      </div>
    </li>
  );
}

function Uploader({ propertyId, target, label, needsAlt, onDone }: { propertyId: string; target: Target; label: string; needsAlt: boolean; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [alt, setAlt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = `upload-${target.kind}-${"roomTypeId" in target ? target.roomTypeId : "x"}`;

  async function send() {
    if (!file) return setError("Choose an image first.");
    if (file.size > 8 * 1024 * 1024) return setError("Images can be up to 8 MB.");
    if (needsAlt && alt.trim().length < 3) return setError("Describe the photo in a few words, for people who cannot see it.");
    setBusy(true);
    setError(null);
    const q = new URLSearchParams({ kind: target.kind, ...(needsAlt ? { alt_text: alt.trim() } : {}), ...("roomTypeId" in target ? { room_type_id: target.roomTypeId } : {}) });
    try {
      await uploadImage(`/api/v1/properties/${propertyId}/media?${q}`, file);
      setAlt("");
      setFile(null);
      if (input.current) input.current.value = "";
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload the image.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-control bg-cloud p-3">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="flex flex-wrap items-end gap-2">
        <Field id={id} label={label} hint="JPEG, PNG or WebP, up to 8 MB.">
          <input id={id} ref={input} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block text-sm file:mr-3 file:rounded-md file:border file:border-control file:bg-white file:px-3 file:py-1.5 file:text-sm file:text-forest" />
        </Field>
        {needsAlt ? (
          <div className="min-w-48 flex-1">
            <Field id={`${id}-alt`} label="Description">
              <Input id={`${id}-alt`} value={alt} maxLength={200} onChange={(e) => setAlt(e.target.value)} placeholder="Chalet deck facing the waterhole" />
            </Field>
          </div>
        ) : null}
        <Button size="sm" className="h-10" loading={busy} onClick={send}>
          <ImagePlus aria-hidden />
          Upload
        </Button>
      </div>
    </div>
  );
}

export function PhotoManager({ propertyId, media, roomTypes, canManage }: { propertyId: string; media: MediaAsset[]; roomTypes: { id: string; name: string }[]; canManage: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => router.refresh();
  const logo = media.find((m) => m.kind === "logo");
  const propertyPhotos = media.filter((m) => m.kind === "property_photo");

  async function remove(asset: MediaAsset) {
    setBusy(asset.id);
    setError(null);
    try {
      await api(`/api/v1/media/${asset.id}`, { method: "DELETE" });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the image.");
    } finally {
      setBusy(null);
    }
  }

  const section = "rounded-lg border border-line bg-white px-5 py-5 sm:px-6";
  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <p className="text-sm text-muted">Photos appear on your booking page. Phones load small versions, so pages stay quick on slow connections. Location and camera details are removed from every upload.</p>
      {error ? <Alert tone="error">{error}</Alert> : null}

      <section aria-label="Logo" className={section}>
        <h2 className="text-sm font-semibold text-forest">Logo</h2>
        <p className="mt-1 text-[13px] text-muted">Shown at the top of your booking page. A PNG with a transparent background works best.</p>
        {logo ? <ul className="mt-3 flex"><Thumb asset={logo} canManage={canManage} busy={busy === logo.id} onDelete={() => void remove(logo)} /></ul> : null}
        {canManage ? <div className="mt-3"><Uploader propertyId={propertyId} target={{ kind: "logo" }} label={logo ? "Replace logo" : "Logo image"} needsAlt={false} onDone={refresh} /></div> : null}
      </section>

      <section aria-label="Property photos" className={section}>
        <h2 className="text-sm font-semibold text-forest">Property photos</h2>
        <p className="mt-1 text-[13px] text-muted">The first photo is the large one at the top of the booking page.</p>
        {propertyPhotos.length ? (
          <ul className="mt-3 flex flex-wrap gap-3">
            {propertyPhotos.map((p) => <Thumb key={p.id} asset={p} canManage={canManage} busy={busy === p.id} onDelete={() => void remove(p)} />)}
          </ul>
        ) : <p className="mt-3 text-sm text-muted">No photos yet.</p>}
        {canManage ? <div className="mt-3"><Uploader propertyId={propertyId} target={{ kind: "property_photo" }} label="Add a photo" needsAlt onDone={refresh} /></div> : null}
      </section>

      {roomTypes.map((rt) => {
        const photos = media.filter((m) => m.room_type_id === rt.id);
        return (
          <section key={rt.id} aria-label={`${rt.name} photos`} className={section}>
            <h2 className="text-sm font-semibold text-forest">{rt.name}</h2>
            {photos.length ? (
              <ul className="mt-3 flex flex-wrap gap-3">
                {photos.map((p) => <Thumb key={p.id} asset={p} canManage={canManage} busy={busy === p.id} onDelete={() => void remove(p)} />)}
              </ul>
            ) : <p className="mt-2 text-sm text-muted">No photos of this room type yet.</p>}
            {canManage ? <div className="mt-3"><Uploader propertyId={propertyId} target={{ kind: "room_type_photo", roomTypeId: rt.id }} label="Add a photo" needsAlt onDone={refresh} /></div> : null}
          </section>
        );
      })}
    </div>
  );
}
