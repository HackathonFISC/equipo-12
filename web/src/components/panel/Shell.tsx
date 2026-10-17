import { useState } from "react";
import {
  CirclePlus,
  Droplet,
  LayoutDashboard,
  Map,
  Menu,
  Search,
  User,
  UserCog,
  X,
} from "lucide-react";
import type { PanelView, ShellProps } from "./contracts";
import { Badge, Button, cx } from "../tremor";
import { HelpDialog } from "./HelpDialog";

const STATE_VARIANT: Record<ShellProps["stateLabel"], "neutral" | "warning" | "success" | "error" | "partial"> = {
  "Sin plan": "neutral",
  Borrador: "neutral",
  Pendiente: "warning",
  Aprobado: "success",
  Rechazado: "error",
  "Error parcial": "partial",
};

const NAV: { view: PanelView; label: string; Icon: typeof Map }[] = [
  { view: "map", label: "Mapa de afectaciones", Icon: Map },
  { view: "admin", label: "Centro de coordinación", Icon: LayoutDashboard },
  { view: "citizen", label: "Reportar una incidencia", Icon: CirclePlus },
  { view: "tracking", label: "Consultar reporte", Icon: Search },
];

function workspaceLabel(role: ShellProps["role"]) {
  return role === "citizen" ? "PORTAL CIUDADANO" : "ADMINISTRACIÓN";
}

function profileNote(role: ShellProps["role"]) {
  return role === "citizen" ? "Portal ciudadano" : "Centro de coordinación";
}

function NavButtons({
  view,
  onNavigate,
  className,
}: {
  view: PanelView;
  onNavigate: (v: PanelView) => void;
  className?: string;
}) {
  return (
    <nav className={cx("flex flex-col gap-1", className)} aria-label="Navegación principal">
      {NAV.map(({ view: itemView, label, Icon }) => {
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
  );
}

function SidebarChrome({
  role,
  view,
  onNavigate,
}: {
  role: ShellProps["role"];
  view: PanelView;
  onNavigate: (v: PanelView) => void;
}) {
  return (
    <>
      <a
        href={role === "admin" ? "/admin" : "/ciudadano"}
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
        {workspaceLabel(role)}
      </div>
      <NavButtons view={view} onNavigate={onNavigate} className="flex-1 px-2" />
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
            <small className="text-sidebar-dim">{profileNote(role)}</small>
          </div>
        </div>
      </div>
    </>
  );
}

export function Shell({
  role,
  view,
  title,
  stateLabel,
  children,
  onSwitchRole,
  onNavigate,
}: ShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const handleNavigate = (next: PanelView) => {
    onNavigate(next);
    setMobileOpen(false);
  };

  const citizenActive = role === "citizen";
  const adminActive = role === "admin";

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[280px] flex-col bg-navy lg:flex">
        <SidebarChrome role={role} view={view} onNavigate={handleNavigate} />
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
        <SidebarChrome role={role} view={view} onNavigate={handleNavigate} />
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
            <div
              className="inline-flex rounded-md border border-line bg-sunken p-0.5"
              aria-label="Rol"
            >
              <a
                id="switchRoleCitizenBtn"
                href="/ciudadano"
                aria-pressed={citizenActive}
                onClick={(e) => {
                  e.preventDefault();
                  onSwitchRole("citizen");
                }}
                className={cx(
                  "inline-flex min-h-[36px] items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium no-underline transition-colors sm:text-sm",
                  citizenActive
                    ? "bg-navy text-white shadow-sm"
                    : "text-muted hover:bg-surface hover:text-ink",
                )}
              >
                <User className="size-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">Ciudadano</span>
              </a>
              <a
                id="switchRoleAdminBtn"
                href="/admin"
                aria-pressed={adminActive}
                onClick={(e) => {
                  e.preventDefault();
                  onSwitchRole("admin");
                }}
                className={cx(
                  "inline-flex min-h-[36px] items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium no-underline transition-colors sm:text-sm",
                  adminActive
                    ? "bg-navy text-white shadow-sm"
                    : "text-muted hover:bg-surface hover:text-ink",
                )}
              >
                <UserCog className="size-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">Administración</span>
              </a>
            </div>

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

            <Badge id="status-badge" variant={STATE_VARIANT[stateLabel]}>
              {stateLabel}
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

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
