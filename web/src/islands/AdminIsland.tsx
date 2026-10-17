import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  getContext,
  postDecision,
  postPreload,
  postReports,
  postReset,
  postReview,
  type Cluster,
  type CoordinatorSnapshot,
  type PlanState,
  type PriorityResult,
} from "../lib/api";

const WORKFLOW_STEPS: { state: Exclude<PlanState, null>; label: string }[] = [
  { state: "borrador", label: "Borrador" },
  { state: "pendiente", label: "Pendiente" },
  { state: "aprobado", label: "Aprobado" },
  { state: "rechazado", label: "Rechazado" },
  { state: "error_parcial", label: "Error parcial" },
];

const APPROVE_DIALOG_TEXT = "Encola avisos SIMULATED. No envía WhatsApp.";

function isTerminalState(state: PlanState): boolean {
  return (
    state === "aprobado" ||
    state === "rechazado" ||
    state === "error_parcial"
  );
}

function isPrimaryButton(id: string, state: PlanState): boolean {
  if (isTerminalState(state)) return false;
  if (state === "pendiente") return id === "btn-aprobar";
  if (state === "borrador" || state === null) return id === "btn-revisar";
  return false;
}

function buttonClass(primary: boolean, disabled: boolean): string {
  const base =
    "rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-50";
  if (primary) {
    return `${base} bg-water text-white`;
  }
  return `${base} border border-line bg-surface text-ink`;
}

function formatHours(hours: number | null): string {
  if (hours == null) return "sin dato";
  return `${hours} h`;
}

function formatAffected(count: number | null): string {
  if (count == null) return "sin dato";
  return String(count);
}

function isScoringFactor(factor: string): boolean {
  const f = factor.toLowerCase();
  if (f.includes("report_count") || f.includes("complaint")) return false;
  if (f.includes("queja") || f.includes("volumen") || f.includes("repet")) {
    return false;
  }
  return true;
}

function priorityForCluster(
  priorities: PriorityResult[],
  clusterId: string,
): PriorityResult | undefined {
  return priorities.find((p) => p.cluster_id === clusterId);
}

function groupRoutes(snapshot: CoordinatorSnapshot | null) {
  if (!snapshot?.plan?.assignments?.length) return [];
  const byVehicle = new Map<
    string,
    { sector_id: string; order: number; volume_liters: number }[]
  >();
  const order: string[] = [];
  for (const a of snapshot.plan.assignments) {
    if (!byVehicle.has(a.vehicle_id)) {
      byVehicle.set(a.vehicle_id, []);
      order.push(a.vehicle_id);
    }
    byVehicle.get(a.vehicle_id)!.push({
      sector_id: a.sector_id,
      order: a.order,
      volume_liters: a.volume_liters,
    });
  }
  return order.map((vehicleId) => ({
    vehicleId,
    stops: (byVehicle.get(vehicleId) ?? []).sort((x, y) => x.order - y.order),
  }));
}

