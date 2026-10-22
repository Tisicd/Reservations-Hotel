# F4b — Resiliencia (Parte 1): resultados

Fecha: 2026-10-22 · Rama: `feat/f4b-resiliencia`
Arnés: `tests/chaos/harness.py`; informes por escenario en `docs/resultados/chaos_*.md`.

## Resumen

| Escenario | Integridad | RTO/TTD medido | Objetivo | ¿Cumplido? | Reps | Hallazgos |
|---|---|---|---|---|---|---|
| D (recrear postgres, mismo volumen) | inv 0; sin pérdida; app sin reinicios | RTO 6,48 s (y 1,85–2,18 s en la batería final) | 120 s | sí | 1 (+1 bat.) | Recreación real (`rm -sf`+`up -d --no-build`), RTO a escritura sostenida (3). |
| S (TTD postgres) | 503 fail-closed; 0 2xx; inv 0 | TTD **93,21 s** (events; 93,2–96,6 s entre corridas); TTR **3,43 s** tras SIGCONT; downtime 96,6 s | 30 s (TTD) | **no** | 1 | Medición válida con **SIGSTOP** de los procesos `postgres` (el contenedor sigue arriba y el healthcheck ejecuta y falla). El **8,08 s** previo era `docker pause` sobre el **contenedor postgres**: congela también el healthcheck, Docker no aplica `retries` y la cifra no es válida. Con `retries=12`, TTD ≈ 12 × (5 s + ~3 s de check) ≈ 93–96 s; para 30 s harían falta ~3 reintentos (más falsos unhealthy). |
| S2 (postgres detenido ⇒ /ready) | inv 0; 0 2xx falsos; 6/6 unhealthy | 503 a **4,75 s**; TTD unhealthy **60,8–85,3 s** (payment el más lento); reconexión 200 a **5,96 s** | 30 s (reconexión) | sí | 1 | Healthcheck 5s/5s/12/15s en los 6 servicios. TTD dentro del rango `retries×interval` (60 s) .. `retries×(interval+timeout)` (120 s): 60,8–63,8 s en 5 servicios (check ~0,1–0,3 s) y 85,3 s en payment (su `/ready` tarda ~2,1 s y alarga el periodo). |
| E1 / stop (modo A, operador) | **200/200 ack durables** (+8 durante); 1 cargo; 0 MANUAL_REVIEW; inv 0 | **26,37 / 26,41 / 26,54 s** | 120 s | sí | 3 | Precarga ≥200 con caída en instante aleatorio (semilla 1001–1003); 0 2xx durante la caída. |
| E1 / pkill9 (modo B, autónomo) | 200/200 ack durables; 1 cargo; 0 MR; inv 0 | **20,78 / 20,80 / 20,83 s** | 120 s | sí | 3 | Reinicio por política (`unless-stopped`). |
| E3 / A (pérdida de volumen, backup en reposo) | inv **0**; RPO 5/5 | **30,46 / 30,49 / 30,55 s** | 900 s | sí | 3 | Las 5 reservas creadas tras el backup se pierden (RPO observado). |
| E3 / B (backup en caliente) | inv 0; RPO 5/5 | **30,80 / 31,36 / 32,25 s** | 900 s | sí | 3 | Observacional; no se reprodujo inconsistencia entre BDs con este volumen. |
| B / kill (1 de 3 réplicas) | inv 0; raw 96,43 % vs reintento 100 % | **0,29 / 0,29 / 0,40 / 2,41 / 0,33 s** | 2 s | 4/5 sí; 1/5 no | 5 | El outlier de 2,41 s persiste (1/5) aun con TTL DNS 1 s → hallazgo abierto. |
| B / kill9 | inv 0; reintento 100 % | **0,19–0,26 s** | 2 s | sí | 5 | — |
| E2 (pago desconocido) | 20/20 CONFIRMED; 0 MR; 1 cargo | p50 770 ms / p95 1048 ms / máx 1062 ms | n/a | sí (estado final) | 3 | API síncrona; acotado a 10 hilos. Un rep falló por colisión de inventario entre escenarios (no por pago); corregido con fechas únicas. |
| E4 (reinicio ordenado de postgres) | inv 0; app sin reinicios | **6,50 / 6,55 / 6,61 s** | 30 s | sí | 3 | Reconexión de los 6 servicios ~6,6 s; `RestartCount` sin cambios. |

Batería completa una vez tras el cambio de fechas (make clean-all && make build && make up && make seed && make chaos): **A–D, E1, E2, E4 y S sin fallo duro** (S mantiene integridad/fail-closed pero su TTD no cumple el objetivo de 30 s); E3 omitido por la salvaguarda (CHAOS_ALLOW_VOLUME_DELETE). make invariants → 0; IDs de imagen sin cambios.

## Hallazgos

1. **D no era recreación** (stop/start, 0,06 s). Corregido a recreación real; RTO 1,85–6,48 s.
2. **S TTD (dos cifras reconciliadas)**: el **8,08 s** de F4a se midió con `docker pause` sobre el **contenedor postgres**; al congelar todo el cgroup se congela también el healthcheck, Docker no ejecuta `retries` y la cifra no es válida → descartada. La medición válida usa **SIGSTOP** de los procesos `postgres` (contenedor arriba): **93,21 s** (96,62 s en otra corrida) vía `docker events`, TTR 3,43 s tras SIGCONT. `retries=12` con `interval=5s` y checks de ~3 s dan TTD ≈ 12×8 ≈ 96 s: **objetivo de 30 s NO cumplido**. Compromiso: bajar a ~3 reintentos daría ~24 s pero marcaría unhealthy ante fallos transitorios; se mantiene 12 y se documenta el incumplimiento.
3. **S2**: con postgres detenido, los 6 servicios devuelven `/ready` 503 a los 4,75 s. Docker los marca unhealthy entre **60,8 y 85,3 s**, dentro del rango teórico [60, 120] s = `retries×interval` .. `retries×(interval+timeout)`; payment tarda más (85,3 s) porque su check dura ~2,1 s y el periodo efectivo sube a ~7,1 s. Reconexión a 200: 5,96 s.
4. **Atribución de errores**: gateway responde **429** por `limit_conn`/`limit_req`; 429 no cuenta como impacto. B/kill raw 96,43 % vs reintento 100 % ⇒ la caída es de la réplica.
5. **B/kill rep4 = 2,41 s** (>2 s) intermitente; no se ajusta el objetivo. Causa probable: ventana de DNS/expulsión de la réplica; se deja abierto.
6. **E3-B ×3** con invariantes 0 (no se reprodujo inconsistencia entre BDs con el volumen usado).
7. **RPO real depende de la frecuencia de backup** (hoy `make backup` manual); E3 pierde 5/5 reservas creadas tras el backup. Ver `docs/proceso/backup-restore.md`.
8. **E1 durabilidad**: con ≥200 reservas reconocidas antes de la caída, todas sobreviven con el mismo estado y 1 cargo (I7 verificado).

## Pendiente / limitaciones

- Parte 2 (k6 + `make report`) no iniciada.
- Variante determinista de E3-B no implementada; queda como observacional.
- Backup/restore en Python (`scripts/backup.py`, `restore.py`) en lugar de `.sh`, por portabilidad; documentado.
