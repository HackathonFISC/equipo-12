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
              Su reporte lo revisan tres agentes: el de ingesta lo ordena y lo ubica, el de evaluación mide la urgencia y el de planificación propone el reparto de cisternas. Al final, una persona de la coordinación decide.
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
              <strong className="text-ink">de demostración</strong>: no llegan a tu teléfono ni por WhatsApp. Los ves en «Consultar mi reporte».
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
            Cómo funciona: (1) entra un reporte de un vecino, (2) el sistema mide la urgencia y arma el reparto de cisternas, (3) una persona de la coordinación aprueba o rechaza ese reparto, (4) solo entonces quedan escritos los avisos de{" "}<strong className="text-ink">demostración</strong> para cada sector. No hay envío real a teléfonos en esta demo.
          </p>
        </>
      )}
      <p className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted">
        Los datos y sectores mostrados son ilustrativos:
        <Badge variant="synthetic">DATOS DE EJEMPLO</Badge>
      </p>
      <div className="mt-6 flex justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}
