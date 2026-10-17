// App del portal ciudadano: reporte asistido, consulta de estado y mapa
// comunitario. Portado del PanelApp.tsx anterior (misma lógica, rol citizen
// fijo). Sin compuerta, métricas, trazas ni reset: eso vive en AdminApp.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Shell } from "../components/panel/Shell";
import { Toast } from "../components/panel/Toast";
import { MapView } from "../components/panel/MapView";
import { CitizenWizard } from "../components/panel/CitizenWizard";
import { LocationDialog } from "../components/panel/LocationDialog";
import { ExtractionDialog } from "../components/panel/ExtractionDialog";
import { TrackingView } from "../components/panel/TrackingView";
import { EMPTY_SNAPSHOT } from "../components/panel/contracts";
import { useSnapshot } from "../hooks/useSnapshot";
import { usePanelNav } from "../hooks/usePanelNav";
import {
  lookupReport,
  quickCodes,
  sectorName,
  sectorVisual,
} from "../lib/panelDerive";
import type {
  PanelView,
  PlaceAnchor,
  SectorRow,
  TrackingLookup,
} from "../components/panel/contracts";

const VIEW_TITLES: Partial<Record<PanelView, string>> = {
  citizen: "Reportar incidencia",
  tracking: "Consultar mi reporte",
  map: "Mapa comunitario",
};

