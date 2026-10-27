# Prompt para OpenCode: extraer la fuente del informe (`docs/informe/FUENTE_INFORME.md`)

> Rama: `docs/informe-fuente`, desde `main` (v1.1.0-entrega). **Solo lectura del proyecto; solo se crean archivos en `docs/informe/`.** Duración orientativa: 1 h. El resultado se entrega a otra persona (redactora) que **no tiene acceso al repositorio**: el archivo debe ser **autosuficiente**.

---

## ROL
Analista técnico y archivista de evidencia. Tu único trabajo es **extraer, consolidar y citar** lo que existe. **No redactes el informe ni inventes nada.**

## REGLAS (innegociables)
1. **Cada dato lleva su procedencia** al final entre corchetes: `[fuente: docs/resultados/perf_P1_analisis.md]` (o comando ejecutado, commit o tag).
2. **Verifica cada cifra contra el archivo de resultados vigente**, no contra resúmenes previos. Usa el **valor reconciliado final**. Si una cifra cambió, lista el valor anterior y el motivo en la tabla de **Correcciones** (§9).
3. Lo que no exista o no se haya ejecutado: escribe **`PENDIENTE: <qué falta y dónde obtenerlo>`**. Nunca rellenes.
4. Prefiere **tablas** a prosa; sin duplicados; sin párrafos de relleno. Cifras **textuales** (con unidades y número de repeticiones).
5. **No copies texto largo de terceros**; resume con tus palabras. No incluyas contraseñas, tokens, cédulas ni datos personales.
6. Tamaño objetivo: **≤ 15.000 palabras** en un solo archivo `docs/informe/FUENTE_INFORME.md`. Si no cabe, divide en `FUENTE_INFORME_01.md`, `_02.md`… y un índice. Los diagramas van como **texto** (mermaid o ASCII).

## LEE
`docs/01-enunciado.md`, `docs/02-plan.md`, `docs/03-estado-del-proyecto.md`, `docs/04-arquitectura.md`, `docs/05-contratos-api.md`, `docs/adr/*`, `docs/fases/*`, `docs/resultados/*` (**todos**, incluidos `REPORTE.md`, `perf_*`, `chaos_*`, `F4a-cierre.md`, `F4b-resiliencia.md`, `entorno.md`, `ensayo-desde-cero.md`, `docker-imagenes-diagnostico.md`), `tests/perf/hypotheses.md`, `tests/perf/thresholds.json`, `docs/imagenes.md`, `docs/variables.md`, `docs/seguridad.md`, `docs/produccion.md`, `docs/swarm.md`, `docs/manual.md`, `docs/RELEASE.md`, `docs/costos/registro.md`, `docs/informe/*`, `docs/prompts/*`, `compose.yaml`, `compose.dev.yaml`, `gateway/conf.d/default.conf`, `Makefile`, `git log` y tags.

## ESTRUCTURA OBLIGATORIA DEL ARCHIVO (respeta los números)
**§0 Metadatos y alcance verificable.** Autor y caso; versiones (tags `v1.0-entrega`, `v1.0.1-entrega`, `v1.1.0-entrega` con commit y fecha); URL del repositorio si existe; **métricas del repositorio** calculadas con un script de biblioteca estándar y mostrando el comando: nº de archivos y líneas por servicio (`app/` vs `tests/`), nº de ADR, nº de documentos, nº de commits, nº de contenedores y de imágenes; **entorno** de pruebas (CPU, núcleos, RAM total y asignada a Docker, versiones de Docker/Compose/PostgreSQL/nginx/Python/k6).

**§1 Problema y objetivos.** Caso 2 (objetivo, contexto del monolito, síntomas) en tus palabras; **los 14 puntos del enunciado** como objetivos específicos; criterios de éxito.

**§2 Proceso de desarrollo.** Metodología (especificación primero, pruebas primero, compuertas G0/G1, fases F0–F6, regla de recorte); **lista de prompts versionados** (`docs/prompts/`) con su propósito; uso de agente de código y de **qué verificó el humano** según los documentos (revisiones, correcciones de cifras, rechazos de entregas); horas por fase y herramientas desde `docs/costos/registro.md` (o `PENDIENTE`). **No atribuyas autoría**: describe hechos documentados.

**§3 Arquitectura y decisiones.** Topología (servicios, workers, redes, puertos, volúmenes, endurecimiento); estilo hexagonal ligera y capas con la regla de dependencias y su verificación (`import-linter`); **un resumen de cada ADR** (contexto, decisión, alternativas, consecuencias, estado); contratos clave (tabla de endpoints públicos/internos); autenticación (ADR-0012); patrones por componente y dónde viven en el código (archivo y función).

