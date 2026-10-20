# TASK: Stabilize F2 and prepare F3 — reservas-platform

Actúa como Senior Engineer. El informe anterior indica que F2 ya funciona: `make lint` limpio, 250 tests aprobados, 10 E2E aprobados, 0 violaciones de invariantes, gateway activo y tres réplicas de availability. No reconstruyas funcionalidades existentes sin comprobar primero el repositorio.

## Reglas
- Inspecciona `git status`, ramas, diff, historial y archivos modificados antes de actuar.
- No sobrescribas ni descartes cambios sin commit. No hagas reset destructivo, force-push ni commits automáticos.
- Trata las métricas del informe como resultados anteriores que deben verificarse.
- Cambios pequeños, pruebas focalizadas y checkpoints claros.
- No alteres contratos ni configuración del gateway sin evidencia reproducible.

## Incremento 1 — Auditoría y línea base
1. Identifica los cambios reales de F2 y comprueba que coincidan con el informe.
2. Ejecuta `make lint`, `make test`, `make e2e` y `make invariants` según los comandos existentes.
3. Registra resultados, duración y cualquier fallo. No ocultes tests ni ajustes expectativas solo para obtener verde.
4. No comiences F3 si la regresión básica falla.

## Incremento 2 — Repetibilidad E2E
1. Investiga qué estado persiste entre ejecuciones y qué pruebas dependen de fechas, IDs, semillas o workers.
2. Aísla los datos de cada ejecución mediante identificadores únicos y fechas dinámicas cuando corresponda.
3. Asegura que los tests no dependan de ejecutar `make test` previamente.
4. Añade `make e2e-reset` explícito si es necesario. Nunca borres volúmenes o datos de desarrollo silenciosamente.
5. Ejecuta `make e2e` dos veces consecutivas desde el mismo estado de entorno y demuestra que ambas ejecuciones pasan.
6. Conserva los resultados como evidencia.

## Incremento 3 — Smoke test del gateway
Implementa `make smoke` reutilizando herramientas y convenciones existentes. Debe verificar:
- Health del gateway en el puerto configurado, sin asumir que 8080 está libre en desarrollo.
- Una ruta pública de cada tipo relevante.
- Endpoint administrativo publicado en loopback.
- Estado de las tres réplicas de availability.
- Continuidad básica después de detener una réplica, si puede probarse sin afectar datos importantes.

Ante un fallo, mostrar la URL, el código HTTP esperado/recibido y el diagnóstico disponible. No codifiques los puertos de desarrollo como constantes duplicadas.

## Incremento 4 — Red y CI
- Documenta en un único lugar los puertos host → contenedor y la regla de acceso por gateway.
- Revisa `proxy_next_upstream`: solo permitir reintentos automáticos donde sean seguros; no repetir POST de reserva o pago sin idempotencia demostrada.
- Comprueba si `actionlint` está disponible y úsalo si puede ejecutarse. Distingue los errores reales del workflow de problemas locales de red o caché.
- No fijes versiones de GitHub Actions solo para silenciar mensajes sin confirmar la causa.

## Incremento 5 — Checkpoint y F3
1. Reejecuta las pruebas afectadas y las regresiones pertinentes.
2. Actualiza la documentación con resultados reales.
3. Resume los cambios agrupados en commits lógicos sugeridos; no hagas commit sin autorización.
4. Si F2 y la repetibilidad están verificadas, presenta un plan mínimo para F3: una pantalla que permita buscar disponibilidad, crear una reserva y consultar el resultado, consumiendo únicamente el gateway.
5. Prioriza un frontend demostrable en el tiempo disponible; no añadas funciones no requeridas.

## Informe final
Incluye estado Git, comandos y resultados, fallos reproducibles, archivos modificados, riesgos pendientes y el siguiente comando concreto. Detente al completar estos incrementos; no inicies otras fases automáticamente.