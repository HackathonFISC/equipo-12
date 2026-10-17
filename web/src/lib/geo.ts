// Base del panel: portado de src/coordinator/web/panel.html

export interface GeoPoint {
  latitude: number;
  longitude: number;
}

export function haversine(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371000;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(rad(lat1)) *
      Math.cos(rad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function nearestOf<T extends Partial<GeoPoint>>(
  list: T[],
  lat: number,
  lng: number,
): { item: T | null; meters: number } {
  let best: T | null = null;
  let dist = Infinity;
  for (const item of list) {
    if (typeof item.latitude !== "number" || typeof item.longitude !== "number") {
      continue;
    }
    const d = haversine(lat, lng, item.latitude, item.longitude);
    if (d < dist) {
      dist = d;
      best = item;
    }
  }
  return { item: best, meters: dist };
}

export function nearestPlaceWithin<T extends Partial<GeoPoint>>(
  places: T[],
  lat: number,
  lng: number,
  maxMeters: number,
): { item: T | null; meters: number } {
  const nearest = nearestOf(places, lat, lng);
  if (nearest.item == null || nearest.meters > maxMeters) {
    return { item: null, meters: nearest.meters };
  }
  return nearest;
}
