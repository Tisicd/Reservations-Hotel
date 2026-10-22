# F4b — Resiliencia (Parte 1): resultados

Fecha: 2026-10-22 · Rama: `feat/f4b-resiliencia`
Arnés: `tests/chaos/harness.py`; informes por escenario en `docs/resultados/chaos_*.md`.

## Resumen

| Escenario | Integridad | RTO/TTD medido | Objetivo | ¿Cumplido? | Reps | Hallazgos |
|---|---|---|---|---|---|---|
| D (recrear postgres, mismo volumen) | inv 0; sin pérdida; app sin reinicios | RTO 6,48 s (y 1,85–2,18 s en la batería final) | 120 s | sí | 1 (+1 bat.) | Recreación real (`rm -sf`+`up -d --no-build`), RTO a escritura sostenida (3). |
| S (postgres no saludable) | 503 fail-closed; 0 2xx; inv 0 | TTD **96,62 s** (events); TTR **4,57 s** tras SIGCONT; downtime 101,2 s | 30 s (TTR) | sí (TTR) | 1 | Se congelan procesos con SIGSTOP; healthcheck postgres 5s/5s/12/15s. TTD 96,6 s ≠ 60 s esperado: cada check fallido consume `timeout` (5 s) además del `interval`. |
| S2 (postgres detenido ⇒ /ready) | inv 0; 0 2xx falsos | 6/6 servicios `/ready`→**503 a 4,78 s**; reconexión 200 a **5,89 s** | 30 s | sí | 1 | `docker stop` de postgres → los 6 servicios fail-closed. |
| E1 / stop (modo A, operador) | **200/200 ack durables** (+8 durante); 1 cargo; 0 MANUAL_REVIEW; inv 0 | **26,37 / 26,41 / 26,54 s** | 120 s | sí | 3 | Precarga ≥200 con caída en instante aleatorio (semilla 1001–1003); 0 2xx durante la caída. |
| E1 / pkill9 (modo B, autónomo) | 200/200 ack durables; 1 cargo; 0 MR; inv 0 | **20,78 / 20,80 / 20,83 s** | 120 s | sí | 3 | Reinicio por política (`unless-stopped`). |
| E3 / A (pérdida de volumen, backup en reposo) | inv **0**; RPO 5/5 | **30,46 / 30,49 / 30,55 s** | 900 s | sí | 3 | Las 5 reservas creadas tras el backup se pierden (RPO observado). |
| E3 / B (backup en caliente) | inv 0; RPO 5/5 | **30,80 / 31,36 / 32,25 s** | 900 s | sí | 3 | Observacional; no se reprodujo inconsistencia entre BDs con este volumen. |
| B / kill (1 de 3 réplicas) | inv 0; raw 96,43 % vs reintento 100 % | **0,29 / 0,29 / 0,40 / 2,41 / 0,33 s** | 2 s | 4/5 sí; 1/5 no | 5 | El outlier de 2,41 s persiste (1/5) aun con TTL DNS 1 s → hallazgo abierto. |
| B / kill9 | inv 0; reintento 100 % | **0,19–0,26 s** | 2 s | sí | 5 | — |
| E2 (pago desconocido) | 20/20 CONFIRMED; 0 MR; 1 cargo | p50 770 ms / p95 1048 ms / máx 1062 ms | n/a | sí (estado final) | 3 | API síncrona; acotado a 10 hilos. Un rep falló por colisión de inventario entre escenarios (no por pago); corregido con fechas únicas. |
| E4 (reinicio ordenado de postgres) | inv 0; app sin reinicios | **6,50 / 6,55 / 6,61 s** | 30 s | sí | 3 | Reconexión de los 6 servicios ~6,6 s; `RestartCount` sin cambios. |

Batería completa una vez tras el cambio de fechas (`make clean-all && make build && make up && make seed && make chaos`): **A–D, E1, E2, E4 y S en verde**; E3 omitido por la salvaguarda (`CHAOS_ALLOW_VOLUME_DELETE`). `make invariants` → 0; IDs de imagen sin cambios.

## Hallazgos

1. **D no era recreación** (stop/start, 0,06 s). Corregido a recreación real; RTO 1,85–6,48 s.
2. **S TTD**: `docker stop` deja `State.Health.Status=unhealthy` pero **no emite** `health_status` y detiene los healthchecks. Se congelan los procesos con SIGSTOP para que el healthcheck falle. TTD medido **96,62 s** con `interval=5s timeout=5s retries=12 start_period=15s`; el valor esperado `retries×interval=60 s` no se cumple porque cada check fallido consume también su `timeout` (≈8 s por reintento). TTR tras descongelar: 4,57 s.
3. **S2**: con postgres detenido, los 6 servicios devuelven `/ready` 503 a los 4,78 s y reconectan a 200 a los 5,89 s (fail-closed correcto).
4. **Atribución de errores**: gateway responde **429** por `limit_conn`/`limit_req`; 429 no cuenta como impacto. B/kill raw 96,43 % vs reintento 100 % ⇒ la caída es de la réplica.
5. **B/kill rep4 = 2,41 s** (>2 s) intermitente; no se ajusta el objetivo. Causa probable: ventana de DNS/expulsión de la réplica; se deja abierto.
6. **E3-B ×3** con invariantes 0 (no se reprodujo inconsistencia entre BDs con el volumen usado).
7. **RPO real depende de la frecuencia de backup** (hoy `make backup` manual); E3 pierde 5/5 reservas creadas tras el backup. Ver `docs/proceso/backup-restore.md`.
8. **E1 durabilidad**: con ≥200 reservas reconocidas antes de la caída, todas sobreviven con el mismo estado y 1 cargo (I7 verificado).

## Pendiente / limitaciones

- Parte 2 (k6 + `make report`) no iniciada.
- Variante determinista de E3-B no implementada; queda como observacional.
- Backup/restore en Python (`scripts/backup.py`, `restore.py`) en lugar de `.sh`, por portabilidad; documentado.
