// Base del panel: portado de src/coordinator/web/panel.html

import { useCallback, useEffect, useState } from "react";
import { PANEL_VIEWS, type PanelView, type Role } from "../components/panel/contracts";

// El rol ya no se cambia dentro de una app: cada portal navega solo sus vistas.
const ROLE_VIEWS: Record<Role, PanelView[]> = {
  admin: ["admin", "map", "tracking"],
  citizen: ["citizen", "tracking", "map"],
};

const ROLE_PORTAL: Record<Role, string> = {
  admin: "/admin",
  citizen: "/ciudadano",
};

function isPanelView(value: string | null): value is PanelView {
  return value != null && (PANEL_VIEWS as string[]).includes(value);
}

export function usePanelNav(role: Role, initialView: PanelView) {
  const views = ROLE_VIEWS[role];
  const [view, setViewState] = useState<PanelView>(
    views.includes(initialView) ? initialView : views[0],
  );

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    if (requested == null || requested === "") return;
    if (isPanelView(requested)) {
      if (views.includes(requested)) {
        setViewState(requested);
      } else {
        // Vista del otro rol: redirige a su portal conservando el parámetro.
        const other: Role = role === "admin" ? "citizen" : "admin";
        window.location.replace(
          `${ROLE_PORTAL[other]}?view=${encodeURIComponent(requested)}`,
        );
      }
      return;
    }
    // String que no es una vista válida: cae a la primera vista del rol.
    setViewState(views[0]);
  }, [role, views]);

  const setView = useCallback((next: PanelView) => {
    setViewState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    window.history.pushState({ view: next }, "", url);
  }, []);

  return { view, setView };
}
