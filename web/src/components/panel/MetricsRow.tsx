import { Badge, Card } from "../tremor";
import type { MetricsRowProps, PlanStateLabel } from "./contracts";

function planBadgeVariant(label: PlanStateLabel) {
  if (label === "Pendiente" || label === "Borrador") return "warning" as const;
  if (label === "Aprobado") return "success" as const;
  if (label === "Rechazado") return "error" as const;
  if (label === "Error parcial") return "partial" as const;
  return "neutral" as const;
}

export function MetricsRow({ metrics, planStateLabel, hasPlan }: MetricsRowProps) {
  const planCount = hasPlan ? 1 : 0;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card>
        <p className="text-xs font-medium uppercase tracking-wide text-muted">
          Reportes
        </p>
        <p
          id="metricReports"
          className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
        >
          {metrics.reports}
        </p>
      </Card>

      <Card>
        <p className="text-xs font-medium uppercase tracking-wide text-muted">
          Sectores afectados
        </p>
        <p
          id="metricSectors"
          className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
        >
          {metrics.sectors}
        </p>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">
            Plan
          </p>
          <Badge variant={planBadgeVariant(planStateLabel)}>{planStateLabel}</Badge>
        </div>
        <p
          id="metricPending"
          className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
        >
          {planCount}
        </p>
        <p className="mt-1 text-xs text-muted">{planStateLabel}</p>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">
            Despachos
          </p>
          <Badge variant="simulated">SIMULATED</Badge>
        </div>
        <p
          id="metricDispatched"
          className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
        >
          {metrics.dispatched}
        </p>
      </Card>
    </div>
  );
}
