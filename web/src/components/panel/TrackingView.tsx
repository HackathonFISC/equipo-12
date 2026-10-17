// Base del panel: portado de src/coordinator/web/panel.html (#view-tracking 863-906, lookupReport 1974-2031)
import { Badge, Button, Callout, Card } from "../tremor";
import type { TrackingViewProps } from "./contracts";

export function TrackingView({
  codes,
  code,
  result,
  emptyMessage,
  onCodeChange,
  onPickCode,
}: TrackingViewProps) {
  return (
    <div className="mx-auto max-w-[900px] space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Consultar reporte
        </p>
        <h1 className="font-display text-2xl font-bold text-ink">
          Estado de una incidencia
        </h1>
      </div>

      <Card>
        <form id="trackingForm" className="flex flex-wrap gap-2" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="tracking-code" className="w-full text-sm font-semibold text-ink">
            Código del reporte
          </label>
          <input
            id="tracking-code"
            type="text"
            autoComplete="off"
            value={code}
            onChange={(event) => onCodeChange(event.target.value)}
            placeholder="Ejemplo: SYN-001"
            className="min-w-48 h-11 min-w-0 flex-1 rounded-md border border-line bg-canvas px-3 text-sm text-ink"
          />
          <Button type="button" variant="primary" onClick={() => onPickCode(code)}>
            Consultar
          </Button>
        </form>
        {codes.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {codes.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  onCodeChange(item);
                  onPickCode(item);
                }}
                className="min-h-[36px] rounded-full border border-line bg-sunken px-3 text-xs font-medium text-ink hover:bg-line"
              >
                {item}
              </button>
            ))}
          </div>
        ) : null}
      </Card>

      {result ? (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg font-semibold text-ink">{result.title}</h2>
            <Badge
              variant={
                result.planStateLabel === "Aprobado"
                  ? "success"
                  : result.planStateLabel === "Pendiente"
                    ? "warning"
                    : result.planStateLabel === "Rechazado"
                      ? "error"
                      : result.planStateLabel === "Error parcial"
                        ? "partial"
                        : "neutral"
              }
            >
              {result.planStateLabel}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted">{result.sectorName}</p>

          <div className="mt-4 grid grid-cols-3 gap-2 rounded-md bg-sunken p-3 text-center">
            <div>
              <p className="text-xs text-muted">Horas sin agua</p>
              <p className="font-display text-xl font-bold tabular-nums">{result.hours}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Afectados</p>
              <p className="font-display text-xl font-bold tabular-nums">{result.people}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Prioridad</p>
              <p className="font-display text-xl font-bold tabular-nums">{result.score}</p>
            </div>
          </div>

          <ol className="mt-4 space-y-3">
            {result.steps.map((step) => (
              <li key={step.stage} className="flex gap-3">
                <span
                  className={`mt-1.5 size-3 shrink-0 rounded-full ${step.done ? "bg-water" : "bg-simulated/40"}`}
                  aria-hidden="true"
                />
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {step.stage}
                  </p>
                  <p className="text-sm text-ink">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>

          {result.vehicle ? (
            <p className="mt-4 text-sm font-medium text-ink">
              {result.planStateLabel === "Aprobado"
                ? `Cisterna asignada: ${result.vehicle}`
                : `Propuesta de cisterna (aún sin aprobación humana): ${result.vehicle}`}
            </p>
          ) : (
            <p className="mt-4 text-sm text-muted">
              Sin cisterna asignada en el turno actual.
            </p>
          )}

          <Callout variant="neutral" title="Aviso al residente" className="mt-4">
            <Badge variant="simulated">SIMULATED</Badge>{" "}
            {result.notice ??
              "Este incidente no tiene avisos en la bandeja simulada todav\u00eda."}
          </Callout>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-muted">
            {emptyMessage ?? "Escriba un código para consultar el estado de un reporte."}
          </p>
        </Card>
      )}
    </div>
  );
}
