import type { Metadata } from "next";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { RatePlan, RatePlanDetail, RoomType, Tax } from "@/lib/types";
import { RatesManager } from "./rates-manager";

export const metadata: Metadata = { title: "Rates" };

export default async function RatesPage({ params, searchParams }: PageProps<"/properties/[id]/rates">) {
  const { id } = await params;
  const { plan: requested } = await searchParams;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const access = accessOf(me);
  if (!access.canAt("rates.view", property.id)) {
    return <p className="text-sm text-muted">Your role does not include rates.</p>;
  }
  const [taxes, plans, roomTypes] = await Promise.all([
    apiGet<Tax[]>(`/api/v1/properties/${property.id}/taxes`),
    apiGet<RatePlan[]>(`/api/v1/properties/${property.id}/rate-plans`),
    apiGet<RoomType[]>(`/api/v1/properties/${property.id}/room-types`),
  ]);
  const selected = plans.find((p) => p.id === requested) ?? plans.find((p) => p.status === "active") ?? plans[0];
  const detail = selected ? await apiGet<RatePlanDetail>(`/api/v1/rate-plans/${selected.id}`) : null;

  return (
    <RatesManager
      property={property}
      taxes={taxes}
      plans={plans}
      plan={detail}
      roomTypes={roomTypes.filter((t) => t.status === "active")}
      canManage={access.canAt("rates.manage", property.id)}
    />
  );
}