export default function CitizenApp({ initialView }: { initialView: PanelView }) {
  const { view, setView } = usePanelNav("citizen", initialView);
  const { snapshot, busy, error, submitCitizen } = useSnapshot();

  const [districtFilter, setDistrictFilter] = useState<
    "all" | "Arraiján" | "La Chorrera"
  >("all");
  const [selectedSectorId, setSelectedSectorId] = useState<string | null>(null);
  const [locationOpen, setLocationOpen] = useState(false);
  const [pendingFix, setPendingFix] = useState<
    null | {
      latitude: number;
      longitude: number;
      accuracyM: number | null;
      sourceKind: "browser" | "manual" | "preset";
    }
  >(null);
  const [extraction, setExtraction] = useState<{
    reportId: string;
    sector: string;
    place: string;
    hours: string;
    people: string;
    vulnerabilities: string;
    uncertainties: string;
    clusterId: string;
    score: string;
  } | null>(null);
  const [tracking, setTracking] = useState<{
    code: string;
    result: TrackingLookup | null;
    emptyMessage: string | null;
  }>({ code: "", result: null, emptyMessage: null });
  const [toastMessage, setToastMessage] = useState("");
  const [toastVisible, setToastVisible] = useState(false);

  const showToast = useCallback((message: string) => {
    setToastMessage(message);
    setToastVisible(true);
    window.setTimeout(() => setToastVisible(false), 4000);
  }, []);

  useEffect(() => {
    if (error) showToast(error);
  }, [error, showToast]);

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

  const places: PlaceAnchor[] = useMemo(
    () =>
      (snapshot?.places ?? [])
        .filter((place) => typeof place.place_id === "string")
        .map((place) => ({
          place_id: String(place.place_id),
          sector_id: String(place.sector_id ?? ""),
          name: String(place.name ?? place.place_id),
          latitude: Number(place.latitude ?? 0),
          longitude: Number(place.longitude ?? 0),
        })),
    [snapshot],
  );

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

  const handleCitizenSubmit = useCallback(
    async (body: { text: string; latitude?: number; longitude?: number }) => {
      try {
        const ctx = await submitCitizen(body);
        const latest = ctx.latest_report;
        const reportId =
          latest && "report_id" in latest && typeof latest.report_id === "string"
            ? latest.report_id
            : ctx.extracted_reports.at(-1)?.report_id ?? "";
        const report = ctx.extracted_reports.find(
          (row) => row.report_id === reportId,
        );
        const cluster = ctx.clusters.find((c) =>
          c.source_report_ids.includes(reportId),
        );
        const priority = cluster
          ? ctx.priorities.find((p) => p.cluster_id === cluster.cluster_id) ?? null
          : null;
        const mergedNote =
          cluster && cluster.report_count > 1
            ? "Su reporte se fusionó con reportes previos del mismo sector (≤ 800 m). Más quejas no suben la prioridad."
            : null;
        setExtraction({
          reportId,
          sector: report
            ? sectorName(ctx, report.candidate_sector_id)
            : "Sector sin clasificar",
          place: report?.raw_location_mention ?? "",
          hours:
            report?.duration_hours != null ? `${report.duration_hours} h` : "sin dato",
          people:
            report?.affected_count != null
              ? String(report.affected_count)
              : "sin dato",
          vulnerabilities: (report?.vulnerability_flags ?? []).join(", "),
          uncertainties: mergedNote
            ? `${mergedNote} ${(report?.uncertainties ?? []).join(" ")}`
            : (report?.uncertainties ?? []).join(" "),
          clusterId: cluster?.cluster_id ?? "",
          score: priority ? `${priority.score}/100` : "—",
        });
        showToast(
          mergedNote
            ? "Reporte duplicado: se fusionó con uno previo."
            : "Reporte recibido.",
        );
      } catch (submitError) {
        showToast(
          submitError instanceof Error
            ? submitError.message
            : "No se pudo enviar el reporte.",
        );
      }
    },
    [showToast, submitCitizen],
  );

  const busyText = busy ? "Procesando…" : null;

  return (
    <Shell
      role="citizen"
      view={view}
      title={VIEW_TITLES[view] ?? "Portal ciudadano"}
      onNavigate={setView}
    >
      {busyText ? (
        <p className="mb-3 text-sm text-muted" role="status" aria-live="polite">
          {busyText}
        </p>
      ) : null}

      {/* Las tres vistas viven montadas y se ocultan por clase: así el
          borrador del wizard sobrevive al cambio de vista y el HTML servido
          trae los ids de las tres (mapNewReport incluido). */}
      <div className={view === "citizen" ? "" : "hidden"}>
        <CitizenWizard
          snapshot={snapshot ?? EMPTY_SNAPSHOT}
          synthesized=""
          busy={busy}
          locationFix={
            pendingFix
              ? { latitude: pendingFix.latitude, longitude: pendingFix.longitude }
              : null
          }
          onOpenLocation={() => setLocationOpen(true)}
          onSubmit={(body) => {
            void handleCitizenSubmit(body);
          }}
        />
      </div>

      <div className={view === "tracking" ? "" : "hidden"}>
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
      </div>

      <div className={view === "map" ? "" : "hidden"}>
        <MapView
          role="citizen"
          snapshot={snapshot ?? EMPTY_SNAPSHOT}
          districtFilter={districtFilter}
          selectedSectorId={selectedSectorId}
          sectors={sectorRows}
          onDistrictFilter={setDistrictFilter}
          onSelectSector={(sectorId) => setSelectedSectorId(sectorId)}
        />
      </div>

      <LocationDialog
        open={locationOpen}
        pending={
          pendingFix
            ? {
                ...pendingFix,
                place: null,
                sectorId: null,
                anchorMeters: null,
              }
            : null
        }
        places={places}
        error=""
        onClose={() => setLocationOpen(false)}
        onConfirm={() => setLocationOpen(false)}
        onPickPlace={(place) => {
          setPendingFix({
            latitude: place.latitude,
            longitude: place.longitude,
            accuracyM: null,
            sourceKind: "preset",
          });
        }}
        onCoords={(lat, lng) => {
          setPendingFix({
            latitude: lat,
            longitude: lng,
            accuracyM: null,
            sourceKind: "manual",
          });
        }}
      />

      <ExtractionDialog
        open={extraction != null}
        reportId={extraction?.reportId ?? ""}
        sector={extraction?.sector ?? ""}
        place={extraction?.place ?? ""}
        hours={extraction?.hours ?? ""}
        people={extraction?.people ?? ""}
        vulnerabilities={extraction?.vulnerabilities ?? ""}
        uncertainties={extraction?.uncertainties ?? ""}
        clusterId={extraction?.clusterId ?? ""}
        score={extraction?.score ?? ""}
        onClose={() => setExtraction(null)}
      />

      <Toast message={toastMessage} visible={toastVisible} />
    </Shell>
  );
}
