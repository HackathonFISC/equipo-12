# Flujo en el teléfono y aprobación

Recorrido de los dos reportes que ya se enviaron y de la aprobación que los cerró. El panel estaba en `http://127.0.0.1:8000`. La sesión se vació antes, así que el plan solo contiene estos dos reportes.

El cuadro de texto es lo que se envía. El asistente de la pantalla solo sugiere. El servidor vuelve a leer el texto y fija horas, personas y sector.

## 1. Ciudadano de Burunga

1. Abre `http://127.0.0.1:8000/ciudadano` en el teléfono.
2. Deja seleccionado **Reportar incidencia**. El título es **Portal del ciudadano**.
3. En el paso **1 ¿Qué pasó?** escribe:

   > En Burunga llevamos 48 horas sin agua, somos 60 familias con ninos y adultos mayores sin suministro.

4. El asistente rápido muestra **36 h**, **60 personas** y el lugar **Burunga**. 48 horas cae en el tramo visual de 36. El 60 es el conteo de familias, no el de personas.
5. Toca **Siguiente: dónde**.
6. En **2 ¿Dónde?** elige el distrito **Arraijan** y el sector **Burunga**. No usa el GPS.
7. Toca **Siguiente: cuánto**.
8. En **3 ¿Cuánto y quiénes?** deja sin marcar los botones de 6, 18, 36 y 72 horas. El texto ya trae las 48 horas. Marca **Adultos mayores** y **Niñez**.
9. Toca **Siguiente: confirmar**.
10. En **4 Confirmar** lee que tres agentes analizan el reporte, que el puntaje es `priority-v1` y que más quejas no suben la prioridad.
11. Toca **Enviar reporte**. El botón pasa a **Enviando…**.
12. Aparece **Reporte recibido.** y la ventana **Resultado del análisis**, código `svc-1`.

    | Agente | Resultado |
    |---|---|
    | Ingesta | Burunga, 48 h, 240 afectados, `ADULTOS_MAYORES`, `INFANTES` |
    | Evaluación | `cluster:ARRAIJAN_BURUNGA:BURUNGA_CENTRO`, prioridad **31.57/100** |
    | Planificación | ver panel de coordinación |

13. La nota dice que 240 personas salen de 4 por familia y que las coordenadas son un ancla de demostración.
14. Cierra la ventana. En **Consultar mi reporte** el código es `svc-1`. No hay botón de aprobar.

El borrador queda `stub-plan-ddbc9be98f07`, estado **Borrador**. `cisterna-3` llevaría 3600 L a Burunga. El aviso está en vista previa, canal `SIMULATED`, y no se envió.

## 2. Ciudadano de Vista Alegre

1. Otra persona abre el mismo portal, `http://127.0.0.1:8000/ciudadano`.
2. En **1 ¿Qué pasó?** escribe:

   > Sin agua por el chino de Vista Alegre desde hace 48 horas, 60 familias y una escuela afectadas.

3. El asistente muestra **36 h**, **60 personas** y **Chino de Vista Alegre**.
4. Toca **Siguiente: dónde**.
5. En **2 ¿Dónde?** elige **Arraijan** y **Vista Alegre**. No usa el GPS.
6. Toca **Siguiente: cuánto**.
7. En **3 ¿Cuánto y quiénes?** no marca horas. No hay casilla de escuela: eso queda en el texto.
8. Toca **Siguiente: confirmar** y luego **Enviar reporte**.
9. Aparece **Reporte recibido.** La ventana, código `svc-2`, muestra:

    | Agente | Resultado |
    |---|---|
    | Ingesta | Vista Alegre, 48 h, 240 afectados, `ESCUELA` |
    | Evaluación | `cluster:ARRAIJAN_VISTA_ALEGRE:VISTA_ALEGRE_CHINO`, prioridad **23.57/100** |
    | Planificación | ver panel de coordinación |

10. Cierra la ventana. En **Consultar mi reporte** el código es `svc-2`. Tampoco puede aprobar.

El plan anterior se reemplaza por `stub-plan-8be1ae6665ec`. Sigue en **Borrador**. La misma `cisterna-3` haría dos paradas:

| Orden | Sector | Horas | Personas | Puntaje | Litros |
|---:|---|---:|---:|---:|---:|
| 1 | Burunga | 48 | 240 | 31.57 | 3600 |
| 2 | Vista Alegre | 48 | 240 | 23.57 | 3600 |

Nadie queda sin cisterna. Los dos avisos siguen en vista previa.

## 3. Coordinación y aprobación

1. Abre `http://127.0.0.1:8000/admin`.
2. Entra a **Centro de coordinación**.
3. Lee el cartel: los datos son `SYNTHETIC_DEMO` o `ASSUMPTION`, `priority-v1` no es política del IDAAN y ningún agente aprueba el plan.
4. En **Plan de distribución** la insignia dice **Borrador**. El recorrido marca Borrador.
5. Ve 7200 litros, 1 cisterna y 2 paradas. La ruta es Burunga y luego Vista Alegre.
6. Lee que la propuesta no encola avisos `SIMULATED` hasta la revisión humana.
7. Escribe `coordinador` en **Coordinador**.
8. Escribe en **Comentario**: `apruebo el borrador del solver`.
9. Toca **Enviar a revisión**. La insignia pasa a **Pendiente**. Se habilitan **Aprobar plan**, **Rechazar** y **Corregir plan**.
10. Toca **Aprobar plan**.
11. El cuadro dice: «Encola avisos SIMULATED. No envía WhatsApp a residentes.»
12. Toca **Confirmar**.
13. El aviso dice que el plan quedó aprobado, con auditoría `aud-04eb42aa0e3b`, y que los avisos `SIMULATED` se encolaron.
14. La insignia queda en **Aprobado**. `execution.saved` es verdadero.
15. Hay dos avisos en cola, uno por Burunga y otro por Vista Alegre, canal `SIMULATED`. No salió WhatsApp.

En el teléfono, **Consultar mi reporte** con `svc-1` o `svc-2` ya muestra el plan aprobado. El residente no recibe un mensaje de WhatsApp.
