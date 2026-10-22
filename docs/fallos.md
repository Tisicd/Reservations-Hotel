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
| E4 | Reinicio ordenado de PostgreSQL con servicios activos | servicios reconectan sin reiniciarse | pendiente (recortable) |
| S | Detener `postgres`; observar `/ready` y salud de Docker | 503 (nunca 2xx falsos), TTD, tiempo a healthy | `chaos_S_stop_1.md` |

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
