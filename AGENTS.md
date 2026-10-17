# AGUAJUSTA OESTE — contexto del repositorio

Contexto completo para cualquier agente (OpenCode, Cursor, Claude Code u otro) que clone este repo. Léelo antes de trabajar. No dependas de archivos locales que no estén en git.

**Repositorio:** https://github.com/HackathonFISC/equipo-12  
**Equipo:** Joaquín Porsella (@porsellaj), Edward Sparks (@EdwardSparks), Franz Vera (@Meowty7).  
**Reto:** 1 — Agua. Nombre provisional: AguaJusta Oeste.  
**Problema:** en Panamá Oeste (prioridad Arraiján y La Chorrera) los reportes de falta de agua llegan dispersos, duplicados y sesgados por visibilidad. Quien más se queja recibe primero, no quien más lo necesita. El sistema convierte ese caos en un plan de cisternas justo, explicable y aprobable por un humano.

`01_CONTEXTO_MAESTRO.md`, `02_EQUIPO_Y_METODOLOGIA.md` y `03_PROMPT_MAESTRO_OPENCODE.md` son copias locales del equipo, ignoradas por git. Este archivo es la fuente que viaja con el repositorio. Si existen en la máquina, léelos como complemento; si contradicen a este archivo, prevalece lo que está commiteado aquí hasta que el equipo actualice este archivo.

## Objetivo del producto

Transformar reportes ciudadanos desordenados en un plan de distribución de cisternas **justo, explicable, determinístico y sujeto a aprobación humana**. No es una interfaz de chat ni una respuesta sustituible por un prompt: percibe datos, los analiza, ejecuta herramientas, deja trazas y actúa sobre un estado persistente.

La injusticia que hay que romper: el mismo incidente reportado muchas veces no compra prioridad. La prioridad sale de horas sin agua, afectados y vulnerabilidad, con desglose auditable. El volumen de quejas no es un factor.

## Requisitos de la competencia

1. Mínimo 3 agentes con roles distintos que se comuniquen.
2. Mínimo una herramienta que ejecute una acción real (solver, escritura en base, outbox), no solo texto.
3. Validación, deduplicación, puntuación, asignación y rutas con código. El LLM no decide esos números.
4. Humano en el ciclo: revisar, corregir, aprobar o rechazar. El sistema explica la decisión. Ningún agente aprueba su propio plan.
5. Trazabilidad de agente, herramienta, entradas/salidas relevantes, errores y decisión humana. Nunca secretos.
6. Evals propios: mínimo 15 casos, métrica definida y resultados realmente ejecutados.
7. Guardrails ante entrada vacía, imposible, maliciosa, absurda, incompleta, duplicada, fuera de área y archivo inexistente.
8. README, diagrama, instalación/ejecución, fuentes, evals, bitácora de IA y documento de metodología.
9. Video de demo de máximo 3 minutos y sustentación de máximo 7 minutos.
10. Repo registrado en la primera hora, commits durante las 24 h, tag `final-24h` sobre el último commit válido en T0 + 24 h. Nada evaluable después del tag.

## MVP

1. La persona coordinadora carga o pega reportes de texto.
2. Ingesta extrae campos y marca incertidumbre. No inventa ubicación, afectados ni duración.
3. Código determinístico normaliza alias de sectores, valida rangos, agrupa duplicados y conserva procedencia.
4. Evaluación analiza evidencia y factores cualitativos. El código aplica la fórmula de prioridad y muestra el desglose. Los pesos son política de prototipo, no política oficial del IDAAN.
5. Planificación llama una herramienta determinística de asignación/rutas con capacidad, turnos y ventanas. OR-Tools solo si se instala y valida temprano; si no, heurística determinística probada y documentada.
6. El coordinador revisa el borrador, corrige si hace falta y aprueba o rechaza.
7. Solo tras aprobación, una transacción guarda el plan, las asignaciones, la outbox de notificaciones simuladas y el log de auditoría (SQLite si el starter lo permite).
8. La UI muestra reportes consolidados, prioridad con explicación, plan/rutas, demanda no atendida, trazas y la acción humana.

Sin integración operativa verificada, no afirmar despacho real de cisternas, WhatsApp real ni avería actual. Etiquetar `OFFICIAL_SOURCE`, `SYNTHETIC_DEMO` o `ASSUMPTION`. La acción real demostrable es ejecutar el solver y persistir el despacho aprobado con outbox simulada.

## Agentes

Flujo por defecto secuencial: Ingesta → Evaluación → Planificación. Paralelizar solo ramas independientes y si el tiempo o la cuota lo justifican. Contratos Pydantic. El esquema valida forma, no verdad.