export default function AdminIsland() {
  const [snapshot, setSnapshot] = useState<CoordinatorSnapshot | null>(null);
  const [actor, setActor] = useState("coordinador");
  const [comment, setComment] = useState("");
  const [reportsText, setReportsText] = useState("");
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(
    null,
  );
  const [approvalMessage, setApprovalMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const approveDialogRef = useRef<HTMLDialogElement>(null);

  const state: PlanState = snapshot?.state ?? null;

  const reportLines = useMemo(
    () =>
      reportsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    [reportsText],
  );

  const selectedPriority = useMemo(() => {
    if (!snapshot || !selectedClusterId) return null;
    return priorityForCluster(snapshot.priorities, selectedClusterId) ?? null;
  }, [snapshot, selectedClusterId]);

  const routes = useMemo(() => groupRoutes(snapshot), [snapshot]);

  const applySnapshot = useCallback((data: CoordinatorSnapshot) => {
    setSnapshot(data);
    setApprovalMessage("");
  }, []);

  const runAction = useCallback(
    async (action: () => Promise<CoordinatorSnapshot>) => {
      setBusy(true);
      try {
        const data = await action();
        applySnapshot(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error desconocido";
        setApprovalMessage(msg);
      } finally {
        setBusy(false);
      }
    },
    [applySnapshot],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setBusy(true);
      try {
        const data = await getContext();
        if (!cancelled) applySnapshot(data);
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Error desconocido";
          setApprovalMessage(msg);
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applySnapshot]);

  const planId = snapshot?.plan?.plan_id ?? "";

  const confirmApprove = () => {
    if (!planId) {
      setApprovalMessage("No hay un plan cargado.");
      approveDialogRef.current?.close();
      return;
    }
    approveDialogRef.current?.close();
    void runAction(() =>
      postDecision({
        plan_id: planId,
        action: "APPROVE",
        actor: actor.trim() || "coordinador",
        comment: comment.trim() || undefined,
      }),
    );
  };

  const onReject = () => {
    if (!planId) {
      setApprovalMessage("No hay un plan cargado.");
      return;
    }
    void runAction(() =>
      postDecision({
        plan_id: planId,
        action: "REJECT",
        actor: actor.trim() || "coordinador",
        comment: comment.trim() || undefined,
      }),
    );
  };

  const onCorrect = () => {
    if (!planId) {
      setApprovalMessage("No hay un plan cargado.");
      return;
    }
    if (!comment.trim()) {
      setApprovalMessage("Corregir requiere un comentario.");
      return;
    }
    void runAction(() =>
      postDecision({
        plan_id: planId,
        action: "CORRECT",
        actor: actor.trim() || "coordinador",
        comment: comment.trim(),
      }),
    );
  };

  const onReview = () => {
    void runAction(() => postReview());
  };

  const onPreload = () => {
    void runAction(() => postPreload());
  };

  const onProcessTexts = () => {
    if (!reportLines.length) return;
    void runAction(() => postReports(reportLines));
  };

  const onReset = () => {
    void runAction(() => postReset());
  };

  const onSelectCluster = (cluster: Cluster) => {
    setSelectedClusterId(cluster.cluster_id);
  };

  const breakdownItems =
    selectedPriority?.breakdown.filter((row) =>
      isScoringFactor(row.factor),
    ) ?? [];

  const unserved = snapshot?.plan?.unserved_demand ?? [];
  const traces = snapshot?.traces ?? [];
  const outbox = snapshot?.outbox_notices ?? [];
  const clusters = snapshot?.clusters ?? [];

  const renderStep = (step: (typeof WORKFLOW_STEPS)[number]) => {
    const isCurrent = state === step.state;
    const colorClass =
      step.state === "borrador"
        ? "text-draft"
        : step.state === "pendiente"
          ? "text-pending"
          : step.state === "aprobado"
            ? "text-approved"
            : step.state === "rechazado"
              ? "text-rejected"
              : "text-partial";
    return (
      <li
        key={step.state}
        aria-current={isCurrent ? "step" : undefined}
        className={`rounded-lg border border-line bg-surface px-3 py-2 text-center text-sm ${isCurrent ? "ring-2 ring-water/30" : ""}`}
      >
        <span className={`block font-semibold ${colorClass}`}>
          {step.label}
        </span>
      </li>
    );
  };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <div
        className="border-b border-line bg-synthetic/10 px-4 py-3 text-sm text-ink"
        role="status"
      >
        Datos sintéticos (SYNTHETIC_DEMO). Los avisos son SIMULATED y no envían
        WhatsApp.
      </div>

      <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Centro de coordinación
            </p>
            <h1 className="font-display text-2xl font-bold text-navy">
              AguaJusta Oeste
            </h1>
            <p className="mt-1 text-sm text-muted">
              Prioridad{" "}
              <strong className="text-ink">priority-v1</strong> · el volumen de
              quejas no es un factor de puntuación.
            </p>
          </div>
          <button
            type="button"
            id="reset-session"
            className={buttonClass(false, busy)}
            disabled={busy}
            onClick={onReset}
          >
            Reiniciar ciclo
          </button>
        </header>

        <section
          className="rounded-xl border border-line bg-info/5 px-4 py-3 text-sm"
          aria-label="Canal de avisos"
        >
          <span className="mr-2 inline-flex rounded-full bg-simulated/10 px-2 py-0.5 text-xs font-semibold text-simulated">
            SIMULATED
          </span>
          Bandeja simulada: los avisos no salen por WhatsApp ni Telegram.
        </section>

        <section aria-label="Estado del plan">
          <h2 className="mb-2 text-sm font-semibold text-muted">
            Estado del plan
          </h2>
          {state === null ? (
            <p className="mb-2 text-sm text-muted">Sin plan</p>
          ) : null}
          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {WORKFLOW_STEPS.map(renderStep)}
          </ol>
        </section>

        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 font-display text-lg font-semibold">
            Carga de reportes
          </h2>
          <label
            htmlFor="reports-input"
            className="mb-1 block text-sm text-muted"
          >
            Un reporte por línea
          </label>
          <textarea
            id="reports-input"
            rows={4}
            className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
            placeholder="48 horas sin agua y 15 personas por el chino de Vista Alegre"
            value={reportsText}
            onChange={(e) => setReportsText(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              id="load-reports"
              className={buttonClass(false, busy)}
              disabled={busy}
              onClick={onPreload}
            >
              Cargar lote
            </button>
            {reportLines.length > 0 ? (
              <button
                type="button"
                className={buttonClass(false, busy)}
                disabled={busy}
                onClick={onProcessTexts}
              >
                Procesar textos
              </button>
            ) : null}
          </div>
        </section>

        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 font-display text-lg font-semibold">
            Clusters consolidados
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-line text-muted">
                  <th className="py-2 pr-4 font-medium">Sector</th>
                  <th className="py-2 pr-4 font-medium">Reportes</th>
                  <th className="py-2 pr-4 font-medium">Horas</th>
                  <th className="py-2 font-medium">Afectados</th>
                </tr>
              </thead>
              <tbody>
                {clusters.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-muted">
                      Sin clusters. Cargue un lote o procese textos.
                    </td>
                  </tr>
                ) : (
                  clusters.map((c) => (
                    <tr
                      key={c.cluster_id}
                      className={`cursor-pointer border-b border-line/60 hover:bg-canvas ${selectedClusterId === c.cluster_id ? "bg-water-soft/40" : ""}`}
                      onClick={() => onSelectCluster(c)}
                    >
                      <td className="py-2 pr-4 font-mono text-xs">
                        {c.sector_id}
                      </td>
                      <td className="py-2 pr-4">{c.report_count}</td>
                      <td className="py-2 pr-4">
                        {formatHours(c.max_duration_hours)}
                      </td>
                      <td className="py-2">
                        {formatAffected(c.estimated_affected_count)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 rounded-lg border border-line bg-canvas p-4">
            <h3 className="text-sm font-semibold">Desglose priority-v1</h3>
            {!selectedPriority ? (
              <p className="mt-2 text-sm text-muted">
                Seleccione un cluster para ver factores, puntos y explicación.
              </p>
            ) : (
              <>
                <p className="mt-2 text-sm">
                  Puntuación:{" "}
                  <strong>{selectedPriority.score.toFixed(1)}</strong> ·{" "}
                  {selectedPriority.formula_version}
                </p>
                <ul className="mt-3 space-y-2">
                  {breakdownItems.length === 0 ? (
                    <li className="text-sm text-muted">Sin desglose.</li>
                  ) : (
                    breakdownItems.map((row) => (
                      <li
                        key={`${row.factor}-${row.reason}`}
                        className="rounded border border-line bg-surface px-3 py-2 text-sm"
                      >
                        <span className="font-medium">{row.factor}</span>
                        <span className="text-muted"> · {row.points} pts</span>
                        {row.reason ? (
                          <p className="text-muted">{row.reason}</p>
                        ) : null}
                      </li>
                    ))
                  )}
                </ul>
                <p className="mt-3 text-sm text-muted">
                  {selectedPriority.explanation}
                </p>
              </>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 font-display text-lg font-semibold">
            Rutas propuestas
          </h2>
          <div id="plan-routes" className="space-y-4">
            {routes.length === 0 ? (
              <p className="text-sm text-muted">
                Cargue el lote operativo para ver rutas OR-Tools.
              </p>
            ) : (
              routes.map(({ vehicleId, stops }) => (
                <article
                  key={vehicleId}
                  className="rounded-lg border border-line bg-canvas p-3"
                >
                  <h3 className="font-semibold">{vehicleId}</h3>
                  <ol className="mt-2 space-y-1 text-sm">
                    {stops.map((stop) => (
                      <li key={`${vehicleId}-${stop.order}-${stop.sector_id}`}>
                        {stop.order}. {stop.sector_id} — {stop.volume_liters}{" "}
                        L
                      </li>
                    ))}
                  </ol>
                </article>
              ))
            )}
          </div>

          <div className="mt-4">
            <h3 className="text-sm font-semibold">Demanda no atendida</h3>
            {unserved.length === 0 ? (
              <p className="mt-1 text-sm text-muted">
                Sin sectores pendientes en el plan.
              </p>
            ) : (
              <ul className="mt-2 list-disc pl-5 text-sm">
                {unserved.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 font-display text-lg font-semibold">
            Supervisión humana
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label
                htmlFor="actor-input"
                className="mb-1 block text-sm text-muted"
              >
                Coordinador
              </label>
              <input
                id="actor-input"
                type="text"
                className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                value={actor}
                onChange={(e) => setActor(e.target.value)}
              />
            </div>
            <div>
              <label
                htmlFor="comment-input"
                className="mb-1 block text-sm text-muted"
              >
                Comentario
              </label>
              <textarea
                id="comment-input"
                rows={2}
                className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                placeholder="Obligatorio al corregir el plan"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              id="btn-revisar"
              className={buttonClass(isPrimaryButton("btn-revisar", state), busy)}
              disabled={busy || state !== "borrador"}
              onClick={onReview}
            >
              Enviar a revisión
            </button>
            <button
              type="button"
              id="btn-aprobar"
              className={buttonClass(isPrimaryButton("btn-aprobar", state), busy)}
              disabled={busy || state !== "pendiente"}
              onClick={() => approveDialogRef.current?.showModal()}
            >
              Aprobar plan
            </button>
            <button
              type="button"
              id="btn-rechazar"
              className={buttonClass(false, busy)}
              disabled={busy || state !== "pendiente"}
              onClick={onReject}
            >
              Rechazar
            </button>
            <button
              type="button"
              id="btn-corregir"
              className={buttonClass(false, busy)}
              disabled={busy || state !== "pendiente"}
              onClick={onCorrect}
            >
              Corregir plan
            </button>
          </div>

          <p
            id="approvalMessage"
            className="mt-3 min-h-[1.25rem] text-sm text-rejected"
            aria-live="polite"
          >
            {approvalMessage}
          </p>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-line bg-surface p-4">
            <h2 className="mb-3 font-display text-lg font-semibold">
              Trazabilidad agéntica
            </h2>
            <div
              id="agentTraceList"
              className="space-y-2 text-sm"
              aria-live="polite"
            >
              {traces.length === 0 ? (
                <p className="text-muted">
                  Todavía no hay trazas. Cargue un lote para ver ingesta,
                  prioridad y solver.
                </p>
              ) : (
                traces.map((t) => (
                  <div
                    key={t.trace_id}
                    className="rounded border border-line bg-canvas px-3 py-2"
                  >
                    <p>
                      <strong>{t.actor}</strong> · {t.action}
                    </p>
                    <p className="text-muted">{t.output_summary}</p>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="rounded-xl border border-line bg-surface p-4">
            <h2 className="mb-3 font-display text-lg font-semibold">
              Bandeja de avisos
            </h2>
            <div id="outbox-list" className="space-y-2 text-sm">
              {outbox.length === 0 ? (
                <p className="text-muted">
                  Sin avisos encolados. Tras aprobar aparecerán entradas{" "}
                  SIMULATED.
                </p>
              ) : (
                outbox.map((n, idx) => (
                  <div
                    key={`${n.sector_id}-${idx}`}
                    className="rounded border border-line bg-canvas px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs">{n.sector_id}</span>
                      <span className="rounded-full bg-simulated/10 px-2 py-0.5 text-xs font-semibold text-simulated">
                        SIMULATED
                      </span>
                      <span className="text-muted">{n.status}</span>
                    </div>
                    <p className="mt-1">{n.message}</p>
                    <p className="text-xs text-muted">Canal: {n.channel}</p>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>

      <dialog
        ref={approveDialogRef}
        className="max-w-md rounded-xl border border-line bg-surface p-6 text-ink shadow-lg backdrop:bg-navy/40"
      >
        <p className="text-sm">{APPROVE_DIALOG_TEXT}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className={buttonClass(false, false)}
            onClick={() => approveDialogRef.current?.close()}
          >
            Cancelar
          </button>
          <button
            type="button"
            className={buttonClass(true, false)}
            onClick={confirmApprove}
          >
            Confirmar
          </button>
        </div>
      </dialog>
    </div>
  );
}
