import Link from "next/link";
import { Wordmark } from "@/components/brand/wordmark";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 text-center">
      <Wordmark className="mb-8" />
      <h1 className="text-lg font-semibold text-forest">Page not found</h1>
      <p className="mt-1 text-sm text-muted">The page you opened does not exist or has moved.</p>
      <Link href="/" className="mt-6 text-sm font-medium text-teal underline underline-offset-2">
        Go to overview
      </Link>
    </main>
  );
}
