import type { Metadata } from "next";
import Link from "next/link";
import { Wordmark } from "@/components/brand/wordmark";
import { Alert } from "@/components/ui/alert";
import { apiGet, ServerApiError } from "@/lib/server/api";
import type { InvitationPreview } from "@/lib/types";
import { AcceptForm } from "./accept-form";

export const metadata: Metadata = { title: "Join your team" };

export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = await params;
  let preview: InvitationPreview | null = null;
  let problem: string | null = null;
  try {
    preview = await apiGet<InvitationPreview>(`/api/v1/invitations/token/${encodeURIComponent(token)}`);
  } catch (err) {
    problem = err instanceof ServerApiError ? err.message : "This invitation could not be loaded. Try again shortly.";
  }

  return (
    <main className="flex min-h-dvh flex-col items-center px-4 py-10 sm:py-16">
      <div className="w-full max-w-md">
        <Wordmark className="mb-10 block" />
        {preview ? (
          <>
            <h1 className="text-xl font-semibold text-forest">Join {preview.organisation_name}</h1>
            <p className="mt-1 text-sm text-muted">
              You have been invited as <strong className="font-medium text-charcoal">{preview.role_name}</strong>
              {preview.property_name ? ` at ${preview.property_name}` : ""}.
            </p>
            <AcceptForm token={token} preview={preview} />
          </>
        ) : (
          <>
            <h1 className="text-xl font-semibold text-forest">Invitation</h1>
            <Alert tone="error" className="mt-6">{problem}</Alert>
            <p className="mt-6 text-sm">
              <Link href="/sign-in" className="font-medium text-teal underline underline-offset-2">Go to sign in</Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}
