import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { PropertyTabs } from "@/components/properties/property-tabs";
import { requireOrganisation } from "@/lib/server/api";
import { loadProperty } from "@/lib/server/properties";
import { PROPERTY_TYPE_LABELS } from "@/lib/types";

export default async function PropertyLayout({ children, params }: LayoutProps<"/properties/[id]">) {
  const me = await requireOrganisation();
  if (!me.active_organisation.permissions.includes("properties.view")) redirect("/");
  const { id } = await params;
  const property = await loadProperty(id);
  return (
    <>
      <PageHeader
        title={property.name}
        description={`${PROPERTY_TYPE_LABELS[property.property_type]}${property.status === "archived" ? " · Archived" : ""}`}
      />
      <PropertyTabs id={property.id} />
      {children}
    </>
  );
}
