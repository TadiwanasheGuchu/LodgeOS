"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { Invoice } from "@/lib/types";

/** An invoice without a booking: a walk-in meal, a day visitor's activity. */
export function NewInvoice({ propertyId }: { propertyId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        Invoice without a booking
      </Button>
      {open ? (
        <Dialog open onOpenChange={setOpen}>
          <DialogContent title="New invoice" description="For a stay, open the booking and choose “Create invoice” instead.">
            <form method="post"
              noValidate
              className="flex flex-col gap-4"
              onSubmit={async (e) => {
                e.preventDefault();
                if (name.trim().length < 2) return setError("Say who the invoice is for.");
                setBusy(true);
                setError(null);
                try {
                  const inv = await api<Invoice>(`/api/v1/properties/${propertyId}/invoices`, { method: "POST", body: { bill_to_name: name.trim() } });
                  router.push(`/invoices/${inv.id}`);
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : "Could not create the invoice.");
                  setBusy(false);
                }
              }}
            >
              {error ? <Alert tone="error">{error}</Alert> : null}
              <Field id="new-bill-to" label="Bill to">
                <Input id="new-bill-to" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} placeholder="Name or company" />
              </Field>
              <div className="border-t border-line pt-4">
                <Button type="submit" loading={busy}>Start invoice</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}
