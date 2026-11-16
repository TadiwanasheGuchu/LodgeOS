import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { PropertySummary, Room } from "@/lib/types";
import { RoomBoard } from "./room-board";

export const metadata: Metadata = { title: "Room status" };

export default async function RoomsPage({ searchParams }: PageProps<"/rooms">) {
  const me = await requireOrganisation();
  const perms = me.active_organisation.permissions;
  if (!perms.includes("rooms.view")) redirect("/");

  const properties = await apiGet<PropertySummary[]>("/api/v1/properties");
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Room status" />
        <Alert tone="info">
          No properties yet.{" "}
          {perms.includes("properties.manage") ? (
            <Link href="/properties/new" className="font-medium underline underline-offset-2">
              Add your first property
            </Link>
          ) : (
            "Ask your manager to set up the property and its rooms."
          )}
        </Alert>
      </>
    );
  }

  const { property: requested } = await searchParams;
  const current = properties.find((p) => p.id === requested) ?? properties[0];
  const rooms = await apiGet<Room[]>(`/api/v1/properties/${current.id}/rooms`);

  return (
    <>
      <PageHeader
        title="Room status"
        description={properties.length > 1 ? undefined : current.name}
        actions={
          properties.length > 1 ? (
            <nav aria-label="Property" className="flex flex-wrap gap-1.5">
              {properties.map((p) => (
                <Link
                  key={p.id}
                  href={`/rooms?property=${p.id}`}
                  aria-current={p.id === current.id ? "page" : undefined}
                  className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white"
                >
                  {p.name}
                </Link>
              ))}
            </nav>
          ) : null
        }
      />
      {rooms.length === 0 ? (
        <Alert tone="info">
          {current.name} has no rooms yet.{" "}
          {perms.includes("rooms.manage") ? (
            <Link href={`/properties/${current.id}/rooms`} className="font-medium underline underline-offset-2">
              Add rooms
            </Link>
          ) : null}
        </Alert>
      ) : (
        <RoomBoard
          key={current.id}
          rooms={rooms}
          timeZone={current.timezone}
          canHousekeep={perms.includes("rooms.housekeeping_update")}
          canMaintain={perms.includes("rooms.maintenance_update")}
        />
      )}
    </>
  );
}
