# Informe — Plataforma de reservas (borrador)

> **Borrador ensamblado desde evidencia del repositorio.** Cada cifra enlaza a
> su archivo. Las secciones 1, 3, 10 y 14 quedan **PENDIENTE (persona)** porque
> requieren juicio, matriz ponderada y precios vigentes. La tesis: esta
> solución es la más adecuada **para este caso y estas restricciones**, no una
> arquitectura universalmente superior.

## 1. Resumen ejecutivo

**PENDIENTE (persona).**

## 2. Análisis del negocio

El dominio es una plataforma de reservas hoteleras con procesos de clientes,
hoteles, habitaciones, disponibilidad, reservas, pagos, confirmaciones y
notificaciones ([`fases/F0-negocio-y-resiliencia.md`](../fases/F0-negocio-y-resiliencia.md)).
La criticidad se concentra en no sobrevender, no cobrar dos veces y no perder
reservas confirmadas. Los invariantes que gobiernan el diseño y las pruebas son
I1–I7 (sin sobreventa; una reserva por intención; un cobro por reserva;
`CONFIRMED` ⇒ pago y hold confirmados; estados no estables avanzan o expiran;
`CONFIRMED` ⇒ exactamente un evento; lo comprometido sobrevive a reinicios),
definidos en F0 y verificados por `make invariants`
([`fases/F0-negocio-y-resiliencia.md`](../fases/F0-negocio-y-resiliencia.md),
[`fallos.md`](../fallos.md)).

La clasificación de servicios y su necesidad de disponibilidad están en
[`04-arquitectura.md`](../04-arquitectura.md): `availability` es crítico y
escala horizontalmente; `reservation`/`payment` son críticos y síncronos;
`notification` es fail-open; `customer`/`hotel` son datos maestros.

## 3. Alternativas y por qué esta solución

**PENDIENTE (persona).** La matriz ponderada (monolito modular,
microservicios en Compose, serverless, Kubernetes, BD gestionada) y los
criterios (integridad, aislamiento, complejidad, costo, plazo,
demostrabilidad) los redacta la persona; las decisiones ya están en
[ADR-0001](../adr/0001-microservicios-hexagonal-ligera.md),
[ADR-0002](../adr/0002-postgresql-compartido-seis-bds.md) y
[`02-plan.md`](../02-plan.md).

## 4. Arquitectura

- **Topología:** 6 microservicios, 5 workers, PostgreSQL 16 con 6 BDs/roles y
  nginx como única entrada. Redes `edge-net`, `backend-net` y `data-net`
  (las dos últimas `internal: true`) ([`compose.yaml`](../../compose.yaml),
  [`04-arquitectura.md`](../04-arquitectura.md)).
- **Hexagonal ligera** en availability/reservation/payment/notification
  (`api → application → domain`, `infrastructure` hacia fuera); CRUD modular
  en customer/hotel. `import-linter` verifica las capas (ADR-0001,
  [`04-arquitectura.md`](../04-arquitectura.md)).
- **Patrones:** saga orquestada con una única `advance(reservation_id)`
  (ADR-0003); inventario atómico/fail-closed (ADR-0005); pago con estados
  explícitos (ADR-0006); outbox + relay + inbox idempotente (ADR-0004);
  gateway con DNS dinámico y reintentos solo en idempotentes (ADR-0007).
- **Frontend** HTML/JS sin build servido por nginx (ADR-0008), consumiendo solo
  `/api/*` públicos.
- **Fuente de verdad** de hoteles/habitaciones/precios en `hotel`
  (ADR-0010).

## 5. Decisiones tecnológicas

| Decisión | Alternativa descartada | Consecuencia | Evidencia |
|---|---|---|---|
| Python 3.12 + FastAPI + Pydantic + SQLAlchemy/psycopg | Otros frameworks/ORM | Tipado y validación; ecosistema probado | ADR-0009 |
| PostgreSQL único con 6 BDs/roles | BD por servicio en contenedores separados, NoSQL | Aislamiento lógico y operación simple; punto único de fallo | ADR-0002 |
| Docker Compose | Kubernetes/Swarm para la entrega | Reproducible en un host; Swarm queda como análisis | ADR-0001, [`swarm.md`](../swarm.md) |
| nginx gateway | API gateway gestionado | Control de exposición y límites; sin WAF/TLS en local | ADR-0007 |
| Saga orquestada | Coreografía | Estados y recuperación en un solo lugar | ADR-0003 |
| Outbox + relay + inbox | RabbitMQ | Sin broker extra; entrega al menos una vez | ADR-0004, ADR-0011 |
| Inventario atómico `UPDATE … WHERE` | Locks aplicativos | Sin sobreventa; fail-closed | ADR-0005 |
| Payment adapter con `DECLINED/FAILED_TECHNICAL/UNKNOWN` | Reintento ciego | Evita doble cobro; conciliación | ADR-0006 |
| Frontend HTML/JS sin build | React/Vite | Cero dependencias y demo visual | ADR-0008 |
| `hotel` como fuente de verdad de datos maestros | Copias locales | Validación coherente | ADR-0010 |

