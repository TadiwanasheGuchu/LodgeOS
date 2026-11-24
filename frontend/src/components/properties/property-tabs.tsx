"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function PropertyTabs({ id }: { id: string }) {
  const pathname = usePathname();
  const tabs = [
    { href: `/properties/${id}`, label: "Details" },
    { href: `/properties/${id}/room-types`, label: "Room types" },
    { href: `/properties/${id}/rooms`, label: "Rooms" },
    { href: `/properties/${id}/rates`, label: "Rates" },
    { href: `/properties/${id}/photos`, label: "Photos" },
    { href: `/properties/${id}/online-booking`, label: "Online booking" },
    { href: `/properties/${id}/buildings`, label: "Buildings" },
  ];
  return (
    <nav aria-label="Property sections" className="-mx-4 mb-6 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0">
      <ul className="flex gap-1">
        {tabs.map((t) => (
          <li key={t.href}>
            <Link
              href={t.href}
              aria-current={pathname === t.href ? "page" : undefined}
              className="inline-block border-b-2 border-transparent px-3 py-2.5 text-sm whitespace-nowrap text-muted hover:text-forest aria-[current=page]:border-forest aria-[current=page]:font-medium aria-[current=page]:text-forest"
            >
              {t.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
