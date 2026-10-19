# AGENTS.md: instrucciones para el agente (OpenCode)

## Contexto
Plataforma de reservas con microservicios (Caso 2, UCE). Lee `docs/01-enunciado.md`, `docs/02-plan.md`, `docs/fases/F0-negocio-y-resiliencia.md`, **`docs/04-arquitectura.md`**, **`docs/05-contratos-api.md`** y los ADR en `docs/adr/` antes de actuar. Prioridad: **funcional, reproducible y verificable**, no estética.

## Stack (no cambiar sin aprobación)
Python 3.12 + FastAPI, SQLAlchemy/psycopg, PostgreSQL 16, Docker Compose, nginx, pytest + httpx, k6. RabbitMQ solo si se indica explícitamente.

## Reglas de trabajo
1. **Test primero**: escribe el test (o el criterio de aceptación ejecutable) antes de implementar.
2. **Una tarea a la vez**, cambios pequeños; no modifiques archivos fuera del alcance de la tarea.
3. Cada servicio es dueño exclusivo de su BD (`<servicio>_db`, rol propio). Prohibido leer BDs de otros servicios.
4. Nada de configuración o secretos en código/imágenes: variables de entorno o `*_FILE`. Mantén `.env.example` actualizado y documenta cada variable en `docs/variables.md`.
5. Todo servicio expone `GET /health` (liveness) y `GET /ready` (BD + dependencias críticas), logs JSON y propaga `X-Request-ID`.
6. Llamadas HTTP salientes: timeout explícito; reintentos máx. 3 con backoff+jitter, solo en operaciones idempotentes.
7. Escrituras críticas (reserva, pago) requieren `Idempotency-Key`.
8. Dockerfiles: multistage, usuario no-root, sin archivos innecesarios, versiones fijadas, `HEALTHCHECK`.
9. Solo el gateway publica puerto. `backend-net` y `data-net` son `internal: true`.
10. Si algo del plan es ambiguo o inviable, **pregunta o propón alternativa**; no inventes silenciosamente.
11. No marques una tarea como terminada sin ejecutar los tests y mostrar el resultado.

## Reglas de integridad (de F0; no negociables)
- Respeta los invariantes I1-I7. Toda prueba de integración/caos termina ejecutando el chequeador de invariantes.
- **Persistir el estado antes de cada llamada externa.** Transiciones de reserva solo según la máquina de estados de F0 §1.2; registrar cada una en `reservation_events`.
- **Availability escritura = fail-closed:** si no se puede verificar inventario, rechazar (503). Nunca asumir disponibilidad. Inventario con `UPDATE … WHERE held+confirmed < total` atómico y `CHECK` en BD.
- **Pago:** distinguir `DECLINED` / `FAILED_TECHNICAL` / `UNKNOWN`. Ante `UNKNOWN`, consultar estado antes de reintentar; nunca crear un segundo cobro con otra clave.
- **Notification = fail-open:** nunca bloquea ni cancela una reserva confirmada. Outbox transaccional, entrega al menos una vez, dedupe por `event_id`.
- No añadir Redis, RabbitMQ ni réplicas de PostgreSQL sin pasar las compuertas de F0 §7.
- No relajar `fsync`/`synchronous_commit`. Pruebas de integridad con `docker kill`, no solo `docker stop`.

## Arquitectura (obligatoria; ver docs/04-arquitectura.md y ADR-0001)
- Servicios con lógica (availability, reservation, payment, notification): capas `api` · `application` · `domain` · `infrastructure`. customer/hotel: CRUD modular, sin puertos.
- Dependencias: `api`/`infrastructure` → `application` → `domain`. `domain` es Python puro (sin FastAPI, SQLAlchemy, httpx, pydantic). **`import-linter` debe pasar** (plantilla en `services/_template/importlinter.example`).
- Puertos (`Protocol`) **solo** donde hay frontera real (ver tabla §6 de arquitectura). Prohibido: repositorios genéricos, Unit of Work, interfaces "por si acaso".
- Sin modelos compartidos entre servicios; cada cliente HTTP define sus DTO. Cumple exactamente `docs/05-contratos-api.md`; si necesitas cambiar un contrato, **propón el cambio y actualiza el doc/ADR** antes.
- Saga/estados: una sola función `advance(reservation_id)` para el camino normal y la recuperación (ADR-0003).
- No añadas dependencias fuera de ADR-0009 sin justificarlas por escrito en el PR.
- Documenta mientras construyes: PR con checklist de `.github/pull_request_template.md`; actualiza `docs/variables.md` y `docs/costos/registro.md` cuando corresponda.

## Comandos esperados (Makefile)
`make up` · `make test` · `make chaos` · `make perf` · `make report` · `make down` · `make clean`

## Estructura
```
services/{customer,hotel,availability,reservation,payment,notification}/
gateway/  tests/{e2e,chaos,perf}/  docs/  docs/resultados/
compose.yaml  .env.example  Makefile
```

## Definition of Done por tarea
- Tests relevantes pasan localmente (`make test` o el subconjunto indicado).
- `docker compose up` sigue levantando todo en estado `healthy`.
- Docs/variables actualizadas si cambió algo de configuración o API.
- Descripción breve de qué cambió y cómo verificarlo.
