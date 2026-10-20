# TASK: Close F1, integrate safely, and start F2 — reservas-platform

Actúa como **Senior Software Architect + DevOps Engineer**. Trabaja directamente sobre el repositorio existente. El objetivo es cerrar formalmente F1 y avanzar inmediatamente hacia F2, manteniendo el alcance del Caso 2 UCE y la fecha límite del 25 de octubre de 2026.

## 1. Contexto confirmado

- Rama actual: `feat/f1-t1-4-cierre`.
- `main` está atrasada respecto a la rama de trabajo.
- F1 implementa customer, hotel, availability, reservation y payment.
- PostgreSQL único con seis bases de datos lógicas.
- Reservation usa una saga, máquina de estados y transactional outbox.
- Availability implementa holds atómicos con TTL.
- Payment admite `DECLINED`, `FAILED_TECHNICAL` y `UNKNOWN`, con ledger idempotente.
- Existen pruebas de invariantes I1–I7, pruebas de inyección y escenarios E2E.
- Referencia reportada: 231 tests, lint verde y 7 E2E aprobados. **Son resultados previos que debes volver a verificar, no asumir como vigentes.**
- Faltan notification-service, relay del outbox, gateway Nginx, tres réplicas de availability, frontend, automatizaciones de caos/rendimiento y documentación final.

## 2. Reglas obligatorias

1. Inspecciona primero `git status`, ramas, historial, diferencias con `main`, commits pendientes y archivos modificados.
2. Lee `docs/fases/F1-flujo-critico.md`, `docs/resultados/F1.md`, `docs/resultados/T1.3-reservation.md`, ADR 0001–0010, `04-arquitectura.md`, `05-contratos-api.md` y `Makefile`.
3. No ejecutes `clean-all`, `clean` ni comandos destructivos hasta verificar exactamente qué eliminan y si pueden borrar datos, volúmenes o evidencia.
4. No descartes cambios, uses `reset --hard`, reescribas historia ni fuerces pushes.
5. No inventes resultados de pruebas, métricas ni archivos. Registra los resultados reales.
6. No cambies contratos, invariantes o decisiones de F0 sin justificarlo mediante ADR.
7. Mantén cambios pequeños, testeables y compatibles con la arquitectura existente. No reescribas servicios que ya funcionan.
8. No fusiones, etiquetes ni publiques cambios si hay pruebas críticas fallidas o conflictos pendientes. Si no puedes publicar, deja instrucciones precisas.

## 3. Fase A — Cerrar F1

Ejecuta las tareas en este orden:

1. Determina qué commits de `feat/f1-t1-4-cierre` faltan en `main` y verifica que sean los cambios esperados.
2. Comprueba secretos, configuración y estado de los datos antes de levantar o limpiar contenedores.
3. Ejecuta, según los comandos realmente disponibles:
   - `make up-dev`
   - `make seed` dos veces, comprobando idempotencia
   - `make test`
   - `make lint`
   - `make e2e`
   - `make invariants`
   - Las verificaciones de import-linter y costos exigidas por el checklist de F1.
4. Si falla una prueba, encuentra la causa, corrige solo lo necesario y vuelve a ejecutar las verificaciones afectadas. Investiga los fallos intermitentes; no los ocultes ni deshabilites tests para obtener un resultado verde.
5. Revisa las invariantes y el checklist real de salida de F1. Actualiza `docs/fases/F1-flujo-critico.md` y `docs/resultados/F1.md` con evidencia verificable.
6. Si todo pasa, integra la rama en `main` mediante un merge normal y seguro. Verifica nuevamente la suite pertinente después del merge.
7. Crea el tag `f1` únicamente si no existe y la integración está validada. Si ya existe, no lo muevas.
8. Publica `main` y el tag al remoto configurado, si tienes acceso y el estado es seguro. No fuerces el push.

**Gate G0:** F1 se considera cerrada solo si el código está integrado, las pruebas requeridas pasan, el checklist refleja evidencia real y el estado Git queda claro.

## 4. Fase B — Iniciar F2 sin demora

