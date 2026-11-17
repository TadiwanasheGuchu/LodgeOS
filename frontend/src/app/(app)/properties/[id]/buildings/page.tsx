import type { Metadata } from "next";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { Building } from "@/lib/types";
import { BuildingsManager } from "./buildings-manager";

export const metadata: Metadata = { title: "Buildings" };

export default async function BuildingsPage({ params }: PageProps<"/properties/[id]/buildings">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const buildings = await apiGet<Building[]>(`/api/v1/properties/${property.id}/buildings`);
  return (
    <BuildingsManager
      propertyId={property.id}
      buildings={buildings}
      canManage={accessOf(me).canAt("properties.manage", property.id)}
    />
  );
}
