import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { COUNTRIES, CURRENCIES } from "@/lib/reference-data";
import type { Organisation } from "@/lib/types";
import { OrganisationForm } from "./organisation-form";

export const metadata: Metadata = { title: "Organisation" };

export default async function SettingsPage() {
  const me = await requireOrganisation();
  const org = await apiGet<Organisation>("/api/v1/organisation");
  const canManage = accessOf(me).can("organisation.manage");

  return (
    <>
      <PageHeader
        title="Organisation"
        description="Defaults used across your properties. Individual properties can override currency and timezone."
      />
      <div className="max-w-2xl rounded-lg border border-line bg-white px-5 py-5 sm:px-6">
        {canManage ? (
          <OrganisationForm organisation={org} />
        ) : (
          <>
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_1fr]">
              <dt className="text-muted">Name</dt>
              <dd className="font-medium text-forest">{org.name}</dd>
              <dt className="text-muted">Currency</dt>
              <dd>
                <span className="font-mono">{org.default_currency}</span>{" "}
                {CURRENCIES.find((c) => c.code === org.default_currency)?.name}
              </dd>
              <dt className="text-muted">Timezone</dt>
              <dd>{org.default_timezone.replaceAll("_", " ")}</dd>
              <dt className="text-muted">Country</dt>
              <dd>{COUNTRIES.find((c) => c.code === org.country_code)?.name ?? org.country_code ?? "Not set"}</dd>
            </dl>
            <p className="mt-5 border-t border-line pt-4 text-[13px] text-muted">
              Only the organisation owner can change these details.
            </p>
          </>
        )}
      </div>
    </>
  );
}
