# Manual de instalación, uso y operación

> Verificado en el **ensayo desde cero** (`docs/resultados/ensayo-desde-cero.md`),
> donde se ejecutaron y cronometraron todos los comandos de esta página.

## 1. Requisitos

- **Docker Desktop** con backend WSL2 (Windows) o Docker Engine + Compose v2
  (Linux/macOS).
- **≥ 6 GB de RAM asignados a Docker** (el entorno de medida usó 7,45 GiB;
  `docs/resultados/entorno.md`). Con menos, PostgreSQL y las réplicas pueden
  quedar sin memoria.
- **GNU Make**, **git** y **Python 3.12+** (el repo crea su `.venv` con
  `make deps`; `make test`/`make e2e` lo usan).
- Red la primera vez (descarga de imágenes base y dependencias). El CI usa
  Ubuntu; localmente se probó en Windows 11 + Docker Desktop 4.48.

## 2. Instalación desde cero

```bash
git clone <repo>
cd reservas-platform
cp .env.example .env      # valores de ejemplo; no se versiona
make build                # 6 imágenes :local (multistage)
make up                   # perfil dev: público 8088 + admin 8081
make seed                 # hoteles, habitaciones, clientes e inventario
make smoke                # frontend + cabeceras + rutas internas
```

- `make up` genera los secretos (`secrets/*.txt`) si faltan.
- El **primer arranque en frío** tarda más (creación de BDs, migraciones y
  healthchecks). En el ensayo (con caché de Docker) `build + up + seed` sumó
  **41,3 s** (3,3 + 21,5 + 16,5); sin caché/venv será mayor. Ver
  `docs/resultados/ensayo-desde-cero.md`.
- URLs: frontend `http://127.0.0.1:8088/`; admin
  `http://127.0.0.1:8081/svc/...`; PostgreSQL dev en `127.0.0.1:5433`.
- En producción (`make up-prod`) el gateway publica **8080** y **no** publica
  el listener admin.

## 3. Comandos

| Comando | Qué hace |
|---|---|
| `make build` | Construye las 6 imágenes `:local` (multistage). |
| `make up` | Levanta el perfil **dev** (`compose.yaml` + `compose.dev.yaml`), público 8088 y admin 8081. |
| `make up-dev` | Igual que `up` (alias explícito). |
| `make up-prod` | Levanta solo el perfil público (gateway 8080, sin admin). |
| `make down` | Detiene el stack; **conserva** volúmenes y datos. |
| `make clean` | `down -v`: borra contenedores **y volúmenes** del proyecto. |
| `make clean-all` | `clean` + borra `secrets/seed.json` (siembra desde cero). |
| `make seed` | Siembra idempotente (hoteles, habitaciones, clientes, inventario). |
| `make test` | Pruebas de infraestructura + unitarias de los 6 servicios (detiene workers temporalmente). |
| `make e2e` | `up-dev` + `gateway-refresh` + `seed` + `pytest tests/e2e` (incluye el flujo público del frontend). |
| `make smoke` | HTML/JS/CSS, cabeceras de seguridad, `/api/hotels` y `/svc` no expuesto. |
| `make check-ui` | Rutas `/api` usadas por la UI: p?blicas y no bloqueadas; sin rutas internas. |
| `make invariants` | I1–I7 con `--grace 60`; debe dar 0 violaciones. |
| `make check-docs` | Variables usadas por servicios/compose = documentadas. |
| `make lint` | ruff/import-linter/contratos de capas. |
| `make chaos [SCEN=...] [REPEAT=n]` | A, B, C, D, E1, E2, E3, E4, S, S2. E3 exige `CHAOS_ALLOW_VOLUME_DELETE=1`. |
| `make perf [PERF=P1|P3|P3b|P4|all]` | k6 en contenedor; escribe `docs/resultados/perf_*.md`. |
| `make report` | Consolida `REPORTE.md` y actualiza `fallos.md`. |
| `make backup` | Dumps de las 6 BDs en `backups/<timestamp>/` (ignorado por git). |
| `make restore DIR=backups/<timestamp>` | Restaura las 6 BDs desde un backup. |
| `make images` | Tabla de imágenes del proyecto y huérfanas. |
| `make prune` | Elimina imágenes dangling del proyecto. |
| `make gateway-refresh` | Recrea/reinicia el gateway para releer DNS (tras escalar). |

