import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { accessOf } from "@/lib/access";
import type { Organisation, Permission, PropertySummary, TodayData } from "@/lib/types";
import { PropertyClock } from "./property-clock";
import { TodayPanel } from "./today-panel";

export const metadata: Metadata = { title: "Overview" };

const links: { href: string; title: string; text: string; permission?: Permission }[] = [
  {
    href: "/calendar",
    title: "Calendar",
    text: "Every room by date, and bookings that still need a room.",
    permission: "reservations.view",
  },
  {
    href: "/rooms",
    title: "Room status",
    text: "Which rooms are dirty, clean or inspected, and which have a maintenance problem.",
    permission: "rooms.view",
  },
  {
    href: "/properties",
    title: "Properties",
    text: "Check-in times, room types, rooms and buildings for each property.",
    permission: "properties.view",
  },
  {
    href: "/settings",
    title: "Organisation details",
    text: "Name, currency, timezone and country used across your properties.",
  },
  { href: "/team", title: "Team", text: "See who has access and in which role.", permission: "members.view" },
  {
    href: "/activity",
    title: "Activity log",
    text: "Every sign-in and settings change, with who made it and when.",
    permission: "audit.view",
  },
];

export default async function OverviewPage() {
  const me = await requireOrganisation();
  const org = await apiGet<Organisation>("/api/v1/organisation");
  const access = accessOf(me);
  // Front-desk view: today's movements for up to three properties the person can see.
  const frontDesk = access.canAnywhere("reservations.view")
    ? (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("reservations.view", p.id)).slice(0, 3)
    : [];
  const today = await Promise.all(
    frontDesk.map(async (p) => ({ property: p, data: await apiGet<TodayData>(`/api/v1/properties/${p.id}/today`) })),
  );
  const firstName = me.user.full_name.split(" ")[0];

  return (
    <>
      <PageHeader title={`Hello, ${firstName}`} description={`${org.name} · ${me.active_organisation.role_label}`} />

      {today.length ? (
        <div className="mb-6 flex flex-col gap-6">
          {today.map(({ property, data }) => (
            <TodayPanel key={property.id} propertyName={property.name} data={data} />
          ))}
        </div>
      ) : null}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section aria-labelledby="setup-heading" className="rounded-lg border border-line bg-white">
          <h2 id="setup-heading" className="border-b border-line px-5 py-3 text-sm font-semibold text-forest">
            What you can do in LodgeOS today
          </h2>
          <ul className="divide-y divide-line text-sm">
            {links
              .filter((l) => !l.permission || accessOf(me).canAnywhere(l.permission))
              .map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="flex items-center gap-3 px-5 py-3.5 hover:bg-mist">
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-forest">{l.title}</span>
                      <span className="block text-muted">{l.text}</span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-muted" aria-hidden />
                  </Link>
                </li>
              ))}
          </ul>
          <p className="border-t border-line bg-cloud px-5 py-3 text-[13px] text-muted">
            Invoices, payments and housekeeping task lists are being built next.
          </p>
        </section>

        <section aria-labelledby="property-heading" className="rounded-lg border border-line bg-white px-5 py-4">
          <h2 id="property-heading" className="text-sm font-semibold text-forest">
            Organisation
          </h2>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted">Local time</dt>
            <dd className="tabular">
              <PropertyClock timeZone={org.default_timezone} />
            </dd>
            <dt className="text-muted">Timezone</dt>
            <dd>{org.default_timezone.replaceAll("_", " ")}</dd>
            <dt className="text-muted">Currency</dt>
            <dd className="font-mono">{org.default_currency}</dd>
          </dl>
        </section>
      </div>
    </>
  );
}
