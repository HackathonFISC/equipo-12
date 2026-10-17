// Cabecera oscura compartida (estilo consola): logo AguaJusta Oeste,
// búsqueda, selector de ámbito/distrito y menús de usuario/ayuda a la derecha.
// El ámbito es distrito (Arraiján / La Chorrera).
import { Droplet, Menu, Search } from "lucide-react";
import type { PlanStateLabel, ShellHeaderProps } from "./contracts";
import { Badge, Button, cx } from "../tremor";

const HEADER_VARIANT: Record<PlanStateLabel, "neutral" | "warning" | "success" | "error" | "partial"> = {
  "Sin plan": "neutral",
  Borrador: "neutral",
  Pendiente: "warning",
  Aprobado: "success",
  Rechazado: "error",
  "Error parcial": "partial",
};

export function AppHeader({
  title,
  stateLabel,
  scope = "all",
  onScopeChange,
  onOpenMenu,
  onHelp,
}: ShellHeaderProps) {
  const label: PlanStateLabel = stateLabel ?? "Sin plan";

  return (
    <header
      className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-[var(--color-header-border)] bg-[var(--color-header-bg)]/95 px-4 backdrop-blur-sm text-[var(--color-header-text)] lg:px-6"
    >
      {onOpenMenu ? (
        <Button
          type="button"
          variant="ghost"
          className="lg:hidden shrink-0"
          aria-label="Abrir menú"
          onClick={onOpenMenu}
        >
          <Menu className="size-5" aria-hidden="true" />
        </Button>
      ) : null}

      <a
        href="/"
        className="flex shrink-0 items-center gap-2.5 text-[var(--color-header-text)] no-underline"
        aria-label="AguaJusta Oeste inicio"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-water text-white">
          <Droplet className="size-5" aria-hidden="true" />
        </span>
        <span className="font-display text-base font-semibold tracking-tight">
          AguaJusta <span className="text-water-deep">OESTE</span>
        </span>
      </a>

      {title ? (
        <div className="breadcrumb hidden min-w-0 flex-1 items-center gap-2 text-sm lg:flex">
          <span className="text-[var(--color-header-muted)]">Panamá Oeste</span>
          <span className="text-line" aria-hidden="true">/</span>
          <strong id="breadcrumbCurrent" className="truncate font-semibold">
            {title}
          </strong>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 items-center gap-3 px-2">
        <div className="relative min-w-[220px]">
          <Search
            className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-[var(--color-header-search-muted)] pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Buscar reportes, sectores…"
            className="w-full rounded-md border border-[var(--color-header-search-border)] bg-[var(--color-header-search-bg)] px-3 py-1.5 pl-9 text-sm text-[var(--color-header-search-text)] placeholder-[var(--color-header-search-muted)] focus:border-[var(--color-header-search-focus)] focus:outline-none transition-colors"
          />
        </div>

        <select
          value={scope}
          onChange={(e) => onScopeChange?.(e.target.value as "all" | "Arraiján" | "La Chorrera")}
          className="rounded-md border border-[var(--color-header-border)] bg-[var(--color-header-bg)] px-3 py-1.5 text-sm text-[var(--color-header-text)] focus:border-[var(--color-header-search-focus)] focus:outline-none"
          aria-label="Ámbito por distrito"
        >
          <option value="all">Todos los distritos</option>
          <option value="Arraiján">Arraiján</option>
          <option value="La Chorrera">La Chorrera</option>
        </select>
      </div>

      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 sm:gap-3">
        {stateLabel != null && (
          <Badge id="status-badge" variant={HEADER_VARIANT[label]}>
            {label}
          </Badge>
        )}

        <Button
          id="helpButton"
          type="button"
          variant="secondary"
          className="min-h-[36px] min-w-[36px] px-2.5"
          aria-label="Ayuda"
          onClick={onHelp}
        >
          ?
        </Button>
      </div>
    </header>
  );
}
