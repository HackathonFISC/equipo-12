// Base del panel: portado de src/coordinator/web/panel.html

import type {
  Cluster,
  CoordinatorSnapshot,
  ExtractedReport,
  PlanAssignment,
  PlanState,
  PriorityResult,
  SectorMapEntry,
  TraceEntry,
} from "./api";
import type {
  DuplicateBlock,
  IncidentStatus,
  IncidentTableRow,
  MetricsRow,
  PlanRouteRow,
  PlanStateLabel,
  TraceStageCard,
  TrackingLookup,
  TrackingStep,
} from "../components/panel/contracts";
import { haversine } from "./geo";
import { fold, niceName, prettyDistrict } from "./text";

function findSector(
  snapshot: CoordinatorSnapshot,
  id: string,
): SectorMapEntry | null {
  for (const sector of snapshot.sectors) {
    if (sector.sector_id === id) return sector;
  }
  return null;
}

function findPlace(snapshot: CoordinatorSnapshot, id: string) {
  for (const place of snapshot.places) {
    if (place.place_id === id) return place;
  }
  return null;
}

function placeLabelFor(snapshot: CoordinatorSnapshot, placeId: string): string {
  if (!placeId) return "";
  const single = findPlace(snapshot, placeId);
  if (single && typeof single.name === "string") {
    return niceName(single.name);
  }
  const parts = placeId.split("+");
  const names = parts.map((pid) => {
    const found = findPlace(snapshot, pid);
    if (found && typeof found.name === "string") return niceName(found.name);
    return pid
      .replace(/^place_/, "")
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  });
  return names.join(" + ");
}

export function sectorName(snapshot: CoordinatorSnapshot, id: string): string {
  const sector = findSector(snapshot, id);
  if (sector && typeof sector.name === "string") return niceName(sector.name);
  if (id === "UNKNOWN") return "Sector desconocido";
  return String(id || "Sector").replace(/_/g, " ");
}

function priorityForCluster(
  snapshot: CoordinatorSnapshot,
  clusterId: string,
): PriorityResult | null {
  for (const priority of snapshot.priorities) {
    if (priority.cluster_id === clusterId) return priority;
  }
  return null;
}

function assignmentFor(
  snapshot: CoordinatorSnapshot,
  sectorId: string,
): PlanAssignment | null {
  const plan = snapshot.plan;
  if (!plan) return null;
  let found: PlanAssignment | null = null;
  for (const assignment of plan.assignments) {
    if (assignment.sector_id === sectorId) found = assignment;
  }
  return found;
}

function clusterForReport(
  snapshot: CoordinatorSnapshot,
  reportId: string,
): Cluster | null {
  for (const cluster of snapshot.clusters) {
    if (cluster.source_report_ids.includes(reportId)) return cluster;
  }
  return null;
}

function clusterById(
  snapshot: CoordinatorSnapshot,
  clusterId: string,
): Cluster | null {
  for (const cluster of snapshot.clusters) {
    if (cluster.cluster_id === clusterId) return cluster;
  }
  return null;
}

function priorityLevel(score: number | null | undefined): "low" | "medium" | "high" {
  const n = Number(score);
  if (!Number.isFinite(n)) return "low";
  if (n >= 65) return "high";
  if (n >= 38) return "medium";
  return "low";
}

function rowStatus(
  snapshot: CoordinatorSnapshot,
  cluster: Cluster,
): IncidentStatus {
  const state = snapshot.state;
  const assigned = assignmentFor(snapshot, cluster.sector_id);
  const unserved =
    snapshot.plan?.unserved_demand.includes(cluster.sector_id) ?? false;
  if (state === "aprobado" && assigned) return "approved";
  if ((state === "pendiente" || state === "borrador") && assigned) {
    return "planned";
  }
  if (
    cluster.requires_human_review ||
    cluster.geo_precision === "UNKNOWN" ||
    cluster.geo_precision === "SECTOR" ||
    unserved
  ) {
    return "analyzing";
  }
  return "received";
}

