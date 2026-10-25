# Ensayo desde cero (F5)

**Resultado: pasada limpia.** Clon nuevo, sin `.venv`/`secrets`/`backups`, con
el stack principal detenido. Proyecto Compose aislado **`f5-ensayo`**. Log
completo: [`ensayo-desde-cero.log`](ensayo-desde-cero.log).

- Inicio: 2026-10-23 22:33:22 (-05:00)
- Fin: 2026-10-23 23:10:42 (-05:00)
- Duración total: **37 min 20 s** (suma de pasos; incluye la creación del
  `.venv` y la descarga/instalación de dependencias de prueba).
- Clone: `C:\Users\David\AppData\Local\Temp\opencode\f5-ensayo`
  (rama `docs/f5-entrega`).
- `.env`: copiado de `.env.example`; secretos generados por `make up`.
- `COMPOSE_PROJECT_NAME=f5-ensayo` (ver “Pasos manuales/desviaciones”).
- `CHAOS_ALLOW_VOLUME_DELETE=1` para E3 (solo afecta al proyecto de ensayo).

## Comandos y duraciones

| # | Comando | Duración | Exit | Resultado |
|---|---|---|---|---|
| 1 | `make clean-all` (pre) | 4,7 s | 0 | volumen/redes del ensayo previos eliminados |
| 2 | `cp .env.example .env` | 0,0 s | 0 | `.env` local |
| 3 | `make build` | **3,3 s** | 0 | 6 imágenes `:local` (caché de Docker) |
| 4 | `make up` | **21,5 s** | 0 | stack dev healthy |
| 5 | verificación de proyecto | 0,1 s | 0 | contenedores `f5-ensayo-*` |
| 6 | `make seed` | 16,5 s | 0 | 3 hoteles, 2 clientes (incluye venv) |
| 7 | `make test` | 210,8 s | 0 | unitarias + 18 tests de invariantes |
| 8 | `make e2e` | 63,0 s | 0 | **11 passed** (incluye flujo público) |
| 9 | `make smoke` | 30,1 s | 0 | frontend/cabeceras + 3 tests de infra |
| 10 | `make invariants` | 5,8 s | 0 | **0 violaciones** |
| 11 | `make check-docs` | 5,1 s | 0 | **62 variables**, todas documentadas |
| 12 | `CHAOS_ALLOW_VOLUME_DELETE=1 make chaos` | **1.036,6 s** | 0 | A–S2, `hard_fail=False` |
| 13 | `make perf` | **769,9 s** | 0 | P1, P3, P3b y P4 |
| 14 | `make report` | 5,8 s | 0 | `REPORTE.md` + `fallos.md` |
| 15 | `make backup` | 7,1 s | 0 | 6 BDs |
| 16 | `make restore DIR=backups/...` | 27,7 s | 0 | restore 22,4 s; `alembic_version=0001` |
| 17 | `make prune` | 0,2 s | 0 | imágenes viejas dangling |
| 18 | `make images` | 0,3 s | 0 | **6 imágenes, 0 huérfanas** |
| 19 | `make down` | 5,2 s | 0 | stack detenido |
| 20 | `make up-prod` | 21,6 s | 0 | perfil público healthy |
| 21 | health prod | 0,1 s | 0 | `/healthz` OK (IPv6/contenedor) |
| 22 | `make down` | 4,2 s | 0 | — |
| 23 | `make clean` | 0,3 s | 0 | volúmenes borrados |
| 24 | `make clean-all` | 0,3 s | 0 | + semilla |
| 25 | `make images` (final) | 0,2 s | 0 | **6 imágenes, 0 huérfanas** |

## Salidas resumidas

- **Chaos:** B/kill9 0,25 s; C/kill9 7,93 s; C/stop 16,93 s; D 1,99 s;
  E1/stop 26,50 s; E1/pkill9 20,74 s; E2 estado final OK; E3/A 29,94 s;
  E3/B 30,29 s; E4 6,77 s; **S/stop TTD 95,03 s, `cumplido=False`** (el
  objetivo de 30 s sigue sin cumplirse, como se documentó); S2 5,84 s.
  Todos con `hard_fail=False`.
