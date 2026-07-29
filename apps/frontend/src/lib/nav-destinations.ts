export interface NavDestination {
  href: string;
  label: string;
}

/** Centralized navigation destinations shared by desktop and compact nav. */
export const NAV_DESTINATIONS: NavDestination[] = [
  { href: "/", label: "Home" },
  { href: "/catalogue", label: "Catalogue" },
  { href: "/rankings", label: "Rankings" },
  { href: "/methodology", label: "Methodology" },
  { href: "/about", label: "About" },
];
