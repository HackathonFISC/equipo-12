# RETOS OFICIALES DE LA COMPETENCIA
Agentes de IA para resolver problemas sociales reales de Panamá

*Organiza:* Facultad de Ingeniería de Sistemas Computacionales • Universidad Tecnológica de Panamá
# 1. Información general
Construir un sistema de agentes de IA que resuelva el reto de Agua, un problema social real de Panamá.

| Aspecto | Detalle |
| --- | --- |
| Fechas | 9 y 10 de octubre de 2026, presencial, 24 horas continuas |
| Equipos | 3 integrantes |
| Reto | Agua |
| Uso de IA | Permitido y esperado. Debe documentarse en la Bitácora de IA |
| Herramientas | Libres: cualquier lenguaje, framework (LangGraph, CrewAI, AutoGen, SDKs propios), modelo o nube |
| Datos | Cada equipo investiga y consigue su propia información (sección 4) |
| Evaluación final | CONTECS 2026 |

> **REGLA DE ORO:** Si la solución se puede reemplazar con un buen prompt en ChatGPT, no califica. Buscamos sistemas de agentes que perciben, deciden y actúan, no interfaces de chat.

# 2. Requisitos mínimos
Toda solución debe cumplir estos requisitos obligatorios.
**1. Arquitectura multiagente:** al menos 3 agentes con roles distintos que se comuniquen entre sí.
**2. Herramientas que actúan:** al menos una herramienta ejecuta una acción real (escribir en base de datos, enviar un mensaje, ejecutar un solver), no solo genera texto.
**3. Componente determinístico:** cálculos, rutas, asignaciones y verificaciones se hacen con código, no con el LLM.
**4. Humano en el ciclo:** un actor humano aprueba o corrige decisiones clave, y el sistema explica por qué decidió lo que decidió.
**5. Trazabilidad:** logs o trazas (Langfuse, LangSmith o propios) que muestren qué agente tomó cada decisión.
**6. Evals propios:** un set de al menos 15 casos de prueba con su métrica y resultados.
**7. Guardrails:** manejo de entradas maliciosas, fuera de alcance o absurdas.

# 3. Reto: Agua

**Centro de coordinación agéntico para la crisis del agua en Panamá Oeste**

Construyan un sistema que convierta el caos de reportes ciudadanos en un plan de distribución de agua justo, rápido y explicable.
## 3.1 Problema
El crecimiento urbano acelerado de Panamá Oeste, sobre todo en Arraiján y La Chorrera, ha superado la capacidad de las plantas potabilizadoras y de las redes de distribución. Cuando hay mantenimientos, daños en tuberías o baja producción, comunidades enteras pasan días sin agua y dependen de carros cisterna.
Hoy los reportes llegan dispersos por WhatsApp, redes sociales y llamadas, y nadie los consolida. El mismo incidente se reporta cientos de veces, mientras que los sectores con menos presencia en redes quedan invisibles. La distribución se decide sin datos: muchas veces recibe primero quien más se queja, no quien más lo necesita, y un centro de salud o un hogar de adultos mayores puede esperar más que una barriada con más visibilidad.
Además, los residentes no saben si ni cuándo llegará el agua. Esa falta de información genera protestas, cierres de calles y desconfianza en las instituciones. El reto es pasar de una reacción caótica a una coordinación basada en datos, justa y transparente.
## 3.2 Actores en conflicto

| Actor | Qué quiere | Restricción |
| --- | --- | --- |
| Residentes | Agua pronto e información clara | Reportan con ubicaciones vagas, por voz o foto |
| Coordinación (IDAAN o municipio) | Priorizar con justicia | Pocos carros cisterna |
| Instituciones críticas | Prioridad absoluta | Hospitales, escuelas, albergues |
| Conductores | Rutas claras y factibles | Capacidad, horario y combustible limitados |

## 3.3 Entradas esperadas
Reportes en texto, notas de voz, fotos de tuberías rotas o grifos secos, ubicaciones imprecisas ("cerca del chino de Vista Alegre"), duplicados y reportes falsos o exagerados.
## 3.4 Agentes mínimos sugeridos
1. Ingesta: transcribe audio, analiza imágenes y extrae ubicación, severidad y personas afectadas.
2. Geolocalización y deduplicación: convierte descripciones en coordenadas y agrupa reportes del mismo incidente.
3. Priorización: puntaje por sector según horas sin agua, población y vulnerabilidad.
4. Planificador: solver de rutas con capacidad y ventanas de tiempo (VRP) para asignar carros cisterna.
5. Comunicación: avisa a cada barrio por WhatsApp o Telegram, en texto y audio, y responde preguntas.
6. Supervisión humana: el coordinador aprueba o modifica el plan; el sistema justifica cada decisión.

# 4. Entregables y congelamiento del código

| Entregable | Contenido | Plazo |
| --- | --- | --- |
| Repositorio | Código en GitHub, creado al inicio y registrado ante la organización, con commits durante el periodo oficial | Registro en la  |
| Tag de congelamiento
| README | Problema, arquitectura de agentes, tecnologías, fuentes de datos, instalación, ejecución y credenciales de demo (sin claves reales; usar .env.example) | |
| Diagrama de arquitectura | Agentes, herramientas, flujos y punto de intervención humana | |
| Evals | Set de al menos 15 casos de prueba, métrica y resultados | |
| Bitácora de IA | Qué partes se hicieron con IA, con qué herramienta y qué se modificó a mano | |
| Documento de metodología | Despliegue, funcionamiento y arquitectura, adicional a los formularios del día | |
| Video demo | Máximo 3 minutos, mostrando el sistema funcionando de punta a punta | |

> IMPORTANTE Cualquier commit posterior al tag de congelamiento se ignora en la evaluación.

# 5. Evaluación
Se evalúa sobre todo cómo se resolvió el problema, no la cantidad de código. Todos los equipos se califican con la misma rúbrica base y se publica un único ranking general.
## Rúbrica base

| Criterio | Qué se evalúa | Peso |
| --- | --- | --- |
| Impacto y solución del problema | Qué tan bien resuelve el problema real, para quién y con qué información verificable lo sustenta | 30 % |
| Diseño agéntico | Roles, herramientas, autonomía, componente determinístico y nivel alcanzado | 25 % |
| Funcionamiento en vivo | Demostración en vivo del sistema funcionando de punta a punta | 20 % |
| Robustez | Evals, guardrails y manejo de entradas inesperadas o maliciosas | 15 % |
| Presentación y Bitácora de IA | Claridad, transparencia en el uso de IA y documentación | 10 % |
