# Análisis de evolución a Docker Swarm (punto 10)

> **No implementado**: este documento analiza la migración; el fragmento final
> es ilustrativo y **no se ejecutó**. La solución entregada es Docker Compose.

## Qué se replicaría y por qué

| Componente | ¿Réplicas? | Motivo / cuidado |
|---|---|---|
| `availability` (API) | **Sí** (ya x3) | Stateless; P1 midió 189 → 394 rps (2,09×) con 1 vs 3 réplicas; el techo está en CPU de availability/PostgreSQL (`resultados/perf_P1.md`, `perf_P1_analisis.md`) |
| `reservation` (API) | Sí | Stateless; evita la cola de la saga síncrona; P3 mostró p95 5–6,5 s por la espera, no por locks (`perf_P3.md`) |
| `payment` (API) | Sí | Stateless delante de PostgreSQL; idempotencia por `reservation_id` (ADR-0006) |
| `notification` (API) | Sí | Solo lectura pública; el worker es el que entrega (ver abajo) |
| `customer` / `hotel` | Sí | CRUD stateless; lecturas mayoritarias |
| `gateway` (nginx) | Sí, tras un LB externo | En Swarm el *routing mesh* puede publicar el puerto; nginx ya balancea `availability` por DNS (`resolver 127.0.0.11`); en Swarm el DNS es otro y habría que revisar `resolve` o usar `tasks.<servicio>` |
| `availability-worker` (expiración) | Sí, con cuidado | Usa `with_for_update(skip_locked=True)` para reclamar holds; varias réplicas son seguras (código `services/availability/.../store.py`) |
| `reservation-worker` / `relay` | Sí, con *leases* | Reclaman con `locked_until` y `SKIP LOCKED` (`repository.py`); conviene revisar el tamaño de lote y el heartbeat |
| `payment-worker` | Sí, con *leases*/`SKIP LOCKED` | Reconciliación idempotente por `reservation_id`; `RECONCILE_*` |
| `notification-worker` | Sí, con *leases* | `claim_due` con `NOTIFICATION_LEASE_SECONDS` y `SKIP LOCKED`; entrega al menos una vez y dedupe por `event_id` (ADR-0004) |
| `postgres` | **No** en Swarm básico | Estado único y escritor único; replicar requiere primario/standby, PITR y *failover* (fuera de alcance). En Swarm se mantiene como servicio con volumen y *placement* fijo |
| Migraciones (`*-migrate`) | No como réplica | Deben ejecutarse **una vez** por despliegue (job/`deploy.restart_policy: none`), no como servicio escalado |

## Qué cambia al pasar de Compose a Swarm

1. **Imágenes**: no se permite `build:` en el *stack*; se construyen y publican
   en un registro (p. ej. `registry.local/reservas/availability:1.0`) y el
   *stack* referencia `image:` con tag/digest.
2. **`deploy`**: `replicas`, `update_config` (rolling), `restart_policy`,
   `resources` (límites/reservas), `placement` (p. ej. PG en un nodo con
   volumen), `labels`.
3. **Secretos**: `docker secret` en lugar de archivos montados; los servicios
   ya leen `*_FILE`, así que el cambio es de origen del archivo.
4. **Redes**: `overlay` para `backend-net`/`data-net` (con `attachable` si hace
   falta depurar); `edge-net` para el gateway. En Swarm, `internal: true` sigue
   siendo válido.
5. **`depends_on` no existe**: la resiliencia ya depende de reintentos,
   `/ready` y healthchecks; el arranque debe tolerar que PostgreSQL aún no esté.
6. **Publicación de puertos**: `ports` con *ingress* o `mode: host`; el
   listener admin `8081` **no** se publica en producción.
7. **Balanceo**: el *routing mesh* reparte entre tareas; para `availability`,
   revisar el `resolve` de nginx o poner un LB delante. El DNS de Swarm
   (`tasks.<servicio>`) no es el de Compose (`127.0.0.11`).
8. **Migraciones**: job separado con `restart_policy: {condition: none}` y
   dependencia explícita en el proceso de despliegue, no en el *stack*.

## Fragmento ilustrativo (**no ejecutado**)

```yaml
version: "3.9"
services:
  availability:
    image: registry.example/reservas/availability:1.0
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        order: start-first
      restart_policy:
        condition: on-failure
      resources:
        limits: {cpus: "1.0", memory: 256M}
    networks: [backend-net, data-net]
    secrets: [availability_db_password]
  postgres:
    image: postgres:16
    deploy:
      replicas: 1
      placement:
        constraints: [node.labels.data == "true"]
    volumes: [pgdata:/var/lib/postgresql/data]
    networks: [data-net]
    secrets: [postgres_password]
networks:
  backend-net:
    driver: overlay
    internal: true
  data-net:
    driver: overlay
    internal: true
volumes:
  pgdata:
```

## Conclusión

Swarm es una evolución razonable para **escalar los servicios stateless y los
workers** (que ya usan *leases* y `SKIP LOCKED`), pero **no resuelve** la BD
única, el backup coordinado, TLS/auth, WAF/CDN ni la observabilidad: esas son
decisiones de `produccion.md`. No se implementó para no introducir una
plataforma nueva sin pruebas de equivalencia; el Compose actual es reproducible
y medido.
