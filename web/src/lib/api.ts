export type SectorId =
  | "ARRAIJAN_VISTA_ALEGRE"
  | "ARRAIJAN_BURUNGA"
  | "ARRAIJAN_NUEVO_CHORRILLO"
  | "ARRAIJAN_VACAMONTE"
  | "ARRAIJAN_CERRO_SILVESTRE"
  | "ARRAIJAN_CABECERA"
  | "CHORRERA_BARRIO_COLON"
  | "CHORRERA_BARRIO_BALBOA"
  | "CHORRERA_GUADALUPE"
  | "CHORRERA_EL_COCO"
  | "CHORRERA_PUERTO_CAIMITO"
  | "UNKNOWN";

export type ProvenanceTag = "OFFICIAL_SOURCE" | "SYNTHETIC_DEMO" | "ASSUMPTION";

export type PlanState =
  | "borrador"
  | "pendiente"
  | "aprobado"
  | "rechazado"
  | "error_parcial"
  | null;

export type GeoPrecision = "POINT" | "SECTOR" | "UNKNOWN";

export type EvidenceType =
  | "TEXT_REPORT"
  | "INSTITUTIONAL_REPORT"
  | "MULTIPLE_NEIGHBORS"
  | "UNVERIFIED_CLAIM";

export type GuardrailStatus =
  | "VALID"
  | "NEEDS_REVIEW"
  | "REJECTED_EMPTY"
  | "REJECTED_MALICIOUS"
  | "REJECTED_OUT_OF_SCOPE"
  | "REJECTED_ABSURD";

export type VulnerabilityFlag =
  | "HOSPITAL_SALUD"
  | "ESCUELA"
  | "ADULTOS_MAYORES"
  | "INFANTES"
  | "ALBERGUE"
  | "NINGUNA";

export interface Cluster {
  cluster_id: string;
  sector_id: SectorId;
  source_report_ids: string[];
  report_count: number;
  max_duration_hours: number | null;
  estimated_affected_count: number | null;
  vulnerability_flags: VulnerabilityFlag[];
  evidence_types: EvidenceType[];
  requires_human_review: boolean;
  uncertainties: string[];
  provenance_tags: ProvenanceTag[];
  place_id: string;
  latitude: number | null;
  longitude: number | null;
  geo_precision: GeoPrecision;
}

export interface PriorityBreakdownItem {
  factor: string;
  points: number;
  reason: string;
}

export interface PriorityResult {
  cluster_id: string;
  score: number;
  breakdown: PriorityBreakdownItem[];
  formula_version: string;
  explanation: string;
}

export interface PlanAssignment {
  vehicle_id: string;
  sector_id: SectorId;
  order: number;
  volume_liters: number;
}

export interface PlanDraft {
  plan_id: string;
  assignments: PlanAssignment[];
  route_order: string[];
  constraints_satisfied: string[];
  unserved_demand: string[];
  explanation: string;
}

export interface ExtractedReport {
  report_id: string;
  candidate_sector_id: SectorId;
  raw_location_mention: string;
  duration_hours: number | null;
  affected_count: number | null;
  vulnerability_flags: VulnerabilityFlag[];
  evidence_type: EvidenceType;
  confidence: number;
  uncertainties: string[];
  requiere_revision: boolean;
  guardrail_status: GuardrailStatus;
  guardrail_reason: string;
  provenance: ProvenanceTag;
  place_id: string;
  latitude: number | null;
  longitude: number | null;
  geo_precision: GeoPrecision;
  raw_text: string;
  source_channel: string;
}

export interface TraceEntry {
  trace_id: string;
  actor: string;
  action: string;
  input_summary: string;
  output_summary: string;
  status: string;
  timestamp: string;
}

export interface ExecutionResult {
  saved: boolean;
  plan_id: string;
  audit_id: string;
  outbox_id: string | null;
  detail: string;
}

export interface OutboxNotice {
  sector_id: string;
  message: string;
  channel: "SIMULATED";
  status: "QUEUED" | "PREVIEW";
}

export interface SectorMapEntry {
  sector_id: string;
  name: string;
  latitude: number;
  longitude: number;
  [key: string]: unknown;
}

export interface PlaceFixture {
  place_id?: string;
  sector_id?: string;
  latitude?: number;
  longitude?: number;
  [key: string]: unknown;
}

export interface SampleReportFixture {
  report_id?: string;
  text?: string;
  [key: string]: unknown;
}

export interface CoordinatorSnapshot {
  clusters: Cluster[];
  priorities: PriorityResult[];
  plan: PlanDraft | null;
  state: PlanState;
  traces: TraceEntry[];
  execution: ExecutionResult | null;
  provenance_tags: string[];
  sectors: SectorMapEntry[];
  extracted_reports: ExtractedReport[];
  places: PlaceFixture[];
  sample_reports: SampleReportFixture[];
  outbox_notices: OutboxNotice[];
}

export interface HealthResponse {
  status: string;
  modo: string;
  formula_version: string;
  solver: string;
  fixtures: {
    sectors: number;
    places: number;
    sample_reports: number;
  };
  db_ok: boolean;
  state: PlanState;
}

export interface CitizenReportBody {
  text: string;
  source_channel?: string;
  sector?: string;
  nombre?: string;
  latitude?: number;
  longitude?: number;
}

export interface DecisionBody {
  plan_id: string;
  action: "APPROVE" | "REJECT" | "CORRECT";
  actor: string;
  comment?: string;
}

export type CitizenReportResponse = CoordinatorSnapshot & {
  latest_report?: ExtractedReport | Record<string, never>;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err =
      typeof data === "object" &&
      data !== null &&
      "error" in data &&
      typeof (data as { error: unknown }).error === "string"
        ? (data as { error: string }).error
        : res.statusText;
    throw new Error(err);
  }
  return data as T;
}

export function getContext(): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/context");
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}

export function postReports(texts: string[]): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/reports", {
    method: "POST",
    body: JSON.stringify({ texts }),
  });
}

export function postReview(): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/review", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function postDecision(body: DecisionBody): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/decision", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postCitizenReport(
  body: CitizenReportBody,
): Promise<CitizenReportResponse> {
  return requestJson<CitizenReportResponse>("/api/citizen-report", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postPreload(): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/preload", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function postReset(): Promise<CoordinatorSnapshot> {
  return requestJson<CoordinatorSnapshot>("/api/reset", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
