import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { accessOf } from "@/lib/access";
import { addDays, formatStayDate, isIsoDate, todayIn } from "@/lib/dates";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { HousekeepingBoard, PropertySummary } from "@/lib/types";
import { DayList } from "./day-list";

export const metadata: Metadata = { title: "Housekeeping" };

const pill =
  "rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white";

export default async function HousekeepingPage({ searchParams }: PageProps<"/housekeeping">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("rooms.view")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("rooms.view", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Housekeeping" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const today = todayIn(current.timezone);
  const tomorrow = addDays(today, 1);
  const day = isIsoDate(sp.date) && sp.date >= today ? sp.date : today;
  const board = await apiGet<HousekeepingBoard>(`/api/v1/properties/${current.id}/housekeeping?date=${day}`);
  const link = (q: Record<string, string>) => `/housekeeping?${new URLSearchParams({ property: current.id, ...q })}`;

  return (
    <>
      <PageHeader title="Housekeeping" description={`${current.name} · ${formatStayDate(day, { weekday: "long", day: "numeric", month: "long" })}`} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <nav aria-label="Day" className="flex gap-1.5">
          <Link href={link({ date: today })} aria-current={day === today ? "page" : undefined} className={pill}>Today</Link>
          <Link href={link({ date: tomorrow })} aria-current={day === tomorrow ? "page" : undefined} className={pill}>Tomorrow</Link>
        </nav>
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5 sm:ml-auto">
            {properties.map((p) => (
              <Link key={p.id} href={`/housekeeping?property=${p.id}`} aria-current={p.id === current.id ? "page" : undefined} className={pill}>
                {p.name}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>
      <DayList
        key={`${current.id}-${day}`}
        propertyId={current.id}
        timezone={current.timezone}
        board={board}
        canWork={access.canAt("rooms.housekeeping_update", current.id)}
        currentUserId={me.user.id}
      />
    </>
  );
}