- **Ingesta.** Texto en el MVP. No gastar tiempo en audio o fotos si el starter no lo facilita. Salida: ubicación/sector candidato, duración, afectados, evidencia, confianza, incertidumbres, `requiere_revision`.
- **Evaluación de necesidad.** Factores, evidencia, riesgos e incertidumbres. No calcula ni modifica el score numérico.
- **Planificación.** Analiza restricciones y llama la herramienta del algoritmo. Devuelve plan propuesto, factibilidad y demanda no cubierta.

Cada agente recibe solo sus herramientas. Permisos en código, no solo en prompts. `instructions`, tools con nombre/tipos/docstrings, `output_type=BaseModel` en salidas que alimentan decisiones. Subagente = `Agent` llamado desde una tool del orquestador (`@orquestador.tool`, `RunContext`, `usage=ctx.usage` si el SDK lo permite). `UsageLimits` y parada antes de la primera llamada real. Sin loops ni reintentos ilimitados. Errores recuperables vuelven como `ERROR: ...`; el orquestador decide parar, usar datos parciales o pedir revisión.

## Contratos

Ajustar nombres y rutas al starter, pero estos conceptos se acuerdan antes de separar el trabajo:

- `ReportInput`: texto, identificador, procedencia.
- `ReportExtracted`: incidente/sector candidato, duración, afectados, evidencia, incertidumbre, requiere revisión.
- `Assessment`: factores y evidencias. El score final lo calcula el código.
- `PriorityResult`: valor, desglose, versión de la fórmula, explicación.
- `PlanDraft`: asignaciones, rutas/orden, capacidad/turnos, restricciones cumplidas, demanda no cubierta.
- `HumanDecision`: aprobar/rechazar/corregir, actor, comentario, timestamp.
- `ExecutionResult`: si se guardó plan/outbox y el id de auditoría.

El LLM no fija el score final, la capacidad de una cisterna ni la validez de una ruta.

## Equipo y orden de integración

- **Joaquín:** orquestación, contratos Pydantic, modelo/credenciales, `UsageLimits`, Ingesta, flujo 1→2→3, integración, health check, README, tag. No implementa el solver ni toda la UI.
- **Edward:** fixtures, alias, validación, deduplicación, score explicable, restricciones, solver, evals iniciales y fuentes. Funciones puras y pruebas unitarias. No presentar la capa de tuberías del IDAAN como cortes actuales.
- **Franz:** panel del coordinador, prioridad/rutas, aprobar/rechazar/corregir, persistencia auditable, trazas, diagrama y guion del video. Estados visibles: borrador, pendiente, aprobado, rechazado, error/parcial. No cambia contratos ni añade servicios externos sin acuerdo.

Orden: (1) starter, contratos y nombres de módulos en los primeros 20 minutos; registrar el repo en la primera hora; (2) fixtures sintéticos y validación de rutas; (3) motor determinístico y tests; (4) agentes en `MODO=test`; (5) tool de planificación y persistencia tras aprobación; (6) panel y trazas; (7) 15+ evals y un smoke test real controlado; (8) README, metodología, bitácora, video y tag. Cada persona es dueña de su área, commits pequeños, sin editar el mismo archivo a la vez. Antes de cambiar un contrato compartido, coordinarlo.

## Datos

Fixtures determinísticos versionados. No regenerarlos con el LLM en cada ejecución. Capa GIS candidata del IDAAN: https://sig.idaan.gob.pa/server/rest/services/Servicios_vista/AcueductoSDE/MapServer/5 — es infraestructura de tuberías, no reportes de averías, población, camiones ni ETA. Usarla solo tras comprobar campos, cobertura, atribución y extracción. Registrar título, entidad, URL, fecha de acceso, campos usados, cobertura y límites en `docs/FUENTES_Y_DATOS.md`. No inventar estadísticas oficiales, pesos institucionales ni personas reales.

## Reglas de implementación

