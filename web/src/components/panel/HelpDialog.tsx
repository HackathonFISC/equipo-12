import { Badge, Button, Dialog } from "../tremor";
import type { HelpDialogProps } from "./contracts";

export function HelpDialog({ role, open, onClose }: HelpDialogProps) {
  return (
    <Dialog
      id="helpDialog"
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      aria-label="Ayuda"
      className="max-w-lg"
    >
      {role === "citizen" ? (
        <>
          <h2 className="font-display text-xl font-semibold text-ink">
            ¿Qué pasa con su reporte?
          </h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-muted">
            <li>
              Su reporte pasa por 3 agentes: ingesta, evaluación de necesidad y
              planificación de rutas.
            </li>
            <li>
              Si ya hay reportes de su mismo sector (a 800 m o menos), se agrupan en un
              solo incidente.
            </li>
            <li>
              Más quejas no suben la prioridad: la deciden las horas sin agua, las
              personas afectadas y la vulnerabilidad.
            </li>
            <li>
              Los avisos al residente son{" "}
              <strong className="text-ink">SIMULATED</strong> de demostración: no hay
              WhatsApp real.
            </li>
          </ol>
          <p className="mt-3 text-sm text-muted">
            Consulte el estado de su reporte con su código en «Consultar mi reporte».
          </p>
        </>
      ) : (
        <>
          <h2 className="font-display text-xl font-semibold text-ink">Ayuda</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Flujo del prototipo: (1) un reporte ciudadano entra por ingesta, (2) dos
            agentes determinísticos evalúan y planifican rutas, (3) un coordinador humano
            aprueba o rechaza el borrador, (4) solo entonces se encola la outbox{" "}
            <strong className="text-ink">SIMULATED</strong> en SQLite. No hay despacho
            real ni WhatsApp verificado en demo.
          </p>
        </>
      )}
      <p className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted">
        Los datos y sectores mostrados son ilustrativos:
        <Badge variant="synthetic">SYNTHETIC_DEMO</Badge>
      </p>
      <div className="mt-6 flex justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}
