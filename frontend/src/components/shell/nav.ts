import type { Permission } from "@/lib/types";

export type NavIcon = "overview" | "settings" | "team" | "activity";

export interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  /** Shown only if the user has this permission. */
  permission: Permission | null;
}

// Only screens that exist are listed. Modules are added here as they are built.
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview", icon: "overview", permission: null },
  { href: "/team", label: "Team", icon: "team", permission: "members.view" },
  { href: "/activity", label: "Activity log", icon: "activity", permission: "audit.view" },
  { href: "/settings", label: "Organisation", icon: "settings", permission: "organisation.view" },
];

export function navFor(permissions: Permission[]): NavItem[] {
  return NAV_ITEMS.filter((item) => item.permission === null || permissions.includes(item.permission));
}
