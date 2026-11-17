import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { PropertyForm } from "@/components/properties/property-form";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { Organisation } from "@/lib/types";

export const metadata: Metadata = { title: "Add property" };

export default async function NewPropertyPage() {
  const me = await requireOrganisation();
  if (!accessOf(me).can("properties.manage")) redirect("/properties");
  const org = await apiGet<Organisation>("/api/v1/organisation");
  return (
    <>
      <PageHeader title="Add property" description="Next you will add its room types and rooms." />
      <div className="max-w-3xl rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        <PropertyForm defaults={{ timezone: org.default_timezone, currency: org.default_currency, country: org.country_code }} />
      </div>
    </>
  );
}
