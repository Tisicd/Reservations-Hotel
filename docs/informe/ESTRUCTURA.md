# Informe escrito (entrega 25 oct): estructura

**Tesis:** esta solución es la más adecuada **para este caso y estas restricciones**, no una arquitectura universalmente superior. El informe lo demuestra con criterios, alternativas y mediciones, y reconoce sus límites.

| # | Sección | Contenido | Fuente en el repo |
|---|---|---|---|
| 1 | Resumen ejecutivo | Problema, solución, resultados clave (1 página) | — |
| 2 | Análisis del negocio | Procesos, criticidad, **invariantes**, qué no puede perderse | `fases/F0` |
| 3 | Alternativas y por qué esta solución | Matriz ponderada: monolito modular · microservicios en Compose (elegida) · serverless · Kubernetes · BD gestionada. Criterios: integridad, aislamiento de fallos, complejidad, costo, plazo, demostrabilidad | ADR-0001/0002 |
| 4 | Arquitectura | Topología, hexagonal ligera, patrones por componente, capas verificadas por herramienta | `04-arquitectura` |
| 5 | Decisiones tecnológicas | Una por stack/dependencia, con alternativa descartada y consecuencia | `adr/`, ADR-0009 |
| 6 | Contratos y flujo de reserva | Estados, saga, idempotencia | `05-contratos-api`, ADR-0003 |
| 7 | Resiliencia y fallos | Matriz de fallos; escenarios A–D, E1–E4; RTO/RPO objetivo vs. medido | `resultados/` |
| 8 | Rendimiento | k6: lectura 1 vs 3 réplicas; escritura bajo contención; cuellos de botella | `resultados/` |
| 9 | Seguridad | Exposición, secretos, amenazas y lo que Compose **no** resuelve | `seguridad.md` |
| 10 | **Costos** | Ver abajo | `costos/` |
| 11 | **Manual** | Requisitos, instalación, `make up/test/chaos/perf/report`, uso del frontend, solución de problemas, reinicio desde cero | `README` + `manual.md` |
| 12 | Evolución a producción | Réplicas de BD, multinodo/Swarm/K8s, colas durables, observabilidad, WAF/CDN, PITR | `produccion.md`, `swarm.md` |
| 13 | Limitaciones y trabajo futuro | Host único, BD compartida, simulaciones, `docker kill` ≠ corte eléctrico | todo lo anterior |
| 14 | Conclusión | Por qué es la mejor opción **para este caso** (criterios + evidencia) | — |
| A | Anexo: trazabilidad | Tabla requisito del enunciado (1–14) → evidencia | `01-enunciado` |

## Costos (sección 10): qué incluir
| Tipo | Contenido | Cómo se obtiene |
|---|---|---|
| Desarrollo | Horas por fase × tarifa de referencia junior (supuesto explícito) | `costos/registro.md` (se llena a diario) |
| Herramientas de IA | Suscripciones/tokens usados en el proyecto | `costos/registro.md` |
| Infraestructura del proyecto | Local (Docker): $0 incremental; demo online opcional: costo mensual del VPS | **Precios vigentes verificados al redactar** (no se estiman de memoria) |
| Infraestructura de producción (estimado) | 3 escenarios: demo · producción pequeña (1 host + backups) · producción HA (multinodo + BD gestionada con réplica) | Cotización con precios publicados a la fecha, con fuentes citadas |
| Costo de **no** hacerlo | Impacto de sobreventa/cobro doble/caída total (cualitativo y con supuestos explícitos) | Del análisis de F0 |
