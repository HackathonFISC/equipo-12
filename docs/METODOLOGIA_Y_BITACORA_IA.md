# Metodología de ingeniería agéntica y bitácora de IA

Equipo 12 — AguaJusta Oeste — Reto 1 (Agua). Documento requerido por la competencia FISC AI Agents 2026.

---

## Parte 1 — Metodología de ingeniería agéntica

### Principio rector

Separación estricta entre:

1. **Percepción y razonamiento cualitativo** — LLM vía `pydantic-ai` (extracción de campos, factores, restricciones narradas).
2. **Decisión numérica y operativa** — Python determinístico, fórmula `priority-v1`, **OR-Tools**, SQLite transaccional.

El LLM no fija puntajes finales, capacidades de cisternas ni validez de rutas.

### Contratos y límites

- **`src/contracts.py`:** modelos Pydantic v2 con `extra="forbid"`, enums cerrados (`SectorId`, estados de plan, acciones humanas).
- **`UsageLimits(request_limit=4, tool_calls_limit=5, total_tokens_limit=4000)`** en agentes para evitar bucles costosos.
- **`MODO=test`:** agentes alimentados con **`FunctionModel`** y respuestas fijas; evals y CI no consumen cuota de API por defecto.
- **`MODO=live`:** solo para smoke controlado; ante `429` se aborta sin rotar claves.

### Defensa en profundidad

| Capa | Implementación |
|------|----------------|
| Guardrails de ingesta | `src/ingestion/guardrails.py` — vacío, malicioso, absurdo, fuera de área |
| Geolocalización | Catálogo + Haversine 800 m — no inventar coordenadas |
| Prioridad | `score_cluster` en código — invariante `report_count` |
| Planificación | `solve_assignment` — OR-Tools con capacidad y ventana temporal |
| Secretos | `redact_secrets` en logs y auditoría |
| Validación de esquema | Pydantic en cada handoff entre agentes |

### Compuerta de supervisión humana

Flujo en `src/coordinator/service.py` y `src/coordinator/store.py`:

```
BORRADOR → PENDIENTE → APROBADO | RECHAZADO | ERROR_PARCIAL
                ↑________ CORRECT (vuelve a BORRADOR)
```

- Persistencia con **`BEGIN IMMEDIATE`** en SQLite.
- Outbox **`SIMULATED`** solo si `action == APPROVE` y `plan_id` coincide (`src/communication/outbox.py`).
- Ningún agente del pipeline puede emitir `APPROVE`.

### Coordinación del equipo

- **Git** como fuente de verdad versionada.
- **ShadowSync** (`https://sync.belta.dev`) para contexto en vivo, locks de archivo y diffs entre Joaquín, Edward y Franz.
- División por área: orquestación/contratos/ingesta (Joaquín), motor determinístico/solver/evals (Edward), panel/persistencia/trazas (Franz).

### Verificación

- **177** pruebas unitarias (`tests/`).
- **44** casos de eval en tres módulos (`evals/`).
- Métricas registradas en JSON versionado bajo `evals/results_*.json`.

---

## Parte 2 — Bitácora de uso de IA

Herramientas: Cursor Agent, Claude, asistentes en IDE, generación asistida de tests y documentación. Todo cambio crítico fue revisado por humanos y cubierto por pruebas determinísticas.

### Contratos y configuración (`src/contracts.py`, `src/config.py`)

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Borrador inicial de modelos Pydantic | Sí | Ajuste de enums, nombres alineados al starter, tests en `tests/test_contracts.py` |
| `redact_secrets` | Asistido | Casos con tokens ficticios en `tests/test_config.py` |

**Limitación detectada:** propuestas iniciales mezclaban campos opcionales con valores por defecto que ocultaban incertidumbre. **Corrección:** campos explícitos `null` + `requiere_revision` en ingesta.

### Agente 1 — Ingesta

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Estructura del agente y prompts | Sí | 18 evals de ingesta en 1.0; guardrails ejecutados antes del LLM |
| Guardrails adversariales | Asistido | Casos EVAL-14…18 (malicioso, vacío, absurdo, fuera de área) |

**Error inicial:** el modelo tendía a inferir afectados cuando el texto no los mencionaba. **Corrección:** reglas en guardrails + eval `no_hallucination_rate`.

### Deduplicador y geolocalizador

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Esqueleto Haversine y catálogo | Asistido | Pruebas con Chino/Xtra separados; Loma Cova + Burunga unidos |
| Retención sector vs punto | Diseño manual | ALLOC-12 y EVAL de deduplicación |

**Error inicial:** fusionar todo el sector Vista Alegre en un solo cluster. **Corrección:** umbral 800 m y regla de mención genérica de sector.

### Agente 2 — Priorización

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Agente + tool wrapper | Sí | `score_cluster_tool` delega a `priority.py`; ALLOC-05…08 volume invariance |
| Fórmula priority-v1 | Edward + revisión | 14 tests en `tests/test_priority.py` |

**Limitación:** el LLM a veces proponía “ajustes” narrativos al score. **Corrección:** el agente solo devuelve factores; el código calcula el número.

### Agente 3 — Planificación (OR-Tools)

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Integración RoutingModel | Asistido | ALLOC-09…16, 177 tests de regresión |
| Infactibilidad con demanda alta | Detectado en demo | **`AddDisjunction`** con penalización ponderada por prioridad |

**Error inicial:** solver fallaba o dejaba rutas inválidas cuando la demanda superaba la flota. **Corrección:** disyunciones ponderadas; demanda no cubierta explícita en `PlanDraft`.

### Orquestador (`src/orchestration/agent.py`)

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Secuencia ingest → prioritize → plan | Sí | ALLOC-16 pipeline; tests de coordinador |
| Async en hilos HTTP | Bug Python 3.14 | **`new_event_loop` / cierre explícito** en `_call_outside_run` |

**Error:** fugas de event loop al llamar agentes async desde `ThreadingHTTPServer`. **Corrección:** loop dedicado por invocación y cleanup documentado en cierre 2026-10-17.

### Coordinador, panel y API

| Aspecto | IA | Verificación humana |
|---------|-----|---------------------|
| Portal v10 `/ciudadano` y `/admin` | Asistido (Edward/Franz) | `tests/test_coordinator_app.py`; paridad IDs HTML/JS |
| Outbox antes de APPROVE | Revisión Franz | SUP-08, `dispatches_without_approve=0` |
| `GET /api/health`, `POST /api/reset` | Cierre Task 1–2 | Botón `#reset-session` en panel |

**Error inicial:** textos del panel sugerían “stub” mientras el motor ya era OR-Tools. **Corrección:** disclaimers auditables (priority-v1, OR-Tools, SIMULATED).

### Evals

| Suite | Casos | IA | Verificación |
|-------|-------|-----|--------------|
| `eval_ingestion` | 18 | Casos adversariales asistidos | Métricas 1.0 en JSON |
| `eval_allocation` | 16 | Escenarios ALLOC asistidos | Assert directo OR-Tools en ALLOC-09/16 |
| `eval_supervision` | 10 | Flujos APPROVE/REJECT | SQLite + outbox |

### Documentación

README, fuentes, diagrama y este documento: redacción asistida por IA, **revisión del equipo** contra código y resultados de evals ejecutados en `MODO=test`.

---

## Referencias cruzadas

- [`README.md`](../README.md) — instalación, evals, arquitectura resumida
- [`docs/FUENTES_Y_DATOS.md`](FUENTES_Y_DATOS.md) — procedencia y SIG IDAAN
- [`docs/diagrama_supervision.md`](diagrama_supervision.md) — flujo humano en el loop
