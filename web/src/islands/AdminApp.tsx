// App del centro de coordinación: métricas, compuerta humana, trazas y mapa
// operativo. Portado del PanelApp.tsx anterior (misma lógica, rol admin fijo).
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Callout, Card } from "../components/tremor";
import { Shell } from "../components/panel/Shell";
import { Toast } from "../components/panel/Toast";
import { MetricsRow } from "../components/panel/MetricsRow";
import { IncidentsTable } from "../components/panel/IncidentsTable";
import { PlanGate } from "../components/panel/PlanGate";
import { TracesPanel } from "../components/panel/TracesPanel";
import { DuplicatesPanel } from "../components/panel/DuplicatesPanel";
import { MapView } from "../components/panel/MapView";
import { TrackingView } from "../components/panel/TrackingView";
import { DetailDialog } from "../components/panel/DetailDialog";
import { EMPTY_SNAPSHOT } from "../components/panel/contracts";
import { useSnapshot } from "../hooks/useSnapshot";
import { usePanelNav } from "../hooks/usePanelNav";
import {
  buildIncidentRows,
  computeMetrics,
  derivePlan,
  deriveTraces,
  duplicateBlocks,
  lookupReport,
  planStateLabel,
  quickCodes,
  sectorName,
  sectorVisual,
} from "../lib/panelDerive";
import type {
  PanelView,
  PlanStateLabel,
  SectorRow,
  TrackingLookup,
} from "../components/panel/contracts";

const VIEW_TITLES: Partial<Record<PanelView, string>> = {
  admin: "Coordinación",
  map: "Mapa operativo",
  tracking: "Consultar reporte",
};