Una vez superado G0, comienza la implementación de F2. No te detengas a generar un plan extenso: consulta los ADR y contratos existentes y trabaja en incrementos verticales.

### B1. Notification service

Implementa `services/notification/` siguiendo una arquitectura hexagonal ligera y las convenciones del repositorio.

Requisitos:
- API documentada con `POST /notifications`, `GET /notifications` y endpoints de health/readiness compatibles con los contratos existentes.
- Persistencia propia en `notification_db`; añade el secreto y la configuración Compose necesarios.
- Inbox idempotente por `event_id`, con restricción única en la base de datos.
- Worker con reintentos limitados, backoff y manejo de eventos duplicados.
- Fallo de notificaciones no debe revertir ni bloquear una reserva confirmada.
- Tests unitarios, integración y contrato.

### B2. Relay del transactional outbox

Implementa el relay desde `reservation` hacia `notification`:
- Lee eventos pendientes del outbox usando concurrencia segura.
- Entrega al menos una vez; el consumidor deduplica mediante `event_id`.
- Marca el evento como entregado únicamente tras una respuesta aceptada.
- Gestiona timeout, reinicio, respuesta incierta y reintentos sin perder eventos ni generar efectos duplicados.
- Mantén la actualización del outbox separada de las transacciones de negocio cuando corresponda.
- Añade pruebas de caída de notification, entrega duplicada y recuperación.

### B3. Gateway y balanceo

Implementa `gateway/nginx` con:
- Único puerto público `8080`.
- Rutas a los servicios según los contratos.
- Balanceo de tres réplicas de `availability`.
- DNS dinámico de Docker mediante `resolver 127.0.0.11`, con parámetros apropiados.
- Timeouts y rate limiting configurables.
- Redes edge/backend/data sin exponer puertos internos innecesarios.
- Pruebas HTTP que verifiquen rutas, disponibilidad del gateway y continuidad cuando una réplica de availability se detiene.

Comprueba que las tres réplicas comparten el inventario persistente de PostgreSQL y no dependen de estado local para garantizar la ausencia de sobreventas.

### B4. Decisión sobre RabbitMQ

No introduzcas RabbitMQ automáticamente. Consulta los criterios de F0 y evalúa la solución HTTP + outbox con resultados medidos. Registra la decisión en un ADR o en la documentación prevista. Prioriza la entrega funcional y reproducible.

### B5. Gate G1

Añade o actualiza pruebas para:
- Caída de notification sin afectar la reserva.
- Recuperación y entrega posterior de eventos pendientes.
- Idempotencia ante entregas repetidas.
- Balanceo con una de tres réplicas caída.
- Healthchecks, readiness, redes y secretos.
- Regresión completa de F1.

Actualiza `docs/resultados/F2.md` con implementación, pruebas, limitaciones y evidencia real.

## 5. Método de ejecución

Trabaja por lotes pequeños:

1. Inspección y cierre de F1.
2. Notification API, persistencia y pruebas.
3. Relay del outbox y pruebas de recuperación.
4. Gateway, réplicas y pruebas de balanceo.
5. Regresión completa y actualización de documentación.

Después de cada lote, ejecuta las pruebas pertinentes y revisa `git diff`. Conserva las convenciones existentes y evita nuevas dependencias si no son necesarias.

No empieces el frontend, k6 ni la documentación extensa de entrega durante esta tarea, salvo que sean necesarios para resolver una dependencia inmediata. Se abordarán en F3–F5.

## 6. Informe final obligatorio

Devuelve un resumen con:

1. Estado inicial y final de Git: ramas, commits, merge, tag y push.
2. Comandos ejecutados y resultados reales.
3. Fallos detectados, correcciones y pruebas pendientes.
4. Archivos creados o modificados.
5. Estado de F1 y de cada componente de F2.
6. Evidencia del comportamiento ante fallos y limitaciones aún abiertas.
7. Próximo comando concreto para continuar.

**Prioridad:** cerrar F1 de forma segura y comenzar F2 inmediatamente. No sacrifiques integridad, pruebas ni evidencia para aparentar progreso.