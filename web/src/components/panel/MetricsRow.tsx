import { Badge, Callout, Card } from "../tremor";
import type { MetricsRowProps, PlanStateLabel } from "./contracts";

function planBadgeVariant(label: PlanStateLabel) {
  if (label === "Pendiente" || label === "Borrador") return "warning" as const;
  if (label === "Aprobado") return "success" as const;
  if (label === "Rechazado") return "error" as const;
  if (label === "Error parcial") return "partial" as const;
  return "neutral" as const;
}

type ArrivalNotice = {
  variant: "warning" | "success" | "error";
  text: string;
};

function arrivalNotice(label: PlanStateLabel): ArrivalNotice | null {
  switch (label) {
    case "Borrador":
      return {
        variant: "warning",
        text: "Llegó un plan nuevo. Nadie lo ha aprobado. Léelo abajo y decide: enviarlo a revisión, aprobarlo, corregirlo o rechazarlo.",
      };
    case "Pendiente":
      return {
        variant: "warning",
        text: "Este plan está esperando tu decisión. Revísalo y apruébalo, corrígelo o recházalo.",
      };
    case "Aprobado":
      return {
        variant: "success",
        text: "Una persona ya aprobó este plan. Los avisos a los vecinos quedan escritos en esta página. No se envía WhatsApp ni SMS a los residentes.",
      };
    case "Rechazado":
      return {
        variant: "error",
        text: "Este plan fue rechazado. Los reportes siguen vigentes. Hay que armar otro reparto.",
      };
    case "Error parcial":
      return {
        variant: "warning",
        text: "El reparto quedó a medias. Revisa qué sectores no recibieron cisterna antes de decidir.",
      };
    default:
      return null;
  }
}

export function MetricsRow({ metrics, planStateLabel, hasPlan }: MetricsRowProps) {
  const planCount = hasPlan ? 1 : 0;
  const notice =
    hasPlan && planStateLabel !== "Sin plan" ? arrivalNotice(planStateLabel) : null;

  return (
    <div className="space-y-3">
      {notice ? (
        <Callout
          id="arrival-notice"
          role="status"
          aria-live="polite"
          variant={notice.variant}
          title="Aviso del plan"
        >
          {notice.text}
        </Callout>
      ) : null}
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
            <Badge variant="simulated">DEMOSTRACIÓN</Badge>
          </div>
          <p
            id="metricDispatched"
            className="font-display mt-2 text-3xl font-bold tabular-nums text-ink"
          >
            {metrics.dispatched}
          </p>
        </Card>
      </div>
    </div>
  );
}
