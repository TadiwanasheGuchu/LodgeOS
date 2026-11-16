import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { AuditLogPage, Organisation } from "@/lib/types";
import { ActivityList } from "./activity-list";

export const metadata: Metadata = { title: "Activity log" };

export default async function ActivityPage() {
  const me = await requireOrganisation();
  if (!me.active_organisation.permissions.includes("audit.view")) redirect("/");
  const [page, org] = await Promise.all([
    apiGet<AuditLogPage>("/api/v1/organisation/audit-logs?limit=50"),
    apiGet<Organisation>("/api/v1/organisation"),
  ]);

  return (
    <>
      <PageHeader
        title="Activity log"
        description={`Sign-ins and changes in ${org.name}. Times are ${org.default_timezone.replaceAll("_", " ")} time.`}
      />
      <ActivityList initial={page} timeZone={org.default_timezone} />
    </>
  );
}
