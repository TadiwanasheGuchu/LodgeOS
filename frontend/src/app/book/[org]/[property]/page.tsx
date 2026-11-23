import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { apiGet, ServerApiError } from "@/lib/server/api";
import type { PublicProperty } from "@/lib/types";
import { BookingFlow } from "./booking-flow";

async function load(org: string, property: string): Promise<PublicProperty> {
  try {
    return await apiGet<PublicProperty>(`/api/v1/public/properties/${encodeURIComponent(org)}/${encodeURIComponent(property)}`);
  } catch (err) {
    if (err instanceof ServerApiError && (err.status === 404 || err.status === 422)) notFound();
    throw err;
  }
}

export async function generateMetadata({ params }: PageProps<"/book/[org]/[property]">): Promise<Metadata> {
  const { org, property } = await params;
  const p = await load(org, property);
  return { title: `Book ${p.name}`, description: p.description ?? `Check availability and book ${p.name} directly.` };
}

export default async function BookPage({ params }: PageProps<"/book/[org]/[property]">) {
  const { org, property } = await params;
  const p = await load(org, property);
  return (
    <div className="min-h-dvh bg-cloud">
      <header className="bg-forest text-white">
        <div className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
          <p className="font-display text-2xl sm:text-3xl">{p.name}</p>
          {p.address.length > 0 ? <p className="mt-1 text-sm text-mist">{p.address.join(", ")}</p> : null}
          {p.description ? <p className="mt-3 max-w-2xl text-[15px] whitespace-pre-line text-white/90">{p.description}</p> : null}
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <BookingFlow org={org} slug={property} property={p} />
      </main>
      <footer className="mx-auto max-w-3xl px-4 pb-8 text-[13px] text-muted">
        <p>
          Check-in from {p.check_in_time.slice(0, 5)} · check-out by {p.check_out_time.slice(0, 5)}
          {p.phone ? <> · <a className="underline-offset-2 hover:underline" href={`tel:${p.phone}`}>{p.phone}</a></> : null}
          {p.email ? <> · <a className="underline-offset-2 hover:underline" href={`mailto:${p.email}`}>{p.email}</a></> : null}
        </p>
        <p className="mt-1">Prices in {p.currency}, taxes included. Booking powered by LodgeOS.</p>
      </footer>
    </div>
  );
}
