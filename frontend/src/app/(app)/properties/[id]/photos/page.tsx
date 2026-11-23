import type { Metadata } from "next";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import type { MediaAsset, RoomType } from "@/lib/types";
import { PhotoManager } from "./photo-manager";

export const metadata: Metadata = { title: "Photos" };

export default async function PhotosPage({ params }: PageProps<"/properties/[id]/photos">) {
  const { id } = await params;
  const [me, property] = await Promise.all([requireOrganisation(), loadProperty(id)]);
  const [media, roomTypes] = await Promise.all([
    apiGet<MediaAsset[]>(`/api/v1/properties/${property.id}/media`),
    apiGet<RoomType[]>(`/api/v1/properties/${property.id}/room-types`),
  ]);
  return (
    <PhotoManager
      propertyId={property.id}
      media={media}
      roomTypes={roomTypes.filter((t) => t.status === "active").map((t) => ({ id: t.id, name: t.name }))}
      canManage={accessOf(me).canAt("properties.manage", property.id)}
    />
  );
}