export function planStateLabel(state: PlanState): PlanStateLabel {
  if (state == null) return "Sin plan";
  if (state === "borrador") return "Borrador";
  if (state === "pendiente") return "Pendiente";
  if (state === "aprobado") return "Aprobado";
  if (state === "rechazado") return "Rechazado";
  if (state === "error_parcial") return "Error parcial";
  return "Sin plan";
}

export function computeMetrics(snapshot: CoordinatorSnapshot): MetricsRow {
  const extracted = snapshot.extracted_reports;
  const total = Array.isArray(extracted)
    ? extracted.length
    : snapshot.clusters.reduce(
        (sum, cluster) => sum + Number(cluster.report_count || 0),
        0,
      );
  const sectors: Record<string, true> = {};
  for (const cluster of snapshot.clusters) {
    if (cluster.sector_id && cluster.sector_id !== "UNKNOWN") {
      sectors[cluster.sector_id] = true;
    }
  }
  let dispatched = 0;
  if (snapshot.state === "aprobado") {
    for (const notice of snapshot.outbox_notices) {
      if (notice.status === "QUEUED") dispatched += 1;
    }
  }
  const pending =
    snapshot.state === "borrador" || snapshot.state === "pendiente" ? 1 : 0;
  return {
    reports: total,
    sectors: Object.keys(sectors).length,
    pending,
    dispatched,
  };
}

export function buildIncidentRows(
  snapshot: CoordinatorSnapshot,
): IncidentTableRow[] {
  return snapshot.clusters.map((cluster) => {
    const priority = priorityForCluster(snapshot, cluster.cluster_id);
    const score = priority ? priority.score : "—";
    const level = priority ? priorityLevel(priority.score) : "low";
    const status = rowStatus(snapshot, cluster);
    const people =
      cluster.estimated_affected_count == null
        ? "sin dato"
        : String(cluster.estimated_affected_count);
    const codeLabel =
      cluster.source_report_ids.length > 0
        ? cluster.source_report_ids.join(", ")
        : cluster.cluster_id;
    const placeLabel = cluster.place_id
      ? `${placeLabelFor(snapshot, cluster.place_id)} · ${cluster.report_count} rep.`
      : `${cluster.report_count} reporte(s)`;
    return {
      clusterId: cluster.cluster_id,
      code: codeLabel,
      place: placeLabel,
      sector: sectorName(snapshot, cluster.sector_id),
      people,
      score,
      level,
      status,
    };
  });
}

export interface DerivedPlan {
  liters: number;
  vehicles: number;
  stops: number;
  routes: PlanRouteRow[];
  unserved: string[];
  silent: string[];
}

export function derivePlan(snapshot: CoordinatorSnapshot): DerivedPlan {
  const plan = snapshot.plan;
  let liters = 0;
  const vehicleSet: Record<string, true> = {};
  const stops = plan?.assignments.length ?? 0;
  for (const assignment of plan?.assignments ?? []) {
    liters += Number(assignment.volume_liters || 0);
    vehicleSet[assignment.vehicle_id] = true;
  }
  const groups = new Map<string, PlanAssignment[]>();
  const order: string[] = [];
  for (const assignment of plan?.assignments ?? []) {
    if (!groups.has(assignment.vehicle_id)) {
      groups.set(assignment.vehicle_id, []);
      order.push(assignment.vehicle_id);
    }
    groups.get(assignment.vehicle_id)?.push(assignment);
  }
  const routes: PlanRouteRow[] = order.map((vehicleId) => {
    const items = (groups.get(vehicleId) ?? []).slice().sort((a, b) => a.order - b.order);
    const sum = items.reduce(
      (total, item) => total + Number(item.volume_liters || 0),
      0,
    );
    const names = items
      .map((item) => sectorName(snapshot, item.sector_id))
      .join(" · ");
    return {
      vehicleId,
      names,
      liters: sum,
      stops: items.length,
    };
  });
  const unserved = (plan?.unserved_demand ?? []).map((id) =>
    sectorName(snapshot, id),
  );
  const silent = silentSectors(snapshot).map((sector) =>
    niceName(typeof sector.name === "string" ? sector.name : sector.sector_id),
  );
  return {
    liters,
    vehicles: Object.keys(vehicleSet).length,
    stops,
    routes,
    unserved,
    silent,
  };
}

