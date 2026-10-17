# Rediseño visual del panel AguaJusta

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

## Goal

Reconstruir la interfaz de `/admin` (coordinación) y `/ciudadano` (portal) con la densidad y la estructura visual de la consola de Oracle Cloud (capturas en `captures/oci-dashboard-frankfurt/`), **sin copiar marca, logo, nombre Oracle ni textos de OCI**. La identidad sigue siendo AguaJusta Oeste. Solo se rehace la UI en su sitio, reutilizando toda la lógica existente (hooks, lib, contratos, derivados). No se toca `src/` de Python, contratos, fórmula priority-v1, solver, deduplicación ni la compuerta humana.

## Architecture

Dos aplicaciones insulares montadas por Astro:
- `web/src/pages/admin.astro` y `web/src/pages/coordinacion.astro` montan `web/src/islands/AdminApp.tsx` (rol admin fijo).
- `web/src/pages/ciudadano.astro` monta `web/src/islands/CitizenApp.tsx` (rol ciudadano fijo).
- Ambas comparten `web/src/components/panel/Shell.tsx`, que se divide en una cabecera oscura compartida y un menú lateral por secciones.
- La lógica de datos vive sin cambios en `web/src/hooks/useSnapshot.ts`, `web/src/hooks/usePanelNav.ts`, `web/src/lib/api.ts`, `web/src/lib/panelDerive.ts`, `web/src/lib/parseReport.ts`, `web/src/lib/text.ts` y `web/src/components/panel/contracts.ts`.
- Los componentes de UI se rehacen en `web/src/components/panel/*` sobre las primitivas Tremor ya adaptadas en `web/src/components/tremor/*` (Badge, Button, Card, Table, Tracker, Dialog, Callout, Accordion, CategoryBar, BarList) y `lucide-react`. Leaflet y `leaflet.heat` se mantienen por CDN.

## Tech Stack

- Astro 7 (`astro`, `@astrojs/react`), build estático (`output: "static"`).
- React 19 (`react`, `react-dom`).
- Tailwind 4 (`tailwindcss`, `@tailwindcss/vite`, `tailwind-merge`) + `class-variance-authority` + `clsx`. Tokens de color en `web/src/styles/global.css` (`@theme`).
- `lucide-react` para iconos.
- Leaflet 1.9.4 + leaflet.heat 0.2.0 por CDN (ya en `web/src/layouts/Base.astro`), sin nuevas dependencias.
- Componentes Tremor adaptados (Apache-2.0) en `web/src/components/tremor/`.
- Verificación de UI: `cd web && bun run build`. Tests de comportamiento: `TMP=/tmp MODO=test .venv/bin/python -m unittest discover -s tests` (al menos el build si el cambio no toca Python).

## Límites duros (recordatorio)

- Sin nuevas dependencias. Sin arrancar servidores.
- No cambiar `src/` de Python, contratos (`contracts.ts`, `api.ts`), fórmula priority-v1, solver, deduplicación ni la compuerta humana.
- El ciudadano no aprueba: sin botón APPROVE, sin outbox. Avisos SIMULATED solo tras aprobación humana del coordinador.
- Textos del flujo se conservan tal cual: títulos, botones y estados `Borrador`/`Pendiente`/`Aprobado`/`Rechazado`.
- Sin marca/logo/nombre Oracle ni textos de OCI. Identidad: AguaJusta Oeste.
- Commits solo si una tarea lo pide, mensaje del equipo, sin `Co-authored-by`.

---

## Tareas (en este orden, cada una entregable sola)

### Tarea 1: Tokens y shell compartido — cabecera oscura, búsqueda, selector de ámbito, navegación lateral

**Objetivo:** Admin y ciudadano comparten una cabecera oscura de estilo consola (logo AguaJusta Oeste, búsqueda, selector de ámbito por distrito) y un menú lateral por secciones, dejando de parecer el mismo shell genérico. No hay región Oracle: el ámbito es distrito (Arraiján / La Chorrera).

