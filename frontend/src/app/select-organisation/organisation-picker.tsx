"use client";

import { Building2, Check, ChevronRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { api, ApiError } from "@/lib/api-client";
import { ROLE_LABELS, type Membership } from "@/lib/types";

export function OrganisationPicker({
  memberships,
  currentId,
}: {
  memberships: Membership[];
  currentId: string | null;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(id: string) {
    setPending(id);
    setError(null);
    try {
      await api("/api/v1/auth/active-organisation", { method: "POST", body: { organisation_id: id } });
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not switch organisation.");
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-white">
        {memberships.map((m) => (
          <li key={m.organisation_id}>
            <button
              type="button"
              onClick={() => choose(m.organisation_id)}
              disabled={pending !== null}
              className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-mist disabled:opacity-70"
            >
              <Building2 className="size-5 shrink-0 text-teal" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-forest">{m.organisation_name}</span>
                <span className="block text-[13px] text-muted">{ROLE_LABELS[m.role]}</span>
              </span>
              {pending === m.organisation_id ? (
                <Loader2 className="size-4 animate-spin text-muted" aria-label="Opening" />
              ) : m.organisation_id === currentId ? (
                <Check className="size-4 text-teal" aria-label="Current" />
              ) : (
                <ChevronRight className="size-4 text-muted" aria-hidden />
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
