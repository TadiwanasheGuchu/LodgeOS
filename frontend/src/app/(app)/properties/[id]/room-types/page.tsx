import type { Metadata } from "next";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { RoomType } from "@/lib/types";
import { RoomTypesManager } from "./room-types-manager";

export const metadata: Metadata = { title: "Room types" };

export default async function RoomTypesPage({ params }: PageProps<"/properties/[id]/room-types">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const perms = me.active_organisation.permissions;
  const roomTypes = perms.includes("rooms.view")
    ? await apiGet<RoomType[]>(`/api/v1/properties/${property.id}/room-types`)
    : null;
  if (roomTypes === null) {
    return <p className="text-sm text-muted">Your role does not include room details.</p>;
  }
  return <RoomTypesManager propertyId={property.id} initial={roomTypes} canManage={perms.includes("rooms.manage")} />;
}
