// Base del panel: portado de src/coordinator/web/panel.html
// El rol ya no se cambia: se es. Cada portal tiene su propio cromo y navegación.
import { useState } from "react";
import {
  CirclePlus,
  Droplet,
  LayoutDashboard,
  Map,
  Menu,
  Search,
  X,
} from "lucide-react";
import type { PanelView, PlanStateLabel, ShellProps } from "./contracts";
import { Badge, Button, cx } from "../tremor";
import { HelpDialog } from "./HelpDialog";

const STATE_VARIANT: Record<PlanStateLabel, "neutral" | "warning" | "success" | "error" | "partial"> = {
  "Sin plan": "neutral",
  Borrador: "neutral",
  Pendiente: "warning",
  Aprobado: "success",
  Rechazado: "error",
  "Error parcial": "partial",
};

type NavItem = { view: PanelView; label: string; Icon: typeof Map };

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

function AdminSidebar({
  view,
  onNavigate,
}: {
  view: PanelView;
  onNavigate: (v: PanelView) => void;
}) {
  return (
    <>
      <a
        href="/admin"
        className="flex items-center gap-3 px-5 py-6 text-white no-underline"
        aria-label="AguaJusta Oeste inicio"
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-water text-white">
          <Droplet className="size-5" aria-hidden="true" />
        </span>
        <span className="font-display leading-tight">
          <strong className="block text-base font-semibold tracking-tight">AguaJusta</strong>
          <small className="text-[11px] font-medium uppercase tracking-wider text-sidebar-dim">
            OESTE
          </small>
        </span>
      </a>
      <div className="px-5 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-dim">
        Administración
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-2" aria-label="Navegación principal">
        {ADMIN_NAV.map(({ view: itemView, label, Icon }) => {
          const active = view === itemView;
          return (
            <button
              key={itemView}
              type="button"
              data-view={itemView}
              aria-current={active ? "page" : undefined}
              onClick={() => onNavigate(itemView)}
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
        })}
      </nav>
      <div className="mt-auto space-y-4 border-t border-white/10 px-5 py-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="synthetic">SYNTHETIC_DEMO</Badge>
          <p className="text-xs leading-snug text-sidebar-dim">
            Motor local · 3 agentes + OR-Tools + SQLite
          </p>
        </div>
        <div className="flex items-center gap-3 text-sidebar">
          <div
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-navy-active text-xs font-semibold text-white"
            aria-hidden="true"
          >
            AO
          </div>
          <div className="min-w-0 text-sm">
            <strong className="block truncate text-white">AguaJusta Oeste</strong>
            <small className="text-sidebar-dim">Centro de coordinación</small>
          </div>
        </div>
      </div>
    </>
  );
}

function AdminShell({
  view,
  title,
  stateLabel,
  children,
  onNavigate,
}: Omit<ShellProps, "role">) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const label: PlanStateLabel = stateLabel ?? "Sin plan";

  const handleNavigate = (next: PanelView) => {
    onNavigate(next);
    setMobileOpen(false);
  };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[280px] flex-col bg-navy lg:flex">
        <AdminSidebar view={view} onNavigate={handleNavigate} />
      </aside>

      {mobileOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-navy/60 lg:hidden"
          aria-label="Cerrar menú"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <div
        id="mobileMenu"
        className={cx(
          "fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-navy shadow-xl transition-transform duration-200 lg:hidden",
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
        <AdminSidebar view={view} onNavigate={handleNavigate} />
      </div>

      <div className="lg:ml-[280px]">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur-sm lg:px-6">
          <Button
            type="button"
            variant="ghost"
            className="lg:hidden"
            aria-label="Abrir menú"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-5" aria-hidden="true" />
          </Button>

          <div className="breadcrumb flex min-w-0 flex-1 items-center gap-2 text-sm text-muted">
            <span>Panamá Oeste</span>
            <span className="text-line" aria-hidden="true">
              /
            </span>
            <strong id="breadcrumbCurrent" className="truncate font-semibold text-ink">
              {title}
            </strong>
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 sm:gap-3">
            <span
              id="connectionMode"
              className="hidden items-center gap-1.5 text-xs text-muted sm:inline-flex"
            >
              <span
                className="size-2 shrink-0 rounded-full bg-approved animate-pulse"
                aria-hidden="true"
              />
              Conectado
            </span>

            <Badge id="status-badge" variant={STATE_VARIANT[label]}>
              {label}
            </Badge>

            <Button
              id="helpButton"
              type="button"
              variant="secondary"
              className="min-h-[36px] min-w-[36px] px-2.5"
              aria-label="Ayuda"
              onClick={() => setHelpOpen(true)}
            >
              ?
            </Button>
          </div>
        </header>

        <main className="mx-auto max-w-[1600px] p-6">{children}</main>
      </div>

      <HelpDialog role="admin" open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

function CitizenShell({
  view,
  title,
  children,
  onNavigate,
}: Omit<ShellProps, "role" | "stateLabel">) {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3 sm:px-6">
          <a
            href="/ciudadano"
            className="flex items-center gap-2.5 text-ink no-underline"
            aria-label="AguaJusta Oeste, portal ciudadano"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-water text-white">
              <Droplet className="size-5" aria-hidden="true" />
            </span>
            <span className="font-display text-base font-semibold tracking-tight">
              AguaJusta <span className="text-water-deep">OESTE</span>
            </span>
          </a>

          <nav
            aria-label="Navegación del portal ciudadano"
            className="flex min-w-0 flex-1 flex-wrap items-center gap-2 sm:justify-end"
          >
            {CITIZEN_NAV.map(({ view: itemView, label, Icon }) => {
              const active = view === itemView;
              return (
                <button
                  key={itemView}
                  type="button"
                  data-view={itemView}
                  aria-current={active ? "page" : undefined}
                  onClick={() => onNavigate(itemView)}
                  className={cx(
                    "inline-flex min-h-[44px] items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                    active
                      ? "border-transparent bg-water text-white"
                      : "border-line bg-surface text-muted hover:bg-water-soft hover:text-water-deep",
                  )}
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  <span>{label}</span>
                </button>
              );
            })}
          </nav>

          <Button
            id="helpButton"
            type="button"
            variant="secondary"
            className="min-h-[44px] min-w-[44px] px-2.5"
            aria-label="Ayuda"
            onClick={() => setHelpOpen(true)}
          >
            ?
          </Button>

          <p className="sr-only">Sección actual: {title}</p>
        </div>
      </header>

      <section aria-label="Sobre este portal" className="border-b border-line bg-water-soft">
        <div className="mx-auto max-w-[1080px] px-4 py-5 sm:px-6">
          <p className="font-display text-lg font-semibold leading-snug text-water-deep">
            Cada reporte cuenta una vez.
          </p>
          <p className="mt-1 text-sm text-muted">
            La prioridad la deciden las horas sin agua, las personas y la vulnerabilidad.
          </p>
          <p className="mt-3">
            <Badge variant="synthetic">SYNTHETIC_DEMO</Badge>
          </p>
        </div>
      </section>

      <main className="mx-auto max-w-[1080px] p-4 sm:p-6 lg:p-8">{children}</main>

      <HelpDialog role="citizen" open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

export function Shell({ role, view, title, stateLabel, children, onNavigate }: ShellProps) {
  if (role === "citizen") {
    return (
      <CitizenShell view={view} title={title} onNavigate={onNavigate}>
        {children}
      </CitizenShell>
    );
  }
  return (
    <AdminShell view={view} title={title} stateLabel={stateLabel} onNavigate={onNavigate}>
      {children}
    </AdminShell>
  );
}
