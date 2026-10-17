// Base del panel: portado de src/coordinator/web/panel.html

import type { ReactNode } from "react";
import type {
  CoordinatorSnapshot,
  ExecutionResult,
  OutboxNotice,
  PlanState,
  PriorityResult,
  TraceEntry,
} from "../../lib/api";

export type Role = "admin" | "citizen";
export type PanelView = "map" | "admin" | "citizen" | "tracking";
export type PlanStateLabel =
  | "Sin plan"
  | "Borrador"
  | "Pendiente"
  | "Aprobado"
  | "Rechazado"
  | "Error parcial";

export interface SectorRow {
  sectorId: string;
  name: string;
  district: string;
  latitude: number;
  longitude: number;
  people: number;
  score: number | null;
  level: "low" | "medium" | "high" | "silent";
  label: string;
  color: string;
}

export interface PlaceAnchor {
  place_id: string;
  sector_id: string;
  name: string;
  latitude: number;
  longitude: number;
  aliases?: string[];
}

export interface PendingFix {
  latitude: number;
  longitude: number;
  accuracyM: number | null;
  sourceKind: "browser" | "manual" | "map" | "preset";
  place: PlaceAnchor | null;
  sectorId: string | null;
  anchorMeters: number | null;
}

export interface MetricsRow {
  reports: number;
  sectors: number;
  pending: number;
  dispatched: number;
}

export type IncidentStatus = "received" | "analyzing" | "planned" | "approved";

export interface IncidentTableRow {
  clusterId: string;
  code: string;
  place: string;
  sector: string;
  people: string;
  score: string | number;
  level: "low" | "medium" | "high";
  status: IncidentStatus;
  district?: string;
}

export interface IncidentStatusCounts {
  all: number;
  received: number;
  analyzing: number;
  planned: number;
  approved: number;
}

export interface PlanRouteRow {
  vehicleId: string;
  names: string;
  liters: number;
  stops: number;
}

export interface MetricsRowProps {
  metrics: MetricsRow;
}

export interface IncidentsTableProps {
  rows: IncidentTableRow[];
  query: string;
  status: "all" | IncidentStatus;
  counts: IncidentStatusCounts;
  onQueryChange: (value: string) => void;
  onStatusChange: (value: "all" | IncidentStatus) => void;
  onOpenDetail: (clusterId: string) => void;
  districtFilter?: "all" | "Arraiján" | "La Chorrera";
  onDistrictFilter?: (value: "all" | "Arraiján" | "La Chorrera") => void;
  onOpen?: (clusterId: string) => void;
}

export interface PlanGateProps {
  state: PlanState;
  stateLabel: PlanStateLabel;
  liters: number;
  vehicles: number;
  stops: number;
  routes: PlanRouteRow[];
  unserved: string[];
  silent: string[];
  actor: string;
  comment: string;
  message: string;
  execution: ExecutionResult | null;
  busy: boolean;
  onActor: (value: string) => void;
  onComment: (value: string) => void;
  onReview: () => void;
  onApprove: () => void;
  onReject: () => void;
  onCorrect: () => void;
}

export interface TraceStageCard {
  label: string;
  action: string;
  traceId: string;
  status: string;
  inputText: string;
  outputText: string;
}

export interface TracesPanelProps {
  stages: TraceStageCard[];
  traces: TraceEntry[];
}

export interface DuplicateBlock {
  kind: "dual_focus" | "merged_reports" | "human_review";
  sectorId: string;
  sectorName: string;
  title: string;
  detail: string;
  badge: string;
}

export interface DuplicatesPanelProps {
  blocks: DuplicateBlock[];
  notices: OutboxNotice[];
}

export interface MapViewProps {
  role: Role;
  snapshot: CoordinatorSnapshot;
  districtFilter: "all" | "Arraiján" | "La Chorrera";
  selectedSectorId: string | null;
  sectors: SectorRow[];
  onDistrictFilter: (value: MapViewProps["districtFilter"]) => void;
  onSelectSector: (sectorId: string) => void;
}

export interface CitizenWizardProps {
  snapshot: CoordinatorSnapshot;
  synthesized: string;
  busy: boolean;
  locationFix: { latitude: number; longitude: number } | null;
  onOpenLocation: () => void;
  onSubmit: (body: {
    text: string;
    source_channel?: string;
    sector?: string;
    nombre?: string;
    latitude?: number;
    longitude?: number;
  }) => void;
}

export interface LocationDialogProps {
  open: boolean;
  pending: PendingFix | null;
  places: PlaceAnchor[];
  error: string;
  onClose: () => void;
  onConfirm: () => void;
  onPickPlace: (place: PlaceAnchor) => void;
  onCoords: (lat: number, lng: number) => void;
}

export interface ExtractionDialogProps {
  open: boolean;
  reportId: string;
  sector: string;
  place: string;
  hours: string;
  people: string;
  vulnerabilities: string;
  uncertainties: string;
  clusterId: string;
  score: string;
  onClose: () => void;
}

export interface TrackingStep {
  stage: string;
  text: string;
  done: boolean;
}

export interface TrackingLookup {
  title: string;
  chip: string;
  hours: string;
  people: string;
  score: string;
  steps: [TrackingStep, TrackingStep, TrackingStep, TrackingStep];
  notice: string | null;
  vehicle: string | null;
  planStateLabel: PlanStateLabel;
  sectorName: string;
  priority: PriorityResult | null;
}

export interface TrackingViewProps {
  codes: string[];
  code: string;
  result: TrackingLookup | null;
  emptyMessage: string | null;
  onCodeChange: (value: string) => void;
  onPickCode: (code: string) => void;
}

export type DistrictScope = "all" | "Arraiján" | "La Chorrera";

export interface ShellHeaderProps {
  title?: string;
  stateLabel?: PlanStateLabel;
  scope?: DistrictScope;
  onScopeChange?: (value: DistrictScope) => void;
  onOpenMenu?: () => void;
  onHelp?: () => void;
  query?: string;
  onQueryChange?: (value: string) => void;
}

export interface SidebarNavProps {
  role: Role;
  view: PanelView;
  onNavigate: (view: PanelView) => void;
}

export interface ShellProps {
  role: Role;
  view: PanelView;
  title: string;
  stateLabel?: PlanStateLabel;
  scope?: DistrictScope;
  query?: string;
  children: ReactNode;
  onNavigate: (view: PanelView) => void;
  onScopeChange?: (value: DistrictScope) => void;
  onQueryChange?: (value: string) => void;
}

export interface ToastProps {
  message: string;
  visible: boolean;
}

export interface DetailDialogProps {
  open: boolean;
  clusterId: string | null;
  sectorName: string;
  clusterMeta: Record<string, string>;
  priority: PriorityResult | null;
  onClose: () => void;
}

export interface HelpDialogProps {
  role: Role;
  open: boolean;
  onClose: () => void;
}

export const PANEL_VIEWS: PanelView[] = ["map", "admin", "citizen", "tracking"];

export const EMPTY_SNAPSHOT: CoordinatorSnapshot = {
  clusters: [],
  priorities: [],
  plan: null,
  state: null,
  traces: [],
  execution: null,
  provenance_tags: [],
  sectors: [],
  extracted_reports: [],
  places: [],
  sample_reports: [],
  outbox_notices: [],
};
