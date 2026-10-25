# 03. Estado del proyecto y mapa de lectura

> **Punto de entrada para agentes.** Léelo primero y luego **solo** los documentos de tu tarea (tabla §5). No cargues todo el repositorio: ahorra contexto.
> Actualiza este archivo al cerrar cada fase (máx. 80 líneas).

## 1. Estado (2026-10-20)
| Fase | Estado | Detalle |
|---|---|---|
| F0 Negocio y resiliencia | ✔ G0 cerrado | `fases/F0-negocio-y-resiliencia.md` |
| F1 Flujo crítico | ✔ | availability, payment, reservation, customer, hotel, chequeador de invariantes, e2e. Tag `f1` |
| F2 Integración | ✔ consolidada | notification + outbox/relay, gateway, availability x3. G1 formal: ver `fases/F2-integracion.md` |
| F3/F3b Frontend | **Implementado** (2026-10-23) | SPA hash con inicio/resultados/ficha/pago/estado/mis reservas y modo demo: `gateway/html/`, `make smoke`, `make check-ui`, `test_public_flow.py`; guion en `manual.md` |
| F3c Autenticación | **Implementado** (2026-10-24) | Cuentas = clientes, scrypt, sesiones opacas, `auth_request`, login/registro UI; reservar/cancelar exigen Bearer: ADR-0012, `seguridad.md` |
| F4 Fallos, carga y reportes | **Cerrado** (F4a/b/c) | Caos A–S2 y carga P1/P3/P3b/P4: `resultados/REPORTE.md`, `fallos.md`; P2/P5 recortados |
| F5 Entrega (informe, manual, costos) | **Documentación y ensayo** (2026-10-23); pendientes persona 1/3/10/14 | `manual.md`, `seguridad.md`, `produccion.md`, `swarm.md`, `informe/INFORME.md`, `resultados/ensayo-desde-cero.md` |
| F6 Defensa (28–30 oct, por confirmar) | Pendiente | `fases/F6-defensa.md` |

**Calendario:** se va ~1 día por delante del plan. Propuesta: F3 mar 20–mié 21 · F4 mié 21–vie 23 · F5 vie 23–sáb 24 · **entrega dom 25** · F6 26–29. El colchón sobrante se usa en calidad (F4), no en alcance nuevo.

## 2. Hechos que no cambian
- 6 servicios + workers (`reservation-worker`, `reservation-relay`, `payment-worker`, `availability-worker`, `notification-worker`); PostgreSQL 16 con 6 BDs y 6 roles; nginx como única entrada (puerto dev según `.env`, hoy `127.0.0.1:8088`).
- Hexagonal ligera en availability, reservation, payment, notification; CRUD modular en customer/hotel (`04-arquitectura.md`, ADR-0001).
- Saga con `advance(reservation_id)`; estado persistido antes de cada llamada; clave de pago = `reservation_id` (ADR-0003).
- Fail-closed en escritura de inventario; fail-open en notificaciones (outbox → relay → inbox idempotente).
- Comandos: `make up|up-prod|down|clean|clean-all|seed|test|e2e|smoke|invariants|lint|build|images|prune`; F4a añade `make chaos [SCEN=A|B|C|D|E2|S] [REPEAT=n]` (no forma parte de `make test` ni del CI por defecto).

## 3. Invariantes (el contrato de pruebas)
I1 sin sobreventa · I2 una reserva por intención y cadena de estados legal · I3 un cobro por reserva · I4 CONFIRMED ⇔ pago y hold confirmados · I5 todo estado no estable avanza o expira · I6 CONFIRMED ⇒ exactamente un evento (entregado o pendiente) · I7 lo comprometido sobrevive a reinicios. Chequeador: `make invariants`.

## 4. Decisiones vigentes y riesgos abiertos
- **RabbitMQ: no se implementa** (G1 propuesto): el outbox funciona y no hay problema medido que lo justifique; se documenta como evolución.
- Réplica de PostgreSQL, Redis, Kubernetes: no. Documentados en `produccion.md` (F5).
- Dos modos de caída para pruebas: **A** `docker kill` (sin reinicio automático; RTO con operador) y **B** `kill -9` interno (reinicio por política; RTO autónomo). `proceso/modos-de-caida.md`.
- Abiertos: outbox sin *dead-letter* (se añade alarma en F4); sin TLS ni health check activo en nginx OSS; Playwright opcional (ver F3).

## 5. Mapa de lectura (qué leer por tipo de tarea)
| Tarea | Lee |
|---|---|
| Frontend | `fases/F3-frontend.md`, `05-contratos-api.md` §6 y §2 |
| Pruebas de fallos / carga | `fases/F4-*.md`, `fases/F0-*.md` §2.3 y §4, `proceso/modos-de-caida.md` |
| Documentación / informe | `fases/F5-entrega.md`, `informe/ESTRUCTURA.md`, `01-enunciado.md` (trazabilidad) |
| Cambiar un servicio | `04-arquitectura.md` §4–§7, su ADR, su sección en `05-contratos-api.md` |
| Docker / imágenes | `prompts/T-docker-imagenes.md`, `imagenes.md`, `variables.md` |
| Decisiones | `adr/README.md` |
