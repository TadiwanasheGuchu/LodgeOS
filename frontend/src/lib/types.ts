// Shapes returned by the LodgeOS API (backend/app/modules/*/schemas.py).

export type Permission =
  | "organisation.view"
  | "organisation.manage"
  | "members.view"
  | "members.manage"
  | "audit.view"
  | "properties.view"
  | "properties.manage"
  | "rooms.view"
  | "rooms.manage"
  | "rooms.housekeeping_update"
  | "rooms.maintenance_update";

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
  /** Highest system role key, or "" when only custom roles are held. */
  role: Role | "";
  role_label: string;
}

export interface Me {
  user: { id: string; email: string; full_name: string };
  memberships: Membership[];
  active_organisation: {
    id: string;
    name: string;
    slug: string;
    role: Role | "";
    role_label: string;
    /** Granted for every property. */
    permissions: Permission[];
    /** Granted for specific properties only. */
    property_permissions: Record<string, Permission[]>;
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

export interface Assignment {
  id: string;
  role_id: string;
  role_key: string | null;
  role_name: string;
  property_id: string | null;
  property_name: string | null;
}

export interface Member {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: Role | "";
  role_label: string;
  status: "active" | "disabled";
  created_at: string;
  assignments: Assignment[];
}

export interface RoleDefinition {
  id: string;
  key: string | null;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: Permission[];
}

export interface Invitation {
  id: string;
  email: string;
  full_name: string;
  role_id: string;
  role_name: string;
  property_id: string | null;
  property_name: string | null;
  state: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  created_at: string;
}

export interface InvitationPreview {
  organisation_name: string;
  email: string;
  full_name: string;
  role_name: string;
  property_name: string | null;
  has_account: boolean;
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

export type PropertyType =
  | "guesthouse"
  | "boutique_hotel"
  | "hotel"
  | "lodge"
  | "safari_lodge"
  | "resort"
  | "serviced_apartments"
  | "other";

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  guesthouse: "Guesthouse",
  boutique_hotel: "Boutique hotel",
  hotel: "Hotel",
  lodge: "Lodge",
  safari_lodge: "Safari lodge",
  resort: "Resort",
  serviced_apartments: "Serviced apartments",
  other: "Other",
};

export interface Property {
  id: string;
  name: string;
  slug: string;
  property_type: PropertyType;
  status: "active" | "archived";
  timezone: string;
  currency: string;
  country_code: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  phone: string | null;
  email: string | null;
  check_in_time: string;
  check_out_time: string;
  created_at: string;
}

export interface PropertySummary extends Property {
  room_count: number;
  room_type_count: number;
}

export interface Building {
  id: string;
  property_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  status: "active" | "archived";
}

export interface RoomType {
  id: string;
  property_id: string;
  name: string;
  code: string;
  description: string | null;
  bed_configuration: string | null;
  base_occupancy: number;
  max_occupancy: number;
  max_adults: number;
  max_children: number;
  sort_order: number;
  status: "active" | "archived";
  room_count: number;
}

export type HousekeepingStatus = "dirty" | "clean" | "inspected";
export type MaintenanceStatus = "none" | "out_of_service" | "out_of_order";

export interface Room {
  id: string;
  property_id: string;
  number: string;
  floor: string | null;
  notes: string | null;
  status: "active" | "archived";
  room_type_id: string;
  room_type_code: string;
  room_type_name: string;
  building_id: string | null;
  building_name: string | null;
  housekeeping_status: HousekeepingStatus;
  housekeeping_updated_at: string | null;
  maintenance_status: MaintenanceStatus;
  maintenance_reason: string | null;
  maintenance_updated_at: string | null;
}