## 4. Frontend (demo tipo sitio de reservas)

La UI es una SPA sin build, con **rutas por hash** (no recarga), marca
ficticia **Reservas UCE** y solo llamadas `/api/*` públicas:

| Ruta | Pantalla |
|---|---|
| `#/` | Inicio: hero, buscador (ciudad real, fechas, huéspedes) y destinos de `GET /api/hotels` |
| `#/buscar?...` | Resultados en tarjetas: "desde", cupo real, total, filtros (ciudad, precio, capacidad) y orden por precio |
| `#/login?returnTo=...` | Inicio de sesión |
| `#/registro?returnTo=...` | Crear cuenta |
| `#/hotel/<id>?...` | Ficha: galería SVG generada, habitaciones, capacidad, total y "Reservar" |
| `#/reservar?...` | Requiere sesión: resumen + pago simulado + confirmar |
| `#/reserva/<id>` | "Procesando…": timeline de `/events`, estado y notificación |
| `#/mis-reservas` | Reservas de la cuenta con sesión |

- **Sin datos inventados:** no hay reseñas, estrellas ni amenidades; solo
  hoteles, habitaciones, precios, capacidad y cupo reales de la API.
- **Ilustraciones:** SVG deterministas generados con `createElementNS` a
  partir del id; sin imágenes externas ni stock.
- **Pago simulado:** `Tarjeta aprobada` (`ok`), `Tarjeta rechazada`
  (`decline`), `Banco sin respuesta` (`process_then_drop_response`) y
  `Pago lento` (`slow`); aviso de no usar datos reales.
- **Autenticación:** reservar exige cuenta; `#/login` y `#/registro` con
  errores claros, bloqueo temporal y límites. El token va en
  `sessionStorage` y `Authorization: Bearer`. Cuenta demo (solo dev):
  `demo@reservas-uce.test` con `DEMO_USER_PASSWORD` del `.env`.
- **Técnico:** interruptor en el pie abre un panel con el log de llamadas
  (método, ruta, HTTP, ms, `request_id`, `Idempotent-Replayed`), timeline
  cruda y "Reenviar la misma solicitud".
- **Responsive:** probado a **375 px** y **1280 px**; `prefers-color-scheme`
  para oscuro; foco visible; `aria-live` en estados; formularios con `label`.
- **Límites:** concurrencia ≤ 2, caché de hoteles/habitaciones, backoff en
  429/503 y reintento con la misma clave; una nueva reserva genera nueva
  clave. `make check-ui` valida que solo se usen rutas públicas.

### Tres flujos de demo

| Flujo | Simulación | Final |
|---|---|---|
| Feliz | `ok` | `CONFIRMED` + notificación `SENT` |
| Rechazo | `decline` | `PAYMENT_DECLINED` → `CANCELLED`, sin cobro |
| Respuesta perdida | `process_then_drop_response` | `PAYMENT_UNKNOWN` → `CONFIRMED`, 1 cobro |

### 10 capturas para `docs/resultados/ui/`

1. `01-inicio.png` — hero, buscador y destinos.
2. `02-resultados.png` — tarjetas con "desde", cupo y filtros.
3. `03-ficha.png` — galería, habitaciones y total.
4. `04-pago.png` — huésped + pago simulado + aviso.
5. `05-procesando.png` — timeline en curso.
6. `06-confirmada.png` — confirmada, código, notificación.
7. `07-mis-reservas.png` — lista con insignias y cancelar.
8. `08-modo-demo.png` — panel técnico con `HTTP 200` e
   `Idempotent-Replayed: true`.
9. `09-login.png` — inicio de sesión y error genérico.
10. `10-registro.png` — creación de cuenta y política de contraseña.

Capturar cada pantalla a **375 px** y **1280 px**; el flujo
`process_then_drop_response` debe mostrar `PAYMENT_UNKNOWN` antes de
`CONFIRMED`. Los errores 429/503 se muestran con `request_id`, espera y
reintento con la misma clave.

### Acceso y reserva (F3c)

