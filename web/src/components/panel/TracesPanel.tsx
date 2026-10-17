// Base del panel: portado de src/coordinator/web/panel.html (agentTraceList, 704-710)
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, Badge, Button } from "../tremor";
import type { TracesPanelProps } from "./contracts";
import { ConsoleWidget } from "./ConsoleWidget";

const STATUS_VARIANT: Record<string, "success" | "error" | "warning"> = {
  ok: "success",
  error: "error",
};

export function TracesPanel({ stages }: TracesPanelProps) {
  const openAll = (open: boolean) => {
    for (const el of document.querySelectorAll<HTMLDetailsElement>("#agentTraceList details")) {
      el.open = open;
    }
  };

  return (
    <ConsoleWidget
      title="Trazabilidad · Qué hizo cada agente"
      actions={[
        { label: "Contraer todas", onSelect: () => openAll(false) },
        {
          label: "Copiar folios de registro",
          onSelect: () => {
            void navigator.clipboard?.writeText(stages.map((stage) => stage.traceId).join("\n"));
          },
        },
      ]}
      footer={
        stages.length > 0 ? (
          <Button type="button" variant="secondary" onClick={() => openAll(true)}>
            Ver todas
          </Button>
        ) : null
      }
    >
    <div>
      <div className="flex items-center justify-between gap-2">
        <Badge variant="default">{stages.length} registro(s)</Badge>
      </div>
      <p className="mt-1 text-xs text-muted">
        Quién actuó, qué hizo, con qué datos y qué salió de cada intervención. Sin datos personales ni claves.
      </p>
      <div id="agentTraceList" aria-live="polite" className="mt-3">
        {stages.length === 0 ? (
          <p className="text-sm text-muted">Todavía no hay registros de actividad.</p>
        ) : (
          <Accordion>
            {stages.map((stage) => {
              const variant = STATUS_VARIANT[stage.status] ?? "warning";
              return (
                <AccordionItem key={stage.traceId}>
                  <AccordionTrigger>
                    <span className="flex min-w-0 flex-wrap items-center gap-2 pr-3">
                      <span className="truncate font-semibold">{stage.label}</span>
                      <Badge variant={variant}>
                        {stage.status === "ok" ? "Listo" : stage.status === "error" ? "Hubo un problema" : "En revisión"}
                      </Badge>
                      <span className="text-xs text-muted">folio {stage.traceId}</span>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <dl className="grid gap-2 text-sm">
                      <div>
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Qué se hizo</dt>
                        <dd className="text-ink">{stage.action}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Con qué datos</dt>
                        <dd title={stage.inputText}>{stage.inputText}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Resultado</dt>
                        <dd title={stage.outputText}>{stage.outputText}</dd>
                      </div>
                    </dl>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}
      </div>
    </div>
    </ConsoleWidget>
  );
}
