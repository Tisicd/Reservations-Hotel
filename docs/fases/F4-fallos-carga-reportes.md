# F4: Fallos, carga y reportes

**Objetivo:** demostrar con datos qué falla, cómo se recupera y dónde están los límites. **Es la evidencia central de la defensa.** Cada prueba termina con `make invariants` y comprobación de pérdida (`snapshot_committed` / `assert_no_loss`).

## Prerrequisitos
`k6` instalado · control de imágenes resuelto · `make backup`/`make restore` (pg_dump por BD en `backups/`, restauración con cronómetro) · alarma `OUTBOX_BACKLOG_OLD` en el chequeador.

## Arnés (`tests/chaos/harness.py`)
- **Tráfico de fondo**: reservas continuas con claves únicas a ritmo fijo + lecturas de disponibilidad.
- **Canario**: sondea el flujo completo cada 500 ms para delimitar la ventana de indisponibilidad y calcular el **RTO medido**.
- **Caídas:** modo A `docker kill` + reinicio tras *N* s (RTO con operador) y modo B `docker exec … kill -9` (RTO autónomo por política de reinicio).
- **Salida:** JSON + `docs/resultados/chaos_<id>.md` con las 5 preguntas del enunciado respondidas con cifras (afectados, siguen funcionando, información perdida, cómo se recupera, mejora posible).

## Escenarios
| ID | Acción | Resultado esperado | Métricas |
|---|---|---|---|
| **A** | Detener `notification` bajo carga | Reservas siguen `CONFIRMED`; eventos pendientes se entregan al volver | % éxito, pendientes máx., tiempo de vaciado |
| **B** | Detener 1 de 3 réplicas de `availability` | Sin errores sostenidos | errores, p95 antes/durante/después |
| **C** | Reiniciar `reservation` con reservas en curso (`slow`) | Sin duplicados ni estados huérfanos | RTO, reservas recuperadas por el worker |
| **D** | Eliminar y recrear `postgres` con el mismo volumen | Datos íntegros; servicios reconectan | filas antes/después, RTO |
| **E1** | `postgres` caído (modos A y B) en plena carga de escritura | Sin sobreventa ni cobro doble; fail-closed | invariantes, RTO, errores 503 |
| **E2** | Pago con resultado desconocido | `UNKNOWN` → reconcilia; 1 cobro | tiempo hasta estado final |
| **E3** | Borrar volumen y restaurar backup | RTO medido; RPO = antigüedad del backup | tiempo, datos perdidos |
| **E4** | Reiniciar `postgres` con servicios activos | Pools reconectan sin reiniciar | tiempo de recuperación |
| **S** | Servicio no saludable (BD inaccesible ⇒ `/ready` 503 ⇒ `unhealthy`) | Docker lo marca; se recupera solo | tiempo a `unhealthy` y a `healthy` |

## Carga (k6, `tests/perf/`)
| ID | Prueba | Pregunta |
|---|---|---|
| P1 | Lectura de disponibilidad con 1 vs 3 réplicas | ¿Escala la lectura? |
| P2 | Mezcla 90 % lectura / 10 % reservas | ¿Cómo se comporta el sistema real? |
| P3 | **Contención:** muchas reservas por el mismo cupo | ¿La escritura escala con réplicas? (hipótesis: no, se serializa en PostgreSQL) |
| P4 | Sobre el límite de `limit_req` | ¿429 sin degradar a los demás? |
| P5 | Rampa hasta saturación | ¿Dónde está el cuello (CPU, conexiones, BD)? |
Protocolo: calentamiento, **3 repeticiones**, hardware y versiones registrados, umbrales definidos **antes** (p. ej. p95 < 300 ms y errores < 1 % en carga nominal), muestreo de `docker stats` y de conexiones en PostgreSQL. Los resultados son **comparativos** (k6 y servicios comparten máquina).

## Reporte (`make report` → `docs/resultados/REPORTE.md`)
Tablas de escenarios, RTO/RPO **objetivo vs medido**, comparativa 1 vs 3 réplicas separando lectura y escritura, y sección de **hallazgos** (la redactas tú: incluye lo que no cumplió).

## Prioridad si falta tiempo
A–D → E1 → E2 → P1 → P3 → E3 → S → E4 → P2 → P5 → P4.

## Criterio de salida
- [ ] `make chaos`, `make perf`, `make report` reproducibles desde cero.
- [ ] Cada escenario con sus 5 respuestas y **0 violaciones de invariantes**.
- [ ] RTO/RPO medidos documentados, aunque no cumplan el objetivo.
- [ ] `docs/fallos.md` y `docs/seguridad.md` (punto 9 y 12 del enunciado) generados/redactados.
- [ ] Tag `f4`.
