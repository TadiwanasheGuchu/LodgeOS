import type { Metadata } from "next";
import { apiGet, ServerApiError } from "@/lib/server/api";
import type { PortalBooking } from "@/lib/types";
import { StayPortal } from "./stay-portal";

export const metadata: Metadata = {
  title: "Your booking",
  // A private link: keep it out of search engines and referrer headers.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function StayPage({ params }: PageProps<"/stay/[token]">) {
  const { token } = await params;
  let booking: PortalBooking | null = null;
  let problem: string | null = null;
  try {
    booking = await apiGet<PortalBooking>(`/api/v1/stay/${encodeURIComponent(token)}`);
  } catch (err) {
    if (err instanceof ServerApiError && err.status < 500) problem = err.message;
    else throw err;
  }
  return (
    <div className="min-h-dvh bg-cloud">
      <header className="bg-forest text-white">
        <div className="mx-auto max-w-2xl px-4 py-6">
          <p className="font-display text-2xl">{booking?.property.name ?? "Your booking"}</p>
          {booking?.property.address.length ? <p className="mt-1 text-sm text-mist">{booking.property.address.join(", ")}</p> : null}
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 py-6">
        {booking ? (
          <StayPortal token={token} initial={booking} />
        ) : (
          <p role="alert" className="rounded-lg border border-line bg-white px-5 py-6 text-sm">{problem}</p>
        )}
      </main>
    </div>
  );
}
