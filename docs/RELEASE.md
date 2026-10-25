# RELEASE — entrega F5

## Contenido

- Código de los 6 servicios, workers, gateway (nginx + frontend), tests
  (`unit`, `e2e`, `chaos`, `perf`, `invariants`, `infra`), `compose.yaml`,
  `compose.dev.yaml`, Makefile y scripts (`seed`, `backup`, `restore`,
  `report`, `smoke`, `check_vars`).
- Documentación: `docs/` (arquitectura, ADR, contratos, manual, seguridad,
  producción, swarm, imágenes, variables), `docs/resultados/` (caos, carga,
  reporte consolidado) e informe borrador
  [`informe/INFORME.md`](informe/INFORME.md).
- **No** incluye: `secrets/`, `backups/`, `.env`, `.venv/` (se generan o son
  locales). Ver `.gitignore`.

## Ensayo desde cero

Pasada limpia en 37 min 20 s (clon nuevo, proyecto `f5-ensayo`, stack
principal detenido): ver
[`resultados/ensayo-desde-cero.md`](resultados/ensayo-desde-cero.md) y el log
completo [`resultados/ensayo-desde-cero.log`](resultados/ensayo-desde-cero.log).

## Cómo reproducir

```bash
cp .env.example .env
make build && make up && make seed
make test && make e2e && make smoke && make invariants && make check-docs
CHAOS_ALLOW_VOLUME_DELETE=1 make chaos
make perf PERF=P1 && make perf PERF=P3b
make report
```

Requisitos y problemas en [`manual.md`](manual.md). El ensayo desde cero con
duraciones está en [`resultados/ensayo-desde-cero.md`](resultados/ensayo-desde-cero.md).

## Estado verificado

- `main` (`d8db913`, F4c + F3) con CI verde; rama de entrega
  `docs/f5-entrega` (CI al cerrar).
- `make invariants` ⇒ **0**; `make images` ⇒ mismas 6 imágenes del producto,
  **0 huérfanas** (`resultados/REPORTE.md`, `imagenes.md`).
- Escaneos: trivy **47 HIGH/0 CRITICAL** por imagen; gitleaks **0** en 64
  commits ([`resultados/seguridad-trivy.txt`](resultados/seguridad-trivy.txt),
  `seguridad.md`).

## Limitaciones y hallazgos abiertos (honesto)

1. **B/kill intermitente:** 1 de 5 repeticiones con **2,41 s** (> 2 s); no se
   ajustó el objetivo (`resultados/REPORTE.md`, `chaos_B_kill_*.md`).
2. **S no cumple el TTD:** **93,21 s** > 30 s por `retries=12`; se mantiene por
   evitar falsos unhealthy (`resultados/F4b-resiliencia.md`,
   `chaos_S_stop_1.md`). El TTR tras recuperar es 3,43 s.
3. **P2 y P5 no ejecutados** (mezcla 90/10 y rampa de saturación de la mezcla);
   recorte declarado en `REPORTE.md`. P3 y P3b sí se ejecutaron.
4. **Resultados comparativos de una sola máquina:** k6, servicios y PostgreSQL
   comparten CPU/RAM; no son cifras absolutas
   (`perf_P1_analisis.md`, `entorno.md`).
5. **Backup en caliente sin garantía de consistencia entre servicios** y **RPO
   dependiente de ejecutar `make backup`**; E3 pierde las 5/5 reservas
   posteriores al backup (`proceso/backup-restore.md`, `chaos_E3_*.md`).
6. **Seguridad:** sin TLS ni autenticación; límites por IP (no WAF/CDN); 47
   HIGH/0 CRITICAL por imagen (44 base Debian + 3 `starlette 0.41.3`); sin
   rotación de secretos ni observabilidad de producción (`seguridad.md`,
   `produccion.md`).
7. **P3:** el rps del burst es ruidoso (CV hasta 31 %) y la latencia de 5–6,5 s
   es la saga síncrona, no contención (`perf_P3.md`).
8. **Riesgo de build sin red/caché:** el build monoetapa temporal necesitó
   `--trusted-host` por el proxy TLS local; las imágenes del producto ya
   construidas y el CI no se ven afectados (`imagenes.md`).

## Pendientes de la persona

- Secciones **1, 3, 10 y 14** del informe (resumen, matriz de alternativas,
  costos con precios vigentes y conclusión).
- Capturas de la UI en `docs/resultados/ui/` (5 momentos descritos en
  `manual.md`).
- Tag propuesto `v1.0-entrega` y `git archive` verificado con gitleaks
  (sin `secrets/`, `backups/`, `.env` ni `.venv`); la persona decide publicarlo.


## Autenticación (F3c)

- Cuentas = clientes; scrypt (N=32768, ~200 ms), sesiones opacas con hash
  SHA-256, TTL 8 h, bloqueo temporal y rate limit; Bearer en `sessionStorage`.
- Reservar/cancelar requieren sesión por `auth_request`; el gateway inyecta
  `X-User-Id` y lo vacía en el resto. `/api/customers*` cerrado.
- **Fuera de alcance / pendiente:** verificación de email, recuperación de
  contraseña, MFA, roles, anti-bot, TLS y cookie `HttpOnly`+CSRF (ADR-0012).
  El registro aún puede enumerar correos por `409`. Los `GET` de reservas
  siguen públicos por UUID (Hito D no implementado); cancelar sí comprueba
  dueño.
- **Cuenta demo:** `demo@reservas-uce.test` con `DEMO_USER_PASSWORD` (solo
  dev; `.env.example`); no hay valor en el perfil de producción.
- Límites: login 20 r/m burst 10; registro 10 r/m burst 5; 429.
- Evidencia: `docs/adr/0012`, `docs/seguridad.md`, `tests/customer/...`,
  `tests/e2e/test_public_flow.py`.
## Etiqueta propuesta (F3c)

`v1.1.0-entrega` (autenticacion basica). `v1.0.1-entrega` queda como respaldo.
No se fusiona a `main` sin aprobacion.
