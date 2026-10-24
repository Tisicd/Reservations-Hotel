#!/usr/bin/env python3
"""Comprueba que toda variable usada (servicios + compose) esté documentada."""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "variables.md"
SERVICES = ROOT / "services"


def code_vars() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in SERVICES.glob("*/app/**/*.py"):
        text = path.read_text(encoding="utf-8")
        names = set(re.findall(
            r'(?:getenv|environ\.get|_env)\s*\(\s*["\']([A-Z][A-Z0-9_]+)',
            text))
        names |= set(re.findall(
            r'environ\s*\[\s*["\']([A-Z][A-Z0-9_]+)', text))
        found.setdefault(path.parts[1], set()).update(names)
    return found


def compose_vars() -> set[str]:
    cmd = ["docker", "compose", "-f", "compose.yaml",
           "-f", "compose.dev.yaml", "config", "--format", "json"]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        out: set[str] = set()
        for service in data.get("services", {}).values():
            out |= set((service.get("environment") or {}).keys())
        return out
    # Fallback sin Docker: variables de los bloques environment.
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    out = set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]+):", text, re.MULTILINE))
    out |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", text))
    return out


def doc_vars() -> set[str]:
    text = DOCS.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|", text,
                          re.MULTILINE))


def main() -> None:
    code = code_vars()
    compose = compose_vars()
    docs = doc_vars()
    used = set().union(*code.values()) | compose
    missing = sorted(used - docs)
    extra = sorted(docs - used)

    for svc in sorted(code):
        absent = sorted(code[svc] - docs)
        if absent:
            print(f"  {svc}: faltan en docs/variables.md: {absent}")
    if compose - docs:
        print(f"  compose: faltan en docs/variables.md: {sorted(compose - docs)}")
    if extra:
        print(f"  aviso: documentadas no usadas por servicios/compose "
              f"({len(extra)}): {extra}")

    if missing:
        print(f"check-docs FALLA: {len(missing)} variable(s) sin documentar")
        sys.exit(1)
    print(f"check-docs OK: {len(used)} variables usadas, todas documentadas")


if __name__ == "__main__":
    main()
