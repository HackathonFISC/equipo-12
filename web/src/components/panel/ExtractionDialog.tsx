// Base del panel: portado de src/coordinator/web/panel.html (aiExtractionDialog 934-944, pipeline de 3 agentes)
import { Badge, Button, Dialog } from "../tremor";
import type { ExtractionDialogProps } from "./contracts";

function AgentCard({
  title,
  lines,
}: {
  title: string;
  lines: { label: string; value: string }[];
}) {
  return (
    <div className="rounded-md border border-line bg-sunken p-3">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <dl className="mt-2 space-y-1 text-sm">
        {lines.map((line) => (
          <div key={line.label} className="flex justify-between gap-2">
            <dt className="text-muted">{line.label}</dt>
            <dd className="text-right font-medium text-ink">{line.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ExtractionDialog({
  open,
  reportId,
  sector,
  place,
  hours,
  people,
  vulnerabilities,
  uncertainties,
  clusterId,
  score,
  onClose,
}: ExtractionDialogProps) {
  return (
    <Dialog id="aiExtractionDialog" open={open} onOpenChange={(next) => !next && onClose()} aria-label="Resultado del análisis">
      <h2 className="font-display text-xl font-semibold text-ink">Resultado del análisis</h2>
      <p className="mt-1 text-sm text-muted">
        Reporte <code className="rounded bg-sunken px-1.5 py-0.5 text-xs">{reportId}</code> ·{" "}
        {place || sector}
      </p>

      <div className="mt-3 space-y-2">
        <AgentCard
          title="Agente 1 · Ingesta"
          lines={[
            { label: "Sector", value: sector },
            { label: "Horas", value: hours },
            { label: "Afectados", value: people },
            { label: "Vulnerabilidad", value: vulnerabilities || "ninguna" },
          ]}
        />
        <AgentCard
          title="Agente 2 · Evaluación"
          lines={[
            { label: "Cluster", value: clusterId || "—" },
            { label: "Prioridad", value: score },
            { label: "Incertidumbre", value: uncertainties || "sin datos" },
          ]}
        />
        <AgentCard
          title="Agente 3 · Planificación"
          lines={[
            { label: "Estado del plan", value: "ver panel de coordinación" },
          ]}
        />
      </div>

      <p className="mt-3 text-xs text-muted">
        El puntaje es determinístico (priority-v1). Ningún agente aprueba el plan: la
        compuerta es humana.
      </p>
      <div className="mt-4 flex justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}