export function silentSectors(snapshot: CoordinatorSnapshot): SectorMapEntry[] {
  const seen: Record<string, true> = {};
  for (const cluster of snapshot.clusters) {
    seen[cluster.sector_id] = true;
  }
  return snapshot.sectors.filter(
    (sector) => sector.sector_id !== "UNKNOWN" && !seen[sector.sector_id],
  );
}

export function duplicateBlocks(
  snapshot: CoordinatorSnapshot,
  maxItems?: number,
): DuplicateBlock[] {
  const rows: DuplicateBlock[] = [];
  const bySector: Record<string, Cluster[]> = {};
  for (const cluster of snapshot.clusters) {
    if (!cluster.sector_id) continue;
    (bySector[cluster.sector_id] ??= []).push(cluster);
  }
  for (const sid of Object.keys(bySector)) {
    const group = bySector[sid] ?? [];
    if (group.length > 1 && sid !== "UNKNOWN") {
      const note = group
        .map((cluster) => {
          const label = cluster.place_id
            ? placeLabelFor(snapshot, cluster.place_id)
            : sectorName(snapshot, cluster.sector_id);
          return `${label} (${cluster.report_count} rep.)`;
        })
        .join(" vs. ");
      let dist = "";
      const first = group[0];
      const second = group[1];
      if (
        first &&
        second &&
        typeof first.latitude === "number" &&
        typeof second.latitude === "number" &&
        typeof first.longitude === "number" &&
        typeof second.longitude === "number"
      ) {
        const meters = Math.round(
          haversine(
            first.latitude,
            first.longitude,
            second.latitude,
            second.longitude,
          ),
        );
        dist = ` · ${meters} m (> 800 m).`;
      }
      rows.push({
        kind: "dual_focus",
        sectorId: sid,
        sectorName: sectorName(snapshot, sid),
        title: sectorName(snapshot, sid),
        badge: "2 focos distintos",
        detail: note + dist,
      });
    }
  }
  for (const cluster of snapshot.clusters) {
    if (Number(cluster.report_count) > 1) {
      const placeTitle = cluster.place_id
        ? placeLabelFor(snapshot, cluster.place_id)
        : sectorName(snapshot, cluster.sector_id);
      rows.push({
        kind: "merged_reports",
        sectorId: cluster.sector_id,
        sectorName: sectorName(snapshot, cluster.sector_id),
        title: `${sectorName(snapshot, cluster.sector_id)} · ${placeTitle}`,
        badge: `${cluster.report_count} reportes`,
        detail: `Fusiona ${(cluster.source_report_ids || []).join(", ")} (≤ 800 m). Invariante al volumen de quejas.`,
      });
    }
    if (
      cluster.requires_human_review ||
      cluster.geo_precision === "UNKNOWN" ||
      cluster.geo_precision === "SECTOR"
    ) {
      const shortUnc =
        cluster.geo_precision === "SECTOR"
          ? "Mención general del sector sin ancla; separado para revisión."
          : "Ubicación fuera de catálogo; retenida para revisión humana.";
      rows.push({
        kind: "human_review",
        sectorId: cluster.sector_id,
        sectorName: sectorName(snapshot, cluster.sector_id),
        title: sectorName(snapshot, cluster.sector_id),
        badge: "Revisión humana",
        detail: `Precisión ${cluster.geo_precision || "UNKNOWN"} · ${shortUnc}`,
      });
    }
  }
  if (maxItems != null && rows.length > maxItems) {
    return rows.slice(0, maxItems);
  }
  return rows;
}

