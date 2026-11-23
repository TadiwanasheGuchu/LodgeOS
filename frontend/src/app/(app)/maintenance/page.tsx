import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { accessOf } from "@/lib/access";
import { todayIn } from "@/lib/dates";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { MaintenanceTicket, PropertySummary, Room } from "@/lib/types";
import { MaintenanceBoard } from "./maintenance-board";

export const metadata: Metadata = { title: "Maintenance" };

export default async function MaintenancePage({ searchParams }: PageProps<"/maintenance">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("rooms.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("rooms.view", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Maintenance" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const showClosed = sp.view === "closed";
  const [tickets, rooms] = await Promise.all([
    apiGet<MaintenanceTicket[]>(`/api/v1/properties/${current.id}/maintenance/tickets${showClosed ? "?closed=true" : ""}`),
    apiGet<Room[]>(`/api/v1/properties/${current.id}/rooms`),
  ]);

  return (
    <>
      <PageHeader title="Maintenance" description={current.name} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5">
            {properties.map((p) => (
              <Link key={p.id} href={`/maintenance?property=${p.id}`} aria-current={p.id === current.id ? "page" : undefined}
                className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white">
                {p.name}
              </Link>
            ))}
          </nav>
        ) : null}
        <nav aria-label="Ticket list" className="ml-auto flex gap-1.5 text-sm">
          <Link href={`/maintenance?property=${current.id}`} aria-current={showClosed ? undefined : "page"} className="rounded-md px-3 py-1.5 text-forest hover:bg-mist aria-[current=page]:bg-mist aria-[current=page]:font-medium">Open</Link>
          <Link href={`/maintenance?property=${current.id}&view=closed`} aria-current={showClosed ? "page" : undefined} className="rounded-md px-3 py-1.5 text-forest hover:bg-mist aria-[current=page]:bg-mist aria-[current=page]:font-medium">Closed</Link>
        </nav>
      </div>
      <MaintenanceBoard
        key={`${current.id}-${showClosed}`}
        propertyId={current.id}
        tickets={tickets}
        rooms={rooms.map((r) => ({ id: r.id, number: r.number }))}
        canWork={access.canAt("rooms.maintenance_update", current.id)}
        currentUserId={me.user.id}
        today={todayIn(current.timezone)}
        showClosed={showClosed}
      />
    </>
  );
}
