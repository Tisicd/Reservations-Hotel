# Backup y restauración (F4b)

Procedimiento reproducible para respaldar y restaurar las 6 bases del proyecto.

## Comandos

- `make backup` → `python scripts/backup.py`
  - `pg_dump -Fc` de cada BD (`customer_db`, `hotel_db`, `availability_db`,
    `payment_db`, `reservation_db`, `notification_db`) a
    `backups/<timestamp>/<db>.dump`.
  - Escribe `manifest.json` con hora, tamaño y `sha256` de cada dump.
  - `backups/` está en `.gitignore`.
- `make restore DIR=backups/<timestamp>` → `python scripts/restore.py <dir>`
  - Verifica el `sha256` de cada dump contra el manifiesto.
  - Detiene servicios de aplicación y workers (no `postgres`).
  - Restaura cada BD conectando **como el rol dueño** con
    `pg_restore --clean --if-exists --no-owner`.
  - Verifica `alembic_version` por BD.
  - Vuelve a levantar el stack (`up -d --no-build --wait`) y cronometra.

> Nota: el prompt pedía `scripts/backup.sh`/`restore.sh`; se implementaron en
> Python (`scripts/backup.py`, `scripts/restore.py`) por portabilidad en el host
> Windows del proyecto y por consistencia con `scripts/*.py`.

## Escenario E3 (pérdida del volumen)

Solo se ejecuta con `CHAOS_ALLOW_VOLUME_DELETE=1`:

```
$env:CHAOS_ALLOW_VOLUME_DELETE="1"
make chaos SCEN=E3 REPEAT=1
```

Salvaguardas del arnés antes de borrar:
1. El volumen debe tener el label `com.docker.compose.project=reservas-platform`.
2. El nombre debe empezar por `reservas-platform_` y contener `pgdata`.
3. Si hay ambigüedad, aborta sin borrar.

Pasos: backup en T0 → crear 5 reservas después → `rm -sf postgres` + borrar el
volumen → `up -d --no-build postgres` (init-db recrea roles/BDs) → `restore` →
`up -d --no-build --wait`.

- **Variante A (backup en reposo):** se detienen las escrituras antes del backup.
  Aserción dura: invariantes **0** tras restaurar. RPO observado = reservas
  creadas después del backup que se pierden.
- **Variante B (backup en caliente):** backup con servicios activos. Es
  observacional: se reportan las violaciones de invariantes si aparecen (los
  `pg_dump` por BD no son una instantánea consistente entre servicios).

## RPO real y frecuencia de backup

El **RPO observado** tras una pérdida de volumen es la antigüedad del último
backup: todo lo confirmado después de `T0` se pierde al restaurar. Hoy `make
backup` es **manual**, así que el RPO real depende de cuándo se ejecute:

- Si se hace backup cada `N` horas, el RPO ≤ `N` horas (peor caso: justo antes
  del siguiente backup).
- En E3 el backup se tomó en `T0` y se crearon 5 reservas después; el RPO
  observado fue **5/5** reservas perdidas (la brecha real frente al RPO objetivo
  de F0, que asume backups programados ≤ 24 h).
- Para reducir el RPO: programar `make backup` (cron/Task Scheduler) o pasar a
  WAL archiving / PITR (documentado como evolución en F0 §3.1, no implementado).

No se oculta la brecha: el diseño actual garantiza RPO 0 ante caída de
proceso/contenedor (volumen íntegro), pero **no** ante pérdida del volumen sin
un backup reciente.
