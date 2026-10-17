// Base del panel: portado de src/coordinator/web/panel.html

export interface LeafletLatLng {
  lat: number;
  lng: number;
}

export interface LeafletMapOptions {
  scrollWheelZoom?: boolean;
  zoomSnap?: number;
  zoomDelta?: number;
  maxBounds?: unknown;
  maxBoundsViscosity?: number;
  minZoom?: number;
}

export interface LeafletMap {
  invalidateSize: () => void;
  setView: (
    center: [number, number],
    zoom: number,
    options?: { animate?: boolean },
  ) => void;
  fitBounds: (
    bounds: unknown,
    options?: { padding?: number[]; maxZoom?: number },
  ) => void;
  removeLayer: (layer: unknown) => void;
}

export interface LeafletLayer {
  addTo: (map: LeafletMap) => unknown;
  clearLayers?: () => void;
  on?: (event: string, handler: () => void) => void;
}

export interface LeafletStatic {
  map: (element: HTMLElement, options?: LeafletMapOptions) => LeafletMap;
  tileLayer: (url: string, options?: Record<string, unknown>) => LeafletLayer;
  latLngBounds: (points: [number, number][] | unknown) => unknown;
  layerGroup: () => LeafletLayer;
  polyline: (
    points: [number, number][],
    options?: Record<string, unknown>,
  ) => LeafletLayer;
  polygon: (
    points: [number, number][],
    options?: Record<string, unknown>,
  ) => LeafletLayer;
  circleMarker: (
    latlng: [number, number],
    options?: Record<string, unknown>,
  ) => LeafletLayer;
  popup: (options?: Record<string, unknown>) => {
    setLatLng: (latlng: [number, number]) => {
      setContent: (html: string) => { openOn: (map: LeafletMap) => void };
    };
  };
  heatLayer?: (
    points: [number, number, number][],
    options?: Record<string, unknown>,
  ) => LeafletLayer;
}

interface LeafletWindow extends Window {
  L?: LeafletStatic;
}

export function leafletReady(timeoutMs = 5000): Promise<LeafletStatic | null> {
  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      const w = window as LeafletWindow;
      if (w.L) {
        resolve(w.L);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(null);
        return;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  });
}
