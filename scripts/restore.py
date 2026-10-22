"""Restaura las 6 bases desde un directorio de backup.

Uso: python scripts/restore.py backups/<timestamp>
Detiene servicios de aplicacion y workers (no postgres), restaura cada BD con
el rol dueno correcto (`pg_restore --clean --if-exists --no-owner`), verifica
`alembic_version` y vuelve a levantar el stack. Cronometra el proceso.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = [
    "docker", "compose",
    "-f", str(ROOT / "compose.yaml"),
    "-f", str(ROOT / "compose.dev.yaml"),
]
# (base, rol dueno). Se restaura conectando como el rol dueno.
DATABASES = [
    ("customer_db", "customer"),
    ("hotel_db", "hotel"),
    ("availability_db", "availability"),
    ("payment_db", "payment"),
    ("reservation_db", "reservation"),
    ("notification_db", "notification"),
]
APP_SERVICES = [
    "gateway", "customer", "hotel", "availability", "availability-worker",
    "payment", "payment-worker", "reservation", "reservation-worker",
    "reservation-relay", "notification", "notification-worker",
]


def run(cmd: list[str], input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=input_bytes, capture_output=True)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python scripts/restore.py backups/<timestamp>", file=sys.stderr)
        return 2
    backup_dir = pathlib.Path(argv[1])
    if not backup_dir.is_dir():
        print(f"no existe el directorio {backup_dir}", file=sys.stderr)
        return 2
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        print("falta manifest.json en el backup", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    started = time.monotonic()
    print("deteniendo servicios de aplicacion (postgres sigue arriba)...")
    run([*COMPOSE, "stop", *APP_SERVICES])

    for db, role in DATABASES:
        entry = manifest["databases"].get(db)
        if not entry:
            raise SystemExit(f"el backup no contiene {db}")
        data = (backup_dir / entry["file"]).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            raise SystemExit(f"checksum invalido para {db}")
        print(f"  restaurando {db} como {role}...")
        result = run(
            [*COMPOSE, "exec", "-T", "postgres",
             "pg_restore", "--clean", "--if-exists", "--no-owner",
             "-U", role, "-d", db],
            input_bytes=data,
        )
        if result.returncode != 0:
            raise SystemExit(
                f"pg_restore {db} fallo: {result.stderr.decode(errors='replace')}"
            )

    print("verificando versiones de migracion (alembic_version)...")
    for db, role in DATABASES:
        result = run(
            [*COMPOSE, "exec", "-T", "postgres",
             "psql", "-U", role, "-d", db, "-tAc",
             "select version_num from alembic_version"],
        )
        version = result.stdout.decode(errors="replace").strip() or "n/a"
        print(f"  {db}: {version}")

    print("levantando servicios...")
    result = run([*COMPOSE, "up", "-d", "--no-build", "--wait"])
    if result.returncode != 0:
        raise SystemExit(f"up fallo: {result.stderr.decode(errors='replace')}")

    elapsed = time.monotonic() - started
    print(f"restore completado en {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
