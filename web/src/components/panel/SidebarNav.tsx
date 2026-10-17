// Raíl claro bajo la cabecera. El ítem activo es una banda #d4d3d0.
import { X } from "lucide-react";
import type { PanelView, Role, SidebarNavProps } from "./contracts";
import { cx } from "../tremor";

type NavItem = { view: PanelView; label: string };

const ADMIN_NAV: NavItem[] = [
  { view: "admin", label: "Centro de coordinación" },
  { view: "map", label: "Mapa operativo" },
  { view: "tracking", label: "Consultar reporte" },
];

const CITIZEN_NAV: NavItem[] = [
  { view: "citizen", label: "Reportar incidencia" },
  { view: "tracking", label: "Consultar mi reporte" },
  { view: "map", label: "Mapa comunitario" },
];

const SECTION_LABEL: Record<Role, string> = {
  admin: "Coordinación",
  citizen: "Ciudadano",
};

export function SidebarNav({
  role,
  view,
  onNavigate,
  mobileOpen,
  setMobileOpen,
}: SidebarNavProps & {
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}) {
  const items = role === "admin" ? ADMIN_NAV : CITIZEN_NAV;

  const links = (
    <nav className="flex flex-col py-2" aria-label="Navegación principal">
      <p className="px-4 pb-2 text-base font-semibold text-[#1c1c1a]">
        {SECTION_LABEL[role]}
      </p>
      {items.map(({ view: itemView, label }) => {
        const active = view === itemView;
        return (
          <button
            key={itemView}
            type="button"
            data-view={itemView}
            aria-current={active ? "page" : undefined}
            onClick={() => {
              onNavigate(itemView);
              setMobileOpen(false);
            }}
            className={cx(
              "mx-2 rounded px-3 py-2 text-left text-sm text-[#1c1c1a]",
              active ? "bg-[var(--color-rail-active)] font-semibold" : "hover:bg-[#dad9d6]",
            )}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );

  return (
    <>
      <aside className="sticky top-12 hidden h-[calc(100vh-3rem)] w-[232px] shrink-0 bg-[var(--color-rail)] lg:block">
        {links}
      </aside>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Cerrar menú"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-[232px] flex-col bg-[var(--color-rail)]">
            <button
              type="button"
              className="ml-auto p-3"
              aria-label="Cerrar menú"
              onClick={() => setMobileOpen(false)}
            >
              <X className="size-4" aria-hidden="true" />
            </button>
            {links}
          </aside>
        </div>
      ) : null}
    </>
  );
}
