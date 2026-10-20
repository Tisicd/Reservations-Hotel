# 04. Arquitectura (v1.0, G0 cerrado el 2026-10-19)

Decisiones en `docs/adr/`. Negocio, invariantes y modos de fallo en `docs/fases/F0-negocio-y-resiliencia.md`.

## 1. Topología
```
                      Internet / navegador
                              │
              ┌───────────────┴────────────────┐
              │ gateway (nginx)                │  :8080 público  ·  127.0.0.1:8081 admin/dev
              │ frontend estático · rate limit │
              └───────────────┬────────────────┘
                 edge-net     │
  ────────────────────────────┼─────────────────────────────  backend-net (internal)
   customer   hotel   availability x3   reservation   payment   notification
                                        reservation-worker      notification-worker
  ────────────────────────────┼─────────────────────────────  data-net (internal)
                       postgres (6 BDs, 6 roles, volumen pgdata)
```
Solo el gateway publica puertos. Los workers usan la misma imagen que su API con otro comando.

### 1.1 Matriz de puertos (host -> contenedor)

| Origen | Destino | Host | Contenedor | Exposición |
|---|---|---|---|---|
| navegador/tests | gateway público | `8080` (despliegue) o `127.0.0.1:8088` (dev, `GATEWAY_DEV_PORT`) | `8080` | público |
| operador local | gateway administrativo | `127.0.0.1:8081` | `8081` | solo loopback |
| host dev | PostgreSQL | `127.0.0.1:5433` (`POSTGRES_DEV_PORT`) | `5432` | solo loopback |
| contenedores | customer, hotel, availability x3, reservation, payment, notification | no publicado | `8000` | `backend-net` |
| workers | -- | no publicado | -- | `backend-net` / `data-net` |

Regla: el frontend y los clientes externos usan **solo** el gateway; semillas,
pruebas y caos pueden usar el listener administrativo en loopback. Ningún
servicio de aplicación publica puertos. Tras recrear contenedores,
`make gateway-refresh` (usado por `test`, `e2e` y `smoke`) reinicia nginx para
no conservar IPs viejas; el `resolver` tiene TTL de 2 s.

## 2. Estilo
Microservicios + **hexagonal ligera** donde hay lógica de negocio (ADR-0001). Dos formas de servicio:

| Forma | Servicios | Motivo |
|---|---|---|
| Hexagonal ligera (`api`/`application`/`domain`/`infrastructure`) | availability, reservation, payment, notification | Reglas, estados e invariantes que deben probarse sin BD ni HTTP |
| CRUD modular (`api`/`service`/`models`) | customer, hotel | Sin lógica de dominio que proteger; las capas serían ceremonia |

**Fuente de verdad de datos maestros (G0, ADR-0010):** `hotel` es dueño de hoteles, habitaciones y precios; `reservation` los valida por HTTP (con timeout y error explícito) antes de persistir. `availability` solo gestiona inventario, disponibilidad y holds; no replica ni consulta datos maestros. Si la carga demuestra que esa llamada limita el rendimiento, se evaluará replicar datos de lectura de `hotel` mediante eventos, con control de antigüedad y reconciliación.

## 3. Estructura del repositorio
```
reservas-platform/
├── AGENTS.md  README.md  Makefile  compose.yaml  .env.example
├── docs/            (01-enunciado, 02-plan, 04-arquitectura, 05-contratos-api, adr/, fases/, informe/, costos/, proceso/, resultados/)
├── gateway/         nginx.conf, conf.d/, (frontend se copia aquí en la imagen)
├── frontend/        index.html, app.js, styles.css
├── services/
│   ├── _template/   importlinter.example
│   ├── availability/ reservation/ payment/ notification/   (hexagonal)
│   └── customer/ hotel/                                    (CRUD modular)
├── tests/           e2e/ chaos/ perf/ invariants/
└── .github/         workflows/, pull_request_template.md
```

## 4. Estructura interna de un servicio hexagonal
```
services/reservation/
├── app/
│   ├── main.py                 ← raíz de composición: crea adapters y los inyecta
│   ├── config.py               ← lee variables de entorno / *_FILE
│   ├── api/                    ← FastAPI: routers, schemas (Pydantic), errores HTTP, dependencias
│   ├── application/            ← casos de uso (advance, create_reservation, cancel…), puertos (Protocol), DTO internos
│   ├── domain/                 ← entidades, máquina de estados, reglas, errores y eventos de dominio (Python puro)
│   ├── infrastructure/
│   │   ├── db/                 ← SQLAlchemy Core, repositorio, migraciones (alembic/)
│   │   ├── clients/            ← clientes HTTP a customer/hotel/availability/payment (con sus DTO propios)
│   │   └── workers/            ← recuperación de sagas, relay del outbox (python -m app.infrastructure.workers.recovery)
│   └── logging.py              ← JSON + X-Request-ID
├── tests/{unit,integration}/
├── Dockerfile  (multistage, no-root, HEALTHCHECK)
└── pyproject.toml
```
`customer` y `hotel`: `app/{main,config,api,service,models}.py` + `tests/`.

