"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import { describeAction, describeChanges } from "@/lib/audit";
import { formatDateTime } from "@/lib/format";
import type { AuditLogPage } from "@/lib/types";

export function ActivityList({ initial, timeZone }: { initial: AuditLogPage; timeZone: string }) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    setError(null);
    try {
      const page = await api<AuditLogPage>(
        `/api/v1/organisation/audit-logs?limit=50&cursor=${encodeURIComponent(cursor)}`,
      );
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load more activity.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    return <p className="rounded-lg border border-line bg-white px-5 py-8 text-center text-sm text-muted">No activity yet.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <ol className="divide-y divide-line rounded-lg border border-line bg-white">
        {items.map((entry) => {
          const changes = describeChanges(entry);
          return (
            <li key={entry.id} className="grid gap-1 px-4 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4 sm:px-5">
              <time dateTime={entry.created_at} className="tabular text-[13px] text-muted sm:pt-0.5">
                {formatDateTime(entry.created_at, timeZone)}
              </time>
              <div className="min-w-0 text-sm">
                <p>
                  <span className="font-medium text-forest">{entry.actor_name ?? "System"}</span>{" "}
                  <span className="text-charcoal">{describeAction(entry).toLowerCase()}</span>
                </p>
                {changes.length ? (
                  <ul className="mt-1 text-[13px] text-muted">
                    {changes.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {cursor ? (
        <Button variant="secondary" onClick={loadMore} loading={loading} className="self-start">
          Load older activity
        </Button>
      ) : null}
    </div>
  );
}
