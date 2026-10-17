import { type FormEvent, useEffect, useState } from "react";
import {
  getContext,
  type CoordinatorSnapshot,
  type ExtractedReport,
  type PlanState,
} from "../lib/api";

function fieldOrMissing(value: unknown): string {
  if (value == null || value === "") return "sin dato";
  return String(value);
}

function planLabel(state: PlanState): string {
  if (state == null) return "sin plan";
  return state;
}

export default function TrackingIsland() {
  const [code, setCode] = useState("");
  const [snapshot, setSnapshot] = useState<CoordinatorSnapshot | null>(null);
  const [match, setMatch] = useState<ExtractedReport | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getContext()
      .then((data) => {
        if (!cancelled) setSnapshot(data);
      })
      .catch(() => {
        if (!cancelled) setSnapshot(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const needle = code.trim();
    if (!needle || !snapshot) {
      setMatch(null);
      return;
    }
    const found =
      snapshot.extracted_reports.find((row) => row.report_id === needle) ??
      null;
    setMatch(found);
  };

  const planState = snapshot?.state ?? null;

  return (
    <section className="rounded-2xl border border-line bg-surface p-5">
      <h2 className="font-display text-xl font-semibold text-ink">
        Consultar un reporte
      </h2>
      <p className="mt-1 mb-4 text-sm text-muted">
        Escriba el código y pulse Consultar. No se busca al cargar la página.
      </p>
      <form
        id="trackingForm"
        className="flex flex-wrap gap-2"
        onSubmit={onSubmit}
      >
        <label htmlFor="tracking-code" className="w-full text-sm font-bold text-ink">
          Código del reporte
        </label>
        <input
          id="tracking-code"
          type="text"
          autoComplete="off"
          className="min-w-48 flex-1 rounded-xl border border-line bg-canvas px-3 py-2 text-ink"
          placeholder="Código del reporte"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <button
          type="submit"
          className="rounded-full bg-water px-5 py-2 text-sm font-bold text-white"
        >
          Consultar
        </button>
      </form>
      <div
        id="tracking-result"
        role="status"
        className="mt-4 min-h-16 rounded-xl border border-line bg-canvas p-4 text-sm"
      >
        {match ? (
          <dl className="grid gap-2">
            <div>
              <dt className="text-muted">Sector</dt>
              <dd className="font-semibold text-ink">
                {fieldOrMissing(match.candidate_sector_id)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Horas</dt>
              <dd className="font-semibold text-ink">
                {fieldOrMissing(match.duration_hours)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Afectados</dt>
              <dd className="font-semibold text-ink">
                {fieldOrMissing(match.affected_count)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Estado del plan</dt>
              <dd className="font-semibold text-ink">{planLabel(planState)}</dd>
            </div>
          </dl>
        ) : queried ? (
          <p className="text-ink">No hay un reporte con ese código.</p>
        ) : null}
      </div>
    </section>
  );
}
