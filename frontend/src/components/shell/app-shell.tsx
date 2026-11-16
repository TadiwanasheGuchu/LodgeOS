"use client";

import { ArrowLeftRight, BedDouble, Building2, History, LayoutGrid, Menu, Settings2, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Wordmark } from "@/components/brand/wordmark";
import { cn } from "@/lib/utils";
import { ROLE_LABELS, type Me } from "@/lib/types";
import { navFor, type NavIcon } from "./nav";
import { SignOutButton } from "./sign-out-button";

const ICONS: Record<NavIcon, typeof LayoutGrid> = {
  overview: LayoutGrid,
  settings: Settings2,
  team: Users,
  activity: History,
  rooms: BedDouble,
  properties: Building2,
};

type ActiveMe = Me & { active_organisation: NonNullable<Me["active_organisation"]> };

export function AppShell({ me, children }: { me: ActiveMe; children: ReactNode }) {
  const pathname = usePathname();
  // The menu is open only for the page it was opened on, so navigating closes it.
  const [menuOpenOn, setMenuOpenOn] = useState<string | null>(null);
  const menuOpen = menuOpenOn === pathname;
  const org = me.active_organisation;
  const items = navFor(org.permissions);

  const navList = (
    <ul className="flex flex-col gap-0.5">
      {items.map((item) => {
        const Icon = ICONS[item.icon];
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm",
                active ? "bg-white/10 font-medium text-white" : "text-mist hover:bg-white/5 hover:text-white",
              )}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );

  const orgBlock = (
    <div className="border-t border-white/10 pt-4">
      <p className="truncate text-sm font-medium text-white">{org.name}</p>
      <p className="text-[13px] text-sage">{ROLE_LABELS[org.role]}</p>
      {me.memberships.length > 1 ? (
        <Link
          href="/select-organisation"
          className="mt-2 inline-flex items-center gap-1.5 text-[13px] text-mist underline-offset-2 hover:text-white hover:underline"
        >
          <ArrowLeftRight className="size-3.5" aria-hidden />
          Switch organisation
        </Link>
      ) : null}
    </div>
  );

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_minmax(0,1fr)]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-8 bg-forest px-3 py-5 lg:flex">
        <Wordmark tone="white" className="px-3 text-xl" />
        <nav aria-label="Main" className="flex-1">
          {navList}
        </nav>
        <div className="px-3">{orgBlock}</div>
      </aside>

      {/* Phone and tablet top bar */}
      <header className="sticky top-0 z-20 bg-forest lg:hidden">
        <div className="flex h-14 items-center justify-between px-4">
          <Wordmark tone="white" className="text-lg" />
          <button
            type="button"
            onClick={() => setMenuOpenOn(menuOpen ? null : pathname)}
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            className="flex size-10 items-center justify-center rounded-md text-white hover:bg-white/10"
          >
            {menuOpen ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
            <span className="sr-only">{menuOpen ? "Close menu" : "Open menu"}</span>
          </button>
        </div>
        {menuOpen ? (
          <nav id="mobile-nav" aria-label="Main" className="flex flex-col gap-4 px-3 pb-4">
            {navList}
            <div className="px-3">{orgBlock}</div>
          </nav>
        ) : null}
      </header>

      <div className="flex min-w-0 flex-col">
        <div className="hidden h-14 items-center justify-end gap-3 border-b border-line bg-white px-6 lg:flex">
          <span className="text-sm text-muted">{me.user.full_name}</span>
          <SignOutButton variant="ghost" />
        </div>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        <div className="border-t border-line bg-white px-4 py-3 lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <span className="truncate text-sm text-muted">{me.user.full_name}</span>
            <SignOutButton variant="ghost" />
          </div>
        </div>
      </div>
    </div>
  );
}
