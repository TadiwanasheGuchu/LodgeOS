import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { PROPERTY_TYPE_LABELS, type PropertySummary } from "@/lib/types";

export const metadata: Metadata = { title: "Properties" };

export default async function PropertiesPage() {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.canAnywhere("properties.view")) redirect("/");
  const properties = await apiGet<PropertySummary[]>("/api/v1/properties");
  const canManage = access.can("properties.manage");

  return (
    <>
      <PageHeader
        title="Properties"
        actions={
          canManage ? (
            <Button asChild>
              <Link href="/properties/new">
                <Plus aria-hidden />
                Add property
              </Link>
            </Button>
          ) : null
        }
      />
      {properties.length === 0 ? (
        <Alert tone="info">
          {canManage ? "Add your first property to set up its rooms." : "No properties have been set up yet."}
        </Alert>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {properties.map((p) => (
            <li key={p.id}>
              <Link href={`/properties/${p.id}`} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-4 hover:bg-mist">
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-forest">{p.name}</span>
                  <span className="block text-sm text-muted">
                    {PROPERTY_TYPE_LABELS[p.property_type]}
                    {p.city ? ` · ${p.city}` : ""}
                  </span>
                </span>
                <span className="tabular text-sm text-charcoal">
                  {p.room_count} {p.room_count === 1 ? "room" : "rooms"} · {p.room_type_count}{" "}
                  {p.room_type_count === 1 ? "type" : "types"}
                </span>
                <span className="font-mono text-[13px] text-muted">{p.currency}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
