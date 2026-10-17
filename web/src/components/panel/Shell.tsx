// Base del panel: portado de src/coordinator/web/panel.html
// El rol ya no se cambia: se es. Cada portal tiene su propio cromo y navegación.
// Admin y ciudadano comparten la cabecera oscura (AppHeader) y el menú lateral
// (SidebarNav). El ámbito es distrito (Arraiján / La Chorrera).
import { useState } from "react";
import type {
  DistrictScope,
  PanelView,
  ShellProps,
} from "./contracts";
import { HelpDialog } from "./HelpDialog";
import { AppHeader } from "./AppHeader";
import { SidebarNav } from "./SidebarNav";

type AdminShellProps = Omit<ShellProps, "role"> & {
  scope?: DistrictScope;
  onScopeChange?: (value: DistrictScope) => void;
};

function AdminShell({
  view,
  title,
  stateLabel,
  scope,
  children,
  onNavigate,
  onScopeChange,
}: AdminShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const handleNavigate = (next: PanelView) => {
    onNavigate(next);
    setMobileOpen(false);
  };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <SidebarNav
        role="admin"
        view={view}
        onNavigate={handleNavigate}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />

      <div className="lg:ml-[280px]">
        <AppHeader
          title={title}
          stateLabel={stateLabel}
          scope={scope}
          onScopeChange={onScopeChange}
          onOpenMenu={() => setMobileOpen(true)}
          onHelp={() => setHelpOpen(true)}
        />

        <main className="mx-auto max-w-[1600px] p-6">{children}</main>
      </div>

      <HelpDialog role="admin" open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

type CitizenShellProps = Omit<ShellProps, "role" | "stateLabel"> & {
  scope?: DistrictScope;
  onScopeChange?: (value: DistrictScope) => void;
};

function CitizenShell({
  view,
  title,
  scope,
  children,
  onNavigate,
  onScopeChange,
}: CitizenShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const handleNavigate = (next: PanelView) => {
    onNavigate(next);
    setMobileOpen(false);
  };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <SidebarNav
        role="citizen"
        view={view}
        onNavigate={handleNavigate}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />

      <div className="lg:ml-[280px]">
        <AppHeader
          title={title}
          scope={scope}
          onScopeChange={onScopeChange}
          onOpenMenu={() => setMobileOpen(true)}
          onHelp={() => setHelpOpen(true)}
        />

        <main className="mx-auto max-w-[1080px] p-4 sm:p-6 lg:p-8">
          {children}
        </main>
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
  children,
  onNavigate,
  onScopeChange,
}: ShellProps) {
  if (role === "citizen") {
    return (
      <CitizenShell
        view={view}
        title={title}
        scope={scope}
        onNavigate={onNavigate}
        onScopeChange={onScopeChange}
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
      onNavigate={onNavigate}
      onScopeChange={onScopeChange}
    >
      {children}
    </AdminShell>
  );
}
