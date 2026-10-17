import { Badge, Button, Dialog } from "../tremor";
import type { HelpDialogProps } from "./contracts";

export function HelpDialog({ open, onClose }: HelpDialogProps) {
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
      <h2 className="font-display text-xl font-semibold text-ink">Ayuda</h2>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Flujo del prototipo: (1) un reporte ciudadano entra por ingesta, (2) dos agentes
        determinísticos evalúan y planifican rutas, (3) un coordinador humano aprueba o
        rechaza el borrador, (4) solo entonces se encola la outbox{" "}
        <strong className="text-ink">SIMULATED</strong> en SQLite. No hay despacho real ni
        WhatsApp verificado en demo.
      </p>
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
