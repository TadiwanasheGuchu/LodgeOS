import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { InHouseGuest, PosItem, PosOutlet, PosSale, PropertySummary, Tax } from "@/lib/types";
import { Catalogue } from "./catalogue";
import { Till } from "./till";

export const metadata: Metadata = { title: "Point of sale" };

const pill =
  "rounded-md border border-line bg-white px-3 py-1.5 text-sm text-forest hover:bg-mist aria-[current=page]:border-forest aria-[current=page]:bg-forest aria-[current=page]:text-white";

export default async function PosPage({ searchParams }: PageProps<"/pos">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("pos.sell")) redirect("/");
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) => access.canAt("pos.sell", p.id));
  if (properties.length === 0) {
    return (
      <>
        <PageHeader title="Point of sale" />
        <Alert tone="info">No properties are set up yet.</Alert>
      </>
    );
  }
  const sp = await searchParams;
  const current = properties.find((p) => p.id === sp.property) ?? properties[0];
  const canManage = access.canAt("pos.manage", current.id);
  const view = sp.view === "items" && canManage ? "items" : "till";
  const [outlets, items] = await Promise.all([
    apiGet<PosOutlet[]>(`/api/v1/properties/${current.id}/pos/outlets`),
    apiGet<PosItem[]>(`/api/v1/properties/${current.id}/pos/items`),
  ]);
  const link = (v: string) => `/pos?${new URLSearchParams({ property: current.id, view: v })}`;

  return (
    <>
      <PageHeader title="Point of sale" description={current.name} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {canManage ? (
          <nav aria-label="Point of sale" className="flex gap-1.5">
            <Link href={link("till")} aria-current={view === "till" ? "page" : undefined} className={pill}>Sell</Link>
            <Link href={link("items")} aria-current={view === "items" ? "page" : undefined} className={pill}>Items</Link>
          </nav>
        ) : null}
        {properties.length > 1 ? (
          <nav aria-label="Property" className="flex flex-wrap gap-1.5 sm:ml-auto">
            {properties.map((p) => (
              <Link key={p.id} href={`/pos?property=${p.id}`} aria-current={p.id === current.id ? "page" : undefined} className={pill}>{p.name}</Link>
            ))}
          </nav>
        ) : null}
      </div>
      {view === "items" ? (
        <Catalogue
          propertyId={current.id}
          currency={current.currency}
          outlets={outlets}
          items={items}
          taxes={(await apiGet<Tax[]>(`/api/v1/properties/${current.id}/taxes`)).filter((t) => t.status === "active")}
        />
      ) : (
        <Till
          key={current.id}
          propertyId={current.id}
          currency={current.currency}
          outlets={outlets.filter((o) => o.status === "active")}
          items={items.filter((i) => i.status === "active")}
          guests={await apiGet<InHouseGuest[]>(`/api/v1/properties/${current.id}/pos/in-house`)}
          sales={await apiGet<PosSale[]>(`/api/v1/properties/${current.id}/pos/sales`)}
          canManage={canManage}
          itemsLink={link("items")}
        />
      )}
    </>
  );
}
