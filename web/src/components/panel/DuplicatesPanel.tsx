// Base del panel: portado de src/coordinator/web/panel.html (duplicateReviewContent y outbox-list, 711-712)
import { Badge, Card } from "../tremor";
import type { DuplicatesPanelProps } from "./contracts";

const BADGE_VARIANT: Record<string, "default" | "warning" | "simulated"> = {
  "2 focos distintos": "warning",
  "Revisión humana": "warning",
};

function badgeVariant(badge: string): "default" | "warning" | "simulated" {
  if (badge.includes("reportes")) return "default";
  return BADGE_VARIANT[badge] ?? "warning";
}

export function DuplicatesPanel({ blocks, notices }: DuplicatesPanelProps) {
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">
        Duplicados y bandeja de avisos
      </h2>

      <h3 className="mt-4 text-sm font-semibold text-ink">Duplicados y revisión</h3>
      <div id="duplicateReviewContent" className="mt-2 space-y-2">
        {blocks.length === 0 ? (
          <p className="text-sm text-muted">Sin duplicados que revisar.</p>
        ) : (
          blocks.map((block, index) => (
            <div
              key={`${block.kind}-${block.sectorId}-${index}`}
              className="rounded-md border border-line bg-sunken p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={badgeVariant(block.badge)}>{block.badge}</Badge>
                <span className="text-sm font-semibold text-ink">{block.title}</span>
              </div>
              <p className="mt-1 text-sm text-muted">{block.detail}</p>
            </div>
          ))
        )}
      </div>

      <h3 className="mt-5 text-sm font-semibold text-ink">Bandeja de avisos</h3>
      <p className="mt-1 text-xs text-muted">
        Avisos a residentes solo en la bandeja{" "}
        <Badge variant="simulated">SIMULATED</Badge> de SQLite, y solo tras aprobación
        humana. No hay WhatsApp real.
      </p>
      <div id="outbox-list" className="mt-2 space-y-2">
        {notices.length === 0 ? (
          <p className="text-sm text-muted">
            Sin avisos. Tras aprobar, se encolan avisos SIMULATED.
          </p>
        ) : (
          notices.map((notice, index) => (
            <div
              key={`${notice.sector_id}-${index}`}
              className="rounded-md border border-line bg-sunken p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="simulated">SIMULATED</Badge>
                <span className="text-sm font-semibold text-ink">
                  {notice.sector_id}
                </span>
                <Badge variant={notice.status === "QUEUED" ? "default" : "neutral"}>
                  {notice.status}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted">{notice.message}</p>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
