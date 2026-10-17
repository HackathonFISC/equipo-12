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
          title="Ingesta · Recibe y ordena tu reporte"
          lines={[
            { label: "Sector", value: sector },
            { label: "Horas sin agua", value: hours },
            { label: "Personas afectadas", value: people },
            { label: "Necesidad especial", value: vulnerabilities || "ninguna indicada" },
          ]}
        />
        <AgentCard
          title="Evaluación · Mide la urgencia del caso"
          lines={[
            { label: "Caso agrupado", value: clusterId ? "sí, unido a reportes del mismo lugar" : "todavía no" },
            { label: "Urgencia (0 a 100)", value: score },
            { label: "Lo que no pudimos confirmar", value: uncertainties || "nada: los datos alcanzan" },
          ]}
        />
        <AgentCard
          title="Planificación · Propone el reparto de cisternas"
          lines={[
            { label: "Cómo va", value: "todavía lo revisa una persona de la coordinación" },
          ]}
        />
      </div>

      <p className="mt-3 rounded-md bg-sunken p-3 text-sm text-ink">
        <strong>Guarda tu código: {reportId}.</strong> Es tu llave para consultar.
        En esta demostración <strong>no te llegará ningún mensaje por WhatsApp ni por
        teléfono</strong>: para saber si tu sector recibe cisterna, entra a «Consultar
        mi reporte» con ese código. El aviso de tu sector aparecerá ahí cuando la
        coordinación apruebe el reparto.
      </p>
      <p className="mt-3 text-xs text-muted">
        La urgencia se calcula con una fórmula fija (horas sin agua, personas y
        vulnerabilidad): reportar lo mismo muchas veces no la sube. Ningún programa
        aprueba el reparto: lo decide una persona.
      </p>
      <div className="mt-4 flex justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}
