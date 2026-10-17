// Base del panel: portado de src/coordinator/web/panel.html

import { useCallback, useEffect, useState } from "react";
import { PANEL_VIEWS, type PanelView, type Role } from "../components/panel/contracts";

function isPanelView(value: string | null): value is PanelView {
  return value != null && (PANEL_VIEWS as string[]).includes(value);
}

export function usePanelNav(initialRole: Role, initialView: PanelView) {
  const [role] = useState<Role>(initialRole);
  const [view, setViewState] = useState<PanelView>(initialView);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("view");
    if (isPanelView(requested)) {
      setViewState(requested);
    }
  }, []);

  const setView = useCallback((next: PanelView) => {
    setViewState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    window.history.pushState({ view: next }, "", url);
  }, []);

  return { role, view, setView };
}
