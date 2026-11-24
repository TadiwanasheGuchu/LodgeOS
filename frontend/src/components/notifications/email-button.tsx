"use client";

import { Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";

/** Queue an email to a guest. The message goes to the outbox and is delivered in the background. */
export function EmailButton({
  url,
  label,
  title,
  description,
  variant = "secondary",
  size = "sm",
  className,
}: {
  url: string;
  label: string;
  title: string;
  description?: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
  className?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  return (
    <>
      <Button variant={variant} size={size} className={className} onClick={() => { setDone(false); setOpen(true); }}>
        <Mail aria-hidden />
        {label}
      </Button>
      {done ? <p role="status" className="text-[13px] text-success">Queued for sending.</p> : null}
      {open ? (
        <SendDialog
          url={url}
          title={title}
          description={description}
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false);
            setDone(true);
            router.refresh();
          }}
        />
      ) : null}
    </>
  );
}

function SendDialog({ url, title, description, onClose, onDone }: { url: string; title: string; description?: string; onClose: () => void; onDone: () => void }) {
  const key = useMemo(() => crypto.randomUUID(), []);
  const [to, setTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent title={title} description={description}>
        <form method="post"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            try {
              await api(url, { method: "POST", body: { to: to.trim() || null, idempotency_key: key } });
              onDone();
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Could not queue the email. Check your connection and try again.");
              setBusy(false);
            }
          }}
        >
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Field id="email-to" label="Send to" hint="Leave empty to use the guest's address on file.">
            <Input id="email-to" type="email" autoComplete="email" value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@example.com" />
          </Field>
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>Send email</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