**Files**
- Create: `web/src/components/panel/AppHeader.tsx` — cabecera oscura compartida (fondo oscuro, logo AguaJusta Oeste con icono Droplet, campo de búsqueda, selector de ámbito/distrito, menús de usuario/ayuda a la derecha).
- Create: `web/src/components/panel/SidebarNav.tsx` — menú lateral por secciones (Admin: Centro de coordinación, Mapa operativo, Consultar reporte; Ciudadano: Reportar incidencia, Consultar mi reporte, Mapa comunitario), con estado activo y versión móvil.
- Modify: `web/src/styles/global.css` — añadir tokens de cabecera oscura (bg, border, texto, hover) sin eliminar los existentes.
- Modify: `web/src/components/panel/Shell.tsx` — usar `AppHeader` + `SidebarNav` tanto en `AdminShell` como en `CitizenShell`; conservar `stateLabel`, `role`, `title`, `onNavigate`.
- Modify: `web/src/components/panel/contracts.ts` — añadir `ShellHeaderProps` / `SidebarNavProps` si hace falta; no cambiar tipos existentes usados por las islas.

**Pasos de test que falle (antes de implementar)**
- `cd web && bun run build` falla o no hay evidencia visual de cabecera oscura compartida (no existe `AppHeader.tsx` ni `SidebarNav.tsx`; Shell tiene cabeceras duplicadas admin/cityano).
- No hay selector de ámbito por distrito en la cabecera; solo filtro de distrito dentro de tablas/mapa.

**Implementación mínima**
- `AppHeader`: `<header className="bg-navy ...">` con logo (Droplet + "AguaJusta OESTE", sin Oracle), `<input type="search">` con lupa, `<select>` de ámbito con opciones "Todos los distritos", "Arraiján", "La Chorrera", y a la derecha badge de estado del plan + botón Ayuda.
- `SidebarNav`: `<aside>` navy fijo en desktop, menú desplegable en mobile; enlaces/por vista con `aria-current`.
- `Shell` renderiza `AppHeader` arriba y `SidebarNav` a la izquierda; el `main` conserva `max-w-[1600px]` (admin) o `max-w-[1080px]` (ciudadano).
- Tokens en `global.css`: `--color-header-bg`, `--color-header-border`, `--color-header-text`, etc.

**Verificación**
- `cd web && bun run build` OK.
- La cabecera es oscura y es idéntica (compartida) en `/admin` y `/ciudadano`.
- El selector de ámbito muestra distritos, no regiones Oracle.

**Commit:** `feat: shell compartido con cabecera oscura y navegación lateral`

---

### Tarea 2: Portal ciudadano en el teléfono — los 4 pasos del flujo, sin aprobar

**Objetivo:** `/ciudadano` muestra el flujo del teléfono tal cual `docs/flujo_telefono_y_aprobacion.md`: "Portal del ciudadano", "Reportar incidencia", 4 pasos (¿Qué pasó? / ¿Dónde? / ¿Cuánto y quiénes? / Confirmar), "Enviar reporte", "Reporte recibido", "Resultado del análisis" con los 3 agentes, "Consultar mi reporte" por código. No hay botón de aprobar.

**Files**
- Modify: `web/src/islands/CitizenApp.tsx` — conservar lógica (`submitCitizen`, `lookupReport`, `tracking`, `extraction`); solo rehacer la presentación para que cada vista use el nuevo lenguaje visual.
- Modify: `web/src/components/panel/CitizenWizard.tsx` — 4 tarjetas/etapas con los rótulos exactos: "¿Qué pasó?", "¿Dónde?", "¿Cuánto y quiénes?", "Confirmar"; botón "Enviar reporte" (pasa a "Enviando…"); sin botón de aprobar.
- Modify: `web/src/components/panel/ExtractionDialog.tsx` — "Resultado del análisis" con 3 tarjetas agente (Ingesta, Evaluación, Planificación) y los mismos rótulos de resultado.
- Modify: `web/src/components/panel/TrackingView.tsx` — "Consultar mi reporte", campo de código, chips rápidos, estado Borrador/Pendiente/Aprobado/Rechazado, pastilla de estado.
- Modify: `web/src/components/panel/LocationDialog.tsx` — ubicación (GPS, referencias, coordenadas), conservar Leaflet anclas.
- Modify: `web/src/components/panel/contracts.ts` — solo si se añaden props nuevas; no cambiar `CitizenWizardProps` ni `TrackingViewProps` de forma que rompa las islas.

