// Base del panel: portado de src/coordinator/web/panel.html (#view-map 579-615, renderLeaflet ~1860)
import { useEffect, useMemo, useRef } from "react";
import { Badge, BarList, Callout, Card } from "../tremor";
import { leafletReady } from "../../lib/leafletReady";
import { PANAMA_OESTE_BORDER } from "../../lib/border";
import { districtLabel } from "../../lib/panelDerive";
import type { MapViewProps } from "./contracts";

const LEVEL_TEXT: Record<string, string> = {
  high: "text-priority-high",
  medium: "text-priority-mid",
  low: "text-priority-low",
  silent: "text-simulated",
};

interface LeafletLike {
  addTo: (map: unknown) => LeafletLike;
  bindTooltip: (text: string) => LeafletLike;
  remove: () => void;
  removeLayer: (layer: unknown) => void;
  invalidateSize: () => void;
  fitBounds: (bounds: unknown, options?: Record<string, unknown>) => void;
}

interface LeafletNS {
  map: (el: HTMLElement, opts?: Record<string, unknown>) => LeafletLike;
  tileLayer: (url: string, opts?: Record<string, unknown>) => LeafletLike;
  polygon: (pts: [number, number][], opts?: Record<string, unknown>) => LeafletLike;
  circleMarker: (latlng: [number, number], opts?: Record<string, unknown>) => LeafletLike;
  layerGroup: () => LeafletLike & { clearLayers: () => void };
  latLngBounds: (latlngs: [number, number][]) => unknown;
  heatLayer?: (points: number[][], opts?: Record<string, unknown>) => LeafletLike;
}

// Firmas de calor: clusters con coordenadas (peso por reportes) o anclas de respaldo.
function heatPoints(snapshot: MapViewProps["snapshot"]): number[][] {
  const clustered = snapshot.clusters.filter(
    (cluster) =>
      typeof cluster.latitude === "number" && typeof cluster.longitude === "number",
  );
  if (clustered.length > 0) {
    return clustered.map((cluster) => [
      cluster.latitude as number,
      cluster.longitude as number,
      Math.min(1, Math.max(0.28, (cluster.report_count || 1) / 6)),
    ]);
  }
  return snapshot.places
    .filter(
      (place) =>
        typeof place.latitude === "number" && typeof place.longitude === "number",
    )
    .map((place) => [Number(place.latitude), Number(place.longitude), 0.4]);
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
};

