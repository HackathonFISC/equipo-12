// Menú lateral por secciones compartido por Admin y Ciudadano.
// Escritorio: aside navy fijo a la izquierda. Mobile: menú desplegable (drawer)
// con estado activo mediante aria-current.
import { CirclePlus, LayoutDashboard, Map, Search, X } from "lucide-react";
import type { PanelView, Role, SidebarNavProps } from "./contracts";
import { Badge, Button, cx } from "../tremor";

type NavItem = {
  view: PanelView;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
};

const ADMIN_NAV: NavItem[] = [
  { view: "admin", label: "Centro de coordinación", Icon: LayoutDashboard },
  { view: "map", label: "Mapa operativo", Icon: Map },
  { view: "tracking", label: "Consultar reporte", Icon: Search },
];

const CITIZEN_NAV: NavItem[] = [
  { view: "citizen", label: "Reportar incidencia", Icon: CirclePlus },
  { view: "tracking", label: "Consultar mi reporte", Icon: Search },
  { view: "map", label: "Mapa comunitario", Icon: Map },
];

const SECTION_LABEL: Record<Role, string> = {
  admin: "Administración",
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

  const handleNavigate = (next: PanelView) => {
    onNavigate(next);
    setMobileOpen(false);
  };

  const links = items.map(({ view: itemView, label, Icon }) => {
    const active = view === itemView;
    return (
      <button
        key={itemView}
        type="button"
        data-view={itemView}
        aria-current={active ? "page" : undefined}
        onClick={() => handleNavigate(itemView)}
        className={cx(
          "flex min-h-[44px] w-full items-center gap-3 border-l-[3px] px-4 py-2.5 text-left text-sm transition-colors",
          active
            ? "border-water-bright bg-navy-active font-medium text-white"
            : "border-transparent text-sidebar hover:bg-navy-raised hover:text-white",
        )}
      >
        <Icon className="size-[18px] shrink-0 opacity-90" aria-hidden="true" />
        <span>{label}</span>
      </button>
    );
  });

  return (
    <>
      {/* Aside fijo en desktop (navy). */}
      <aside
        className="fixed inset-y-0 left-0 z-40 hidden w-[280px] flex-col bg-[var(--color-navy)] lg:flex"
        aria-label="Navegación principal"
      >
        <div className="px-5 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-dim">
          {SECTION_LABEL[role]}
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-2">{links}</nav>
      </aside>

      {mobileOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-navy/60 lg:hidden"
            aria-label="Cerrar menú"
            onClick={() => setMobileOpen(false)}
          />

          <div
            id="mobileMenu"
            className={cx(
              "fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-[var(--color-navy)] shadow-xl transition-transform duration-200 lg:hidden",
              mobileOpen ? "translate-x-0" : "-translate-x-full pointer-events-none",
            )}
            aria-hidden={!mobileOpen}
          >
            <div className="flex justify-end p-2">
              <Button
                type="button"
                variant="ghost"
                className="min-h-[44px] text-sidebar hover:bg-navy-raised hover:text-white"
                aria-label="Cerrar menú"
                onClick={() => setMobileOpen(false)}
              >
                <X className="size-5" aria-hidden="true" />
              </Button>
            </div>
            <div className="px-5 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-dim">
              {SECTION_LABEL[role]}
            </div>
            <nav className="flex flex-1 flex-col gap-1 px-2">{links}</nav>
            <div className="mt-auto border-t border-white/10 px-5 py-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="synthetic">SYNTHETIC_DEMO</Badge>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
