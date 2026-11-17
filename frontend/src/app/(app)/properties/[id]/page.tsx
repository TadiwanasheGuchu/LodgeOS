import type { Metadata } from "next";
import { PropertyForm } from "@/components/properties/property-form";
import { COUNTRIES } from "@/lib/reference-data";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { Organisation } from "@/lib/types";
import { loadProperty } from "@/lib/server/properties";
import { ArchiveProperty } from "./archive-property";

export const metadata: Metadata = { title: "Property details" };

export default async function PropertyDetailsPage({ params }: PageProps<"/properties/[id]">) {
  const { id } = await params;
  const [me, property, org] = await Promise.all([
    requireOrganisation(),
    loadProperty(id),
    apiGet<Organisation>("/api/v1/organisation"),
  ]);
  const canManage = accessOf(me).canAt("properties.manage", property.id);

  if (!canManage) {
    const address = [property.address_line1, property.address_line2, property.city, property.region, property.postal_code]
      .filter(Boolean)
      .join(", ");
    return (
      <div className="max-w-3xl rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted">Check-in from</dt>
          <dd className="tabular">{property.check_in_time.slice(0, 5)}</dd>
          <dt className="text-muted">Check-out by</dt>
          <dd className="tabular">{property.check_out_time.slice(0, 5)}</dd>
          <dt className="text-muted">Timezone</dt>
          <dd>{property.timezone.replaceAll("_", " ")}</dd>
          <dt className="text-muted">Currency</dt>
          <dd className="font-mono">{property.currency}</dd>
          <dt className="text-muted">Country</dt>
          <dd>{COUNTRIES.find((c) => c.code === property.country_code)?.name ?? property.country_code ?? "—"}</dd>
          <dt className="text-muted">Address</dt>
          <dd>{address || "—"}</dd>
          <dt className="text-muted">Phone</dt>
          <dd>{property.phone ?? "—"}</dd>
          <dt className="text-muted">Email</dt>
          <dd>{property.email ?? "—"}</dd>
        </dl>
      </div>
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div className="rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        <PropertyForm
          property={property}
          defaults={{ timezone: org.default_timezone, currency: org.default_currency, country: org.country_code }}
        />
      </div>
      <ArchiveProperty property={property} />
    </div>
  );
}
