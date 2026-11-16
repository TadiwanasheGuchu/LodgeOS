import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Wordmark } from "@/components/brand/wordmark";
import { apiGet } from "@/lib/server/api";
import type { Me } from "@/lib/types";
import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default async function SignInPage() {
  // Already signed in: go straight to work.
  // If the API is unreachable, still show the form; submitting reports the problem.
  let signedIn = false;
  try {
    await apiGet<Me>("/api/v1/auth/me");
    signedIn = true;
  } catch {
    signedIn = false;
  }
  if (signedIn) redirect("/");

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <section
        aria-hidden
        className="hidden flex-col justify-between bg-forest px-12 py-10 text-white lg:flex"
      >
        <Wordmark tone="white" />
        <div className="max-w-sm">
          <p className="font-display text-3xl leading-tight">
            Reservations, rooms and accounts for your property, in one place.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-mist">
            Built for guesthouses and lodges in Namibia and Zimbabwe.
          </p>
        </div>
        <p className="text-xs text-sage">Hospitality, intelligently managed.</p>
      </section>

      <section className="flex flex-col justify-center px-4 py-10 sm:px-10">
        <div className="mx-auto w-full max-w-sm">
          <Wordmark className="mb-10 block lg:hidden" />
          <h1 className="text-xl font-semibold text-forest">Sign in</h1>
          <p className="mt-1 text-sm text-muted">Use the email address your property manager registered for you.</p>
          <SignInForm />
        </div>
      </section>
    </main>
  );
}
