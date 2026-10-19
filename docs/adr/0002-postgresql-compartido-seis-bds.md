# ADR-0002: PostgreSQL compartido con 6 BDs lógicas y 6 roles
**Estado:** Aceptado · **Fase:** F0

## Contexto
Inventario, reservas y pagos necesitan transacciones ACID, restricciones de integridad (`CHECK`, `UNIQUE`) y bloqueos para controlar concurrencia. Una reserva sobrevendida o un cobro duplicado son errores de negocio, no de rendimiento.

## Decisión
- Un contenedor PostgreSQL 16, seis bases (`customer_db`, `hotel_db`, `availability_db`, `reservation_db`, `payment_db`, `notification_db`) y **un rol por base** sin privilegios sobre las demás. Volumen nombrado `pgdata`, checksums de datos activados en `initdb`.
- `fsync`, `synchronous_commit` y `full_page_writes` **no se relajan**. Se fijan `statement_timeout`, `lock_timeout` e `idle_in_transaction_session_timeout`.
- Backup con `pg_dump` por BD + prueba de restauración (`make backup` / `make restore`). PITR y réplicas se documentan como evolución.
- Redis no se incluye.

## Alternativas descartadas
| Alternativa | Por qué no |
|---|---|
| Un PostgreSQL por servicio | Mejor aislamiento de recursos, pero 6 contenedores más, más memoria y más superficie de fallo en un solo host. Se documenta como evolución |
| Un esquema compartido | Rompe la propiedad exclusiva de datos |
| Redis como fuente de verdad | No ofrece las garantías transaccionales requeridas |
| MongoDB | Sin ventaja para datos relacionales con invariantes fuertes |

## Consecuencias
(+) Integridad garantizada por la BD, no solo por el código. (−) **Punto único de fallo y de contención compartido**: si PostgreSQL cae, caen todos los servicios con estado. No hay aislamiento de recursos entre servicios. Se mitiga con pools acotados, timeouts y backups, y se **demuestra** en las pruebas E1 y E3. (−) `docker kill` no simula un corte eléctrico real ni un fallo de disco.
