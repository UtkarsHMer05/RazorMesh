"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/", label: "Overview" },
  { href: "/buyer", label: "Buyer" },
  { href: "/merchant", label: "Merchant" },
  { href: "/security-lab", label: "Security Lab" },
  { href: "/audit", label: "Audit" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function ClientNav() {
  const pathname = usePathname();
  return (
    <div className="nav">
      {ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={isActive(pathname, item.href) ? "page" : undefined}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}