**Pasos de test que falle (antes de implementar)**
- No existe un flujo de 4 pasos con los rótulos exactos del flujo; el wizard actual sí los tiene pero la presentación no sigue la densidad de consola.
- Ciudadano ve opciones de aprobación (no debe haber ninguna).
- Falta "Resultado del análisis" con 3 agentes al enviar.

**Implementación mínima**
- Conservar `STEPS = ["¿Qué pasó?", "¿Dónde?", "¿Cuánto y quiénes?", "Confirmar"]` y el título "Portal del ciudadano".
- Paso 4 "Confirmar": resumen + botón "Enviar reporte"; al enviar, toast "Reporte recibido." y abrir `ExtractionDialog` "Resultado del análisis" (Ingesta / Evaluación / Planificación).
- `TrackingView`: buscar por código (`svc-1`, `svc-2`), mostrar chip de estado, pasos ETAPA 01..04, cisterna asignada, aviso SIMULATED. Sin botón de aprobar.
- `ExtractionDialog`: 3 agentes con mismos textos (cluster, prioridad score/100, "ver panel de coordinación").

**Verificación**
- `cd web && bun run build` OK.
- En `/ciudadano`: 4 pasos con rótulos exactos, "Enviar reporte", no hay botón "Aprobar plan"; tras enviar aparece "Resultado del análisis" con 3 agentes; "Consultar mi reporte" busca por código.

**Commit:** `feat: portal ciudadano con los 4 pasos del flujo y sin aprobar`

---

### Tarea 3: Centro de coordinación — lista tipo tabla de instancias, filtro, pastilla de estado

**Objetivo:** `/admin` vista "Centro de coordinación" muestra una tabla densa tipo consola de instancias (reportes/paradas/clusteres): título, una línea de contexto, filtro aplicado, botón primario, tabla con columnas (código, lugar, sector, afectados, prioridad, estado), pastilla de estado por fila. Cartel SYNTHETIC_DEMO/ASSUMPTION y prioridad-v1 no es política del IDAAN.

**Files**
- Modify: `web/src/islands/AdminApp.tsx` — vista `admin`: rehacer presentación (cabecera de sección con título + línea de contexto, filtro, botón primario "Procesar lote", tabla, métricas, plan gate a un costado); conservar `useSnapshot`, `buildIncidentRows`, `computeMetrics`, `derivePlan`, filtros `query`/`status`/`districtFilter`.
- Modify: `web/src/components/panel/IncidentsTable.tsx` — tabla densa: encabezado pegajoso, fila clickeable, pastilla de estado (`Badge`) por fila, columna de prioridad con color de nivel, conteo "N de M resultados".
- Modify: `web/src/components/panel/MetricsRow.tsx` — tarjetas métricas (reportes, sectores, plan pendiente, despachos SIMULATED) con densidad de consola.
- Modify: `web/src/components/panel/PlanGate.tsx` — conservar compuerta (se rehace en la tarea 4); aquí solo asegurar que encaja en el nuevo shell.
- Modify: `web/src/components/panel/contracts.ts` — solo si se añaden props; no romper `IncidentsTableProps`.

**Pasos de test que falle (antes de implementar)**
- No hay tabla de instancias con columnas código/lugar/sector/afectados/prioridad/estado.
- No hay pastilla de estado por fila ni filtro aplicado visible.
- Falta el cartel SYNTHETIC_DEMO/ASSUMPTION en la vista de coordinación.

**Implementación mínima**
- `IncidentsTable`: `<TableRoot>` con `TableHead` (Código, Lugar, Sector, Afectados, Prioridad, Estado), `TableBody` filas `cursor-pointer` con `onClick` para abrir detalle; estado como `Badge` (Recibido/En análisis/En plan/Aprobado); columna prioridad con clase de color por nivel.
- `AdminApp` vista admin: Callout de advertencia con `Badge SYNTHETIC_DEMO` + `Badge ASSUMPTION`; `MetricsRow`; `IncidentsTable` con `query`, `status`, `districtFilter`; `PlanGate` a la derecha.
- Filtro aplicado se muestra como chip o texto de contexto bajo el título.