## 6. Contratos y flujo de reserva

- Contratos en [`05-contratos-api.md`](../05-contratos-api.md): cabeceras
  `X-Request-ID`/`Idempotency-Key`, errores 4xx/5xx, representación de reserva.
- Estados: `RECEIVED, HELD, PAYMENT_PENDING, PAYMENT_UNKNOWN, PAID,
  CONFIRMED, PAYMENT_DECLINED, REFUND_REQUIRED, CANCELLING, CANCELLED,
  REJECTED_NO_INVENTORY, FAILED_TECHNICAL, MANUAL_REVIEW`
  ([`05-contratos-api.md`](../05-contratos-api.md), ADR-0003).
- Flujo: persistir `RECEIVED` → hold atómico → pago → confirmar hold →
  `CONFIRMED` y evento de outbox. `advance(reservation_id)` es la misma
  función para el camino normal y la recuperación (ADR-0003).
- Idempotencia: misma clave y cuerpo ⇒ `200` + `Idempotent-Replayed: true`,
  sin duplicar ([`05-contratos-api.md`](../05-contratos-api.md),
  `tests/e2e/test_public_flow.py`).
- `CANCELLING` tiene plazo (`CANCEL_DEADLINE_SECONDS=120`); al vencer pasa a
  `MANUAL_REVIEW` sin asumir reembolso (ADR-0003, ADR-0011).

## 7. Resiliencia y fallos

Objetivos de F0 y resultados (detalle en
[`resultados/REPORTE.md`](../resultados/REPORTE.md); cada fila enlaza su
informe):

| Escenario | Integridad | Medido | Objetivo | ¿Cumple? | Reps |
|---|---|---|---|---|---|
| [A/api](../resultados/chaos_A_api_1.md) (notification caída) | fail-open, reservas 100 % | 0,64–0,72 s | 300 s | sí | 3 |
| [A/worker](../resultados/chaos_A_worker_1.md) | backlog 3–4 → 0 | 0,81–1,17 s | 300 s | sí | 3 |
| [B/kill](../resultados/chaos_B_kill_1.md) (1 de 3) | raw 96,43 % vs reintento 100 % | 0,29–2,41 s (mediana 0,33) | 2 s | 1/5 no | 5 |
| [B/kill9](../resultados/chaos_B_kill9_1.md) | reintento 100 % | 0,19–0,26 s | 2 s | sí | 5 |
| [C/kill9](../resultados/chaos_C_kill9_1.md) | 20/20 CONFIRMED, 1 cargo | 6,77–7,73 s | 30 s | sí | 3 |
| [C/stop](../resultados/chaos_C_stop_1.md) | 20/20 CONFIRMED, 1 cargo | 14,85–15,86 s | 30 s | sí | 3 |
| [D](../resultados/chaos_D_stop_1.md) (recreación real) | sin pérdida, app sin reinicio | 2,18 s | 120 s | sí | 1 |
| [E1/stop](../resultados/chaos_E1_stop_1.md) (≥200 acks) | 200/200 durables, 1 cargo | 26,37–29,86 s | 120 s | sí | 3 |
| [E1/pkill9](../resultados/chaos_E1_pkill9_1.md) | 200/200 durables | 20,78–24,21 s | 120 s | sí | 3 |
| [E2/drop](../resultados/chaos_E2_drop_1.md) | 20/20 CONFIRMED, 0 MR | p50 770 ms | estado final | sí | 3 |
| [E3/A](../resultados/chaos_E3_A_1.md) (backup en reposo) | inv 0, RPO 5/5 | 30,46–30,55 s | 900 s | sí | 3 |
| [E3/B](../resultados/chaos_E3_B_1.md) (backup en caliente) | inv 0, RPO 5/5 | 30,80–32,25 s | 900 s | sí | 3 |
| [E4/restart](../resultados/chaos_E4_restart_1.md) | sin reinicios de app | 6,50–6,61 s | 30 s | sí | 3 |
| [S](../resultados/chaos_S_stop_1.md) (TTD postgres) | 503, inv 0 | **93,21 s** (TTR 3,43) | 30 s (TTD) | **no** | 1 |
| [S2](../resultados/chaos_S2_stop_1.md) | 6/6 unhealthy, 503 | 503 a 4,75 s; TTD 60,8–85,3 s; reconexión 5,96 s | 30 s (reconexión) | sí | 1 |

Hallazgos: `docker stop` no emite `health_status` (se usó SIGSTOP); S no cumple
el TTD por `retries=12`; B/kill tiene un outlier de 2,41 s; RPO depende de
backup manual y los dumps por BD no son consistentes entre servicios
([`F4b-resiliencia.md`](../resultados/F4b-resiliencia.md),
[`proceso/backup-restore.md`](../proceso/backup-restore.md),
[`fallos.md`](../fallos.md)).