export default function AdminApp({ initialView }: { initialView: PanelView }) {
  const { view, setView } = usePanelNav("admin", initialView);
  const { snapshot, busy, error, refresh, reset, loadReports, review, decide } =
    useSnapshot();

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "received" | "analyzing" | "planned" | "approved"
  >("all");
  const [districtFilter, setDistrictFilter] = useState<
    "all" | "Arraiján" | "La Chorrera"
  >("all");
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [actor, setActor] = useState("");
  const [comment, setComment] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [toastVisible, setToastVisible] = useState(false);
  const [tracking, setTracking] = useState<{
    code: string;
    result: TrackingLookup | null;
    emptyMessage: string | null;
  }>({ code: "", result: null, emptyMessage: null });

  const showToast = useCallback((message: string) => {
    setToastMessage(message);
    setToastVisible(true);
    window.setTimeout(() => setToastVisible(false), 4000);
  }, []);

  useEffect(() => {
    if (error) showToast(error);
  }, [error, showToast]);

  const metrics = useMemo(
    () =>
      snapshot
        ? computeMetrics(snapshot)
        : { reports: 0, sectors: 0, pending: 0, dispatched: 0 },
    [snapshot],
  );
  const incidentRows = useMemo(
    () => (snapshot ? buildIncidentRows(snapshot) : []),
    [snapshot],
  );
  const plan = useMemo(
    () =>
      snapshot
        ? derivePlan(snapshot)
        : { liters: 0, vehicles: 0, stops: 0, routes: [], unserved: [], silent: [] },
    [snapshot],
  );
  const stages = useMemo(
    () => (snapshot ? deriveTraces(snapshot) : []),
    [snapshot],
  );
  const dupBlocks = useMemo(
    () => (snapshot ? duplicateBlocks(snapshot, 6) : []),
    [snapshot],
  );
  const codes = useMemo(() => (snapshot ? quickCodes(snapshot) : []), [snapshot]);

  const sectorRows: SectorRow[] = useMemo(() => {
    if (!snapshot) return [];
    const bestScore = new Map<string, number>();
    for (const cluster of snapshot.clusters) {
      for (const priority of snapshot.priorities) {
        if (priority.cluster_id !== cluster.cluster_id) continue;
        const current = bestScore.get(cluster.sector_id);
        if (current == null || priority.score > current) {
          bestScore.set(cluster.sector_id, priority.score);
        }
      }
    }
    return snapshot.sectors.map((sector) => {
      const visual = sectorVisual(snapshot, sector.sector_id);
      const district =
        typeof sector.district === "string" && sector.district
          ? sector.district
          : "Panamá Oeste";
      return {
        sectorId: sector.sector_id,
        name: sectorName(snapshot, sector.sector_id),
        district,
        latitude: sector.latitude,
        longitude: sector.longitude,
        people: Number(
          snapshot.clusters
            .filter((cluster) => cluster.sector_id === sector.sector_id)
            .reduce(
              (sum, cluster) => sum + Number(cluster.estimated_affected_count ?? 0),
              0,
            ),
        ),
        score: bestScore.get(sector.sector_id) ?? null,
        level: visual.level,
        label: visual.label,
        color: visual.color,
      };
    });
  }, [snapshot]);

  const selectedClusterMeta = useMemo(() => {
    if (!snapshot || !selectedClusterId) return { meta: {}, priority: null };
    const cluster = snapshot.clusters.find((c) => c.cluster_id === selectedClusterId);
    if (!cluster) return { meta: {}, priority: null };
    const priority =
      snapshot.priorities.find((p) => p.cluster_id === cluster.cluster_id) ?? null;
    const meta: Record<string, string> = {
      Código: cluster.source_report_ids.join(", ") || cluster.cluster_id,
      Reportes: String(cluster.report_count),
      Precisión: cluster.geo_precision,
      Evidencia: cluster.evidence_types.join(", ") || "—",
      "Requiere revisión": cluster.requires_human_review ? "Sí" : "No",
    };
    return { meta, priority };
  }, [snapshot, selectedClusterId]);

  const stateLabel: PlanStateLabel = planStateLabel(snapshot?.state ?? null);

  const onLookup = useCallback(
    (raw: string) => {
      if (!snapshot) return;
      const result = lookupReport(raw, snapshot);
      setTracking({
        code: raw,
        result,
        emptyMessage: result
          ? null
          : "No hay un reporte con ese código. Pruebe con un código de la lista.",
      });
    },
    [snapshot],
  );

  const handleDecision = useCallback(
    async (action: "APPROVE" | "REJECT" | "CORRECT") => {
      try {
        const ctx = await decide(action, actor, comment);
        const verb =
          action === "APPROVE"
            ? "aprobado"
            : action === "REJECT"
              ? "rechazado"
              : "corregido";
        showToast(
          ctx.execution?.saved
            ? `Plan ${verb}. Auditoría ${ctx.execution.audit_id}. Avisos SIMULATED encolados.`
            : `Plan ${verb} (sin persistencia).`,
        );
      } catch (decisionError) {
        showToast(
          decisionError instanceof Error
            ? decisionError.message
            : "No se pudo registrar la decisión.",
        );
      }
    },
    [actor, comment, decide, showToast],
  );

  const handleLoadReports = useCallback(
    async (raw: string) => {
      const texts = raw
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      if (texts.length === 0) {
        showToast("Pegue al menos un reporte de texto.");
        return;
      }
      try {
        await loadReports(texts);
        showToast(`${texts.length} reporte(s) procesado(s).`);
      } catch {
        /* error already in toast */
      }
    },
    [loadReports, showToast],
  );

  const busyText = busy ? "Procesando…" : null;

  return (
    <Shell
      role="admin"
      view={view}
      title={VIEW_TITLES[view] ?? "Coordinación"}
      stateLabel={stateLabel}
      onNavigate={setView}
    >
      {busyText ? (
        <p className="mb-3 text-sm text-muted" role="status" aria-live="polite">
          {busyText}
        </p>
      ) : null}

      {view === "admin" ? (
        <div className="space-y-4">
          <Callout variant="warning" title="Datos sintéticos de demostración">
            Todos los datos de este panel son{" "}
            <Badge variant="synthetic">SYNTHETIC_DEMO</Badge> o{" "}
            <Badge variant="synthetic">ASSUMPTION</Badge>. La fórmula priority-v1 es
            política de prototipo, no del IDAAN. Ningún agente aprueba el plan.
          </Callout>

          <MetricsRow metrics={metrics} />

          <PlanGate
            state={snapshot?.state ?? null}
            stateLabel={stateLabel}
            liters={plan.liters}
            vehicles={plan.vehicles}
            stops={plan.stops}
            routes={plan.routes}
            unserved={plan.unserved}
            silent={plan.silent}
            actor={actor}
            comment={comment}
            message={
              snapshot?.plan
                ? snapshot.plan.explanation
                : "Sin plan todavía. Cargue reportes y envíe a revisión."
            }
            execution={snapshot?.execution ?? null}
            busy={busy}
            onActor={setActor}
            onComment={setComment}
            onReview={() => {
              void review()
                .then(() => showToast("Plan enviado a revisión (pendiente)."))
                .catch(() => undefined);
            }}
            onApprove={() => {
              void handleDecision("APPROVE");
            }}
            onReject={() => {
              void handleDecision("REJECT");
            }}
            onCorrect={() => {
              void handleDecision("CORRECT");
            }}
          />

          <div className="grid gap-4 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <IncidentsTable
                rows={incidentRows}
                query={query}
                status={statusFilter}
                counts={{
                  all: incidentRows.length,
                  received: incidentRows.filter((row) => row.status === "received")
                    .length,
                  analyzing: incidentRows.filter((row) => row.status === "analyzing")
                    .length,
                  planned: incidentRows.filter((row) => row.status === "planned")
                    .length,
                  approved: incidentRows.filter((row) => row.status === "approved")
                    .length,
                }}
                onQueryChange={setQuery}
                onStatusChange={setStatusFilter}
                districtFilter={districtFilter}
                onDistrictFilter={setDistrictFilter}
                onOpenDetail={(clusterId) => setSelectedClusterId(clusterId)}
              />
            </div>
            <div className="lg:col-span-5">
              <TracesPanel stages={stages} traces={snapshot?.traces ?? []} />
            </div>
            <div className="lg:col-span-7">
              <DuplicatesPanel
                blocks={dupBlocks}
                notices={snapshot?.outbox_notices ?? []}
              />
            </div>
            <div className="lg:col-span-5">
              <Card>
                <h2 className="font-display text-lg font-semibold text-ink">
                  Carga de reportes
                </h2>
                <label
                  htmlFor="reports-input"
                  className="mt-2 block text-sm text-muted"
                >
                  Un reporte por línea
                </label>
                <textarea
                  id="reports-input"
                  rows={4}
                  placeholder="Llevamos 30 horas sin agua en Loma Cova, somos 8 personas…"
                  className="mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    id="load-reports"
                    variant="primary"
                    isLoading={busy}
                    loadingText="Procesando…"
                    onClick={() => {
                      const input =
                        document.querySelector<HTMLTextAreaElement>("#reports-input");
                      void handleLoadReports(input?.value ?? "");
                    }}
                  >
                    Procesar lote
                  </Button>
                  <Button
                    type="button"
                    id="preload-reports"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      void refresh()
                        .then(() => showToast("Contexto actualizado."))
                        .catch(() => undefined);
                    }}
                  >
                    Recargar contexto
                  </Button>
                  <Button
                    type="button"
                    id="reset-session"
                    variant="light"
                    disabled={busy}
                    onClick={() => {
                      void reset()
                        .then(() => showToast("Sesión reiniciada."))
                        .catch(() => undefined);
                    }}
                  >
                    Reiniciar sesión
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </div>
      ) : null}

      {view === "map" ? (
        <MapView
          role="admin"
          snapshot={snapshot ?? EMPTY_SNAPSHOT}
          districtFilter={districtFilter}
          selectedSectorId={null}
          sectors={sectorRows}
          onDistrictFilter={setDistrictFilter}
          onSelectSector={(sectorId) => {
            const cluster = snapshot?.clusters.find((c) => c.sector_id === sectorId);
            if (cluster) setSelectedClusterId(cluster.cluster_id);
          }}
        />
      ) : null}

      {view === "tracking" ? (
        <TrackingView
          codes={codes}
          code={tracking.code}
          result={tracking.result}
          emptyMessage={tracking.emptyMessage}
          onCodeChange={(value) =>
            setTracking((prev) => ({ ...prev, code: value }))
          }
          onPickCode={(value) => onLookup(value)}
        />
      ) : null}

      <DetailDialog
        open={selectedClusterId != null}
        clusterId={selectedClusterId}
        sectorName={
          snapshot && selectedClusterId
            ? sectorName(
                snapshot,
                snapshot.clusters.find((c) => c.cluster_id === selectedClusterId)
                  ?.sector_id ?? "UNKNOWN",
              )
            : ""
        }
        clusterMeta={selectedClusterMeta.meta}
        priority={selectedClusterMeta.priority}
        onClose={() => setSelectedClusterId(null)}
      />

      <Toast message={toastMessage} visible={toastVisible} />
    </Shell>
  );
}
