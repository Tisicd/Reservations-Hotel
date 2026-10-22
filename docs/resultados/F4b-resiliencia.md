# F4b — Resiliencia (Parte 1): resultados

Fecha: 2026-10-22 · Rama: `feat/f4b-resiliencia`
Arnés: `tests/chaos/harness.py`; informes por escenario en `docs/resultados/chaos_*.md`.

## Resumen

| Escenario | Integridad | RTO/TTD medido | Objetivo | ¿Cumplido? | Reps | Hallazgos |
|---|---|---|---|---|---|---|
| D (recrear postgres, mismo volumen) | inv 0; sin pérdida; app sin reinicios | RTO **6,48 s** | 120 s | sí | 1 | Antes 0,06 s era stop/start; ahora es recreación real y RTO a escritura sostenida (3). |
| S (postgres no saludable) | 503 fail-closed; 0 2xx; inv 0 | TTD **8,08 s**; TTR **13,28 s** | 30 s (TTR) | sí | 1 | `docker stop` no emite `health_status`; se usa `docker pause` + `docker events`. |
| E1 / stop (modo A, operador) | ack 10/10 durable; 1 cargo; 0 MANUAL_REVIEW; inv 0 | **26,11 / 26,36 / 26,52 s** | 120 s | sí | 3 | 46× 503 fail-closed, 0 2xx durante la caída. |
| E1 / pkill9 (modo B, autónomo) | ack durable; 1 cargo; 0 MANUAL_REVIEW; inv 0 | **20,57 / 20,69 / 20,83 s** | 120 s | sí | 3 | Reinicio por política (`unless-stopped`). |
| E3 / A (pérdida de volumen, backup en reposo) | inv **0**; RPO 5/5 | **30,46 / 30,49 / 30,55 s** | 900 s | sí | 3 | Las 5 reservas creadas tras el backup se pierden (RPO observado), como define el diseño. |
| E3 / B (backup en caliente) | observacional; inv 0 en esta corrida; RPO 5/5 | **36,39 s** | 900 s | sí | 1 | No se reprodujo inconsistencia entre BDs con este volumen de datos. |
| B / kill (1 de 3 réplicas) | inv 0; raw 96,43 % vs reintento 100 % | **0,38 / 0,40 / 0,42 s** | 2 s | sí | 3 | Antes de la mitigación (TTL DNS 1 s) la 1ª caída daba 2,42 s. |
| B / kill9 | inv 0; reintento 100 % | **0,91 / 0,21 / 0,20 s** | 2 s | sí | 3 | — |
| E2 (pago desconocido) | 20/20 CONFIRMED; 0 MANUAL_REVIEW; 1 cargo | p50 770 ms / p95 1048 ms / máx 1062 ms | n/a | sí (estado final) | 1 | API síncrona; 20 concurrentes → 429 por `limit_conn 10`; acotado a 10 hilos. |
| E4 (reinicio ordenado de postgres) | — | — | — | **pendiente** | 0 | Recortable; no ejecutado. |

`make images`: se compararon los IDs de las 6 imágenes `:local` antes y después
de la batería; sin diferencias (0 imágenes nuevas). `make invariants` → 0.

## Hallazgos

1. **D no era una recreación**: era `stop/start`, de ahí 0,06 s. Corregido a
   `rm -sf` + `up -d --no-build`; RTO ahora 6,48 s.
2. **S TTD**: `docker stop` deja `State.Health.Status=unhealthy` pero **no emite**
   `health_status` y detiene los healthchecks. Se cambió a `docker pause` para
   observar la transición real en `docker events` (TTD 8,08 s). El 0,1 s previo
   era el primer 503, no la detección por Docker.
3. **Atribución de errores**: el gateway ahora responde **429** por
   `limit_conn`/`limit_req`; 429 no cuenta como impacto. B/kill: raw 96,43 %,
   reintento 100 % ⇒ la caída transitoria es de la réplica, no del limitador.
4. **B/kill primera caída lenta**: con `resolver valid=1s` pasa de 2,42 s a
   0,38–0,42 s. No se ajustó el objetivo.
5. **E3-B no reprodujo inconsistencias** con el volumen de datos usado
   (`invariantes=0`); se mantiene como observacional.
6. **E3 RPO**: 5/5 reservas creadas tras el backup se pierden al restaurar; es la
   brecha real entre RPO objetivo (≤ antigüedad del backup) y lo observado.
7. **E4 pendiente** (recortable según el prompt).

## Cómo reproducir

```
make build && make up && make seed
make chaos SCEN=D REPEAT=1
make chaos SCEN=S REPEAT=1
make chaos SCEN=E1 REPEAT=3
make chaos SCEN=B REPEAT=3
make chaos SCEN=E2 REPEAT=1
$env:CHAOS_ALLOW_VOLUME_DELETE="1"; make chaos SCEN=E3 REPEAT=1
make invariants
```

Protocolo de backup/restauración y salvaguardas: `docs/proceso/backup-restore.md`.