## 8. Rendimiento

Hipótesis y resultados (detalle en
[`resultados/perf_P1.md`](../resultados/perf_P1.md),
[`perf_P1_analisis.md`](../resultados/perf_P1_analisis.md),
[`perf_P3.md`](../resultados/perf_P3.md), [`perf_P3b.md`](../resultados/perf_P3b.md),
[`perf_P4.md`](../resultados/perf_P4.md)):

- **P1 (lectura, 1 vs 3 réplicas):** rps máximo sostenible **189 → 394
  (2,09×)**, sublineal. CPU total de `availability` **182 → 444 %**,
  PostgreSQL **76 → 181 %** (máx), gateway ≤29 % de un core y k6 ≤70 %: el
  techo es CPU de availability/PG y el codo de latencia, no la infraestructura
  de medición.
- **P3 (escritura vía reservation):** 12/12 con **CONFIRMED exacto** (20 en
  V1, 50 en V2); p95 5–6,5 s por la **saga síncrona**, no por contención; rps
  del burst ruidoso (CV hasta 31 %).
- **[P3b](../resultados/perf_P3b.md) (holds directos):** HELD exacto, 0 deadlocks, 0×503; V1 acumula
  locks (8–12 en N=1; 37–41 en N=3) y V2 casi ninguno (0–2); la hipótesis
  V1>V2 no se confirma y N=3 baja latencia sin cambiar HELD.
- **P4 (límite público):** 141 y 45 respuestas **429**; canario admin sin 429
  (p95 32 → 95 ms), recuperación 10 ms.

Limitaciones: resultados comparativos en una sola máquina; P2/P5 no
ejecutados; el burst de P3 no sirve para escalado.

## 9. Seguridad

Resumen (detalle y tabla de amenazas en [`seguridad.md`](../seguridad.md)):
solo el gateway publica; redes internas; secretos por archivo (`*_FILE`);
contenedores non-root/`read_only`/`cap_drop`/límites; gateway con 429 por
límites (P4) y CSP/headers en el frontend; idempotencia como control de
integridad. Escaneos: **47 HIGH/0 CRITICAL por imagen** (44 base Debian + 3
`starlette`) y **0 leaks** en 64 commits
([`resultados/seguridad-trivy.txt`](../resultados/seguridad-trivy.txt)).
Pendiente: actualizar starlette/base, TLS, auth, WAF/CDN y rotación de
secretos ([`produccion.md`](../produccion.md)).

## 10. Costos

**PENDIENTE (persona).** Requiere tarifas vigentes y supuestos explícitos;
ver [`fases/F5-entrega.md`](../fases/F5-entrega.md) y
[`informe/ESTRUCTURA.md`](ESTRUCTURA.md).

## 11. Manual

Instalación, requisitos, tabla completa de comandos, frontend, lectura de
reportes, solución de problemas y estructura del repo en
[`manual.md`](../manual.md). El ensayo desde cero (comandos, duraciones y
salidas) está en [`resultados/ensayo-desde-cero.md`](../resultados/ensayo-desde-cero.md).

## 12. Evolución a producción

[`produccion.md`](../produccion.md) relaciona cada limitación medida con su
cambio (BD primaria/standby y PITR; backup coordinado y RPO; 202 inmediato y
más procesos de `reservation`; dead-letter y alarma; multinodo; observabilidad;
TLS/auth; WAF/CDN; gestión de secretos). [`swarm.md`](../swarm.md) analiza qué
replicar (availability, APIs stateless, workers con leases/`SKIP LOCKED`) y qué
no (PostgreSQL), y el cambio de `build:` a registro, `deploy`, secretos y
redes overlay; **no se implementó**.

## 13. Limitaciones y trabajo futuro

- PostgreSQL único, sin réplica ni PITR; S TTD 93,21 s > 30 s por `retries=12`.
- Backup por BD no consistente y RPO dependiente de `make backup` manual.
- B/kill con outlier intermitente de 2,41 s (1/5).
- P2 y P5 no ejecutados; P3 con rps ruidoso; resultados de una sola máquina.
- Sin TLS, autenticación, WAF/CDN, métricas/trazas ni alertas por SLO.
- 47 HIGH/0 CRITICAL por imagen; actualizar `starlette`/base y escanear en CI.
- Fuera de alcance: RabbitMQ (ADR-0011), Playwright y despliegue online.

## 14. Conclusión

**PENDIENTE (persona).**

## Anexo A — Trazabilidad

Tabla de los 14 puntos del enunciado con evidencia y ✔ en
[`01-enunciado.md`](../01-enunciado.md#anexo-de-trazabilidad-14-puntos).
