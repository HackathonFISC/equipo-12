import { useCallback, useEffect, useRef, useState } from "react";
import { getContext, postReports, type SectorMapEntry } from "../lib/api";

const NAME_OVERRIDES: Record<string, string> = {
  "Barrio Colon": "Barrio Colón",
  "Arraijan Cabecera": "Arraiján Cabecera",
  Arraijan: "Arraiján",
};

type ImageMedia = {
  kind: "image";
  filename: string;
  content_base64: string;
  latitude?: number;
  longitude?: number;
};

type AudioMedia = {
  kind: "audio";
  filename: string;
  content_base64: string;
};

function niceName(name: string): string {
  return NAME_OVERRIDES[name] ?? name;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error("No se pudo leer la captura."));
    reader.readAsDataURL(blob);
  });
}

// ponytail: minimal Leaflet typing without adding @types/leaflet
type LeafletMap = {
  invalidateSize: () => void;
  fitBounds: (b: [number, number][], o: object) => void;
};

export default function PublicReport() {
  const [reportText, setReportText] = useState("");
  const [cameraFacing, setCameraFacing] = useState<"user" | "environment">(
    "environment",
  );
  const [cameraOpen, setCameraOpen] = useState(false);
  const [photoPreviewSrc, setPhotoPreviewSrc] = useState("");
  const [photoPreviewHidden, setPhotoPreviewHidden] = useState(true);
  const [photoStatus, setPhotoStatus] = useState("");
  const [audioStatus, setAudioStatus] = useState("");
  const [micLabel, setMicLabel] = useState("Grabar nota");
  const [sendStatus, setSendStatus] = useState("");
  const [sending, setSending] = useState(false);
  const [mapFallback, setMapFallback] = useState(false);
  const [mapInitialized, setMapInitialized] = useState(false);
  const [sectors, setSectors] = useState<SectorMapEntry[]>([]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mapHostRef = useRef<HTMLDivElement>(null);
  const cameraFacingRef = useRef<"user" | "environment">("environment");
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const photoPayloadRef = useRef<ImageMedia | null>(null);
  const audioPayloadRef = useRef<AudioMedia | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordChunksRef = useRef<Blob[]>([]);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<{ clearLayers: () => void } | null>(null);
  const photoObjectUrlRef = useRef<string | null>(null);

  const stopCamera = useCallback(() => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }
    const video = videoRef.current;
    if (video) {
      video.pause();
      video.srcObject = null;
    }
    setCameraOpen(false);
  }, []);

  const openCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setPhotoStatus("Este navegador no permite usar la cámara.");
      return;
    }
    stopCamera();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: cameraFacingRef.current },
        audio: false,
      });
      cameraStreamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      setCameraOpen(true);
    } catch {
      setPhotoStatus(
        "No se pudo abrir la cámara. Permita el acceso en el navegador.",
      );
    }
  }, [stopCamera]);

  const setFacing = useCallback(
    (facing: "user" | "environment") => {
      cameraFacingRef.current = facing;
      setCameraFacing(facing);
      if (cameraStreamRef.current) {
        void openCamera();
      }
    },
    [openCamera],
  );

  const capturePhoto = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setPhotoStatus("No se pudo guardar la foto.");
          return;
        }
        if (photoObjectUrlRef.current) {
          URL.revokeObjectURL(photoObjectUrlRef.current);
        }
        const url = URL.createObjectURL(blob);
        photoObjectUrlRef.current = url;
        setPhotoPreviewSrc(url);
        setPhotoPreviewHidden(false);
        setPhotoStatus("Foto lista. Obteniendo ubicación…");
        stopCamera();

        void blobToBase64(blob)
          .then((encoded) => {
            const payload: ImageMedia = {
              kind: "image",
              filename: "camara.jpg",
              content_base64: encoded,
            };
            photoPayloadRef.current = payload;

            if (!navigator.geolocation) {
              setPhotoStatus(
                "Foto lista. Sin ubicación del aparato: el lugar quedará para revisión.",
              );
              return;
            }
            navigator.geolocation.getCurrentPosition(
              (pos) => {
                photoPayloadRef.current = {
                  ...payload,
                  latitude: pos.coords.latitude,
                  longitude: pos.coords.longitude,
                };
                setPhotoStatus(
                  "Foto lista, con la ubicación de este aparato.",
                );
              },
              () => {
                setPhotoStatus(
                  "Foto lista. Sin ubicación del aparato: el lugar quedará para revisión.",
                );
              },
              { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 },
            );
          })
          .catch((error: Error) => {
            setPhotoStatus(error.message);
          });
      },
      "image/jpeg",
      0.85,
    );
  }, [stopCamera]);

  const toggleMicrophone = useCallback(async () => {
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") {
      recorder.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setAudioStatus("Este navegador no permite usar el micrófono.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordChunksRef.current = [];
      const nextRecorder = new MediaRecorder(stream);
      recorderRef.current = nextRecorder;
      nextRecorder.ondataavailable = (event) => {
        if (event.data?.size) recordChunksRef.current.push(event.data);
      };
      nextRecorder.onstop = () => {
        const blob = new Blob(recordChunksRef.current, {
          type: nextRecorder.mimeType || "audio/webm",
        });
        stream.getTracks().forEach((track) => track.stop());
        void blobToBase64(blob)
          .then((encoded) => {
            audioPayloadRef.current = {
              kind: "audio",
              filename: "nota.webm",
              content_base64: encoded,
            };
            setAudioStatus("Nota de voz lista.");
            setMicLabel("Grabar nota");
          })
          .catch((error: Error) => {
            setAudioStatus(error.message);
            setMicLabel("Grabar nota");
          });
      };
      nextRecorder.start();
      setMicLabel("Detener grabación");
      setAudioStatus("Grabando…");
    } catch {
      setAudioStatus(
        "No se pudo abrir el micrófono. Permita el acceso en el navegador.",
      );
    }
  }, []);

  const sendReport = useCallback(async () => {
    const texts = reportText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    const media: Record<string, unknown>[] = [];
    if (photoPayloadRef.current) media.push({ ...photoPayloadRef.current });
    if (audioPayloadRef.current) media.push({ ...audioPayloadRef.current });
    if (!texts.length && !media.length) {
      setSendStatus("Escriba un reporte, tome una foto o grabe una nota.");
      return;
    }
    setSending(true);
    setSendStatus("");
    try {
      await postReports(texts, media);
      photoPayloadRef.current = null;
      audioPayloadRef.current = null;
      setReportText("");
      setPhotoStatus("");
      setAudioStatus("");
      setPhotoPreviewHidden(true);
      setPhotoPreviewSrc("");
      if (photoObjectUrlRef.current) {
        URL.revokeObjectURL(photoObjectUrlRef.current);
        photoObjectUrlRef.current = null;
      }
      setSendStatus(
        "Su reporte fue recibido. Una persona del equipo lo revisará.",
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo enviar el reporte.";
      if (message.includes("plan already exists")) {
        setSendStatus(
          "En este prototipo se acepta un lote de reportes a la vez. El anterior todavía está en revisión.",
        );
      } else {
        setSendStatus(message);
      }
    } finally {
      setSending(false);
    }
  }, [reportText]);

  type LeafletNS = {
    map: (el: HTMLElement, opts: object) => LeafletMap;
    tileLayer: (
      url: string,
      opts: object,
    ) => { addTo: (map: LeafletMap) => void };
    layerGroup: () => {
      addTo: (map: LeafletMap) => { clearLayers: () => void };
      clearLayers: () => void;
    };
    marker: (latlng: [number, number]) => {
      bindTooltip: (
        text: string,
        opts: object,
      ) => { addTo: (layer: { clearLayers: () => void }) => void };
    };
  };

  const initMap = useCallback(() => {
    const el = mapHostRef.current;
    if (!el) return;
    const L = (window as Window & { L?: LeafletNS }).L;
    const points = sectors.filter(
      (s) =>
        typeof s.latitude === "number" && typeof s.longitude === "number",
    );
    if (!L || !points.length) {
      if (!mapRef.current) setMapFallback(true);
      return;
    }
    setMapFallback(false);
    if (!mapRef.current) {
      el.replaceChildren();
      const map = L.map(el, { scrollWheelZoom: false }).setView(
        [8.91, -79.78],
        12,
      );
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapInitialized(true);
    }
    layerRef.current?.clearLayers();
    const bounds: [number, number][] = [];
    const layer = layerRef.current;
    if (!layer) return;
    points.forEach((s) => {
      L.marker([s.latitude, s.longitude])
        .bindTooltip(niceName(s.name), { permanent: true, direction: "top" })
        .addTo(layer);
      bounds.push([s.latitude, s.longitude]);
    });
    if (bounds.length && mapRef.current) {
      window.setTimeout(() => {
        mapRef.current?.invalidateSize();
        mapRef.current?.fitBounds(bounds, { padding: [36, 36], maxZoom: 13 });
      }, 80);
    }
  }, [sectors]);

  useEffect(() => {
    getContext()
      .then((data) => setSectors(data.sectors ?? []))
      .catch(() => {
        /* mapa vacío si el servicio no responde */
      });
  }, []);

  useEffect(() => {
    if (!sectors.length) return;
    initMap();
    if ((window as Window & { L?: LeafletNS }).L) return;
    const id = window.setInterval(() => {
      if ((window as Window & { L?: LeafletNS }).L) {
        window.clearInterval(id);
        initMap();
      }
    }, 120);
    return () => window.clearInterval(id);
  }, [sectors, initMap]);

  useEffect(() => {
    return () => {
      stopCamera();
      if (photoObjectUrlRef.current) {
        URL.revokeObjectURL(photoObjectUrlRef.current);
      }
    };
  }, [stopCamera]);

  const facingBtn =
    "min-h-11 rounded-full border border-water px-4 py-2 text-sm font-semibold transition-colors";
  const facingActive = "bg-water text-white";
  const facingIdle = "bg-surface text-ink hover:bg-canvas";

  return (
    <>
      <header className="bg-water px-6 py-5 text-white">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          AguaJusta Oeste
        </h1>
        <p className="mt-1 text-sm text-white/85">
          Cuéntenos dónde falta el agua en Arraiján o La Chorrera
        </p>
      </header>

      <main className="mx-auto grid max-w-[1100px] gap-4 p-4 md:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.2fr)]">
        <section className="rounded-2xl border border-line bg-surface p-4 md:p-5">
          <h2 className="font-display text-xl font-semibold text-ink">
            Su reporte
          </h2>
          <p className="mb-3 text-sm text-muted">
            Escriba lo que pasa, tome una foto o grabe una nota. No hace falta
            importar un archivo.
          </p>
          <label
            htmlFor="reports-input"
            className="mb-1 block text-sm font-bold text-ink"
          >
            Texto
          </label>
          <textarea
            id="reports-input"
            className="min-h-28 w-full resize-y rounded-xl border border-line bg-white px-3 py-2 text-ink"
            placeholder="Ejemplo: 48 horas sin agua y 15 personas en el chino de Vista Alegre"
            value={reportText}
            onChange={(e) => setReportText(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              id="btn-camara"
              className={`min-h-11 rounded-full border border-water bg-surface px-4 py-2 text-sm font-bold text-ink ${cameraOpen ? "hidden" : ""}`}
              onClick={() => void openCamera()}
            >
              Abrir cámara
            </button>
            <button
              type="button"
              id="btn-camara-trasera"
              className={`${facingBtn} ${cameraFacing === "environment" ? facingActive : facingIdle}`}
              onClick={() => setFacing("environment")}
            >
              Trasera
            </button>
            <button
              type="button"
              id="btn-camara-frontal"
              className={`${facingBtn} ${cameraFacing === "user" ? facingActive : facingIdle}`}
              onClick={() => setFacing("user")}
            >
              Frontal
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              id="btn-capturar"
              className={`min-h-11 rounded-full bg-water px-4 py-2 text-sm font-bold text-white ${cameraOpen ? "" : "hidden"}`}
              onClick={capturePhoto}
            >
              Tomar foto
            </button>
            <button
              type="button"
              id="btn-cerrar-camara"
              className={`min-h-11 rounded-full border border-water bg-surface px-4 py-2 text-sm font-bold text-ink ${cameraOpen ? "" : "hidden"}`}
              onClick={stopCamera}
            >
              Cerrar cámara
            </button>
            <button
              type="button"
              id="btn-microfono"
              className="min-h-11 rounded-full border border-water bg-surface px-4 py-2 text-sm font-bold text-ink"
              onClick={() => void toggleMicrophone()}
            >
              {micLabel}
            </button>
          </div>
          <video
            id="camera-preview"
            ref={videoRef}
            className={`mt-3 max-h-60 w-full rounded-xl bg-ink object-cover ${cameraOpen ? "" : "hidden"}`}
            playsInline
            autoPlay
            muted
          />
          <canvas id="camera-canvas" ref={canvasRef} className="hidden" />
          <img
            id="photo-preview"
            src={photoPreviewSrc || undefined}
            alt="Foto capturada"
            className={`mt-3 max-h-60 w-full rounded-xl bg-ink object-cover ${photoPreviewHidden ? "hidden" : ""}`}
          />
          <p id="photo-status" className="mt-2 text-sm text-muted">
            {photoStatus}
          </p>
          <p id="audio-status" className="text-sm text-muted">
            {audioStatus}
          </p>
          <div className="mt-4">
            <button
              type="button"
              id="btn-enviar"
              className="min-h-11 rounded-full bg-water px-5 py-2 text-sm font-bold text-white disabled:opacity-45"
              disabled={sending}
              onClick={() => void sendReport()}
            >
              Enviar reporte
            </button>
          </div>
          <p
            id="send-status"
            role="status"
            aria-live="polite"
            className="mt-3 text-sm font-bold text-water"
          >
            {sendStatus}
          </p>
        </section>

        <section className="rounded-2xl border border-line bg-surface p-4 md:p-5">
          <h2 className="font-display text-xl font-semibold text-ink">Mapa</h2>
          <p className="mb-3 text-sm text-muted">
            Arraiján y La Chorrera. Las posiciones son anclas de demostración,
            no un levantamiento ni la red del IDAAN.
          </p>
          <div
            id="sector-map"
            ref={mapHostRef}
            className="h-[360px] rounded-xl bg-canvas md:h-[480px]"
          >
            {mapFallback && !mapInitialized ? (
              <p className="p-4 text-sm text-muted">
                El mapa necesita conexión para cargar el callejero.
              </p>
            ) : null}
          </div>
        </section>
      </main>
    </>
  );
}
