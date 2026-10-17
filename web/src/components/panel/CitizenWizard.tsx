// Base del panel: portado de src/coordinator/web/panel.html (#view-citizen 723-860, parseFreeText 1273-1348)
import { useMemo, useState, type FormEvent } from "react";
import { Badge, Button, Callout, Card } from "../tremor";
import { parseFreeText, type ParseSectorHint } from "../../lib/parseReport";
import { sectorName } from "../../lib/panelDerive";
import type { CitizenWizardProps, PlaceAnchor } from "./contracts";

const VULNERABILITIES = [
  "ADULTOS_MAYORES",
  "EMBARAZADAS",
  "ENFERMEDAD",
  "INFANTES",
] as const;

const STEPS = ["¿Qué pasó?", "¿Dónde?", "¿Cuánto y quiénes?", "Confirmar"];

export function CitizenWizard({
  snapshot,
  busy,
  locationFix,
  onOpenLocation,
  onSubmit,
}: CitizenWizardProps) {
  const [step, setStep] = useState(0);
  const [text, setText] = useState("");
  const [district, setDistrict] = useState("");
  const [sectorId, setSectorId] = useState("");
  const [hours, setHours] = useState<number | null>(null);
  const [people, setPeople] = useState<number | null>(null);
  const [vulns, setVulns] = useState<string[]>([]);
  const coords = locationFix;

  const parsed = useMemo(() => {
    if (!text.trim()) return null;
    const places: PlaceAnchor[] = snapshot.places
      .filter((place) => typeof place.place_id === "string")
      .map((place) => ({
        place_id: String(place.place_id),
        sector_id: String(place.sector_id ?? ""),
        name: String(place.name ?? place.place_id),
        latitude: Number(place.latitude ?? 0),
        longitude: Number(place.longitude ?? 0),
      }));
    const hints: ParseSectorHint[] = snapshot.sectors
      .filter((sector) => typeof sector.name === "string")
      .map((sector) => ({
        sector_id: sector.sector_id,
        name: String(sector.name),
      }));
    return parseFreeText(text, places, hints);
  }, [snapshot.places, snapshot.sectors, text]);

  const districts = useMemo(() => {
    const set = new Set<string>();
    for (const sector of snapshot.sectors) {
      const raw = typeof sector.district === "string" ? sector.district : "";
      if (raw) set.add(raw);
    }
    return [...set].sort();
  }, [snapshot.sectors]);

  const sectorsOfDistrict = snapshot.sectors.filter(
    (sector) => !district || sector.district === district,
  );

  const hourOptions = [6, 18, 36, 72];

  const summary = useMemo(() => {
    const sector = sectorName(snapshot, sectorId || "UNKNOWN");
    const parts = [
      "Falta de agua en " + sector,
      district ? "(" + district + ")" : "",
      hours ? "lleva " + hours + " horas sin agua" : "",
      people ? "afecta a " + people + " personas" : "",
      vulns.length ? "vulnerabilidad: " + vulns.join(", ") : "",
    ].filter(Boolean);
    return parts.join(" · ");
  }, [district, hours, people, sectorId, snapshot, vulns]);

  function toggleVuln(v: string) {
    setVulns((prev) =>
      prev.includes(v) ? prev.filter((item) => item !== v) : [...prev, v],
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({
      text: text.trim() ? text.trim() : summary,
      source_channel: "panel_web",
      sector: sectorId || undefined,
      latitude: coords?.latitude,
      longitude: coords?.longitude,
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Reportar una incidencia
        </p>
        <h1 className="font-display text-2xl font-bold text-ink">
          Portal del ciudadano
        </h1>
      </div>

      <ol className="flex flex-wrap gap-2" aria-label="Pasos">
        {STEPS.map((label, index) => (
          <li key={label} aria-current={step === index ? "step" : undefined}>
            <button
              type="button"
              onClick={() => setStep(index)}
              className={`inline-flex min-h-[36px] items-center gap-2 rounded-full border px-3 text-sm ${
                step === index
                  ? "border-[#312d2a] bg-[#f6f4f3] font-semibold text-[#1c1c1a]"
                  : "border-[#d6d5d2] bg-white text-[#585655]"
              }`}
            >
              <span
                className={`flex size-5 items-center justify-center rounded-full text-xs ${
                  step === index ? "bg-[#312d2a] text-white" : "bg-[#e3e2df] text-[#585655]"
                }`}
              >
                {index + 1}
              </span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      <form onSubmit={handleSubmit}>
        <Card className={step === 0 ? "" : "hidden"}>
          <label htmlFor="citizen-text" className="text-sm font-semibold text-ink">
            Cuéntenos qué pasa
          </label>
          <textarea
            id="citizen-text"
            rows={4}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Ejemplo: llevamos dos días sin agua en Loma Cova, somos 5 personas…"
            className="mt-2 w-full rounded-md border border-line bg-canvas px-3 py-2 text-base text-ink"
          />
          {parsed ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-line bg-sunken p-3 text-sm">
              <span className="font-semibold text-ink">Asistente rápido:</span>
              {parsed.hours != null ? (
                <Badge variant="default">{parsed.hours} h</Badge>
              ) : null}
              {parsed.families != null ? (
                <Badge variant="default">{parsed.families} familias</Badge>
              ) : null}
              {parsed.people != null ? (
                <Badge variant="default">{parsed.people} personas</Badge>
              ) : null}
              {parsed.matchedSector ? (
                <Badge variant="default">{parsed.matchedSector.name}</Badge>
              ) : null}
              {parsed.matchedAnchor ? (
                <Badge variant="default">{parsed.matchedAnchor.name}</Badge>
              ) : null}
              {!parsed.hours &&
              !parsed.people &&
              !parsed.families &&
              !parsed.matchedSector &&
              !parsed.matchedAnchor ? (
                <span className="text-muted">Sin campos detectados todavía.</span>
              ) : null}
            </div>
          ) : null}
          <div className="mt-3 flex justify-end">
            <Button type="button" onClick={() => setStep(1)}>
              Siguiente: dónde
            </Button>
          </div>
        </Card>

        <Card className={step === 1 ? "" : "hidden"}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-semibold text-ink" htmlFor="wizard-district">
              Distrito
              <select
                id="wizard-district"
                value={district}
                onChange={(event) => setDistrict(event.target.value)}
                className="mt-1 h-11 w-full rounded-md border border-line bg-canvas px-3 text-sm font-normal text-ink"
              >
                <option value="">Seleccione…</option>
                {districts.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <fieldset className="mt-3">
            <legend className="text-sm font-semibold text-ink">Sector</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {sectorsOfDistrict.map((sector) => (
                <label
                  key={sector.sector_id}
                  className="flex min-h-[44px] items-center gap-2 rounded-md border border-line bg-canvas px-3 text-sm text-ink"
                >
                  <input
                    type="radio"
                    name="wizard-sector"
                    value={sector.sector_id}
                    checked={sectorId === sector.sector_id}
                    onChange={() => setSectorId(sector.sector_id)}
                  />
                  {typeof sector.name === "string" ? sector.name : sector.sector_id}
                </label>
              ))}
            </div>
          </fieldset>
          {coords ? (
            <p className="mt-3 text-sm text-muted">
              Ubicación: {coords.latitude.toFixed(5)}, {coords.longitude.toFixed(5)}
            </p>
          ) : null}
          <div className="mt-3">
            <Button type="button" variant="secondary" onClick={onOpenLocation}>
              Elegir con GPS o en el mapa
            </Button>
          </div>
          <div className="mt-3 flex justify-between">
            <Button type="button" variant="secondary" onClick={() => setStep(0)}>
              Atrás
            </Button>
            <Button type="button" onClick={() => setStep(2)}>
              Siguiente: cuánto
            </Button>
          </div>
        </Card>

        <Card className={step === 2 ? "" : "hidden"}>
          <fieldset>
            <legend className="text-sm font-semibold text-ink">Horas sin agua</legend>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {hourOptions.map((value) => (
                <label
                  key={value}
                  className="flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-line bg-canvas text-sm text-ink"
                >
                  <input
                    type="radio"
                    name="wizard-hours"
                    value={value}
                    checked={hours === value}
                    onChange={() => setHours(value)}
                  />
                  {value} h
                </label>
              ))}
            </div>
          </fieldset>
          <label className="mt-3 block text-sm font-semibold text-ink" htmlFor="wizard-people">
            Personas afectadas
            <input
              id="wizard-people"
              type="number"
              min={1}
              value={people ?? ""}
              onChange={(event) =>
                setPeople(event.target.value ? Number(event.target.value) : null)
              }
              className="mt-1 h-11 w-full rounded-md border border-line bg-canvas px-3 text-sm font-normal text-ink"
            />
          </label>
          <fieldset className="mt-3">
            <legend className="text-sm font-semibold text-ink">Vulnerabilidad</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {VULNERABILITIES.map((value) => (
                <label
                  key={value}
                  className="flex min-h-[44px] items-center gap-2 rounded-md border border-line bg-canvas px-3 text-sm text-ink"
                >
                  <input
                    type="checkbox"
                    checked={vulns.includes(value)}
                    onChange={() => toggleVuln(value)}
                  />
                  {value === "ADULTOS_MAYORES"
                    ? "Adultos mayores"
                    : value === "EMBARAZADAS"
                      ? "Embarazadas"
                      : value === "ENFERMEDAD"
                        ? "Enfermedad"
                        : "Niñez"}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mt-3 flex justify-between">
            <Button type="button" variant="secondary" onClick={() => setStep(1)}>
              Atrás
            </Button>
            <Button type="button" onClick={() => setStep(3)}>
              Siguiente: confirmar
            </Button>
          </div>
        </Card>

        <Card className={step === 3 ? "" : "hidden"}>
          <h2 className="text-sm font-semibold text-ink">Resumen</h2>
          <p className="mt-2 text-sm text-muted">{summary}</p>
          <Callout
            variant="default"
            title="Revisión automática primero"
            className="mt-3"
          >
            Al enviar, los tres agentes analizan el reporte. El puntaje es determinístico
            (priority-v1); más quejas no suben la prioridad.
          </Callout>
          <div className="mt-3 flex justify-between">
            <Button type="button" variant="secondary" onClick={() => setStep(2)}>
              Atrás
            </Button>
            <Button type="submit" isLoading={busy} loadingText="Enviando…">
              Enviar reporte
            </Button>
          </div>
        </Card>
      </form>
    </div>
  );
}
