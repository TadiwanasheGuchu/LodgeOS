import type { Metadata } from "next";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { Building, Room, RoomType } from "@/lib/types";
import { RoomsManager } from "./rooms-manager";

export const metadata: Metadata = { title: "Rooms" };

export default async function PropertyRoomsPage({ params }: PageProps<"/properties/[id]/rooms">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const access = accessOf(me);
  if (!access.canAt("rooms.view", property.id)) {
    return <p className="text-sm text-muted">Your role does not include room details.</p>;
  }
  const [rooms, roomTypes, buildings] = await Promise.all([
    apiGet<Room[]>(`/api/v1/properties/${property.id}/rooms?include_archived=true`),
    apiGet<RoomType[]>(`/api/v1/properties/${property.id}/room-types`),
    apiGet<Building[]>(`/api/v1/properties/${property.id}/buildings`),
  ]);
  return (
    <RoomsManager
      propertyId={property.id}
      rooms={rooms}
      roomTypes={roomTypes.filter((t) => t.status === "active")}
      buildings={buildings.filter((b) => b.status === "active")}
      canManage={access.canAt("rooms.manage", property.id)}
    />
  );
}
