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
  | "rooms.maintenance_update"
  | "rates.view"
  | "rates.manage"
  | "reservations.view"
  | "reservations.manage";

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
  /** ISO weekdays (1 = Monday) of nights that use weekend prices. */
  weekend_nights: number[];
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

/** Money is a decimal string from the API, e.g. "1250.00". Never do arithmetic on it in the browser. */
export type Money = string;

export interface Tax {
  id: string;
  property_id: string;
  name: string;
  rate_percent: string;
  sort_order: number;
  status: "active" | "archived";
}

export type RatePlanKind = "standard" | "corporate" | "promotional" | "package";
export type MealPlan = "room_only" | "bed_and_breakfast" | "half_board" | "full_board" | "all_inclusive";

export const RATE_PLAN_KIND_LABELS: Record<RatePlanKind, string> = {
  standard: "Standard",
  corporate: "Corporate",
  promotional: "Promotion",
  package: "Package",
};

export const MEAL_PLAN_LABELS: Record<MealPlan, string> = {
  room_only: "Room only",
  bed_and_breakfast: "Bed and breakfast",
  half_board: "Half board",
  full_board: "Full board",
  all_inclusive: "All inclusive",
};

export interface RatePlan {
  id: string;
  property_id: string;
  name: string;
  code: string;
  description: string | null;
  kind: RatePlanKind;
  meal_plan: MealPlan;
  currency: string;
  prices_include_tax: boolean;
  min_stay_nights: number;
  max_stay_nights: number | null;
  stay_from: string | null;
  stay_to: string | null;
  sort_order: number;
  status: "active" | "archived";
}

export interface PriceSet {
  base_price: Money;
  weekend_price: Money | null;
  extra_adult_price: Money;
  extra_child_price: Money;
}

export interface RatePlanPrice extends PriceSet {
  room_type_id: string;
}

export interface Season extends RatePlanPrice {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
}

export interface RatePlanDetail extends RatePlan {
  prices: RatePlanPrice[];
  seasons: Season[];
}

export interface QuoteNight {
  date: string;
  season: string | null;
  weekend: boolean;
  room_price: Money;
  extra_adults: number;
  extra_adult_amount: Money;
  extra_children: number;
  extra_child_amount: Money;
  amount: Money;
}

export interface Quote {
  currency: string;
  prices_include_tax: boolean;
  rate_plan_id: string;
  rate_plan_name: string;
  room_type_id: string;
  room_type_name: string;
  nights: QuoteNight[];
  accommodation_total: Money;
  net_total: Money;
  taxes: { name: string; rate_percent: string; amount: Money }[];
  tax_total: Money;
  total: Money;
}

export type ReservationStatus = "provisional" | "confirmed" | "checked_in" | "checked_out" | "cancelled" | "no_show";
export type BookingSource = "phone" | "walk_in" | "email" | "whatsapp" | "website" | "ota" | "corporate" | "other";

export const RESERVATION_STATUS_LABELS: Record<ReservationStatus, string> = {
  provisional: "Provisional",
  confirmed: "Confirmed",
  checked_in: "Checked in",
  checked_out: "Checked out",
  cancelled: "Cancelled",
  no_show: "No-show",
};

export const BOOKING_SOURCE_LABELS: Record<BookingSource, string> = {
  phone: "Phone",
  walk_in: "Walk-in",
  email: "Email",
  whatsapp: "WhatsApp",
  website: "Website",
  ota: "Online travel agent",
  corporate: "Corporate",
  other: "Other",
};

export interface Guest {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  country_code: string | null;
  notes: string | null;
}

export interface ReservationSummary {
  id: string;
  property_id: string;
  reference: string;
  status: ReservationStatus;
  source: BookingSource;
  guest_id: string;
  guest_name: string;
  check_in: string;
  check_out: string;
  nights: number;
  room_count: number;
  currency: string;
  total_amount: Money;
  created_at: string;
}

export interface ReservationDetail extends ReservationSummary {
  tax_amount: Money;
  notes: string | null;
  cancellation_reason: string | null;
  guest: Guest;
  rooms: {
    id: string;
    room_type_id: string;
    room_type_name: string;
    room_id: string | null;
    room_number: string | null;
    rate_plan_id: string;
    adults: number;
    children: number;
    total_amount: Money;
    tax_amount: Money;
    price_snapshot: {
      currency: string;
      rate_plan: string;
      nights: { date: string; season: string | null; weekend: boolean; amount: Money }[];
      net_total: Money;
      taxes: { name: string; rate_percent: string; amount: Money }[];
      total: Money;
    };
  }[];
  history: { from_status: string | null; to_status: ReservationStatus; reason: string | null; changed_by_name: string | null; changed_at: string }[];
}

export interface RoomTypeAvailability {
  room_type_id: string;
  room_type_name: string;
  room_type_code: string;
  max_occupancy: number;
  free: number;
  nights: { night: string; sellable: number; booked: number; free: number }[];
}

export interface CalendarStay {
  reservation_room_id: string;
  reservation_id: string;
  reference: string;
  status: ReservationStatus;
  guest_name: string;
  room_type_id: string;
  room_id: string | null;
  check_in: string;
  check_out: string;
  adults: number;
  children: number;
}

export interface CalendarData {
  start: string;
  days: number;
  rooms: { id: string; number: string; room_type_id: string; room_type_code: string; building_name: string | null; housekeeping_status: HousekeepingStatus; maintenance_status: MaintenanceStatus }[];
  stays: CalendarStay[];
}

export interface TodayData {
  date: string;
  arrivals: ReservationSummary[];
  departures: ReservationSummary[];
  in_house: number;
  unassigned_arrivals: number;
}

export interface FreeRoom {
  id: string;
  number: string;
  building_name: string | null;
  floor: string | null;
  housekeeping_status: HousekeepingStatus;
  maintenance_status: MaintenanceStatus;
}

export interface RoomBlockInfo {
  id: string;
  room_id: string;
  ticket_id: string | null;
  start_date: string;
  end_date: string;
  reason: string;
  status: "active" | "released";
}

export interface MaintenanceTicket {
  id: string;
  property_id: string;
  room_id: string | null;
  room_number: string | null;
  location: string | null;
  title: string;
  description: string | null;
  priority: "low" | "normal" | "urgent";
  status: "open" | "in_progress" | "resolved" | "cancelled";
  reported_by_name: string;
  assigned_to: string | null;
  assigned_to_name: string | null;
  resolution: string | null;
  created_at: string;
  closed_at: string | null;
  blocks: RoomBlockInfo[];
}

export type HousekeepingKind = "departure" | "stayover" | "arrival" | "vacant";

export interface HousekeepingRoom {
  room_id: string;
  number: string;
  floor: string | null;
  building_name: string | null;
  room_type_code: string;
  housekeeping_status: HousekeepingStatus;
  maintenance_status: MaintenanceStatus;
  blocked: boolean;
  kind: HousekeepingKind | null;
  departing: boolean;
  guest_left: boolean;
  staying: boolean;
  arriving: boolean;
  guests: number;
  task: {
    status: "pending" | "in_progress" | "done" | "declined";
    kind: HousekeepingKind;
    assigned_to: string | null;
    assigned_to_name: string | null;
    note: string | null;
    started_at: string | null;
    completed_at: string | null;
    completed_by_name: string | null;
  } | null;
}

export interface HousekeepingBoard {
  date: string;
  today: string;
  rooms: HousekeepingRoom[];
  assignees: { user_id: string; name: string }[];
}
