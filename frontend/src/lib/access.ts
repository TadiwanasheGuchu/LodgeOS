import type { Me, Permission } from "@/lib/types";

type ActiveOrg = NonNullable<Me["active_organisation"]>;

/**
 * What the signed-in person may do. The API enforces all of this; the UI uses it only
 * to avoid showing controls that would be refused.
 */
export class Access {
  constructor(private readonly org: Pick<ActiveOrg, "permissions" | "property_permissions">) {}

  /** Granted for every property (or for the organisation itself). */
  can(p: Permission): boolean {
    return this.org.permissions.includes(p);
  }

  /** Granted for at least one property. */
  canAnywhere(p: Permission): boolean {
    return this.can(p) || Object.values(this.org.property_permissions).some((ps) => ps.includes(p));
  }

  canAt(p: Permission, propertyId: string): boolean {
    return this.can(p) || (this.org.property_permissions[propertyId] ?? []).includes(p);
  }
}

export function accessOf(me: { active_organisation: ActiveOrg }): Access {
  return new Access(me.active_organisation);
}
