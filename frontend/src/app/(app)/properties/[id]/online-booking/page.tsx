import type { Metadata } from "next";
import { headers } from "next/headers";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { RatePlan } from "@/lib/types";
import { OnlineBookingSettings } from "./settings";

export const metadata: Metadata = { title: "Online booking" };

export default async function OnlineBookingPage({ params }: PageProps<"/properties/[id]/online-booking">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const access = accessOf(me);
  const plans = access.canAt("rates.view", property.id)
    ? (await apiGet<RatePlan[]>(`/api/v1/properties/${property.id}/rate-plans`)).filter((p) => p.status === "active")
    : [];
  const h = await headers();
  const proto = h.get("x-forwarded-proto") ?? "http";
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "";
  const publicUrl = `${proto}://${host}/book/${me.active_organisation.slug}/${property.slug}`;
  return (
    <OnlineBookingSettings
      property={property}
      plans={plans}
      publicUrl={publicUrl}
      canManage={access.canAt("properties.manage", property.id)}
      canManageRates={access.canAt("rates.manage", property.id)}
    />
  );
}