1. Explorar (inicio, resultados y ficha) **no** requiere sesión.
2. Al pulsar **Reservar** sin sesión, la UI redirige a
   `#/login?returnTo=...`; tras autenticarse vuelve al paso de reserva
   conservando la selección.
3. Crear cuenta en `#/registro` (mínimo 10 caracteres) o usar la **cuenta demo
   definida en `.env`** (no hay valores en la documentación de Release).
4. Errores mostrados: login genérico `401`, correo ya registrado `409`,
   contraseña débil `422`, límite `429` con espera y bloqueo temporal. El
   mensaje incluye `request_id`.
5. **Cerrar sesión** desde la cabecera borra el token de `sessionStorage` y
   llama a `POST /api/auth/logout`.

## 5. Cómo leer los reportes

- `docs/resultados/REPORTE.md`: consolidado (entorno, caos, carga, hallazgos;
  las conclusiones las redacta la persona).
- `docs/resultados/chaos_<ID>_<modo>_<rep>.md`: 5 preguntas, RTO/TTD,
  timeline y Health.Log por escenario.
- `docs/resultados/perf_<ID>.md`: hipótesis, tablas, CPU/conexiones/locks y
  conclusión honesta; `perf_P1_analisis.md` explica el 2,09×.
- `docs/fallos.md`: modos de caída, hallazgos y limitaciones.
- `docs/resultados/ensayo-desde-cero.md`: duraciones y salidas del ensayo.

## 6. Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `bind: address already in use` | Puertos 8088/8081/5433 ocupados. Cambiar `GATEWAY_DEV_PORT`/`POSTGRES_DEV_PORT` en `.env`; el 8081 es fijo (detener el proceso que lo usa). |
| `image not found` al hacer `make up` | Faltan imágenes: `make build` (o `make ensure-images`). |
| Arranque lento la primera vez | Migraciones/healthchecks; esperar `make up` (usa `--wait`). Tiempo medido en el ensayo. |
| `429` en la UI o pruebas | Límites por IP del gateway (`50r/s`, `burst`); esperar y reintentar (la UI lo hace). No es un 503. |
| `503` al reservar | Dependencia caída/fail-closed; reintentar con la misma clave (la UI lo hace) y revisar `docker compose ps`. |
| Docker sin memoria / contenedores reiniciándose | Subir RAM de Docker Desktop a ≥ 6 GB. |
| Variables faltantes | `make check-docs` y `docs/variables.md`. |
| Build falla al instalar pip (SSL) | Proxy TLS local: configurar proxy/certs de Docker Desktop; no es un problema del repo/CI. |
| Todo corrupto en dev | `make clean-all && make build && make up && make seed` (borra solo el proyecto). |
| `up-prod` responde 404 en `127.0.0.1:8080` | Otro proceso ocupa el 8080 IPv4 (p. ej. un `httpd` ajeno). El gateway responde dentro del contenedor y por IPv6 (`http://[::1]:8080/healthz`). No mates procesos ajenos. |
| Copia paralela comparte volúmenes | `compose.yaml` fija `name: reservas-platform`; exporta `COMPOSE_PROJECT_NAME=<otro>` en la copia (necesario para aislar E3). |

## 7. Estructura del repositorio

```
services/{customer,hotel,availability,reservation,payment,notification}/
  app/{api,application,domain,infrastructure}/  # hexagonal ligera (ADR-0001)
gateway/{nginx.conf,conf.d/,html/}               # nginx + frontend F3
tests/{e2e,chaos,perf,invariants,infra}/
scripts/{seed,backup,restore,report,smoke,check_vars,docker_images}.py
docs/{adr,fases,resultados,proceso,informe}/ + manual, seguridad, producción, swarm
compose.yaml, compose.dev.yaml, Makefile, .env.example
```

## 8. Reproducción rápida de la evidencia

```bash
make e2e && make invariants          # flujo y contrato de integridad
CHAOS_ALLOW_VOLUME_DELETE=1 make chaos  # A–S2 (destructivo solo en este proyecto)
make perf PERF=P1 && make perf PERF=P3b
make report
```

Los resultados son **comparativos** (k6, servicios y PostgreSQL comparten la
misma máquina), no absolutos.
