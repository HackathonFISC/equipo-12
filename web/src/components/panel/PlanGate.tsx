import { useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Tracker,
  type TrackerBlockProps,
} from "../tremor";
import type { PlanGateProps, PlanStateLabel } from "./contracts";
import type { PlanState } from "../../lib/api";

const APPROVE_DIALOG_TEXT =
  "Encola avisos SIMULATED. No envía WhatsApp a residentes.";

const STEPS: {
  state: Exclude<PlanState, null>;
  label: PlanStateLabel;
  idle: string;
}[] = [
  { state: "borrador", label: "Borrador", idle: "neutral" },
  { state: "pendiente", label: "Pendiente", idle: "warning" },
  { state: "aprobado", label: "Aprobado", idle: "success" },
  { state: "rechazado", label: "Rechazado", idle: "error" },
  { state: "error_parcial", label: "Error parcial", idle: "partial" },
];

const IDLE_COLOR: Record<string, string> = {
  neutral: "bg-draft",
  warning: "pending",
  success: "approved",
  error: "rejected",
  partial: "partial",
};

function stateBadgeVariant(state: PlanState) {
  if (state === "pendiente") return "warning" as const;
  if (state === "aprobado") return "success" as const;
  if (state === "rechazado") return "error" as const;
  if (state === "error_parcial") return "partial" as const;
  if (state === "borrador") return "warning" as const;
  return "neutral" as const;
}

function trackerData(state: PlanState): TrackerBlockProps[] {
  return STEPS.map((step) => ({
    key: step.state,
    tooltip: step.label,
    color:
      state === step.state ? "bg-[#312d2a]" : (IDLE_COLOR[step.idle] ?? step.idle),
  }));
}

export function PlanGate({
  state,
  stateLabel,
  liters,
  vehicles,
  stops,
  routes,
  unserved,
  silent,
  actor,
  comment,
  message,
  execution,
  busy,
  onActor,
  onComment,
  onReview,
  onApprove,
  onReject,
  onCorrect,
}: PlanGateProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const draftLike = state === null || state === "borrador";
  const pending = state === "pendiente";
  const reviewEnabled = !busy && draftLike;
  const decideEnabled = !busy && pending;

  function openConfirm() {
    setConfirmOpen(true);
    dialogRef.current?.showModal();
  }

  function closeConfirm() {
    setConfirmOpen(false);
    dialogRef.current?.close();
  }

  function confirmApprove() {
    closeConfirm();
    onApprove();
  }

  return (
    <Card className="ring-1 ring-[#e5e3e2]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold text-ink">
          Plan de distribución
        </h2>
        <Badge id="planStatus" variant={stateBadgeVariant(state)}>
          {stateLabel}
        </Badge>
      </div>

      <Tracker className="mt-4" data={trackerData(state)} aria-label="Estado del plan" />

      <div className="mt-4 grid grid-cols-3 gap-3 rounded-md bg-sunken p-3">
        <div>
          <p className="text-xs text-muted">Litros</p>
          <p
            id="planTotalLiters"
            className="font-display text-xl font-bold tabular-nums"
          >
            {liters.toLocaleString("es-PA")}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Cisternas</p>
          <p
            id="planVehiclesCount"
            className="font-display text-xl font-bold tabular-nums"
          >
            {vehicles}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Paradas</p>
          <p
            id="planStopsCount"
            className="font-display text-xl font-bold tabular-nums"
          >
            {stops}
          </p>
        </div>
      </div>

      <div id="plan-routes" className="mt-4 space-y-3">
        {routes.length === 0 ? (
          <p className="text-sm text-muted">Ejecute el plan para ver rutas</p>
        ) : (
          routes.map((route) => (
            <Card key={route.vehicleId} className="bg-sunken p-3 shadow-none">
              <p className="font-semibold text-ink">{route.vehicleId}</p>
              <p className="mt-1 text-sm text-muted">{route.names}</p>
              <p className="mt-2 text-sm font-medium tabular-nums">
                {route.liters.toLocaleString("es-PA")} L · {route.stops} paradas
              </p>
            </Card>
          ))
        )}
      </div>

      <div id="unserved-chips" className="mt-4 flex flex-wrap gap-2">
        {unserved.length === 0 ? (
          <span className="text-sm text-muted">Sin sectores pendientes</span>
        ) : (
          unserved.map((name) => (
            <Badge key={name} variant="warning">
              {name}
            </Badge>
          ))
        )}
      </div>

      <div id="silent-sectors-chips" className="mt-3 flex flex-wrap gap-2">
        {silent.length === 0 ? (
          <span className="text-sm text-muted">Sin sectores silenciosos</span>
        ) : (
          silent.map((name) => (
            <Badge key={name} variant="neutral">
              {name} silencioso
            </Badge>
          ))
        )}
      </div>

      <div className="mt-5 rounded-md border border-line bg-water-soft/40 p-4">
        <p className="text-sm font-semibold text-ink">Compuerta humana</p>
        <p className="mt-1 text-xs text-muted">
          La propuesta no encola avisos <Badge variant="simulated">SIMULATED</Badge>{" "}
          hasta revisión humana.
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <label className="block text-sm text-muted" htmlFor="actor-input">
            Coordinador
            <input
              id="actor-input"
              type="text"
              value={actor}
              onChange={(event) => onActor(event.target.value)}
              className="mt-1 h-11 w-full rounded-md border border-line bg-surface px-3 text-sm text-ink"
            />
          </label>
          <label className="block text-sm text-muted" htmlFor="comment-input">
            Comentario
            <textarea
              id="comment-input"
              rows={2}
              value={comment}
              onChange={(event) => onComment(event.target.value)}
              placeholder="Obligatorio al corregir el plan"
              className="mt-1 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            id="btn-revisar"
            variant="secondary"
            disabled={!reviewEnabled}
            onClick={onReview}
          >
            Enviar a revisión
          </Button>
          <Button
            id="btn-aprobar"
            variant="primary"
            disabled={!decideEnabled}
            onClick={openConfirm}
          >
            Aprobar plan
          </Button>
          <Button
            id="btn-rechazar"
            variant="destructive"
            disabled={!decideEnabled}
            onClick={onReject}
          >
            Rechazar
          </Button>
          <Button
            id="btn-corregir"
            variant="light"
            disabled={!decideEnabled}
            onClick={onCorrect}
          >
            Corregir plan
          </Button>
        </div>
      </div>

      <div
        id="approvalMessage"
        role="status"
        aria-live="polite"
        className="mt-3 min-h-[1.25rem] text-sm text-muted"
      >
        {message}
      </div>

      <div id="execution" className="mt-1 text-xs text-muted">
        {execution ? `Auditoría ${execution.audit_id}` : null}
      </div>

      <dialog
        ref={dialogRef}
        data-open={confirmOpen ? "true" : "false"}
        className="max-w-md rounded-xl border border-line bg-surface p-6 text-ink shadow-lg backdrop:bg-navy/40"
        onClose={() => setConfirmOpen(false)}
      >
        <p className="text-sm">{APPROVE_DIALOG_TEXT}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={closeConfirm}>
            Cancelar
          </Button>
          <Button type="button" variant="primary" onClick={confirmApprove}>
            Confirmar
          </Button>
        </div>
      </dialog>
    </Card>
  );
}