export function deriveTraces(snapshot: CoordinatorSnapshot): TraceStageCard[] {
  const traces = snapshot.traces;
  const reportCount = snapshot.extracted_reports.length;
  const clusterCount = snapshot.clusters.length;
  const priorityCount = snapshot.priorities.length;
  const assignCount = snapshot.plan?.assignments.length ?? 0;
  const unservedCount = snapshot.plan?.unserved_demand.length ?? 0;
  const byActor: Record<string, TraceEntry> = {};
  for (const trace of traces) {
    byActor[trace.actor] = trace;
  }
  return [
    {
      label: "Agente 1 · Ingesta y Guardrails",
      action: byActor.ingestion?.action ?? "ingest_report",
      traceId: byActor.ingestion?.trace_id ?? "trace-ing",
      status: byActor.ingestion?.status ?? "ok",
      inputText: `${reportCount} reporte(s) de texto`,
      outputText: `${reportCount} extracción(es) validadas`,
    },
    {
      label: "Agente 2 · Evaluación de necesidad",
      action: byActor.evaluation?.action ?? "assess_need",
      traceId: byActor.evaluation?.trace_id ?? "trace-eval",
      status: byActor.evaluation?.status ?? "ok",
      inputText: `${clusterCount} cluster(s) deduplicados`,
      outputText: `${priorityCount} evaluación(es) cualitativas`,
    },
    {
      label: "Agente 3 · Planificación OR-Tools",
      action: byActor.planning?.action ?? "plan_routes",
      traceId: byActor.planning?.trace_id ?? "trace-plan",
      status: byActor.planning?.status ?? "ok",
      inputText: `${priorityCount} prioridad(es) · capacidad fija`,
      outputText: `${assignCount} parada(s) · ${unservedCount} sector(es) sin cisterna`,
    },
    {
      label: "Orquestador · Compuerta Humana",
      action: byActor.orchestrator?.action ?? "run_orchestration",
      traceId: byActor.orchestrator?.trace_id ?? "trace-orc",
      status: byActor.orchestrator?.status ?? "ok",
      inputText: "Flujo 1 → 2 → 3",
      outputText: `Estado: ${planStateLabel(snapshot.state)}`,
    },
  ];
}

function noticeFor(snapshot: CoordinatorSnapshot, sectorId: string) {
  for (const notice of snapshot.outbox_notices) {
    if (notice.sector_id === sectorId) return notice;
  }
  return null;
}

function findReportByCode(
  snapshot: CoordinatorSnapshot,
  key: string,
): ExtractedReport | null {
  for (const item of snapshot.extracted_reports) {
    if (item.report_id.toLowerCase() === key.toLowerCase()) return item;
  }
  return null;
}

export function quickCodes(snapshot: CoordinatorSnapshot): string[] {
  const codes: string[] = [];
  const add = (code: string | undefined) => {
    if (!code || code.startsWith("cluster:")) return;
    if (!codes.includes(code)) codes.push(code);
  };
  for (const report of snapshot.extracted_reports) {
    add(report.report_id);
  }
  for (const sample of snapshot.sample_reports) {
    if (typeof sample.report_id === "string") add(sample.report_id);
  }
  add("SYN-001");
  return codes.slice(0, 12);
}

