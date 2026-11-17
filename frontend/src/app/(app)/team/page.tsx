import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { accessOf } from "@/lib/access";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import type { Invitation, Member, Organisation, PropertySummary, RoleDefinition } from "@/lib/types";
import { TeamManager } from "./team-manager";

export const metadata: Metadata = { title: "Team" };

export default async function TeamPage() {
  const me = await requireOrganisation();
  const access = accessOf(me);
  if (!access.can("members.view")) redirect("/");
  const [members, roles, invitations, properties, org] = await Promise.all([
    apiGet<Member[]>("/api/v1/organisation/members"),
    apiGet<RoleDefinition[]>("/api/v1/roles"),
    apiGet<Invitation[]>("/api/v1/invitations"),
    apiGet<PropertySummary[]>("/api/v1/properties"),
    apiGet<Organisation>("/api/v1/organisation"),
  ]);
  const myPermissions = new Set(me.active_organisation.permissions);
  // Roles this person may give or take away: those whose permissions they hold everywhere.
  const grantableRoleIds = roles.filter((r) => r.permissions.every((p) => myPermissions.has(p))).map((r) => r.id);

  return (
    <>
      <PageHeader title="Team" description={`Who can use LodgeOS at ${org.name}, and what they can do.`} />
      <TeamManager
        members={members}
        roles={roles}
        grantableRoleIds={grantableRoleIds}
        invitations={invitations}
        properties={properties.map((p) => ({ id: p.id, name: p.name }))}
        canManage={access.can("members.manage")}
        currentUserId={me.user.id}
        timeZone={org.default_timezone}
      />
    </>
  );
}