**§4 Dominio y consistencia.** Invariantes I1–I7 (definición exacta y cómo se comprueba); **máquina de estados de la reserva** (estados, transiciones, plazos) y del pago; saga con `advance`; idempotencia (claves, hash); outbox/relay/inbox; fail-closed vs fail-open; modelo de datos de cada BD (tablas y restricciones relevantes).

**§5 Metodología experimental.** Arnés de caos (componentes, modos de caída A y B, canario, ventanas de indisponibilidad, finalizer, reglas de plausibilidad); tabla de **escenarios** (acción, aserciones duras, métricas); pruebas de carga (P1–P5, P3b), **hipótesis registradas antes de medir con el commit que lo prueba**, umbrales, protocolo (calentamiento, repeticiones, CV), muestreadores; pruebas automáticas (unit, integración, contrato, e2e, humo, invariantes), con **conteos reales** por suite.

**§6 Resultados.** Tablas completas con **cada repetición**: pruebas (totales y por tipo); caos A, B, C, D, E1, E2, E3, E4, S, S2 (integridad, RTO/TTD por repetición, objetivo, ¿cumplido?); E1 (reconocidas, durables); E3 (RPO, RTO); P1, P3, P3b, P4 (todas las cifras, CPU/conexiones/bloqueos); imágenes Docker (tamaños, antes/después, monoetapa vs multistage, contexto); seguridad (conteos de trivy y gitleaks, rutas públicas/protegidas, límites y 429 de P4); **ensayo desde cero** (duración por paso). Para P1, P3b y los RTO incluye una tabla numérica limpia (CSV en bloque de código) lista para graficar.

**§7 Discusión.** Para cada hipótesis: esperado / observado / ¿se cumplió?; explicación según los documentos; **amenazas a la validez** (un solo host, k6 y servicios comparten CPU, ruido con CV, muestreo de bloqueos a 1 s/100 ms, `docker kill` vs corte real); hallazgos (lista numerada con clasificación P0/P1/P2 donde exista y estado: abierto/cerrado).

**§8 Trazabilidad de objetivos.** Tabla de los **14 puntos del enunciado → evidencia (archivo/comando) → estado** (✔ solo si se ejecutó). Añade las funciones extra (autenticación, UI).

**§9 Correcciones de medición.** Tabla `cifra anterior → cifra final → motivo → archivo` (p. ej. D, S/TTD, E2, B, 429, fechas, E1 de 10 a 200 reconocidas).

**§10 Costos.** Lo existente en `docs/informe/costos.md` y `docs/costos/registro.md`, con sus fuentes y los `PENDIENTE`.

**§11 Seguridad.** Amenazas, controles, evidencia y **limitaciones** (sin TLS, sin verificación de email, lectura de reservas abierta, etc.), tal como están documentadas.

**§12 Evolución y limitaciones.** Contenido de `produccion.md`, `swarm.md` y `RELEASE.md` (limitaciones y hallazgos abiertos), sin añadir juicios nuevos.

**§13 Alternativas.** La matriz de `docs/informe/seccion3-alternativas.md` (criterios, pesos, puntuaciones y totales) tal cual.

**§14 Catálogo de evidencias para anexos.** Tabla `id | descripción | ruta | tipo (texto/tabla/diagrama/captura) | útil para (sección)`; incluye **capturas de interfaz** (nombres de archivo en `docs/resultados/ui/`) y los extractos de código **cortos** sugeridos (máquina de estados, UPDATE atómico de inventario, `advance`, `compose.yaml` de un servicio, `default.conf` del gateway, Dockerfile representativo) con ruta y rango de líneas.

**§15 Pendientes y dudas.** Lista de todos los `PENDIENTE` y cualquier inconsistencia detectada entre documentos (señala archivo y línea).

## COMPROBACIONES ANTES DE ENTREGAR
- [ ] Cada tabla de §6 coincide con su archivo `docs/resultados/*.md` (comparación explícita).
- [ ] Ninguna cifra sin `[fuente: ...]`; ningún dato personal ni secreto.
- [ ] Todos los números de §6 se pueden reproducir con el comando o informe citado.
- [ ] `PENDIENTE` y dudas listados en §15.
- [ ] Palabras totales y por sección indicadas al final.

## ENTREGA
Commit `docs(informe): fuente consolidada` en la rama indicada; **no fusiones a `main`**. En tu respuesta final: lista de archivos creados, palabras por sección, `PENDIENTE` y las inconsistencias halladas. La persona subirá `FUENTE_INFORME.md` (y las capturas de `docs/resultados/ui/`) para redactar el informe.

## REGLAS
No inventar · citar la fuente de cada dato · usar el valor reconciliado final · declarar lo no hecho · solo escribir en `docs/informe/` · sin datos personales ni secretos.
