# TASK: Commit F2 safely, review residual risks, and prepare F3

Actúa como Senior Software Engineer y revisor de resiliencia. Trabaja sobre el repositorio `reservas-platform`.

**Objetivo:** consolidar los cambios actuales de F2 mediante commits coherentes, revisar defectos y riesgos técnicos con evidencia, refactorizar solo cuando esté justificado y dejar preparada la implementación del frontend F3. No reconstruyas F2.

## Contexto verificado en el último informe

Rama `main`, HEAD `d867810`. Los cambios de F2 y estabilización siguen sin commit.

Última regresión reportada:
- `make lint`: limpio.
- `make test`: 251 passed.
- `make e2e`: 10 passed en dos ejecuciones consecutivas.
- `make smoke`: 3 ejecuciones correctas.
- `make invariants`: 0 violaciones.
- `actionlint`: exit 0.

El gateway utiliza el puerto público de desarrollo `127.0.0.1:8088`, el administrativo `127.0.0.1:8081` y PostgreSQL `127.0.0.1:5433`. El despliegue mantiene el puerto 8080.

## Fase 1 — Inspección obligatoria

Antes de modificar archivos:
1. Ejecuta `git status --short`, `git diff --stat`, `git diff --check`, `git log --oneline -10` y revisa los archivos nuevos sin seguimiento.
2. Inspecciona los diffs completos por grupos. No confíes únicamente en el informe anterior.
3. Comprueba `.env`, secretos, archivos generados, volúmenes y configuraciones locales. Nunca incluyas credenciales ni datos sensibles en los commits.
4. Confirma qué archivos pertenecen a notification/outbox, E2E, gateway, infraestructura y documentación.
5. Conserva cualquier cambio ajeno a esta tarea.

No uses `git reset --hard`, `git clean -fd`, `git checkout --`, force-push ni otras operaciones destructivas.

## Fase 2 — Revisión técnica dirigida

Inspecciona específicamente estos riesgos:

**Outbox y notificaciones**
- El evento se persiste en la misma transacción que la confirmación de reserva.
- El relay no marca como entregado un evento antes de recibir una aceptación válida.
- Un timeout con resultado incierto no pierde eventos.
- La entrega al menos una vez y el inbox único por `event_id` evitan efectos duplicados.
- Los reintentos tienen límites, backoff y recuperación tras reinicio.

**Gateway**
- Los upstreams se recuperan al recrear contenedores y no conservan IP antiguas indefinidamente.
- Los reintentos automáticos se limitan a operaciones seguras.
- No se reenvían automáticamente POST de reserva o pago tras un resultado incierto.
- Verifica que `PUT` de inventario sea realmente idempotente según su contrato y comportamiento; no lo supongas por el método HTTP.
- `extend_hold` no debe repetirse automáticamente si no existe garantía de idempotencia.
- Las tres réplicas comparten la fuente persistente de inventario.

**Datos y pruebas**
- Los E2E pueden repetirse sin ejecutar antes `make test`.
- La generación aleatoria de fechas no introduce colisiones ni pruebas poco deterministas.
- `make smoke` falla con diagnósticos útiles cuando el gateway o las réplicas no funcionan.
- La limpieza de datos de prueba no borra silenciosamente datos de desarrollo.

Clasifica cada hallazgo como:
- P0: riesgo de pérdida de datos, corrupción o incumplimiento de invariantes.
- P1: defecto reproducible o riesgo serio de resiliencia.
- P2: deuda técnica o mejora opcional.

No refactorices por estilo. Para cada corrección, explica el fallo, aporta una prueba que lo reproduzca y valida la solución. Si no puedes reproducir un supuesto defecto, documéntalo como riesgo por investigar.

## Fase 3 — Crear commits lógicos

Una vez inspeccionados los diffs, prepara commits pequeños y coherentes. Usa los siguientes grupos como guía, adaptándolos a los límites reales de los cambios:

1. `feat(notification): outbox, relay y dedupe`
   Servicio de notificaciones, persistencia, relay, configuración y pruebas directamente relacionadas.

2. `test(e2e): flujos de notificacion y datos unicos`
   Casos E2E y aislamiento de datos que no pertenezcan naturalmente al primer commit.

3. `fix(gateway): DNS dinamico y reintentos seguros`
   Configuración Nginx, puertos, Compose y ajustes de red.

4. `test(infra): smoke y continuidad del gateway`
   `make smoke`, pruebas de infraestructura y soporte de verificación.

5. `docs: resultados F2 y estabilizacion`
   Arquitectura, ADR, variables, resultados y documentación de puertos.

Antes de cada commit:
- Revisa `git diff --cached`.
- Verifica que no incluya archivos ajenos ni secretos.
- Ejecuta las pruebas focalizadas del grupo.
- Usa `git diff --cached --check`.

No uses `git add .` ni `git add -A` indiscriminadamente. Prefiere staging por archivo y por fragmento cuando un archivo contenga cambios de distintos grupos. Si separar un archivo es inseguro o poco práctico, mantén los cambios relacionados juntos y explica por qué.

Después de cada commit, comprueba `git status` y el historial. No crees tags nuevos ni publiques al remoto automáticamente. No cambies commits existentes.

Si encuentras un P0/P1 que invalida la seguridad de los cambios, corrígelo antes del commit afectado y añade una prueba. No detengas toda la consolidación por mejoras P2.

## Fase 4 — Regresión y cierre de F2

Después de los commits:
1. Ejecuta `make lint`, `make test`, `make e2e` dos veces, `make smoke` y `make invariants`.
2. Compara los resultados con la línea base y registra cualquier diferencia.
3. Confirma que todos los cambios previstos estén comprometidos y que no se hayan perdido archivos.
4. Actualiza `docs/resultados/F2.md` solo con resultados efectivamente observados.

Si una prueba falla, diagnostica la causa y corrígela antes de declarar F2 estable. No reduzcas cobertura para conseguir un resultado verde.

## Fase 5 — Preparar F3, sin implementarla todavía

Revisa los contratos reales y prepara una especificación breve para un frontend estático servido por Nginx:

- Una pantalla: buscar hotel y fechas, consultar disponibilidad, elegir habitación, crear reserva y mostrar su estado.
- Llamadas del navegador exclusivamente a través del gateway.
- Cliente nuevo y reserva mediante los endpoints existentes.
- `Idempotency-Key` generado con `crypto.randomUUID()` para la creación de reserva.
- Consulta periódica limitada del estado final, con timeout y manejo visible de errores.
- Sin exponer holds, ledger de pagos, secretos ni endpoints internos.
- Conservar `/healthz` y el comportamiento actual de las rutas desconocidas.
- Ampliar `make smoke` para comprobar que `GET /` devuelve HTML cuando el frontend esté implementado.

No empieces el frontend hasta que los commits y la regresión de F2 estén consolidados.

## Informe final

Entrega:
1. Lista de commits creados y sus hashes.
2. Hallazgos P0/P1/P2 y correcciones aplicadas.
3. Comandos y resultados de pruebas reales.
4. Estado final de Git y cambios pendientes.
5. Riesgos que continúan abiertos.
6. Especificación breve de F3 y siguiente tarea concreta.

No afirmes que todo está corregido si queda alguna prueba fallida o un riesgo sin verificar.