**Verificación**
- `cd web && bun run build` OK.
- `/admin` muestra tabla de instancias con filtro, pastilla de estado, y el cartel de datos sintéticos.

**Commit:** `feat: centro de coordinación con tabla de instancias, filtro y pastilla de estado`

---

### Tarea 4: Ficha del plan — pestañas, desglose priority-v1, ruta, compuerta, confirmación SIMULATED, audit_id

**Objetivo:** Ficha del plan de distribución con pestañas, desglose de la fórmula priority-v1 (etiqueta/valor), ruta ordenada, compuerta humana "Enviar a revisión" / "Aprobar plan" / "Rechazar" / "Corregir plan", confirmación de avisos SIMULATED, y `audit_id`. Insignia Borrador → Pendiente → Aprobado/Rechazado. No WhatsApp a residentes.

**Files**
- Modify: `web/src/components/panel/PlanGate.tsx` — pestañas (Resumen / Desglose priority-v1 / Ruta / Trazas), insignia de estado del plan, botones "Enviar a revisión", "Aprobar plan", "Rechazar", "Corregir plan"; dialog de confirmación con texto "Encola avisos SIMULATED. No envía WhatsApp a residentes."; mostrar `audit_id` tras ejecución. Conservar `PlanGateProps` y toda la lógica de `onReview`/`onApprove`/`onReject`/`onCorrect`.
- Modify: `web/src/components/panel/DetailDialog.tsx` — ficha de detalle con pestañas y pares etiqueta/valor (Código, Reportes, Precisión, Evidencia, Requiere revisión, prioridad con desglose). Conservar `DetailDialogProps`.
- Modify: `web/src/components/panel/contracts.ts` — solo si se añaden props opcionales; no cambiar tipos existentes.

**Pasos de test que falle (antes de implementar)**
- No hay pestañas en la ficha del plan; todo es una sola tarjeta.
- No se ve el desglose priority-v1 (factor/puntos/razón) ni la ruta ordenada.
- Falta `audit_id` visible tras aprobar; falta confirmación SIMULATED.

**Implementación mínima**
- `PlanGate`: `estado` insignia (Borrador/Pendiente/Aprobado/Rechazado), litros/cisternas/paradas, rutas como lista de paradas ordenadas, pestañas; botones con los rótulos exactos; `onApprove` abre dialog de confirmación (SIMULATED, no WhatsApp) y al confirmar llama a la decisión; muestra `Auditoría {audit_id}`.
- `DetailDialog`: pares etiqueta/valor en `dl`, prioridad con `CategoryBar` y lista factor → puntos.

**Verificación**
- `cd web && bun run build` OK.
- Insignia Borrador; "Enviar a revisión" → Pendiente; se habilitan Aprobar/Rechazar/Corregir; "Aprobar plan" → confirmación SIMULATED → Aprobado con `audit_id`. No hay WhatsApp.

**Commit:** `feat: ficha del plan con pestañas, desglose priority-v1, ruta y compuerta SIMULATED`

---

### Tarea 5: Mapa y trazas dentro del mismo lenguaje visual — sin perder Leaflet ni la outbox simulada

**Objetivo:** Mapa operativo y mapa comunitario con Leaflet + heatmap (capas, borde del área de interés, leyenda de niveles), barra de sectores con prioridad, trazas de los 3 agentes (ingesta/evaluación/planificación/orquestador), duplicados y bandeja de avisos SIMULATED. Todo con la densidad y estructura de la consola, sin perder la outbox simulada.

