# Fallos y modos de caída (F4a)

> Esqueleto. Cada escenario tiene su informe con las 5 preguntas del enunciado,
> RTO medido vs objetivo y aserciones de integridad en
> `docs/resultados/chaos_<ID>_<modo>_<rep>.md`.

## Escenarios ejecutados

| ID | Acción | Qué se mide | Informe |
|---|---|---|---|
| A | Detener `notification` (API) o `notification-worker` 20 s bajo carga | reservas siguen (fail-open), backlog del outbox, drenaje | `chaos_A_api_1.md`, `chaos_A_worker_1.md` |
| B | Matar 1 de 3 réplicas de `availability` (`docker kill` y `kill -9` interno) | errores crudo vs con reintento, p95, recuperación de nginx | `chaos_B_kill_1.md`, `chaos_B_kill9_1.md` |
| C | Reiniciar `reservation` con 20 reservas confirmadas | estado estable, 1 cargo por reserva, 0 holds duplicados | `chaos_C_kill9_1.md`, `chaos_C_stop_1.md` |
| D | Reiniciar `postgres` con el mismo volumen bajo carga | no pérdida, RestartCount sin cambios, 503 fail-closed | `chaos_D_stop_1.md` |
| E2 | 20 reservas con `process_then_drop_response` | UNKNOWN → reconciliación → CONFIRMED, 1 cargo | `chaos_E2_drop_1.md`, `chaos_E2_hallazgo.md` |
| E1 | PostgreSQL cae en plena carga (stop/pkill -9) | durabilidad de lo reconocido (I7), invariantes, 1 cargo | `chaos_E1_stop_*.md`, `chaos_E1_pkill9_*.md` |
| E3 | P?rdida del volumen + restaurar backup (A reposo / B caliente) | RTO de restauraci?n, RPO observado, invariantes | `chaos_E3_A_*.md`, `chaos_E3_B_*.md` |
| E4 | Reinicio ordenado de PostgreSQL con servicios activos | servicios reconectan sin reiniciarse | `chaos_E4_restart_*.md` |
| S | Congelar procesos de `postgres` (SIGSTOP) y observar salud | 503 (nunca 2xx falsos), TTD (~93 s), TTR | `chaos_S_stop_1.md` |
| S2 | Detener `postgres`; observar `/ready` y unhealthy de los 6 servicios | 503, TTD de healthchecks (60–85 s), reconexión | `chaos_S2_stop_1.md` |

## Mecanismos de recuperación observados

- `restart: unless-stopped` + healthchecks (modo B autónomo).
- Operador/arnés reinicia el contenedor (modo A).
- Workers de recuperación: `reservation-worker`, `reservation-relay`,
  `payment-worker`, `notification-worker`, `availability-worker` (expiración de holds).
- Fail-open en notificación; fail-closed en escritura de inventario.

## Limitaciones conocidas

- Un solo contenedor PostgreSQL: punto único de fallo (ver D y S).
- Sin réplica de PostgreSQL ni PITR (documentado como evolución en F0 §3.1).
- Sin dead-letter en el outbox; se mitiga con la alarma `OUTBOX_BACKLOG_OLD`.
- **RPO dependiente de backup manual**: E3 pierde las reservas creadas después
  del último `make backup` (5/5 en la prueba). Ver `proceso/backup-restore.md`.
- **Backup por BD, no consistente entre servicios**: los dumps se toman en
  momentos distintos; una restauración puede quedar desalineada entre BDs.
- **S TTD ≈ 93 s > 30 s**: `retries=12` evita falsos unhealthy pero retrasa la
  detección; ver `resultados/F4b-resiliencia.md`.

<!-- report:findings -->
## Hallazgos F4b Parte 2

- B/kill: objetivo no cumplido en 1/5 reps (máx 2.41 s vs 2 s; mediana 0.33 s)
- S/stop: objetivo no cumplido en 1/1 reps (máx 93.21 s vs 30 s; mediana 93.21 s)
- B/kill: 1/5 reps > 2 s (máx 2.41 s); intermitente, no se ajusta el objetivo
- P3 V2/N=3: rps ruidoso (CV 31 %)
- S: `retries=12` da TTD ≈ 93 s (> 30 s); se mantiene por falsos positivos.
- `limit_conn`/`limit_req` son por IP: el listener admin sin límites se usa para medir capacidad; P4 mide el público y observa 429 sin degradar el canario admin.
- RPO depende de la frecuencia de `make backup` (manual).
- Backup por BD, no consistente entre servicios (ventana entre dumps).
- P1: 2,09× explicado por CPU de availability (2,45×) y PostgreSQL (~2,3×); gateway y k6 no son cuello (ver `perf_P1_analisis.md`).
- P3: la latencia de 5–6,5 s es la saga síncrona (`SAGA_SYNC_WAIT_SECONDS=5`), no contención; recomendación: responder 202 inmediato, reducir la espera o más procesos/réplicas de `reservation`.
- P3b: V1 acumula locks (8–41) y V2 casi ninguno, pero V1 no es más lento que V2; N=3 baja latencia sin cambiar HELD (K fijo).
- P2 y P5 no ejecutados (recorte declarado en este reporte).
<!-- /report:findings -->
