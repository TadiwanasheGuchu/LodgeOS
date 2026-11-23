"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RecordPaymentDialog } from "@/components/payments/payment-dialogs";
import { Button } from "@/components/ui/button";

/** Money received without a booking or invoice yet, e.g. a day visitor; kept on account. */
export function WalkInPayment({ propertyId, currency, today }: { propertyId: string; currency: string; today: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        Record a payment
      </Button>
      {open ? (
        <RecordPaymentDialog
          propertyId={propertyId}
          currency={currency}
          suggested={null}
          askPayer
          title="Record a payment"
          description="For a booking or an invoice, record it there so it is applied automatically."
          today={today}
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false);
            router.refresh();
          }}
        />
      ) : null}
    </>
  );
}
