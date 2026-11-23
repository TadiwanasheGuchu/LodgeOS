"use client";

import { ReceiptText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import type { Invoice } from "@/lib/types";

export function CreateInvoice({ reservationId, propertyId }: { reservationId: string; propertyId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="mt-3 flex flex-col gap-2">
      {error ? <Alert tone="info">{error}</Alert> : null}
      <Button
        variant="secondary"
        size="sm"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const inv = await api<Invoice>(`/api/v1/properties/${propertyId}/invoices`, { method: "POST", body: { reservation_id: reservationId } });
            router.push(`/invoices/${inv.id}`);
          } catch (err) {
            setError(err instanceof ApiError ? err.message : "Could not create the invoice.");
            setBusy(false);
          }
        }}
      >
        <ReceiptText aria-hidden />
        Create invoice
      </Button>
    </div>
  );
}
