# Manual de demo del frontend (F3, borrador)

Pantalla única: `http://127.0.0.1:8088/` (perfil dev). Sin build ni
dependencias; HTML/CSS/JS servidos por nginx.

## Preparación

```
make build && make up && make seed
make smoke
```

## 10 pasos

1. Abrir `http://127.0.0.1:8088/` y comprobar la pantalla.
2. Elegir `Hotel Quito Centro`, entrada mañana y salida pasado mañana;
   pulsar **Buscar disponibilidad**.
3. Ver habitaciones con precio y **cupo disponible** (la lista sale de
   `/api/availability`).
4. Elegir `Cliente Demo Uno` o crear uno con nombre/email (se crea con
   `POST /api/customers`).
5. Con simulación `ok`, pulsar **Reservar**; ver el estado y la **línea de
   tiempo** (estado, motivo, hora, +s) y el estado de la notificación.
6. Pulsar **Reenviar con la misma clave**: debe responder `200` con
   `Idempotent-Replayed: true` y la **misma** reserva (sin duplicar).
7. Con la reserva `CONFIRMED`, pulsar **Cancelar** y ver la transición a
   `CANCELLING`/`CANCELLED` (el inventario se libera).
8. Repetir con simulación `decline`: la reserva termina
   `PAYMENT_DECLINED`/`CANCELLED` y no se cobra.
9. Repetir con `process_then_drop_response`: la línea de tiempo pasa por
   `PAYMENT_UNKNOWN` y termina `CONFIRMED`; la notificación debe llegar
   (`SENT`).
10. Forzar `429` (repeticiones rápidas de búsqueda/reserva) y `503`
    (`docker stop availability` o `reservation`): la UI muestra el mensaje
    con `request_id`, espera acotada y reintenta **con la misma clave**;
    al levantar el servicio, el flujo continúa. Al final:
    `make invariants` ⇒ 0.

## Tres flujos de demo

| Flujo | Simulación | Final esperado |
|---|---|---|
| Feliz | `ok` | `CONFIRMED`, notificación `SENT` |
| Pago rechazado | `decline` | `PAYMENT_DECLINED` → `CANCELLED`, sin cobro |
| Respuesta perdida | `process_then_drop_response` | `PAYMENT_UNKNOWN` → `CONFIRMED`, 1 cobro |

## 5 capturas para `docs/resultados/ui/`

1. Búsqueda con habitaciones, precio y cupo.
2. Línea de tiempo de una reserva `CONFIRMED` + notificación `SENT`.
3. Reenvío con la misma clave: `HTTP 200` + `Idempotent-Replayed: true`.
4. Flujo `process_then_drop_response` con `PAYMENT_UNKNOWN` y luego
   `CONFIRMED`.
5. Error `429`/`503` visible con `request_id` y reintento acotado.

## Límites y seguridad

- Polling ≥ 1 s con backoff, máximo dos solicitudes simultáneas, tope de
  90 s; se detiene en estado estable.
- El listener público aplica `limit_req 50r/s burst 40` y `limit_conn` por
  IP; la UI está por debajo. Los `429` no se confunden con `503`.
- Solo se usan rutas `/api/*` públicas; holds, pagos, inventario y `/svc/*`
  no están expuestos (403/404).
- CSP `default-src 'self'`, sin `innerHTML` con datos de la API, JS/CSS
  externos y estáticos montados en solo lectura.
