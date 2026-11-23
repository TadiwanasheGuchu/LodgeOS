"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { Building } from "@/lib/types";

export function BuildingsManager({
  propertyId,
  buildings,
  canManage,
}: {
  propertyId: string;
  buildings: Building[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      router.refresh();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Enter a building name.");
    const ok = await run("add", () =>
      api(`/api/v1/properties/${propertyId}/buildings`, { method: "POST", body: { name: name.trim() } }),
    );
    if (ok) setName("");
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <p className="text-sm text-muted">
        Optional. Use buildings for wings, blocks or separate units, so room lists can be grouped the way staff walk the property.
      </p>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {buildings.length ? (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {buildings.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-3 px-5 py-3">
              <span className={b.status === "archived" ? "text-muted" : "font-medium text-forest"}>
                {b.name}
                {b.status === "archived" ? <span className="ml-2 text-[13px]">Archived</span> : null}
              </span>
              {canManage ? (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={busy === b.id}
                  onClick={() =>
                    run(b.id, () =>
                      api(`/api/v1/buildings/${b.id}`, {
                        method: "PATCH",
                        body: { status: b.status === "active" ? "archived" : "active" },
                      }),
                    )
                  }
                >
                  {b.status === "active" ? "Archive" : "Restore"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-line bg-white px-5 py-6 text-center text-sm text-muted">No buildings.</p>
      )}
      {canManage ? (
        <form method="post" onSubmit={add} noValidate className="flex items-end gap-2">
          <div className="flex-1">
            <Field id="building-name" label="New building">
              <Input id="building-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Garden Wing" />
            </Field>
          </div>
          <Button type="submit" loading={busy === "add"}>Add</Button>
        </form>
      ) : null}
    </div>
  );
}
