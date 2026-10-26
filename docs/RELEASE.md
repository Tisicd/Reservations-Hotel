# RELEASE — entrega v1.1.0

## Versiones entregadas

| Tag | Cambios principales |
|---|---|
| `v1.0-entrega` | Entrega inicial F5: microservicios, Compose, caos A–S2, carga P1/P3/P3b/P4, reporte, manual y ensayo. |
| `v1.0.1-entrega` | F3b: UI tipo sitio de reservas (hash, inicio/resultados/ficha/pago/estado/mis reservas, modo demo) y corrección del usuario demo (IDs de semilla no listables). |
| `v1.1.0-entrega` | F3c: autenticación básica; reservar/cancelar exigen sesión; cuentas en customer, scrypt, sesiones opacas y `auth_request`. |

`v1.0-entrega` y `v1.0.1-entrega` quedan como respaldo. No se fusiona nada más.

## Contenido

- Código de los 6 servicios, workers, gateway (nginx + frontend), tests
  (`unit`, `e2e`, `chaos`, `perf`, `invariants`, `infra`), `compose.yaml`,
  `compose.dev.yaml`, Makefile y scripts (`seed`, `backup`, `restore`,
  `report`, `smoke`, `check_vars`, `check_ui_routes`).
- Documentación: `docs/` (arquitectura, ADR, contratos, manual, seguridad,
  producción, swarm, imágenes, variables), `docs/resultados/` (caos, carga,
  reporte consolidado, ensayos) e informe borrador
  [`informe/INFORME.md`](informe/INFORME.md).
- **No** incluye: `secrets/`, `backups/`, `.env`, `.venv/` (se generan o son
  locales). Ver `.gitignore`.

## Reproducir

```bash
cp .env.example .env
make build && make up && make seed
make test && make e2e && make smoke && make check-ui && make invariants && make check-docs
CHAOS_ALLOW_VOLUME_DELETE=1 make chaos
make perf PERF=P1 && make perf PERF=P3b
make report
```

Requisitos, flujo de registro/login, credenciales demo y problemas en
[`manual.md`](manual.md). Ensayos y duraciones en
[`resultados/ensayo-desde-cero.md`](resultados/ensayo-desde-cero.md).

## Credenciales demo

Las credenciales demo se **definen en `.env`**; no hay valores en este
documento ni en el perfil de producción. Ver [`manual.md`](manual.md).

## Estado verificado (2026-10-24)

- `main` con el cierre de entrega y CI verde; tag `v1.1.0-entrega`.
- `make invariants` ⇒ **0**; `make images` ⇒ mismas 6 imágenes del producto,
  **0 huérfanas**.
- Escaneos: trivy **47 HIGH/0 CRITICAL** por imagen; gitleaks **0** en el
  historial ([`resultados/seguridad-trivy.txt`](resultados/seguridad-trivy.txt),
  `seguridad.md`).
- Ensayo F5: 37 min 20 s; ensayo F3c reducido: 6 min 47 s (proyecto aislado).

## Limitaciones y hallazgos abiertos (honesto)

1. **B/kill intermitente:** 1 de 5 repeticiones con **2,41 s** (> 2 s); no se
   ajustó el objetivo (`resultados/REPORTE.md`, `chaos_B_kill_*.md`).
2. **S no cumple el TTD:** **93,21 s** > 30 s por `retries=12`; TTR tras
   recuperar 3,43 s (`resultados/F4b-resiliencia.md`, `chaos_S_stop_1.md`).
3. **P2 y P5 no ejecutados**; recorte declarado en `REPORTE.md`.
4. **Resultados comparativos en una sola máquina** (k6, servicios y PostgreSQL
   comparten CPU/RAM); no son cifras absolutas (`perf_P1_analisis.md`).
5. **Backup en caliente sin consistencia entre servicios** y **RPO dependiente
   de `make backup`**; E3 pierde 5/5 reservas posteriores
   (`proceso/backup-restore.md`, `chaos_E3_*.md`).
6. **Seguridad:** autenticación básica implementada, pero **sin TLS**, sin
   verificación de email, recuperación, MFA, roles ni anti-bot; registro con
   enumeración residual por `409`; límites por IP (no WAF/CDN); 47 HIGH/0
   CRITICAL por imagen (44 base Debian + 3 `starlette 0.41.3`); sin rotación
   de secretos ni observabilidad de producción (`seguridad.md`, ADR-0012).
7. **Propiedad de reservas:** solo cancelar comprueba dueño; los `GET` de
   reservas siguen públicos por UUID (Hito D no implementado).
8. **P3:** rps del burst ruidoso (CV hasta 31 %); la latencia de 5–6,5 s es la
   saga síncrona (`perf_P3.md`).

## Pendientes de la persona

- Secciones **1, 3, 10 y 14** del informe (resumen, alternativas, costos con
  precios vigentes y conclusión).
- **10 capturas** de UI en `docs/resultados/ui/` (ver `manual.md`).
- Decidir publicación/merge del tag `v1.1.0-entrega`; no se fusionó nada más.
