"use client";

import { Check, Copy, Link2, MessageSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";

/** Create a private link for the guest and share it by copy or WhatsApp (ADR-0013). */
export function GuestLink({ reservationId, reference, propertyName, guestPhone }: { reservationId: string; reference: string; propertyName: string; guestPhone: string | null }) {
  const router = useRouter();
  const [url, setUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const text = url ? `Your booking ${reference} at ${propertyName}: ${url}` : "";
  const wa = url ? `https://wa.me/${guestPhone ? guestPhone.replace(/\D/g, "") : ""}?text=${encodeURIComponent(text)}` : "";

  async function create() {
    setBusy("create");
    setMessage(null);
    try {
      const r = await api<{ url: string }>(`/api/v1/reservations/${reservationId}/guest-links`, { method: "POST" });
      setUrl(r.url);
      setCopied(false);
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof ApiError ? err.message : "Could not create the link." });
    } finally {
      setBusy(null);
    }
  }

  async function revoke() {
    setBusy("revoke");
    setMessage(null);
    try {
      const r = await api<{ revoked: number }>(`/api/v1/reservations/${reservationId}/guest-links/revoke`, { method: "POST" });
      setUrl(null);
      setMessage({ tone: "success", text: r.revoked ? `Withdrew ${r.revoked} link${r.revoked === 1 ? "" : "s"}.` : "There were no active links." });
      router.refresh();
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof ApiError ? err.message : "Could not withdraw the links." });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
      {message ? <Alert tone={message.tone}>{message.text}</Alert> : null}
      {url ? (
        <>
          <p className="text-[13px] text-muted">Private link for the guest. Anyone with it can see this booking.</p>
          <code className="truncate rounded-md border border-line bg-cloud px-2 py-1.5 font-mono text-[12px]">{url}</code>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); }}>
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
              {copied ? "Copied" : "Copy message"}
            </Button>
            <Button asChild size="sm" variant="secondary">
              <a href={wa} target="_blank" rel="noopener">
                <MessageSquare aria-hidden />
                WhatsApp
              </a>
            </Button>
          </div>
        </>
      ) : (
        <Button size="sm" variant="secondary" loading={busy === "create"} onClick={create}>
          <Link2 aria-hidden />
          Share guest link
        </Button>
      )}
      <button type="button" disabled={busy !== null} onClick={revoke} className="self-start text-[12px] text-muted underline-offset-2 hover:text-danger hover:underline">
        Withdraw all guest links
      </button>
    </div>
  );
}
