// Base del panel: portado de src/coordinator/web/panel.html
// El rol ya no se cambia: se es. Cada portal tiene su propio cromo y navegación.
// Admin y ciudadano comparten la cabecera oscura (AppHeader) y el menú lateral
// (SidebarNav). El ámbito es distrito (Arraiján / La Chorrera).
import { useState } from "react";
import type { ShellProps } from "./contracts";
import { HelpDialog } from "./HelpDialog";
import { AppHeader } from "./AppHeader";
import { SidebarNav } from "./SidebarNav";

type AdminShellProps = Omit<ShellProps, "role">;

function AdminShell({
  view,
  title,
  stateLabel,
  scope,
  query,
  children,
  onNavigate,
  onScopeChange,
  onQueryChange,
}: AdminShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="console min-h-screen bg-canvas text-ink">
      <AppHeader
        title={title}
        stateLabel={stateLabel}
        scope={scope}
        query={query}
        onScopeChange={onScopeChange}
        onQueryChange={onQueryChange}
        onOpenMenu={() => setMobileOpen(true)}
        onHelp={() => setHelpOpen(true)}
      />
      <div className="flex">
        <SidebarNav
          role="admin"
          view={view}
          onNavigate={onNavigate}
          mobileOpen={mobileOpen}
          setMobileOpen={setMobileOpen}
        />
        <main className="min-w-0 flex-1 px-6 py-5">{children}</main>
      </div>
      <HelpDialog role="admin" open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

type CitizenShellProps = Omit<ShellProps, "role" | "stateLabel">;

function CitizenShell({
  view,
  title,
  scope,
  query,
  children,
  onNavigate,
  onScopeChange,
  onQueryChange,
}: CitizenShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="console min-h-screen bg-canvas text-ink">
      <AppHeader
        title={title}
        scope={scope}
        query={query}
        onScopeChange={onScopeChange}
        onQueryChange={onQueryChange}
        onOpenMenu={() => setMobileOpen(true)}
        onHelp={() => setHelpOpen(true)}
      />
      <div className="flex">
        <SidebarNav
          role="citizen"
          view={view}
          onNavigate={onNavigate}
          mobileOpen={mobileOpen}
          setMobileOpen={setMobileOpen}
        />
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6">{children}</main>
      </div>
      <HelpDialog role="citizen" open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

export function Shell({
  role,
  view,
  title,
  stateLabel,
  scope,
  query,
  children,
  onNavigate,
  onScopeChange,
  onQueryChange,
}: ShellProps) {
  if (role === "citizen") {
    return (
      <CitizenShell
        view={view}
        title={title}
        scope={scope}
        query={query}
        onNavigate={onNavigate}
        onScopeChange={onScopeChange}
        onQueryChange={onQueryChange}
      >
        {children}
      </CitizenShell>
    );
  }
  return (
    <AdminShell
      view={view}
      title={title}
      stateLabel={stateLabel}
      scope={scope}
      query={query}
      onNavigate={onNavigate}
      onScopeChange={onScopeChange}
      onQueryChange={onQueryChange}
    >
      {children}
    </AdminShell>
  );
}
