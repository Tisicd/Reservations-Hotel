# ADR-0010: Fuente de verdad de datos maestros y validación de hotel/habitación
**Estado:** Aceptado · **Fase:** F0

## Contexto
Una reserva necesita validar cliente y habitación antes de crear el hold. F0 dejó abierto si `reservation` consulta `hotel` por HTTP o si `availability` mantiene datos maestros replicados. Duplicar hoteles/habitaciones crearía una segunda fuente de verdad y sincronización sin una necesidad medida en el MVP.

## Decisión
- `hotel` es la fuente de verdad de hoteles, habitaciones, capacidad y precios.
- `reservation` valida hotel y habitación por HTTP contra `hotel` antes de persistir `RECEIVED`, con timeout y manejo explícito de errores (`404`/`503`).
- `availability` gestiona exclusivamente inventario, disponibilidad y holds; no almacena ni consulta datos maestros.
- `customer` sigue el mismo principio: `reservation` lo valida por HTTP.

## Alternativas descartadas
| Alternativa | Por qué no |
|---|---|
| `availability` replica hoteles/habitaciones | Segunda fuente de verdad y sincronización sin necesidad medida |
| `reservation` lee la BD de `hotel` | Prohibido: cada servicio es dueño exclusivo de su BD |
| Validación diferida/asíncrona | La saga necesita precio y capacidad antes del hold; añade complejidad sin beneficio |

## Consecuencias
(+) Contratos claros y sin duplicación de datos maestros. (+) `availability` queda enfocado en su invariante de inventario. (−) `reservation` añade una dependencia síncrona con `hotel`; se mitiga con timeout, `503` controlado y fail-closed para reservas nuevas.

**Evolución:** si la carga demuestra que la consulta a `hotel` limita el rendimiento o la disponibilidad, se evaluará replicar datos de lectura mediante eventos, con control de antigüedad, reconciliación y un ADR que reemplace esta decisión.
