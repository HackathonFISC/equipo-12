import { Badge, Card } from "../tremor";
import type { MetricsRowProps } from "./contracts";

export function MetricsRow({ metrics }: MetricsRowProps) {
  const pending = metrics.pending ? 1 : 0;

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
          <Badge variant={pending ? "warning" : "neutral"}>
            {pending ? "Pendiente" : "0"}
          </Badge>
        </div>
        <p
          id="metricPending"
          className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
        >
          {pending}
        </p>
        <p className="mt-1 text-xs text-muted">pendiente 0/1</p>
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
