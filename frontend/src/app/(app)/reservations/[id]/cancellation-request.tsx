"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api-client";

export function DismissCancellationRequest({ reservationId }: { reservationId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      size="sm"
      variant="ghost"
      loading={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await api(`/api/v1/reservations/${reservationId}/cancellation-request/dismiss`, { method: "POST" });
          router.refresh();
        } finally {
          setBusy(false);
        }
      }}
    >
      Keep the booking
    </Button>
  );
}
