"""Backup de las 6 bases del proyecto a backups/<timestamp>/ (git-ignored).

Uso: python scripts/backup.py
Requiere el stack levantado (postgres y redes). Usa `docker compose exec`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = [
    "docker", "compose",
    "-f", str(ROOT / "compose.yaml"),
    "-f", str(ROOT / "compose.dev.yaml"),
]
DATABASES = [
    "customer_db", "hotel_db", "availability_db",
    "payment_db", "reservation_db", "notification_db",
]


def dump(db: str) -> bytes:
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", "postgres",
         "pg_dump", "-U", "postgres", "-Fc", "-d", db],
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"pg_dump {db} fallo: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def main() -> int:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "backups" / stamp
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"created_at": stamp, "databases": {}}
    for db in DATABASES:
        data = dump(db)
        path = out / f"{db}.dump"
        path.write_bytes(data)
        manifest["databases"][db] = {
            "file": path.name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        print(f"  {db}: {len(data)} bytes")
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"backup en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
