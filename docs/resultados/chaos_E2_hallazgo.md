# Hallazgo E2 — reservas con resultado de pago desconocido

Fecha: 2026-10-22 · Escenario: E2 (`process_then_drop_response`) · Informe base:
`chaos_E2_drop_1.md` (y repeticiones 2–3).

## Retractación de la atribución anterior

En el informe previo se atribuyó el fallo de E2 al `pip install` del Dockerfile.
**Eso es incorrecto**: el `pip install` ocurre en tiempo de *build*, no puede
explicar un comportamiento de concurrencia en tiempo de ejecución. Queda retirado.

## Qué se observó (evidencia ejecutada)

1. **Estado final de las reservas.** Tras crear 20 reservas con
   `process_then_drop_response` y sondear hasta 90 s:
   - `creadas=20/20`, `estados finales={20 × CONFIRMED}`, `MANUAL_REVIEW=0`,
     `un_cargo_por_reserva=true`, `no_perdida_datos=true`.
   - **Ninguna reserva quedó en `PAYMENT_UNKNOWN`** más allá del ciclo de
     recuperación. Consulta directa a `reservation_db`:
     `E2 reservations by status: [('CONFIRMED', 9), ('REJECTED_NO_INVENTORY', 1)]`
     (la `REJECTED_NO_INVENTORY` era por reutilizar noches ya agotadas en
     ejecuciones previas, no por el pago; corregido en el arnés usando noches
     únicas por ejecución).
   - Por tanto **no es el caso (b)** (defecto de reconciliación).

2. **Experimento controlado de concurrencia** (20 POST simultáneos con
   `process_then_drop_response`, noches nuevas, inventario repuesto):
   ```
   status codes: {201: 10, 503: 10}
   latency ms: p50=11 p95=1063 max=1076
   created ids: 10
   final reservation states: {'CONFIRMED': 10}
   ```
   Es decir: 10 solicitudes aceptadas (201) y **10 rechazadas con 503 de nginx**;
   las 10 aceptadas terminaron `CONFIRMED`. **No hubo `202`** (la API es síncrona:
   espera hasta `SAGA_SYNC_WAIT_SECONDS=5` y responde 201 ya confirmada).

3. **Causa de los 503.** El gateway limita las conexiones concurrentes por IP:
   `gateway/conf.d/default.conf:39` → `limit_conn conn 10;` (y
   `limit_req zone=api burst=20 nodelay`). Con 20 conexiones simultáneas desde
   127.0.0.1, nginx admite 10 y rechaza el resto con **503** (status por defecto
   de `limit_conn`). El reparto 10/10 coincide exactamente con el límite.

4. **Sin errores de pool ni de reconciliación.** Los logs de `reservation` no
   muestran `QueuePool`/timeouts; los de `reservation-worker` solo muestran
   `base de datos no disponible` durante las ventanas de caída de PostgreSQL
   (escenarios D/S), no durante E2.

## Defectos del arnés detectados (caso (a))

- `run_scenario_E2` usaba `snapshot_before` sin definirlo → `NameError`,
  `no_perdida_datos=false` y `hard_fail=true` espurios.
- Reutilizaba las noches `hoy+5..24` en cada ejecución → inventario agotado y
  reservas `REJECTED_NO_INVENTORY` que nunca llegan a `CONFIRMED`.
- Medía el estado final sin una cota clara.

Corregido: `snapshot_before` y `restart_before` definidos; noches únicas por
ejecución (`hoy+1000..`); sondeo hasta 90 s con distribución del tiempo a estado
final; concurrencia acotada a 10 para no medir el `limit_conn` del gateway.

## Clasificación

**Caso (c): límite de capacidad del gateway**, agravado por un **defecto del
test (a)**. No es (b): no hay reservas atascadas en `PAYMENT_UNKNOWN`.

La API de reservas es **síncrona** (bloquea el hilo hasta 5 s). Con 20 clientes
simultáneos, el `limit_conn 10` del gateway rechaza la mitad con 503 antes de
llegar al servicio. Capacidad observada del camino de escritura vía gateway:
**≈ 10 conexiones concurrentes por IP** (`limit_conn conn 10`).

## Recomendaciones

1. **Arnés (hecho):** E2 usa 10 hilos como máximo y noches únicas; así mide el
   flujo de pago, no el limitador.
2. **Producto:** para cargas P2/P3 de F4b, o se sube `limit_conn`/`burst` en el
   gateway o se mide el servicio por la red interna; documentar el límite.
3. **Diseño:** reducir `SAGA_SYNC_WAIT_SECONDS` o responder `202` de inmediato y
   dejar que el worker resuelva, para no ocupar un hilo hasta 5 s por reserva.
   Es la palanca que más mejora la concurrencia sin cambiar la corrección.
