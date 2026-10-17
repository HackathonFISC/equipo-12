// Base del panel: portado de src/coordinator/web/panel.html (autoLocationDialog 912-933, fillGpsPresets 1255-1261, confirmLocation 1450-1479)
import { useEffect, useState } from "react";
import { Badge, Button, Dialog } from "../tremor";
import { nearestOf } from "../../lib/geo";
import type { LocationDialogProps, PlaceAnchor } from "./contracts";

export function LocationDialog({
  open,
  pending,
  places,
  error,
  onClose,
  onConfirm,
  onPickPlace,
  onCoords,
}: LocationDialogProps) {
  const [gpsBusy, setGpsBusy] = useState(false);
  const [latText, setLatText] = useState("");
  const [lngText, setLngText] = useState("");

  useEffect(() => {
    if (!open) {
      setGpsBusy(false);
    }
  }, [open]);

  function requestGps() {
    if (!navigator.geolocation) {
      return;
    }
    setGpsBusy(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsBusy(false);
        onCoords(position.coords.latitude, position.coords.longitude);
      },
      () => setGpsBusy(false),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 },
    );
  }

  function applyTyped() {
    const lat = Number(latText);
    const lng = Number(lngText);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    onCoords(lat, lng);
  }

  const pendingPlace: PlaceAnchor | null =
    pending?.place ??
    (pending
      ? nearestOf(
          places.map((place) => ({
            place_id: place.place_id ?? "",
            sector_id: place.sector_id ?? "",
            name: place.name ?? "",
            latitude: Number(place.latitude ?? 0),
            longitude: Number(place.longitude ?? 0),
          })),
          pending.latitude,
          pending.longitude,
        ).item
      : null);

  return (
    <Dialog id="autoLocationDialog" open={open} onOpenChange={(next) => !next && onClose()} aria-label="Ubicación del reporte">
      <h2 className="font-display text-xl font-semibold text-ink">Ubicación del reporte</h2>
      <p className="mt-1 text-sm text-muted">
        Use GPS, elija un punto de referencia o escriba coordenadas. Las anclas son de
        demostración <Badge variant="synthetic">DATOS DE EJEMPLO</Badge>.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" variant="secondary" isLoading={gpsBusy} loadingText="Buscando…" onClick={requestGps}>
          Usar mi ubicación GPS
        </Button>
      </div>

      <h3 className="mt-4 text-sm font-semibold text-ink">Puntos de referencia</h3>
      <div id="modalPlacesList" className="mt-2 grid max-h-48 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
        {places.slice(0, 15).map((place) => (
          <button
            key={place.place_id}
            type="button"
            className="min-h-[44px] rounded-md border border-line bg-canvas px-3 py-2 text-left text-sm text-ink hover:bg-sunken"
            onClick={() => onPickPlace(place)}
          >
            {place.name}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <label className="text-sm text-muted" htmlFor="lat-manual">
          Latitud
          <input
            id="lat-manual"
            type="text"
            inputMode="decimal"
            value={latText}
            onChange={(event) => setLatText(event.target.value)}
            placeholder="8.980"
            className="mt-1 h-11 w-full rounded-md border border-line bg-canvas px-3 text-sm text-ink"
          />
        </label>
        <label className="text-sm text-muted" htmlFor="lng-manual">
          Longitud
          <input
            id="lng-manual"
            type="text"
            inputMode="decimal"
            value={lngText}
            onChange={(event) => setLngText(event.target.value)}
            placeholder="-79.670"
            className="mt-1 h-11 w-full rounded-md border border-line bg-canvas px-3 text-sm text-ink"
          />
        </label>
      </div>
      <Button type="button" variant="light" className="mt-2" onClick={applyTyped}>
        Usar coordenadas escritas
      </Button>

      {error ? (
        <p className="mt-3 text-sm text-rejected" role="alert">
          {error}
        </p>
      ) : null}
      {pending ? (
        <p className="mt-3 text-sm text-ink">
          Selección actual:{" "}
          <span className="font-semibold">
            {pendingPlace ? pendingPlace.name : `${pending.latitude.toFixed(5)}, ${pending.longitude.toFixed(5)}`}
          </span>{" "}
          <span className="text-muted">
            ({pending.sourceKind === "browser" ? "GPS" : pending.sourceKind === "preset" ? "referencia" : "manual"})
          </span>
        </p>
      ) : null}

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="button" variant="primary" disabled={!pending} onClick={onConfirm}>
          Confirmar ubicación
        </Button>
      </div>
    </Dialog>
  );
}