## 5. Dependencias entre capas
```
        ┌────────────────────────────── main.py (composición: conoce todo) ───────────────┐
        ▼                                                                                  ▼
      api  ───────────────►  application  ◄───────────────  infrastructure
 (FastAPI, schemas)        (casos de uso + puertos)     (SQL, HTTP, workers; implementa puertos)
                                  │
                                  ▼
                               domain   (Python puro: sin FastAPI, SQLAlchemy, httpx, pydantic)
```
| Desde → hacia | Permitido |
|---|---|
| api → application | Sí (llama casos de uso) |
| api → domain | Solo tipos/errores para mapear a HTTP |
| api ↔ infrastructure | **No** (la API no conoce SQL ni clientes) |
| application → domain | Sí |
| application → infrastructure / api | **No** (usa puertos) |
| infrastructure → application / domain | Sí (implementa puertos, usa entidades) |
| domain → cualquier otra capa o framework | **No** |
| main → todas | Sí (único punto que instancia adapters) |

**Se verifica en CI** con `import-linter` (plantilla en `services/_template/importlinter.example`): violar una regla rompe el build. Probado en F0 contra tres violaciones (aplicación→infraestructura, dominio→SQLAlchemy, API→infraestructura).

**Transacciones sin Unit of Work:** el repositorio expone operaciones atómicas con significado de negocio (p. ej. `transition(reservation, event, outbox_event=None)` guarda estado + evento + outbox en una sola TX). La aplicación nunca maneja conexiones.

## 6. Puertos: solo con frontera real
| Servicio | Puerto | Por qué existe | Adapters / dobles |
|---|---|---|---|
| reservation | `ReservationRepository` | Probar la saga y la recuperación sin BD (crash entre pasos) | SQL · memoria (tests) |
| reservation | `AvailabilityClient`, `PaymentClient`, `CustomerClient`, `HotelClient` | Frontera de red; simular timeouts/errores | httpx · dobles programables |
| reservation | `Clock` | Probar plazos y backoff sin dormir | sistema · reloj falso |
| availability | `InventoryStore` | Frontera con SQL atómico | SQL (la concurrencia se prueba contra PostgreSQL real, no con un doble) |
| payment | `PaymentProvider` | Es el Adapter del proveedor externo | Simulado · (real, futuro) |
| payment | `PaymentRepository` | Estados y clave de idempotencia | SQL · memoria |
| notification | `NotificationChannel` | Canal de envío intercambiable | Simulado/log · (email, futuro) |
| notification | `NotificationRepository` | Inbox idempotente y estados | SQL · memoria |
| customer / hotel | — | CRUD directo sobre SQLAlchemy; sin puertos | — |

## 7. Patrones por componente
| Componente | Patrón | Dónde vive | Cómo se prueba |
|---|---|---|---|
| reservation | Saga orquestada + State Machine | `domain/state_machine.py`, `application/advance.py` | Unit con dobles: camino feliz, rechazo, `UNKNOWN`, crash entre pasos |
| reservation | Idempotency Key + hash del cuerpo | `application/create_reservation.py` | Mismo key ×5 y concurrente → 1 reserva |
| reservation | Transactional Outbox + Relay | `infrastructure/db`, `workers/relay.py` | Esc. A, I6 |
| availability | Reserva atómica + Idempotencia + TTL | `infrastructure/db/inventory.py` | Integración con PostgreSQL real: N peticiones, K cupos |
| payment | Adapter + State Machine + ledger append-only | `infrastructure/provider_sim.py`, `domain/payment.py` | Todos los modos de simulación; sin cobro doble |
| notification | Inbox idempotente + worker + backoff | `application/deliver.py`, `workers/deliver.py` | Duplicados, caída y recuperación |
| customer / hotel | CRUD modular | `service.py` | Pruebas de API |
| gateway | API Gateway + balanceo + rate limiting | `gateway/nginx.conf` | Esc. B, k6, prueba de 429 |

## 8. Comunicación y contratos
- HTTP/JSON con contratos explícitos (`docs/05-contratos-api.md`). Cada servicio publica su OpenAPI; se guarda un **snapshot** y un test falla si el contrato cambia sin querer.
- **Sin modelos compartidos**: cada cliente define sus DTO en `infrastructure/clients`.
- Timeouts explícitos en todo cliente; reintentos acotados (≤3, backoff + jitter) **solo** en operaciones idempotentes.
- Propagación de `X-Request-ID`; logs JSON con `request_id`, `reservation_id`, `service`.

## 9. Configuración
Variables de entorno por servicio, con soporte `*_FILE` para secretos (contraseñas de BD). `.env.example` versionado, `.env` ignorado. Tabla de variables en `docs/variables.md`.

## 10. Qué NO hacemos (anti sobre-ingeniería)
Sin repositorios genéricos, Unit of Work, bus de eventos interno, CQRS, event sourcing, ORM de dominio, librería compartida, Redis, Kubernetes ni autenticación completa (JWT/OIDC se documenta como evolución). Cada adición futura requiere un ADR.