- **Perf:** P1/P3/P3b/P4 completos; los informes quedaron en el clon. En P3b
  N=3 se repiten los locks de V1 (36–39) y 0–1 en V2; HELD exacto.
- **Backup/restore:** dumps de 3,8 KB (customer) a 234,7 KB (reservation);
  restore de 22,4 s.
- **Prod:** gateway healthy; `/healthz` 200 (comprobado por IPv6/contenedor;
  ver incidencia).
- **Imágenes:** mismas 6 del producto (174–176 MB) y 0 huérfanas.

## Pasos manuales / desviaciones (declarados)

1. **`.env`**: un clon limpio no lo tiene; se copió de `.env.example` (paso 2).
   `make up` genera los secretos.
2. **`COMPOSE_PROJECT_NAME=f5-ensayo`**: `compose.yaml` tiene `name:
   reservas-platform`, que **prevalece sobre el nombre del directorio**. Sin
   esta variable, el E3 del ensayo apuntaría al volumen del proyecto principal.
   Es una condición necesaria para una copia paralela segura. Se documenta en
   `manual.md`/`RELEASE.md`.
3. **Puerto 8080 ocupado en el host por un `httpd` externo** (proceso ajeno al
   proyecto, IPv4 0.0.0.0:8080): `up-prod` levanta healthy y el gateway
   responde 200 dentro del contenedor y por IPv6 (`http://[::1]:8080/healthz`);
   el chequeo se hizo así. No se detuvo el proceso externo.
4. La primera ejecución del script se detuvo por el manejo de `stderr` de
   PowerShell (`ErrorActionPreference=Stop`), no por el proyecto; se corrigió
   el script y se repitió desde cero.
5. La primera pasada completa falló **solo** en el health check de prod por el
   `httpd` externo; se corrigió el chequeo (IPv6/contenedor) y se repitió el
   ensayo completo hasta la pasada limpia anterior.

## Hallazgos del ensayo (corregidos)

- El **arnés de caos** fijaba `reservas-platform` para localizar el volumen de
  E3; en otra copia podía mirar/borrar el volumen equivocado. Se corrigió para
  usar `COMPOSE_PROJECT_NAME` (commit `fix(chaos)`).
- `docker_images.py` filtraba por `com.docker.compose.project`; ahora usa la
  etiqueta del producto (`com.reservas.project`) y funciona también en la
  copia de ensayo.

## Conclusión

La plataforma se reproduce desde un clon limpio con los comandos documentados,
sin intervención sobre el código: build, arranque, siembra, unitarias, e2e,
smoke, invariantes, caos completo, perf completo, reporte, backup/restore,
imágenes y perfil prod. Las dos condiciones externas (`.env`/proyecto y el
puerto 8080 ocupado) están declaradas y no afectan al producto.


## Ensayo reducido F3c (autenticación)

Clon nuevo, proyecto **`f3c-ensayo`**, stack principal detenido; misma
condición que F5: `.env` copiado y `COMPOSE_PROJECT_NAME` para aislar el
proyecto. **Pasada limpia en 6 min 47 s** (sin pasos manuales adicionales).

| Comando | Duración | Resultado |
|---|---|---|
| `make clean-all` (pre) | 0,5 s | — |
| `make build` | 3,3 s | 6 imágenes (caché) |
| `make up` | 22,6 s | stack healthy, migración **0002** aplicada |
| `make seed` | 38,8 s | datos + **cuenta demo** |
| `make test` | 222,9 s | unitarias + invariantes |
| `make e2e` | 62,3 s | **11 passed** (incluye auth público) |
| `make smoke` | 34,4 s | frontend/cabeceras |
| `make check-ui` | 5,2 s | rutas auth y Bearer |
| `make check-docs` | 5,1 s | 68 variables |
| `make invariants` | 5,9 s | **0** |
| `make down` / `clean-all` | 5,2 / 0,4 s | — |

No hubo fallos. La cuenta demo se creó desde `DEMO_USER_PASSWORD` del
`.env.example`; el flujo público (registro/login/reserva/replay/cancel/logout)
pasó en `make e2e`.
