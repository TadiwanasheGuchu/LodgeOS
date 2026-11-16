"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import type { Property } from "@/lib/types";

export function ArchiveProperty({ property }: { property: Property }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const archived = property.status === "archived";

  async function setStatus(status: "active" | "archived") {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/properties/${property.id}`, { method: "PATCH", body: { status } });
      setConfirming(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the property.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="archive-heading" className="rounded-lg border border-line bg-white px-5 py-4 sm:px-6">
      <h2 id="archive-heading" className="text-sm font-semibold text-forest">
        {archived ? "Archived property" : "Archive property"}
      </h2>
      <p className="mt-1 text-sm text-muted">
        {archived
          ? "This property is hidden from lists and room status. Its records are kept."
          : "Hides the property from lists and room status. Nothing is deleted, and you can restore it later."}
      </p>
      {error ? <Alert tone="error" className="mt-3">{error}</Alert> : null}
      <div className="mt-3 flex gap-2">
        {archived ? (
          <Button variant="secondary" onClick={() => setStatus("active")} loading={busy}>Restore property</Button>
        ) : confirming ? (
          <>
            <Button variant="danger" onClick={() => setStatus("archived")} loading={busy}>Archive {property.name}</Button>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
          </>
        ) : (
          <Button variant="secondary" onClick={() => setConfirming(true)}>Archive…</Button>
        )}
      </div>
    </section>
  );
}
