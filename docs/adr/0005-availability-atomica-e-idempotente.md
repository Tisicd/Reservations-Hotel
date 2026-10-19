# ADR-0005: Inventario con operaciones atómicas e idempotentes
**Estado:** Propuesto · **Fase:** F1

## Contexto
El riesgo principal es la **sobreventa** por concurrencia. Además la lectura (búsqueda) y la escritura (bloqueo de cupo) tienen necesidades opuestas.

## Decisión
- Modelo: `inventory(room_id, hotel_id, night, total, held, confirmed)` con `CHECK (held + confirmed <= total)`; `holds(hold_id = reservation_id, room_id, check_in, check_out, units, status, expires_at)`.
- *Room* = categoría de habitación con `total` unidades (permite probar K cupos con N solicitudes).
- **Crear hold:** una transacción con `UPDATE inventory SET held = held + :u WHERE room_id=:r AND night BETWEEN … AND held + confirmed + :u <= total`; si las filas afectadas ≠ noches pedidas → `ROLLBACK` y `409 NO_INVENTORY`. Noches procesadas en orden fijo (evita interbloqueos). El `CHECK` es la última defensa.
- **Idempotencia:** `hold_id` único; repetir con los mismos parámetros devuelve el hold existente; con parámetros distintos, `409 HOLD_CONFLICT`.
- `confirm` y `release` son idempotentes. Un job libera holds vencidos.
- **Fail-closed:** si no se puede verificar el inventario, `503`. Nunca se asume disponibilidad.
- **Lectura** (búsqueda) separada en casos de uso y endpoints distintos; es lo que escala con réplicas. La escritura se serializa por bloqueo de fila en PostgreSQL.

## Alternativas descartadas
Lock distribuido/Redis (segunda fuente de verdad), `SERIALIZABLE` en todo (reintentos complejos sin ganancia sobre el `UPDATE` con guarda), contador en memoria (se pierde al reiniciar).

## Consecuencias
(+) La invariante I1 la garantiza la BD. (−) Un cupo muy disputado (misma habitación y noches) se serializa: se medirá en F4. Réplicas de `availability` no aceleran la escritura.
