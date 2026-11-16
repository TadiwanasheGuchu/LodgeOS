import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireOrganisation } from "@/lib/server/api";
import { formatDate } from "@/lib/format";
import { ROLE_LABELS, type Member, type Organisation } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Team" };

function StatusLabel({ status }: { status: Member["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[13px]",
        status === "active" ? "text-success" : "text-muted",
      )}
    >
      <span
        aria-hidden
        className={cn("size-1.5 rounded-full", status === "active" ? "bg-success" : "bg-control")}
      />
      {status === "active" ? "Active" : "Disabled"}
    </span>
  );
}

export default async function TeamPage() {
  const me = await requireOrganisation();
  if (!me.active_organisation.permissions.includes("members.view")) redirect("/");
  const [members, org] = await Promise.all([
    apiGet<Member[]>("/api/v1/organisation/members"),
    apiGet<Organisation>("/api/v1/organisation"),
  ]);

  return (
    <>
      <PageHeader
        title="Team"
        description={`${members.length} ${members.length === 1 ? "person has" : "people have"} access to ${org.name}.`}
      />

      {/* Phones: stacked list */}
      <ul className="divide-y divide-line rounded-lg border border-line bg-white md:hidden">
        {members.map((m) => (
          <li key={m.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <p className="font-medium text-forest">{m.full_name}</p>
              <StatusLabel status={m.status} />
            </div>
            <p className="truncate text-sm text-muted">{m.email}</p>
            <p className="mt-1 text-sm">{ROLE_LABELS[m.role]}</p>
          </li>
        ))}
      </ul>

      {/* Tablet and desktop: table */}
      <div className="hidden overflow-hidden rounded-lg border border-line bg-white md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-cloud text-[13px] text-muted">
            <tr>
              <th scope="col" className="px-4 py-2.5 font-medium">Name</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Email</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Role</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Added</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {members.map((m) => (
              <tr key={m.id}>
                <td className="px-4 py-3 font-medium text-forest">{m.full_name}</td>
                <td className="px-4 py-3 text-muted">{m.email}</td>
                <td className="px-4 py-3">{ROLE_LABELS[m.role]}</td>
                <td className="px-4 py-3"><StatusLabel status={m.status} /></td>
                <td className="tabular px-4 py-3 text-muted">{formatDate(m.created_at, org.default_timezone)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-[13px] text-muted">Inviting staff and changing roles will be added with staff management.</p>
    </>
  );
}
