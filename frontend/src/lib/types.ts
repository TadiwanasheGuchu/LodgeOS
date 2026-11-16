// Shapes returned by the LodgeOS API (backend/app/modules/*/schemas.py).

export type Permission =
  | "organisation.view"
  | "organisation.manage"
  | "members.view"
  | "members.manage"
  | "audit.view";

export type Role =
  | "owner"
  | "manager"
  | "receptionist"
  | "housekeeping"
  | "maintenance"
  | "accountant";

export interface Membership {
  organisation_id: string;
  organisation_name: string;
  organisation_slug: string;
  role: Role;
}

export interface Me {
  user: { id: string; email: string; full_name: string };
  memberships: Membership[];
  active_organisation: {
    id: string;
    name: string;
    slug: string;
    role: Role;
    permissions: Permission[];
  } | null;
}

export interface Organisation {
  id: string;
  name: string;
  slug: string;
  status: "active" | "suspended";
  default_currency: string;
  default_timezone: string;
  country_code: string | null;
  created_at: string;
}

export interface Member {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
  status: "active" | "disabled";
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  actor_user_id: string | null;
  actor_name: string | null;
  entity_type: string | null;
  entity_id: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  next_cursor: string | null;
}

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  manager: "Manager",
  receptionist: "Receptionist",
  housekeeping: "Housekeeping",
  maintenance: "Maintenance",
  accountant: "Accountant",
};