**Files**
- Modify: `web/src/components/panel/MapView.tsx` — rehacer presentación (título, línea de contexto, filtro de distrito, mapa Leaflet con heatmap o círculos de respaldo, barra lateral de sectores con puntaje, métricas alta/media/reportes). Conservar `leafletReady`, `PANAMA_OESTE_BORDER`, `heatPoints`, `districtFilter`, `onSelectSector`.
- Modify: `web/src/components/panel/TracesPanel.tsx` — trazas por agente con acordeón (Acción, Entrada, Salida, traceId), estado ok/error. Conservar `TraceStageCard`.
- Modify: `web/src/components/panel/DuplicatesPanel.tsx` — duplicados y bandeja de avisos (canal SIMULATED, estado QUEUED/PREVIEW). Conservar `DuplicateBlock`, `OutboxNotice`.
- Modify: `web/src/components/panel/MapView.tsx` — quitar el botón "Registrar reporte" del mapa operativo (el ciudadano reporta desde el portal, no desde el mapa). El mapa ciudadano conserva su propósito.
- Modify: `web/src/lib/panelDerive.ts` — sin cambios de lógica; solo se consume. (No modificar; listado para claridad.)

**Pasos de test que falle (antes de implementar)**
- El mapa usa Leaflet pero no tiene la densidad de consola (título, línea de contexto, filtro, barra de sectores).
- No hay trazas de los 3 agentes ni bandeja de avisos SIMULATED.
- Mapa operativo ofrece "Registrar reporte" (no debe).

**Implementación mínima**
- `MapView`: cabecera de sección con título ("Panamá Oeste · mapa operativo" / "Mapa comunitario de afectaciones"), línea de contexto, `<select>` filtro de distrito, mapa `<div id="affectedMap">` con Leaflet, heatmap si está disponible y círculos de respaldo, leyenda de niveles (alta/media/baja/sin reportes), barra de sectores con `BarList` y detalle clickeable.
- `TracesPanel`: 4 tarjetas de agente (Ingesta, Evaluación, Planificación OR-Tools, Orquestador) en acordeón.
- `DuplicatesPanel`: bloques de duplicados + lista de avisos `SIMULATED`.

**Verificación**
- `cd web && bun run build` OK.
- Leaflet sigue funcionando (heatmap o círculos de respaldo), no se rompe el mapa; trazas y outbox SIMULATED presentes.

**Commit:** `feat: mapa y trazas en el lenguaje visual de consola, outbox SIMULATED conservada`

---

### Tarea 6: Build de web y comprobación de textos del flujo en el código fuente

**Objetivo:** Verificar que `cd web && bun run build` pasa y que todos los textos del flujo (títulos, botones, estados) siguen presentes en el código fuente tras el rediseño.

**Files**
- Test: `cd web && bun run build`.
- Test: `grep` de textos del flujo sobre `web/src/` (títulos, botones, estados).

**Pasos de test que falle (antes de implementar)**
- `bun run build` falla por algún componente rehacido.
- Algunos textos del flujo desaparecieron al rehacer la UI (ej. "Portal del ciudadano", "Enviar reporte", "Borrador", "Pendiente", "Aprobado", "Rechazado", "Enviar a revisión", "Aprobar plan", "Rechazar", "Corregir plan", "Reporte recibido", "Resultado del análisis", "Consultar mi reporte", "audit_id", "SIMULATED").

**Implementación mínima**
- Ejecutar `cd web && bun run build`; corregir errores de TypeScript/TSX si aparecen.
- Ejecutar greps para confirmar presencia de los textos del flujo.

**Verificación**
- `cd web && bun run build` → OK (sin errores).
- `grep -r` confirma textos del flujo en `web/src/`.
- (Opcional, si no tocó Python) `TMP=/tmp MODO=test .venv/bin/python -m unittest discover -s tests` → OK.

**Commit:** `chore: build de web y comprobación de textos del flujo`

---

## Criterios de aceptación globales

- `cd web && bun run build` pasa sin errores después de cada tarea y al final.
- No se agregó ninguna dependencia nueva.
- No se modificó `src/` de Python, `contracts.ts`, `api.ts`, `panelDerive.ts`, `parseReport.ts`, ni la fórmula priority-v1 / solver / deduplicación / compuerta humana.
- El ciudadano no tiene botón de aprobar; sin APPROVE no hay outbox. Los avisos son `SIMULATED`.
- Identidad: AguaJusta Oeste en todas partes; cero menciones a marca/logo/nombre Oracle ni textos de OCI.
- Textos del flujo conservados exactamente: títulos, botones y estados `Borrador`/`Pendiente`/`Aprobado`/`Rechazado`.
- Cada tarea es entregable y verificable sola con `bun run build`.
