import type { Metadata } from "next";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { RoomType } from "@/lib/types";
import { RoomTypesManager } from "./room-types-manager";

export const metadata: Metadata = { title: "Room types" };

export default async function RoomTypesPage({ params }: PageProps<"/properties/[id]/room-types">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const access = accessOf(me);
  const roomTypes = access.canAt("rooms.view", property.id)
    ? await apiGet<RoomType[]>(`/api/v1/properties/${property.id}/room-types`)
    : null;
  if (roomTypes === null) {
    return <p className="text-sm text-muted">Your role does not include room details.</p>;
  }
  return <RoomTypesManager propertyId={property.id} initial={roomTypes} canManage={access.canAt("rooms.manage", property.id)} />;
}
