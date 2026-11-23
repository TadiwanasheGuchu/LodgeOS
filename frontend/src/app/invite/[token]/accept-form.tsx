"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { InvitationPreview } from "@/lib/types";

const MIN_PASSWORD = 12;

export function AcceptForm({ token, preview }: { token: string; preview: InvitationPreview }) {
  const router = useRouter();
  const [name, setName] = useState(preview.full_name);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!preview.has_account) {
      if (name.trim().length < 2) return setError("Enter your name.");
      if (password.length < MIN_PASSWORD) return setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
      if (password !== confirm) return setError("The passwords do not match.");
    } else if (!password) {
      return setError("Enter your password.");
    }
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/invitations/accept", {
        method: "POST",
        body: { token, password, full_name: preview.has_account ? null : name.trim() },
      });
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not join. Please try again.");
      setBusy(false);
    }
  }

  return (
    <form method="post" onSubmit={submit} noValidate className="mt-8 flex flex-col gap-5">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Field id="accept-email" label="Email">
        <Input id="accept-email" value={preview.email} readOnly disabled />
      </Field>
      {preview.has_account ? (
        <>
          <Alert tone="info">You already have a LodgeOS account. Enter its password to add this organisation to it.</Alert>
          <Field id="accept-password" label="Password">
            <Input id="accept-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        </>
      ) : (
        <>
          <Field id="accept-name" label="Your name">
            <Input id="accept-name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field id="accept-password" label="Choose a password" hint={`At least ${MIN_PASSWORD} characters. A short sentence works well.`}>
            <Input
              id="accept-password"
              type="password"
              autoComplete="new-password"
              aria-describedby="accept-password-hint"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Field id="accept-confirm" label="Type it again">
            <Input id="accept-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
        </>
      )}
      <Button type="submit" size="lg" loading={busy} className="w-full">
        Join {preview.organisation_name}
      </Button>
    </form>
  );
}