export function lookupReport(
  code: string,
  snapshot: CoordinatorSnapshot,
): TrackingLookup | null {
  const key = String(code || "").trim();
  if (!key) return null;

  let report = findReportByCode(snapshot, key);
  let cluster =
    clusterById(snapshot, key) ??
    (report ? clusterForReport(snapshot, report.report_id) : null);

  if (!cluster && !report) {
    for (const candidate of snapshot.clusters) {
      if (
        candidate.source_report_ids.some(
          (id) => id.toLowerCase() === key.toLowerCase(),
        )
      ) {
        cluster = candidate;
      }
    }
  }

  if (!report && !cluster) {
    const knownSample = snapshot.sample_reports.some(
      (sample) =>
        typeof sample.report_id === "string" &&
        sample.report_id.toLowerCase() === key.toLowerCase(),
    );
    if (knownSample) return null;
    return null;
  }

  const sectorId = cluster ? cluster.sector_id : report!.candidate_sector_id;
  const priority = cluster
    ? priorityForCluster(snapshot, cluster.cluster_id)
    : null;
  const assignment = assignmentFor(snapshot, sectorId);
  const notice = noticeFor(snapshot, sectorId);
  const state = snapshot.state;
  const placeHint =
    cluster && cluster.place_id
      ? placeLabelFor(snapshot, cluster.place_id)
      : sectorName(snapshot, sectorId);

  const steps: [TrackingStep, TrackingStep, TrackingStep, TrackingStep] = [
    {
      stage: "ETAPA 01 · Reporte recibido",
      text: report
        ? `Ingesta validó ${report.report_id} en ${sectorName(snapshot, sectorId)}.`
        : "El incidente está consolidado en el lote activo.",
      done: true,
    },
    {
      stage: "ETAPA 02 · Deduplicación",
      text: cluster
        ? `${placeHint} · ${cluster.report_count} reporte(s) agrupados (≤ 800 m). Más quejas no suben el puntaje.`
        : "Todavía no hay cluster para este código.",
      done: Boolean(cluster),
    },
    {
      stage: "ETAPA 03 · Prioridad priority-v1",
      text: priority
        ? `Puntaje determinístico: ${priority.score}/100 (${priority.formula_version}).`
        : "El motor todavía no puntuó este incidente.",
      done: Boolean(priority),
    },
    {
      stage: "ETAPA 04 · Cisterna y supervisión",
      text: assignment
        ? `Cisterna ${assignment.vehicle_id} · ${assignment.volume_liters} L · parada #${assignment.order}.`
        : "Sin cisterna asignada en el turno actual.",
      done: Boolean(assignment && state === "aprobado"),
    },
  ];

  let noticeText: string | null = null;
  if (notice) {
    noticeText = String(notice.message || "")
      .replace(/^Aviso de demostracion para [A-Z_]+\.\s*/i, "")
      .replace(/\s*Este mensaje quedo en la bandeja simulada.*$/i, "");
    if (!noticeText) noticeText = notice.message;
  }

  const vehicle = assignment
    ? `${assignment.vehicle_id} · ${assignment.volume_liters} litros · parada #${assignment.order}`
    : null;

  const hours =
    cluster && cluster.max_duration_hours != null
      ? `${cluster.max_duration_hours} h`
      : report && report.duration_hours != null
        ? `${report.duration_hours} h`
        : "sin dato";

  const people =
    cluster && cluster.estimated_affected_count != null
      ? String(cluster.estimated_affected_count)
      : report && report.affected_count != null
        ? String(report.affected_count)
        : "sin dato";

  return {
    title: key,
    chip: planStateLabel(state),
    hours,
    people,
    score: priority ? `${priority.score}/100` : "—",
    steps,
    notice: noticeText,
    vehicle,
    planStateLabel: planStateLabel(state),
    sectorName: sectorName(snapshot, sectorId),
    priority,
  };
}

export function filterIncidentRows(
  snapshot: CoordinatorSnapshot,
  query: string,
  status: "all" | IncidentStatus,
): IncidentTableRow[] {
  const foldedQuery = fold(query);
  return buildIncidentRows(snapshot).filter((row) => {
    if (status !== "all" && row.status !== status) return false;
    if (!foldedQuery) return true;
    const blob = fold(
      [
        row.clusterId,
        row.code,
        row.sector,
        row.place,
        String(row.score),
      ].join(" "),
    );
    return blob.includes(foldedQuery);
  });
}

export function sectorVisual(
  snapshot: CoordinatorSnapshot,
  sectorId: string,
): { color: string; level: "low" | "medium" | "high" | "silent"; label: string } {
  const assigned = assignmentFor(snapshot, sectorId);
  const reported = snapshot.clusters.some(
    (cluster) => cluster.sector_id === sectorId,
  );
  const unserved =
    snapshot.plan?.unserved_demand.includes(sectorId) ?? false;
  if (assigned) {
    return { color: "#159c9a", level: "low", label: "Cisterna asignada" };
  }
  if (reported || unserved) {
    let best: number | null = null;
    for (const cluster of snapshot.clusters) {
      if (cluster.sector_id !== sectorId) continue;
      const priority = priorityForCluster(snapshot, cluster.cluster_id);
      if (priority && (best == null || priority.score > best)) {
        best = priority.score;
      }
    }
    if (best != null && best >= 65) {
      return { color: "#bd4d4d", level: "high", label: "Reportado" };
    }
    return {
      color: "#b77b17",
      level: "medium",
      label: unserved ? "Sin cisterna" : "Reportado",
    };
  }
  return { color: "#8d8678", level: "silent", label: "Sin reportes" };
}

export function districtLabel(sector: SectorMapEntry): string {
  const district =
    typeof sector.district === "string" ? sector.district : sector.name;
  return prettyDistrict(district);
}
