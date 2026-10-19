# Plan del proyecto v3: Plataforma de reservas reproducible y resiliente
> **v3:** se añaden arquitectura hexagonal ligera, frontend mínimo, entregables escritos (informe, costos, manual) y preparación de defensa. Arquitectura: `04-arquitectura.md` · ADR: `adr/` · Contratos: `05-contratos-api.md` · Negocio y fallos: `fases/F0-negocio-y-resiliencia.md`. El flujo crítico se implementa **antes** que el resto; RabbitMQ y otras herramientas dependen de resultados.
**Hoy: dom 18 oct 2026 · Funcionando para: dom 25 oct 2026**

## 0. Tesis del proyecto
No es "levantar 6 contenedores". Es una plataforma **reproducible, resiliente y con evidencia técnica de sus límites**:
- *Qué funciona* → tests de integración verdes.
- *Qué falla* → escenarios de caos con resultados documentados.
- *Cómo se recupera* → tiempo de recuperación medido.
- *Qué cambiaría en producción* → documento de evolución con riesgos honestos.

Un hallazgo negativo bien medido (p. ej. "escalar a 3 réplicas no mejora porque el cuello es la BD") vale más que un resultado perfecto sin explicar. Es el mensaje central para la defensa y para entrevistas.

## 1. Decisiones (ADR resumido)
| # | Decisión | Motivo | Compromiso aceptado |
|---|---|---|---|
| D1 | Python + FastAPI | Poco código, OpenAPI gratis, fácil para el agente | Menor throughput que Go/Java; irrelevante para el objetivo |
| D2 | **1 contenedor PostgreSQL, 6 BDs lógicas, 1 rol por BD** | Transacciones ACID, `CHECK`/`UNIQUE` y bloqueos para inventario, reservas y pagos | Sin aislamiento de recursos ni HA; punto único de fallo compartido. Se documenta, se prueba (E1, E3) y se mitiga con backups |
| D3 | HTTP síncrono (customer, hotel, availability, payment) | Simple de probar | Acoplamiento temporal → mitigado con timeouts/reintentos |
| D4 | Notificaciones: **outbox transaccional (HTTP) primero; RabbitMQ solo si pasa la compuerta de F0 §7** | La reserva no depende de notificaciones; RabbitMQ no elimina duplicados ni sustituye transacciones | Entrega al menos una vez + dedupe por `event_id` |
| D5 | nginx como gateway + balanceador + rate limiting | Un solo punto expuesto | nginx OSS solo hace health check pasivo; DNS de Docker con `resolver 127.0.0.11` |
| D6 | Compose single-host | Alcance de titulación | Sin tolerancia a caída del host ni autoescalado real (se documenta) |
| D7 | Pagos simulados con latencia/fallo configurables | Permite probar compensaciones y timeouts | No hay pasarela real |
| D8 | Frontend mínimo en HTML + JS servido por nginx (ADR-0008) | Una demo visual facilita la defensa; sin build | Sin componentes; React solo si G1 deja holgura |
| D9 | Hexagonal ligera en servicios con lógica; CRUD modular en customer/hotel (ADR-0001) | Probar saga y estados sin BD; capas verificadas por `import-linter` | Más ficheros; puertos solo con frontera real |
| D10 | Workers en contenedores separados con la misma imagen (ADR-0004) | Aislamiento de fallos API/worker; recuperación demostrable | 2 contenedores más |

## 2. Arquitectura
```
Cliente/k6 ─► gateway (nginx :8080)  ── único puerto publicado
                │  limit_req, limit_conn, timeouts
        [edge-net]
                ▼
 customer · hotel · availability x3 · reservation · payment · notification   [backend-net, internal]
                │
 postgres (6 BDs, volumen pgdata)   [data-net, internal]
 (opcional) rabbitmq (volumen)      [backend-net]
```
- `backend-net` y `data-net` con `internal: true`. Solo el gateway publica puerto.
- Cada servicio solo conoce la BD y los servicios que necesita (matriz de comunicación abajo).
- Contenedores: usuario no-root, `cap_drop: [ALL]`, `read_only` donde sea viable, límites `mem_limit/cpus/pids_limit`.

