"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api-client";

export function SignOutButton({ variant = "secondary" }: { variant?: "secondary" | "ghost" }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Even if the request fails (e.g. session already expired), leave the app.
    }
    router.replace("/sign-in");
    router.refresh();
  }

  return (
    <Button variant={variant} size="sm" onClick={signOut} loading={busy}>
      {busy ? null : <LogOut aria-hidden />}
      Sign out
    </Button>
  );
}