- Inspeccionar antes de codear: `git status --short`, `git remote -v`, `git branch --show-current`, `git log --oneline -5`, README, árbol, dependencias y tests. No `git init`, no repo paralelo, no borrar ni sustituir archivos sin entenderlos.
- Reutilizar el stack del starter salvo incompatibilidad demostrada. Plan de máximo 10 líneas y riesgos reales; luego implementar sin pedir confirmación de lo ya definido aquí.
- Construcción: fixtures y validadores, motor, agentes en test, tool, acción tras aprobación, UI, evals, docs.
- Corrección: reproducir, aislar causa, cambio mínimo, repetir la prueba fallida y las regresiones. No afirmar que un test pasó sin ejecutarlo. Si el mismo error sigue tras una corrección razonable, parar y reportar `BLOQUEADO` con evidencia.
- Rutas desde `Path(__file__).resolve()` o raíz del proyecto. Comprobar que fixtures y políticas existen, son UTF-8, no están vacíos y traen los IDs esperados antes de llamar agentes.
- Claves de enum exactas. Búsqueda textual: singular/plural y con/sin acento. IDs de JavaScript iguales a los IDs HTML.
- Secretos fuera del código, de logs, de README y del contexto del modelo. `.env.example` solo con placeholders. No sobrescribir `.env` ni servirlo por HTTP.
- Desarrollo en `MODO=test` con stubs. Un smoke real solo cuando la estructura pase. Los evals no llaman al proveedor por defecto. Ante `429`, abortar y reportar; no rotar claves para eludir cuota. No cambiar de modelo ya validado sin beneficio demostrado. Una suscripción de chat no es crédito de API.
- Subprocess de servidor: no `stdout=PIPE` ni `stderr=PIPE` para logs continuos; archivo de log abierto mientras viva el hijo y cerrado en `finally`. Logs en Windows: `encoding="utf-8", errors="ignore"`. No Flask+async ni `WindowsSelectorEventLoopPolicy` ni `asyncio.run()` dentro de rutas async como workaround. Scripts Windows en ASCII.
- Commits concretos: `feat: extract citizen report fields`, `feat: add deterministic water priority scoring`, `feat: add coordinator approval flow`, `test: add water allocation eval cases`, `docs: document sources and AI log`.
- Prohibido el trailer `Co-authored-by: Cursor` (y cualquier `Co-authored-by` de agente o herramienta). El mensaje lleva solo el texto del equipo. Si el entorno lo inserta solo, quítalo antes de confirmar.

## Criterios para dar por terminado

1. Tres agentes conectados de punta a punta.
2. La tool de planificación ejecuta un algoritmo determinístico real.
3. Deduplicación, prioridad y restricciones comprobadas con código.
4. Se puede revisar, editar, rechazar y aprobar; sin aprobación no hay acción final.
5. El plan aprobado deja persistencia y traza auditables.
6. Sintético y oficial están etiquetados.
7. Al menos 15 evals ejecutados, con métrica y resultados reales.
8. Entrada inválida o maliciosa, duplicados, ubicación desconocida, capacidad insuficiente y error de herramienta tienen comportamiento definido.
9. Fixtures presentes, no vacíos, con IDs esperados, leídos desde la ruta correcta.
10. API, cliente y UI funcionan sin IDs discordantes.
11. Sin secretos en git, README, logs ni `.env.example`.
12. README, diagrama, metodología y bitácora describen lo implementado, sin afirmaciones inventadas.
13. Tag `final-24h` solo al congelar el commit válido en el deadline.

Reporte de cierre: archivos principales, flujo real, tools que actúan, modelo y motivo, comando de instalación/ejecución, evals y resultados, SHA, limitaciones, estado y siguiente acción.

## Brechas abiertas (análisis 2026-10-16, `VERIFICADO`)

La dirección del plan cubre los 7 requisitos obligatorios y la regla de oro. Cerrar durante la implementación:

1. La comunicación al residente es outbox simulada. Decirlo en demo y pitch. Nunca fingir envíos reales.
2. Un sector con cero reportes sigue invisible salvo que el catálogo cargue población y vulnerabilidad. Documentar el límite en el README.
3. Fijar la métrica de evals al empezar: exactitud de extracción por campo, orden de prioridad contra ground truth, porcentaje de demanda cubierta. Robustez pesa 15 %.
4. Convertir el orden de integración en hitos por hora. `final-24h` es un deadline duro.

## ShadowSync

Canal en vivo del equipo en `https://sync.belta.dev`. No sustituye git. El servidor MCP se llama `shadowsync` y ya está en `.cursor/mcp.json`. El token compartido vive en `.env` (`SHADOWSYNC_TOKEN`); el autor de cada máquina, en `SHADOWSYNC_AUTHOR` (`franz`, `joaquin` o `edward`). No copies el token a este archivo, al README ni a los commits.

Uso obligatorio en cada sesión que lea o cambie código:

1. `fetch_team_context` antes de editar contratos o un archivo que otro pueda estar tocando.
2. `set_file_lock` antes de editarlo y otra vez con `locked: false` al terminar.
3. `push_context_update` después de un cambio de contrato, módulo o decisión. `is_full_file: false` si envías un diff.
4. No publiques `.env`, `.git`, claves, `node_modules` ni `__pycache__`.

```json
{
  "mcpServers": {
    "shadowsync": {
      "url": "https://sync.belta.dev/mcp/sse",
      "headers": {
        "Authorization": "Bearer <SHADOWSYNC_TOKEN>"
      }
    }
  }
}
```

## Cómo alimentar este contexto

