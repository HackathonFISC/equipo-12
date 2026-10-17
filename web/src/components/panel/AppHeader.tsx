// Cabecera a ancho completo, como la consola de referencia:
// fondo #3d3935, búsqueda #1d1c1b y el ámbito a la derecha.
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Menu, Search } from "lucide-react";
import type { DistrictScope, ShellHeaderProps } from "./contracts";

const SCOPE_LABEL: Record<DistrictScope, string> = {
  all: "Panamá Oeste",
  Arraiján: "Arraiján",
  "La Chorrera": "La Chorrera",
};

export function AppHeader({
  scope = "all",
  onScopeChange,
  onOpenMenu,
  query,
  onQueryChange,
}: ShellHeaderProps) {
  const [scopeOpen, setScopeOpen] = useState(false);
  const scopeRoot = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scopeOpen) return;
    const close = (event: MouseEvent) => {
      if (!scopeRoot.current?.contains(event.target as Node)) setScopeOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setScopeOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [scopeOpen]);

  return (
    <header className="sticky top-0 z-40 flex h-12 items-center gap-3 bg-[var(--color-header-bg)] px-3 text-[var(--color-header-text)]">
      <button
        type="button"
        className="flex size-8 items-center justify-center rounded text-white lg:hidden"
        aria-label="Abrir menú"
        onClick={onOpenMenu}
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>
      <a
        href="/"
        className="flex shrink-0 items-center gap-2 text-white no-underline"
        aria-label="AguaJusta Oeste inicio"
      >
        <span className="text-[15px] font-semibold tracking-tight">AguaJusta</span>
      </a>
      <div className="relative mx-2 hidden min-w-0 flex-1 md:block">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-header-search-muted)]"
          aria-hidden="true"
        />
        <input
          type="search"
          value={query ?? ""}
          onChange={(event) => onQueryChange?.(event.target.value)}
          placeholder="Buscar reportes, sectores y documentación"
          className="h-8 w-full rounded bg-[var(--color-header-search-bg)] pl-9 pr-3 text-sm text-white outline-none placeholder:text-[var(--color-header-search-muted)]"
        />
      </div>
      <div ref={scopeRoot} className="relative ml-auto">
        <button
          type="button"
          aria-label="Ámbito por distrito"
          aria-expanded={scopeOpen}
          aria-haspopup="menu"
          className="flex h-8 items-center gap-1 text-sm text-white"
          onClick={() => setScopeOpen((open) => !open)}
        >
          {SCOPE_LABEL[scope]}
          <ChevronDown className={`size-4 text-[#e3e0dc] ${scopeOpen ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
        {scopeOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-10 z-30 w-56 rounded bg-white py-2 text-[#1c1c1a] shadow-[0_8px_24px_rgba(28,28,26,0.16)]"
          >
            <p className="px-3 pb-1 text-xs text-[#585655]">Ámbito</p>
            {(Object.keys(SCOPE_LABEL) as DistrictScope[]).map((value) => (
              <button
                key={value}
                type="button"
                role="menuitem"
                className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-[#f6f4f3] ${value === scope ? "text-[#00688b]" : ""}`}
                onClick={() => {
                  onScopeChange?.(value);
                  setScopeOpen(false);
                }}
              >
                {SCOPE_LABEL[value]}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </header>
  );
}
