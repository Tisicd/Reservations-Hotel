"""Estado de las imagenes Docker del proyecto.

Uso:
  python scripts/docker_images.py          # tabla de imagenes + huerfanas
  python scripts/docker_images.py --check  # falla si falta alguna imagen :local
"""

import subprocess
import sys

PROJECT = "reservas-platform"
COMPOSE_LABEL = f"com.docker.compose.project={PROJECT}"
SERVICES = ["customer", "hotel", "availability", "payment", "reservation", "notification"]


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def image_exists(name: str) -> bool:
    return docker("image", "inspect", f"{name}:local").returncode == 0


def check() -> int:
    missing = [s for s in SERVICES if not image_exists(s)]
    if missing:
        print(
            "Faltan imagenes del proyecto: " + ", ".join(f"{s}:local" for s in missing),
            file=sys.stderr,
        )
        print("Ejecuta 'make build' para construirlas.", file=sys.stderr)
        return 1
    return 0


def table() -> int:
    print("Imagenes del proyecto")
    print("-" * 72)
    result = docker(
        "images",
        "--filter",
        f"label={COMPOSE_LABEL}",
        "--format",
        "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}",
    )
    for line in result.stdout.splitlines():
        repo, image_id, size, age = line.split("\t")
        print(f"{repo:<28} {image_id:<14} {size:>10}  {age}")

    dangling = docker(
        "images",
        "--filter",
        "dangling=true",
        "--filter",
        f"label={COMPOSE_LABEL}",
        "--format",
        "{{.ID}} {{.Size}}",
    ).stdout.splitlines()
    print()
    print(f"Huerfanas (dangling) del proyecto: {len(dangling)}")
    for line in dangling:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else table())