Al cerrar cada hito, actualiza la sección **Estado** de este archivo y confírmala en git (`git add AGENTS.md`, commit, push) para que llegue a las otras máquinas. Registra solo decisiones y cambios relevantes: qué cambió, SHA, comandos y pruebas, resultado `VERIFICADO` / `NO VERIFICADO` / `BLOQUEADO`, limitaciones y siguiente paso. Nunca secretos ni volcados de historial. No intentes versionar `01_CONTEXTO_MAESTRO.md`, `02_EQUIPO_Y_METODOLOGIA.md` ni `03_PROMPT_MAESTRO_OPENCODE.md`: git los ignora a propósito. Si además tienes copia local de `01`, mantenla alineada por el canal del equipo.

## Estado

- 2026-10-16: contexto del repo consolidado en `AGENTS.md`. Análisis de alineación con el reto: `VERIFICADO` (ver brechas arriba). Implementación del MVP: `NO VERIFICADO`. Siguiente paso: inspeccionar el starter, acordar contratos y fijar la métrica de evals antes de separar el trabajo.
- 2026-10-16: ShadowSync (`sync.belta.dev`) es el canal de contexto en vivo. Uso obligatorio documentado en `AGENTS.md` y `.cursor/rules/shadowsync.mdc`. Token solo en `.env` local. Servicio en `k3s-cp-de-01`: `VERIFICADO` (`GET /health` 200). El MVP del reto sigue `NO VERIFICADO`.
- 2026-10-16: Ingesta de Joaquin publicada en origin (`77eaf35`). Catalogo de 11 sectores, guardrails, agente en `MODO=test`, deduplicacion y 18 evals. El vinculo Hospital Nicolas Solano -> `CHORRERA_BARRIO_COLON` es `ASSUMPTION`. El agente no aprueba planes.
- 2026-10-16: Geolocalizador deterministico conectado al deduplicador. Anclas de demostracion en `data/fixtures/places_panama_oeste.json`, todas `ASSUMPTION`, no son un levantamiento ni la capa del IDAAN. Dos lugares del mismo sector se separan si estan a mas de 800 m; Loma Cova se une con Burunga porque estan cerca. Una mencion solo del sector no absorbe un lugar concreto y queda para revision. `python -m unittest discover -s tests -v`: 78 OK, `VERIFICADO`. Priorizacion, planificador y supervision humana: `NO VERIFICADO`.
- 2026-10-16: Comunicador en `src/communication/outbox.py`. Solo encola avisos en SQLite (`SIMULATED_OUTBOX`, estado `QUEUED`) si `HumanDecision.action` es `APPROVE` y el `plan_id` coincide. Rechazo, correccion o id distinto no escriben avisos. El texto libre del plan y del comentario no entra al mensaje. No llama a WhatsApp ni Telegram.
- 2026-10-16: Pull de Franz hasta `7d28c62`. El panel ya llama a `ingest_report` y `deduplicate_reports`, asi que la ingesta, el geolocalizador y la deduplicacion por lugar quedan en el flujo. La bandeja del panel usa `notices_for_panel`: un aviso `SIMULATED` por sector asignado y otro por sector sin cisterna, con el texto del comunicador. Dos cisternas al mismo sector ya no chocan en el comunicador directo. `python -m unittest discover -s tests -v`: 129 OK. `python -m evals.eval_supervision`: case_accuracy=1.0 y dispatches_without_approve=0, `VERIFICADO`. `python -m evals.eval_ingestion`: las cinco metricas en 1.0, `VERIFICADO`. El motor del panel sigue en `demo_engine` STUB-v0 hasta sustituirlo por `priority-v1`.
- 2026-10-16: Panel de supervision humana de Franz en local, sin push a origin. `src/coordinator/`: estados BORRADOR/PENDIENTE/APROBADO/RECHAZADO/ERROR_PARCIAL, costura `PlanEngine` con `demo_engine` (`formula_version=STUB-v0`, etiqueta SYNTHETIC_DEMO), store SQLite (outbox solo tras APPROVE, canal SIMULATED), servicio de un plan por instancia, API stdlib en 127.0.0.1:8000 y `web/panel.html`. Comandos: `TEMP=/tmp .venv/bin/python -m unittest discover -s tests` → 117 OK, `VERIFICADO`; `MODO=test .venv/bin/python -m evals.eval_supervision` → case_accuracy=1.0 y dispatches_without_approve=0, `VERIFICADO`. SHA de ese hito: a4b6de0eb5e7b5ba0bdeb280b5297589b740fe8c. Limitaciones: la outbox no envia WhatsApp; el score y la ruta son stub hasta sustituir `demo_engine` (Joaquín tiene prioridad/agente de priorizacion en local, no cableados aqui); un sector sin reportes sigue invisible. Evaluacion como agente, solver real y tag `final-24h`: `NO VERIFICADO`. Arranque del panel: `.venv/bin/python -m src.coordinator.app`.