### Matriz de comunicación (quién llama a quién)
| Origen → Destino | Permitido | Notas |
|---|---|---|
| gateway → todos los servicios API | Sí | Única entrada externa |
| reservation → customer, availability, payment | Sí | Síncrono, timeout |
| reservation → notification | Sí (vía outbox) | Asíncrono, no bloquea |
| availability → hotel | Opcional | Preferible datos replicados mínimos para no acoplar |
| Cualquier servicio → BD de otro | **No** | Cada rol solo accede a su BD |
| Servicios → internet | No necesario | |

## 3. Contratos API
Ver `05-contratos-api.md` (fuente de verdad) y `adr/`. Se genera un snapshot OpenAPI por servicio y un test de contrato detecta cambios involuntarios.

## 4. Resiliencia (patrones y dónde se prueban)
| Patrón | Implementación | Prueba |
|---|---|---|
| Timeouts explícitos | En cada cliente HTTP y en nginx | Test con payment lento |
| Reintentos acotados | Máx. 2-3, backoff + jitter, **solo operaciones idempotentes** | Test de reintento sin duplicar |
| Idempotencia | `Idempotency-Key` en reservas y pagos | Enviar la misma request 5 veces → 1 reserva, 1 cobro |
| Rate limiting | `limit_req` por IP en nginx + `limit_conn` | k6 por encima del límite → 429, el sistema sigue sano |
| Balanceo + réplicas | availability x3, `proxy_next_upstream` | Escenario B |
| Health checks | `HEALTHCHECK` + `/ready` + `depends_on: service_healthy` | Servicio no saludable simulado (endpoint admin o fallo de BD) |
| Degradación controlada | Reserva funciona sin notification | Escenario A |
| Backpressure | Pool de conexiones acotado por servicio | Cálculo `réplicas × pool ≤ max_connections` |
| *(Stretch)* Circuit breaker | Sobre payment | Solo si hay tiempo |

## 5. Escenarios de fallo (A–D) y qué mide cada uno
Cada uno se automatiza en `tests/chaos/` con un tráfico constante de fondo y produce `docs/resultados/chaos_<X>.md` con las 5 preguntas del enunciado respondidas con datos.

| Esc. | Acción | Hipótesis | Métricas |
|---|---|---|---|
| A | `docker stop notification` durante reservas | Reservas siguen OK; notificaciones quedan pendientes y se entregan al recuperar | % éxito reservas, # pendientes, tiempo hasta vaciar outbox |
| B | `docker stop` 1 de 3 réplicas de availability bajo carga | Sin errores sostenidos; pico breve de latencia | errores durante la caída, p95 antes/durante/después |
| C | `docker restart reservation` con una reserva en curso | Reservas confirmadas persisten; idempotencia evita duplicados al reintentar | tiempo de recuperación (a `healthy`), reservas perdidas/duplicadas |
| D | `rm` del contenedor postgres y recreación con el mismo volumen | Datos íntegros; servicios reconectan | conteo de filas antes/después, MTTR; **contraprueba**: `down -v` pierde datos (info efímera vs persistente) |

Ampliación en `fases/F0...` (E1-E4, T-pago, backup/restore). Adicional: **servicio no saludable** (punto 8) y **PG caído** (hallazgo honesto: todos dependen de la BD compartida → es el punto único de fallo; se documenta mitigación).

## 6. Pruebas de carga (k6)
- **Escenarios:** (1) lectura de disponibilidad con 1 réplica; (2) igual con 3 réplicas; (3) mezcla 90% lectura / 10% reservas; (4) sobre el límite de rate limit; (5) ramp-up hasta saturación.
- **Métricas:** RPS, latencia p50/p95/p99, tasa de error, 429 vs 5xx, CPU/mem por contenedor (`docker stats`), conexiones a PG.
- **Umbrales** (thresholds k6) definidos antes de correr, p. ej. p95 < 300 ms y errores < 1% en carga nominal.
- **Honestidad metodológica:** k6, servicios y PG comparten la misma máquina → los resultados son *comparativos* (1 vs 3), no absolutos. Se documenta hardware, versión, y se repite cada corrida ≥3 veces.
- **Hipótesis a verificar:** escalar availability ayuda hasta que la BD/CPU se satura; después no mejora. Si el cuello es PG, se demuestra con datos.