export function MapView({
  snapshot,
  districtFilter,
  selectedSectorId,
  sectors,
  onDistrictFilter,
  onSelectSector,
}: MapViewProps) {
  const mapDivRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(
    () =>
      sectors.filter(
        (sector) => districtFilter === "all" || sector.district === districtFilter,
      ),
    [districtFilter, sectors],
  );

  const highCount = sectors.filter((sector) => sector.level === "high").length;
  const reportsCount = snapshot.clusters.reduce(
    (sum, cluster) => sum + Number(cluster.report_count || 0),
    0,
  );

  const barData = visible.map((sector) => ({
    name: sector.name,
    value: sector.score == null ? 0 : Math.round(sector.score),
  }));

  useEffect(() => {
    let cancelled = false;
    let map: LeafletLike | null = null;
    let heatLayer: LeafletLike | null = null;
    let markers: (LeafletLike & { clearLayers: () => void }) | null = null;

    async function init() {
      const container = mapDivRef.current;
      if (!container) return;
      const L = await leafletReady();
      if (cancelled || !L || !mapDivRef.current) {
        if (!cancelled && mapDivRef.current && !L) {
          mapDivRef.current.textContent =
            "El mapa no está disponible (sin callejero). Consulte la lista de sectores al costado.";
        }
        return;
      }
      const leaflet = L as unknown as LeafletNS;
      // ponytail: casteo mínimo de Leaflet; la libra por CDN no trae tipos.
      const instance = leaflet.map(container, {
        center: [9.0, -79.9],
        zoom: 10,
        scrollWheelZoom: false,
        minZoom: 9,
      });
      map = instance;
      leaflet
        .tileLayer(
          "https://{s}.basemaps.cartocdn.com/dark_matter/{z}/{x}/{y}{r}.png",
          {
            subdomains: "abcd",
            maxZoom: 20,
            attribution: "© OpenStreetMap © CARTO",
          },
        )
        .addTo(instance);
      leaflet
        .polygon(PANAMA_OESTE_BORDER, {
          color: "#b91c1c",
          weight: 2.2,
          opacity: 0.78,
          fill: false,
        })
        .addTo(instance);
      instance.fitBounds(leaflet.latLngBounds(PANAMA_OESTE_BORDER), {
        padding: [18, 18],
        maxZoom: 11,
      });
      window.setTimeout(() => map?.invalidateSize(), 80);

      // Firmas de calor: heatLayer si el plugin (leaflet.heat por CDN) está.
      const heatLow = token("--color-heat-low");
      const heatMid = token("--color-heat-mid");
      const heatHigh = token("--color-heat-high");
      const points = heatPoints(snapshot);
      if (typeof leaflet.heatLayer === "function" && points.length > 0) {
        const gradient: Record<number, string> = {};
        if (heatLow) gradient[0.2] = heatLow;
        if (heatMid) gradient[0.55] = heatMid;
        if (heatHigh) gradient[1] = heatHigh;
        heatLayer = leaflet.heatLayer(points, {
          radius: 34,
          blur: 26,
          maxZoom: 14,
          minOpacity: 0.28,
          gradient,
        });
        heatLayer.addTo(instance);
        return;
      }
      // Respaldo: círculos por sector del filtro.
      if (!markers) {
        markers = leaflet.layerGroup().addTo(instance) as LeafletLike & {
          clearLayers: () => void;
        };
      }
      for (const sector of visible) {
        leaflet
          .circleMarker([sector.latitude, sector.longitude], {
            radius: 12,
            color: sector.color,
            fillColor: sector.color,
            fillOpacity: 0.45,
            weight: 1.6,
          })
          .addTo(markers)
          .bindTooltip(`${sector.name} · ${sector.label}`);
      }
    }

    void init();
    return () => {
      cancelled = true;
      heatLayer = null;
      markers = null;
      map?.remove();
    };
  }, [visible, snapshot]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Mapa de afectaciones
          </p>
          <h1 className="font-display text-2xl font-bold text-ink">
            Panamá Oeste · calor de reportes
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="synthetic">SYNTHETIC_DEMO</Badge>
          <a
            id="mapNewReport"
            href="/ciudadano"
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-transparent bg-water px-3 py-2 text-sm font-medium text-white shadow-xs hover:bg-water-deep"
          >
            Registrar reporte
          </a>
        </div>
      </div>

      <Callout variant="warning" title="Datos ilustrativos">
        El calor refleja reportes recibidos, no la prioridad del motor. Las anclas de
        ubicación son de demostración <Badge variant="synthetic">ASSUMPTION</Badge>.
      </Callout>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_320px]">
        <Card className="p-0">
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">Mapa</h2>
            <select
              id="mapDistrictFilter"
              aria-label="Filtrar por distrito"
              value={districtFilter}
              onChange={(event) =>
                onDistrictFilter(
                  event.target.value as MapViewProps["districtFilter"],
                )
              }
              className="h-11 rounded-md border border-line bg-surface px-3 text-sm text-ink"
            >
              <option value="all">Todos los distritos</option>
              <option value="Arraiján">Arraiján</option>
              <option value="La Chorrera">La Chorrera</option>
            </select>
          </div>
          <div
            id="affectedMap"
            ref={mapDivRef}
            className="h-[540px] w-full bg-[#0e1419]"
          />
          <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-2 text-xs text-muted">
            <span className="flex items-center gap-1">
              <span className="size-3 rounded-sm bg-[#d92332]" aria-hidden="true" /> alta
            </span>
            <span className="flex items-center gap-1">
              <span className="size-3 rounded-sm bg-[#f2df58]" aria-hidden="true" /> media
            </span>
            <span className="flex items-center gap-1">
              <span className="size-3 rounded-sm bg-[#13b889]" aria-hidden="true" /> baja
            </span>
            <span className="flex items-center gap-1">
              <span className="size-3 rounded-sm bg-[#334155]" aria-hidden="true" /> sin
              reportes
            </span>
            <span className="ml-auto">Borde: área de interés</span>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="text-sm font-semibold text-ink">Sectores</h2>
            <p className="mt-1 text-xs text-muted">
              Puntaje priority-v1 por sector del distrito filtrado.
            </p>
            <div id="mapSectorList" className="mt-3">
              {barData.length === 0 ? (
                <p className="text-sm text-muted">Sin sectores en este distrito.</p>
              ) : (
                <BarList data={barData} className="[&_li]:cursor-pointer" />
              )}
            </div>
          </Card>

          <Card>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-xs text-muted">Prioridad alta</p>
                <p
                  id="mapHighCount"
                  className="font-display text-2xl font-bold tabular-nums text-priority-high"
                >
                  {highCount}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted">Reportes</p>
                <p
                  id="mapReportsCount"
                  className="font-display text-2xl font-bold tabular-nums text-ink"
                >
                  {reportsCount}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted">Sectores</p>
                <p
                  id="mapSectorCount"
                  className="font-display text-2xl font-bold tabular-nums text-ink"
                >
                  {visible.length}
                </p>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-ink">Detalle por sector</h2>
            <ul className="mt-2 divide-y divide-line">
              {visible.map((sector) => (
                <li key={sector.sectorId}>
                  <button
                    type="button"
                    onClick={() => onSelectSector(sector.sectorId)}
                    className={`flex w-full items-center justify-between gap-2 py-2 text-left text-sm ${
                      selectedSectorId === sector.sectorId ? "font-semibold" : ""
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-ink">{sector.name}</span>
                      <span className="block text-xs text-muted">
                        {districtLabel({
                          sector_id: sector.sectorId,
                          name: sector.district,
                          latitude: sector.latitude,
                          longitude: sector.longitude,
                        })}
                      </span>
                    </span>
                    <span className={`shrink-0 text-xs font-medium ${LEVEL_TEXT[sector.level]}`}>
                      {sector.label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
