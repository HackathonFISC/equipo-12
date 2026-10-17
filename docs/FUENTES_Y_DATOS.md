# Fuentes y datos — AguaJusta Oeste

Este documento registra fixtures, procedencia y límites de uso según los requisitos del hackathon. Ningún dato aquí implica integración operativa verificada con el IDAAN.

## Taxonomía de procedencia (`ProvenanceTag`)

| Etiqueta | Significado |
|----------|-------------|
| `OFFICIAL_SOURCE` | Dato obtenido de una fuente institucional documentada (URL, fecha de acceso, campos usados). |
| `SYNTHETIC_DEMO` | Fixture o reporte fabricado para demostración y evals; no representa un incidente real identificable. |
| `ASSUMPTION` | Parámetro de prototipo, ancla geográfica aproximada o peso de política **no** atribuible al IDAAN. |

Los contratos en `src/contracts.py` exigen etiquetar procedencia donde aplica.

## Fixtures en `data/fixtures/`

| Archivo | Contenido | Procedencia |
|---------|-----------|-------------|
| `sectors_panama_oeste.json` | **11 sectores** de Arraiján y La Chorrera: IDs canónicos, alias textuales, coordenadas aproximadas de referencia para mapa y solver. | `SYNTHETIC_DEMO` (catálogo) + `ASSUMPTION` (coordenadas de referencia) |
| `places_panama_oeste.json` | **15 lugares ancla** para geolocalización y deduplicación: Chino de Vista Alegre, Xtra de Vista Alegre, Loma Cova, Burunga, Hospital Nicolás Solano, Parque Feuillet, El Coco, Puerto Caimito, Guadalupe, etc. | `ASSUMPTION` (no es levantamiento de campo ni capa SIG del IDAAN) |
| `sample_citizen_reports.json` | **7 reportes ciudadanos** base para precarga y evals (`SYN-001` …). El centro de coordinación puede añadir **8 reportes operativos** adicionales en precarga para alimentar OR-Tools con escenario denso. | `SYNTHETIC_DEMO` |

### Notas sobre anclas (`places_panama_oeste.json`)

- Vínculo Hospital Nicolás Solano → sector `CHORRERA_BARRIO_COLON`: **`ASSUMPTION`** para demo.
- Umbral Haversine **800 m**: dos puntos en el mismo sector por encima de ese umbral generan **clusters distintos** (caso Vista Alegre).
- Loma Cova y Burunga pueden unirse al estar por debajo del umbral.

## Referencia analizada — SIG IDAAN (no usada como mapa de cortes)

| Campo | Valor |
|-------|--------|
| **Título / servicio** | Acueducto SDE — capa de infraestructura |
| **Entidad** | IDAAN (Instituto de Acueductos y Alcantarillados Nacionales) |
| **URL** | https://sig.idaan.gob.pa/server/rest/services/Servicios_vista/AcueductoSDE/MapServer/5 |
| **Fecha de acceso** | 2026-10-16 |
| **Qué representa** | Infraestructura **estática** de tuberías de acueducto (geometría/atributos de red). |
| **Qué no representa** | Averías en tiempo real, población afectada, flota de cisternas, tiempos de llegada ni prioridad operativa. |

**Decisión del equipo:** no presentar esta capa como mapa de **cortes actuales**. La UI usa fixtures y anclas etiquetadas; el heatmap refleja reportes consolidados del prototipo, no el SIG en producción.

## Parámetros operativos (`ASSUMPTION`)

Estos valores alimentan `priority-v1`, el solver y la UI. **No son política oficial del IDAAN.**

| Parámetro | Valor |
|-----------|--------|
| Fórmula `priority-v1` | Horas 0–40 pts + afectados 0–30 pts + vulnerabilidad 0–30 pts |
| Dotación | **15 L/persona** |
| Velocidad media | **30 km/h** |
| Tiempo de descarga por parada | **20 min** |
| Depósito / depot | `(8.881, -79.782)` cerca de La Chorrera |
| Flota | 3 cisternas: **10 000 L**, **10 000 L**, **8 000 L** |
| Turno / ventana | **480 min** |
| Invariante de volumen | `report_count` **no** altera el score |

## Comunicación con residentes

| Canal | Estado en el prototipo |
|-------|-------------------------|
| Bandeja SQLite `SIMULATED` | Encolada solo tras `HumanDecision.action == APPROVE` |
| WhatsApp a ciudadanos | **No implementado** |
| WhatsApp opcional al equipo | `src/communication/whatsapp.py` — un mensaje de prueba si hay credenciales; no sustituye la outbox simulada |

## Sectores sin reportes

Sectores con **cero reportes** no entran al plan automático. El panel puede listarlos como *Sectores silenciosos* para transparencia; el coordinador debe ingresar un reporte si desea incluirlos.