## 7. Seguridad y análisis de amenazas (alcance realista)
| Amenaza | Qué se implementa | Qué NO resuelve Compose (se documenta) |
|---|---|---|
| Exposición innecesaria | Un solo puerto; redes `internal`; Swagger/RabbitMQ UI no publicados (o solo `127.0.0.1`) | — |
| Credenciales | `.env` fuera de git + `.env.example`; secretos por archivo (`*_FILE`) o Docker secrets; nada en imágenes; `gitleaks`/escaneo en CI | Rotación y gestor de secretos (Vault/Cloud) |
| Saturación de conexiones / slowloris | `limit_conn`, `client_*_timeout`, `worker_connections`, `limit_req` | DDoS volumétrico: requiere CDN/WAF/proveedor upstream |
| Ataques DNS | Fuera del alcance de Compose; si se publica: Cloudflare/DNS gestionado, DNSSEC | Escalar réplicas **no** mitiga DNS ni ataques volumétricos |
| Agotamiento de recursos | `mem_limit`, `cpus`, `pids_limit`, pools acotados | Autoescalado y cuotas por tenant |
| Imágenes/dependencias | Multistage, no-root, `trivy` en CI, versiones fijadas | SBOM y firma de imágenes |
| Inyección/validación | Pydantic, consultas parametrizadas | Pentest completo |

## 8. Evolución hacia producción (documento `docs/produccion.md`)
Cada fila: *limitación actual → cambio → por qué*.
- Caída del host → múltiples nodos (Swarm/K8s) con réplicas distribuidas.
- PG único → réplica en streaming + failover (Patroni o BD gestionada) + backups y PITR.
- Outbox HTTP → RabbitMQ con colas durables/quorum, DLQ y consumidores idempotentes.
- Logs sueltos → observabilidad: métricas Prometheus, dashboards Grafana, trazas OpenTelemetry, alertas por SLO.
- Rate limit local → WAF/CDN, límites por cliente autenticado.
- Autenticación → JWT/OIDC en el gateway (hoy fuera del alcance).
- Swarm: qué servicios usan `deploy.replicas` y `update_config` (análisis requerido por el enunciado).

## 9. Estrategia de pruebas (pirámide mínima)
1. **Unitarias** (pytest) en lógica clave: bloqueos de inventario, idempotencia, saga.
2. **Integración/e2e** (pytest + httpx contra compose real): flujo feliz, pago fallido (compensación), doble envío, reserva sobre cupo agotado (concurrencia: N peticiones simultáneas, solo K éxitos).
3. **Caos** (A–D) + salud.
4. **Carga** (k6).
5. **Contrato**: validar que el OpenAPI de cada servicio no rompe (snapshot).

## 10. Interfaz de entrega (`Makefile`)
| Comando | Hace |
|---|---|
| `make up` | Construye y levanta todo, espera a `healthy` y siembra datos demo |
| `make test` | Unitarias + e2e |
| `make chaos` | Escenarios A–D + salud; genera reportes |
| `make perf` | k6 con 1 y 3 réplicas; genera reportes |
| `make report` | Consolida `docs/resultados/REPORTE.md` (tablas + hallazgos) |
| `make down` / `make clean` | Baja / baja + borra volúmenes |

CI (GitHub Actions): lint → build → `make up` → `make test` → `make chaos` (versión corta) → `trivy` → sube reportes como artefactos.

## 11. Plan de implementación (v3)

**Prioridad MoSCoW:** *Must* = enunciado completo + invariantes I1-I7 + Esc. A-D + E1-E3 + informe escrito. *Should* = frontend mínimo, rate limit, CI, reportes automáticos. *Could* = RabbitMQ, circuit breaker, métricas, React, despliegue online.

