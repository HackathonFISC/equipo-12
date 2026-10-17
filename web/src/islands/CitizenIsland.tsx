import { useRef, useState } from "react";
import {
  postCitizenReport,
  type ExtractedReport,
  type CitizenReportResponse,
} from "../lib/api";

function pickExtraction(
  res: CitizenReportResponse,
): ExtractedReport | null {
  const latest = res.latest_report;
  if (latest && "report_id" in latest && latest.report_id) {
    return latest as ExtractedReport;
  }
  const list = res.extracted_reports;
  if (list.length) return list[list.length - 1] ?? null;
  return null;
}

function fieldOrSinDato(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "sin dato";
  return String(value);
}

export default function CitizenIsland() {
  const [status, setStatus] = useState("");
  const [sending, setSending] = useState(false);
  const [extraction, setExtraction] = useState<ExtractedReport | null>(null);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(
    null,
  );

  const textRef = useRef<HTMLTextAreaElement>(null);
  const autoLocationRef = useRef<HTMLDialogElement>(null);
  const aiExtractionRef = useRef<HTMLDialogElement>(null);

  function openAutoLocation() {
    autoLocationRef.current?.showModal();
  }

  function closeAutoLocation() {
    autoLocationRef.current?.close();
  }

  function confirmLocation() {
    if (!navigator.geolocation) {
      setStatus("Tu navegador no ofrece geolocalización.");
      closeAutoLocation();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
        setStatus("Ubicación guardada para este envío.");
        closeAutoLocation();
      },
      () => {
        setStatus("No se pudo leer la ubicación.");
        closeAutoLocation();
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
    );
  }

  function closeExtractionDialog() {
    aiExtractionRef.current?.close();
  }

  async function handleSend() {
    const text = textRef.current?.value.trim() ?? "";
    if (!text) {
      setStatus("Escribe qué está pasando con el agua antes de enviar.");
      return;
    }

    setSending(true);
    setStatus("Enviando reporte…");
    try {
      const body: Parameters<typeof postCitizenReport>[0] = {
        text,
        source_channel: "citizen_portal",
      };
      if (coords) {
        body.latitude = coords.lat;
        body.longitude = coords.lng;
      }
      const res = await postCitizenReport(body);
      setStatus("El reporte entró a ingesta. Una persona lo revisa.");
      const extracted = pickExtraction(res);
      setExtraction(extracted);
      aiExtractionRef.current?.showModal();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "No se pudo enviar el reporte.";
      setStatus(msg);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5 text-ink shadow-sm">
      <h2 className="font-display text-xl font-bold text-water">
        Reportar falta de agua
      </h2>

      <div className="mt-4">
        <p className="mb-2 text-sm font-semibold text-ink">1. Qué pasó</p>
        <textarea
          id="citizen-text"
          ref={textRef}
          rows={5}
          className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-ink"
          placeholder="Describe la situación: sector, cuánto tiempo sin agua, cuántas personas afectadas…"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-3">
        <button
          type="button"
          className="rounded-lg border border-line bg-canvas px-4 py-2 text-sm font-semibold text-ink"
          onClick={openAutoLocation}
        >
          Usar mi ubicación
        </button>
        <button
          id="citizen-send"
          type="button"
          disabled={sending}
          className="rounded-lg bg-water px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          onClick={() => void handleSend()}
        >
          Enviar reporte
        </button>
      </div>

      <p id="citizen-status" role="status" className="mt-3 text-sm text-muted">
        {status}
      </p>

      <dialog
        id="autoLocationDialog"
        ref={autoLocationRef}
        className="max-w-md rounded-xl border border-line bg-surface p-5 text-ink backdrop:bg-black/40"
      >
        <h3 className="font-display text-lg font-bold">Ubicación del reporte</h3>
        <p className="mt-2 text-sm text-muted">
          Si confirmas, usamos la ubicación de tu dispositivo solo para este
          envío. Puedes cancelar y enviar solo con texto.
        </p>
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-line px-4 py-2 text-sm"
            onClick={closeAutoLocation}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="rounded-lg bg-water px-4 py-2 text-sm font-semibold text-white"
            onClick={confirmLocation}
          >
            Confirmar ubicación
          </button>
        </div>
      </dialog>

      <dialog
        id="aiExtractionDialog"
        ref={aiExtractionRef}
        className="max-w-md rounded-xl border border-line bg-surface p-5 text-ink backdrop:bg-black/40"
      >
        <h3 className="font-display text-lg font-bold">Lo que extrajo ingesta</h3>
        <ul className="mt-3 space-y-2 text-sm">
          <li>
            <span className="font-semibold">Sector: </span>
            {fieldOrSinDato(extraction?.candidate_sector_id)}
          </li>
          <li>
            <span className="font-semibold">Horas sin agua: </span>
            {fieldOrSinDato(extraction?.duration_hours)}
          </li>
          <li>
            <span className="font-semibold">Personas afectadas: </span>
            {fieldOrSinDato(extraction?.affected_count)}
          </li>
        </ul>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="rounded-lg bg-water px-4 py-2 text-sm font-semibold text-white"
            onClick={closeExtractionDialog}
          >
            Entendido
          </button>
        </div>
      </dialog>
    </section>
  );
}
