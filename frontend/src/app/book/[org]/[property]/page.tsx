import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { apiGet, ServerApiError } from "@/lib/server/api";
import type { PublicProperty } from "@/lib/types";
import { Picture } from "@/components/media/picture";
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
        {p.photos[0] ? (
          <div className="mx-auto max-w-3xl sm:px-4 sm:pt-4">
            <Picture image={p.photos[0]} sizes="(min-width: 768px) 736px, 100vw" priority className="aspect-[16/9] w-full object-cover sm:rounded-lg" />
          </div>
        ) : null}
        <div className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
          {p.logo ? (
            // eslint-disable-next-line @next/next/no-img-element -- pre-sized logo from our API
            <img src={p.logo.urls.sm} srcSet={`${p.logo.urls.sm} 1x, ${p.logo.urls.md} 3x`} alt={`${p.name} logo`} className="mb-3 h-12 w-auto rounded bg-white/95 p-1.5" />
          ) : null}
          <p className="font-display text-2xl sm:text-3xl">{p.name}</p>
          {p.address.length > 0 ? <p className="mt-1 text-sm text-mist">{p.address.join(", ")}</p> : null}
          {p.description ? <p className="mt-3 max-w-2xl text-[15px] whitespace-pre-line text-white/90">{p.description}</p> : null}
          {p.photos.length > 1 ? (
            <ul aria-label="More photos" className="-mx-4 mt-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1">
              {p.photos.slice(1).map((ph) => (
                <li key={ph.urls.sm} className="w-40 shrink-0 snap-start">
                  <Picture image={ph} sizes="160px" className="aspect-[4/3] w-full rounded-md object-cover" />
                </li>
              ))}
            </ul>
          ) : null}
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