| Fase | Fecha | Alcance | Compuerta |
|---|---|---|---|
| **F0** Arquitectura y resiliencia | Dom 18 – Lun 19 | ADR, estructura, capas, contratos, estados, matriz de fallos, RTO/RPO | **G0** |
| **F1** Flujo crítico | Lun 19 – Mié 21 | availability, payment, reservation, customer/hotel mínimos, chequeador de invariantes | Tests de concurrencia, idempotencia, pago y recuperación en verde (`fases/F1`) |
| **F2** Integración | Mié 21 – Jue 22 (mediodía) | notification + outbox/relay, gateway, availability x3, healthchecks, redes internas, config externa | **G1**: decide RabbitMQ y congela alcance |
| **F3** Frontend mínimo | Jue 22 PM (timebox 4 h) | Una pantalla: buscar → reservar → resultado + línea de tiempo + notificación | Demo del flujo en el navegador |
| **F4** Fallos, carga y reportes | Vie 23 – Sáb 24 AM | Esc. A-D, E1-E4, backup/restore, k6, `make report` | Reportes con RTO/RPO medidos |
| **F5** Documentación y entrega | Sáb 24 – Dom 25 | Informe (costos, decisiones, manual, justificación), ensayo desde cero, tag `v1.0-entrega` | Tercero reproduce con el README |
| **F6** Defensa | 26 – 29 oct | Entender pruebas, banco de preguntas, guion de demo, ensayos (`informe/defensa.md`) | Defensa 28-30 oct (por confirmar) |

**Documentación continua:** cada fase cierra con docs/ADR actualizados y `costos/registro.md` al día; el informe se ensambla desde lo ya escrito (`informe/ESTRUCTURA.md`), no se redacta al final desde cero.

**Reglas de recorte (en orden):** despliegue online → RabbitMQ → React/pulido del frontend → circuit breaker → métricas. **Nunca:** invariantes, Esc. A-D, E1-E3, reportes, informe.
**Prioridad dentro de F4 si falta tiempo:** Esc. A-D → E1 → E2 → carga lectura 1 vs 3 → E3 → E4 → carga mixta.
**Riesgo reconocido:** el alcance es ajustado para 7 días. Mitigación: customer/hotel son CRUD triviales; frontend acotado a 4 h; pruebas de F4 reutilizan los scripts y el chequeador de F1.

## 12. Definition of Done del proyecto
- [ ] `make clean && make up && make test && make chaos && make perf && make report` funciona desde cero.
- [ ] Invariantes I1-I7 verificadas automáticamente tras cada prueba.
- [ ] Un solo puerto publicado; ningún secreto en imágenes ni en git.
- [ ] 6 servicios con BD propia y rol sin acceso a otras BDs (con test).
- [ ] Esc. A-D y E1-E3 con las 5 preguntas respondidas con métricas reales y RTO/RPO medidos.
- [ ] Comparativa 1 vs 3 réplicas separando **lectura** (escala) y **escritura** (contención en BD), con conclusión honesta.
- [ ] `docs/produccion.md` y `docs/seguridad.md` con limitaciones explícitas (host, BD única, DNS/DDoS).
- [ ] README con arquitectura, cómo correr y hallazgos.
- [ ] Informe escrito completo (decisiones, costos, manual, justificación) y banco de preguntas de defensa.
- [ ] `import-linter` en verde en los servicios hexagonales.

## 13. Riesgos del plan
| Riesgo | Prob./Impacto | Mitigación |
|---|---|---|
| Agente genera código que "parece" funcionar sin test | Alta/Alto | Test primero; revisar diffs; CI obligatorio |
| Tiempo insuficiente | Media/Alto | Congelar alcance el jue 22; MoSCoW |
| Resultados de carga ruidosos (misma máquina) | Alta/Medio | Comparar, repetir ≥3, documentar entorno |
| nginx no re-resuelve DNS al escalar | Media/Medio | `resolver` + variable en `proxy_pass`; test específico |
| PG compartido enmascara el beneficio de réplicas | Alta/Bajo (es un hallazgo) | Medirlo y explicarlo |
| Condiciones de carrera en inventario | Media/Alto | Bloqueo transaccional + test de concurrencia |

## 14. Cómo contarlo en una entrevista junior (guion corto)
"Descompuse un monolito en 6 microservicios con una BD lógica por servicio, lo hice reproducible con Compose y automaticé tests, caos y carga. Medí qué pasa cuando cae notificaciones, una réplica, un servicio o la BD, y documenté qué sigue siendo punto único de fallo y cómo lo resolvería en producción. Usé un agente de IA con especificaciones y tests como contrato, y revisé cada cambio."
