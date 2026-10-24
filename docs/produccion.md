# Evolución a producción

> Cada fila enlaza la evidencia de la limitación. No se inventan cifras: las
> que aparecen provienen de `docs/resultados/` y de los ADR.

| Limitación observada | Cambio para producción | Por qué |
|---|---|---|
| **PostgreSQL único**; S tarda **93,21 s** en marcar unhealthy con `retries=12` (objetivo 30 s) | Réplica primaria/standby, PITR y healthcheck con `retries` menor (p. ej. 3) o chequeo activo externo | Un solo primario es punto único de fallo; `retries=12` evita falsos positivos pero retrasa la detección (`resultados/F4b-resiliencia.md`, `resultados/chaos_S_stop_1.md`) |
| **Backup por BD, no consistente entre servicios**; RPO depende de `make backup` manual | Backup coordinado (snapshot del volumen o `pg_basebackup` + WAL), programado y verificado; RPO/RTO explícitos | E3 pierde las 5/5 reservas posteriores al backup y los dumps se toman en momentos distintos (`proceso/backup-restore.md`, `resultados/chaos_E3_A_*.md`, `chaos_E3_B_*.md`) |
| **Saga síncrona** de `reservation`: p95 5–6,5 s en P3; con holds directos (P3b) el p95 baja a ~1–2 s | Responder **202** inmediato y dejar que el worker avance; o reducir `SAGA_SYNC_WAIT_SECONDS`; más procesos/réplicas de `reservation` | P3 medía la cola de la API síncrona, no la contención de inventario (`resultados/perf_P3.md`, `perf_P3b.md`, `F4c`/`REPORTE.md`) |
| **Outbox sin dead-letter** ni alarma de fallo permanente | Cola durable con *dead-letter*, reintentos con backoff y alerta por antigüedad/backlog | `resultados/F4b-resiliencia.md`, `fallos.md`, `03-estado-del-proyecto.md`; hoy el relay reintenta y el estado queda PENDING/FAILED |
| **Host único**; resultados comparativos de una máquina | Multinodo (Swarm/K8s) con réplicas y *anti-affinity*; balanceo externo | P1 muestra que `availability` escala ~2,09× y que el host comparte CPU con PG y k6 (`resultados/perf_P1.md`, `perf_P1_analisis.md`) |
| **Sin métricas/trazas/SLO**: logs JSON y chequeos | OpenTelemetry (métricas/trazas), Prometheus/Grafana, alertas por SLO y por outbox | `03-estado-del-proyecto.md`; la evidencia actual son informes y logs |
| **Sin TLS ni autenticación** en la demo | TLS en el gateway, autenticación de clientes/operadores, *rate limit* por usuario | `seguridad.md`; el listener público permite reservar a cualquiera |
| **Sin WAF/CDN**; límites por IP | WAF/CDN delante del gateway, listas y *rate limit* distribuido | P4 demuestra 429 al saturar una IP, pero no frena muchas IPs (`resultados/perf_P4.md`, `seguridad.md`) |
| **Secretos en archivos locales**, sin rotación | Gestor de secretos (Vault/Secrets Manager) y rotación; secretos de Swarm/K8s | `seguridad.md`; gitleaks 0 en git, pero el `.env` local y los archivos no rotan |
| **CVEs en imágenes**: 47 HIGH/0 CRITICAL por imagen (44 base + 3 `starlette`) | Reconstruir base, actualizar `starlette`/FastAPI, escanear en CI y firmar imágenes | `resultados/seguridad-trivy.txt`; los 3 de starlette tienen fix (0.49.1/1.1.0/1.3.1) |
| **Migraciones y workers** acoplados a Compose (`depends_on`) | Jobs de migración one-shot, `depends_on` sustituido por reintentos/readiness, *leases* y `SKIP LOCKED` ya presentes | `docs/swarm.md`; los workers ya usan leases y `with_for_update(skip_locked=True)` |
| **Sin CPU limits** (solo memoria/pids) | `resources`/límites de CPU y *requests* en orquestador; pruebas de capacidad por réplica | `compose.yaml`; P1 muestra CPU de `availability` y PG como consumidores (`perf_P1_analisis.md`) |

## Orden sugerido de adopción

1. **TLS + autenticación + WAF/CDN** en el gateway (sin tocar servicios).
2. **Backup coordinado + PITR** y ensayo de restauración (E3) con RPO/RTO
   acordados.
3. **Réplica de PostgreSQL** y *failover*; bajar `retries` del healthcheck a
   un valor compatible con el objetivo de TTD (medir el compromiso).
4. **202 inmediato** en reservas y más procesos/réplicas de `reservation`;
   medir de nuevo P3/P3b.
5. **Observabilidad y SLO** (métricas, trazas, alertas de outbox).
6. **Multinodo** (Swarm/K8s) con réplicas y *anti-affinity*; migrar secretos y
   configuración.
7. **Cadena de suministro**: actualizar starlette/base, SBOM, firma y escaneo
   en CI.

## Lo que no cambia

Los contratos (`05-contratos-api.md`), los invariantes I1–I7 y la saga con
`advance(reservation_id)` (ADR-0003) se mantienen: la evolución es de
infraestructura y operación, no de la lógica de negocio.
