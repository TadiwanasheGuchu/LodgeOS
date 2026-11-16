import type { Metadata } from "next";
import { Wordmark } from "@/components/brand/wordmark";
import { Alert } from "@/components/ui/alert";
import { SignOutButton } from "@/components/shell/sign-out-button";
import { requireMe } from "@/lib/server/api";
import { OrganisationPicker } from "./organisation-picker";

export const metadata: Metadata = { title: "Choose an organisation" };

export default async function SelectOrganisationPage() {
  const me = await requireMe();

  return (
    <main className="flex min-h-dvh flex-col items-center px-4 py-10 sm:py-16">
      <div className="w-full max-w-md">
        <Wordmark className="mb-10 block" />
        <h1 className="text-xl font-semibold text-forest">Choose where to work</h1>
        <p className="mt-1 text-sm text-muted">
          Signed in as {me.user.full_name} ({me.user.email}).
        </p>

        <div className="mt-6">
          {me.memberships.length === 0 ? (
            <Alert tone="info">
              Your account is not active in any organisation. Ask the property owner to add you or to
              re-enable your access.
            </Alert>
          ) : (
            <OrganisationPicker
              memberships={me.memberships}
              currentId={me.active_organisation?.id ?? null}
            />
          )}
        </div>

        <div className="mt-8 border-t border-line pt-4">
          <SignOutButton variant="ghost" />
        </div>
      </div>
    </main>
  );
}
