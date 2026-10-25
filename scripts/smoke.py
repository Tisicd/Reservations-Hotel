"""Smoke del frontend servido por nginx (solo stdlib)."""

import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088").rstrip("/")
MAX_BYTES = 150_000
JS_FILES = [
    "/app.js", "/js/api.js", "/js/ui.js", "/js/router.js",
    "/js/screens.js", "/js/demo.js", "/js/state.js", "/js/auth.js",
]
failures: list[str] = []
total_bytes = 0


def fetch(path: str) -> tuple[int, dict, bytes]:
    request = urllib.request.Request(f"{BASE}{path}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  OK  {message}")
    else:
        failures.append(message)
        print(f" FAIL {message}")


def main() -> None:
    global total_bytes
    status, headers, body = fetch("/")
    check(status == 200, "GET / => 200")
    check("text/html" in headers.get("Content-Type", ""), "GET / => text/html")
    check(body.lstrip().lower().startswith(b"<!doctype html>"),
          "GET / empieza por <!doctype html>")
    total_bytes += len(body)
    html = body.decode("utf-8", "replace").lower()
    check("style=" not in html, "sin estilos inline")
    check(re.search(r"<script(?!\s[^>]*src=)", html) is None, "sin scripts inline")
    check("<style" not in html, "sin bloques <style> inline")
    check(re.search(r'(?:src|href)\s*=\s*["\']https?:', html) is None,
          "sin recursos externos en el HTML")

    for path in JS_FILES:
        status, headers, content = fetch(path)
        total_bytes += len(content)
        check(status == 200, f"GET {path} => 200")
        check("javascript" in headers.get("Content-Type", ""),
              f"GET {path} => Content-Type JavaScript")
    status, headers, css = fetch("/styles.css")
    total_bytes += len(css)
    check(status == 200, "GET /styles.css => 200")
    check("text/css" in headers.get("Content-Type", ""),
          "GET /styles.css => text/css")

    _, headers, _ = fetch("/")
    check("default-src 'self'" in headers.get("Content-Security-Policy", ""),
          "CSP default-src 'self'")
    check(headers.get("X-Content-Type-Options") == "nosniff", "nosniff")
    check(headers.get("X-Frame-Options") == "DENY", "X-Frame-Options DENY")
    check(headers.get("Referrer-Policy") == "no-referrer", "Referrer-Policy")
    check("no-cache" in headers.get("Cache-Control", ""), "Cache-Control no-cache")

    for path in JS_FILES + ["/styles.css"]:
        _, _, content = fetch(path)
        text = content.decode("utf-8", "replace")
        text = text.replace("http://www.w3.org/2000/svg", "")
        check(re.search(r"https?://", text) is None,
              f"{path} sin URLs externas")
        if path.endswith(".js"):
            check(re.search(r"\.innerHTML\s*=", text) is None,
                  f"{path} sin innerHTML con datos")

    check(total_bytes <= MAX_BYTES,
          f"estáticos <= 150 kB (actual {total_bytes} bytes)")

    status, _, _ = fetch("/api/hotels")
    check(status == 200, "GET /api/hotels => 200 (listener publico)")
    status, _, _ = fetch("/svc/customer/health")
    check(status in (403, 404), "GET /svc/customer/health no expuesto")

    if failures:
        print(f"\n{len(failures)} fallo(s)")
        sys.exit(1)
    print(f"\nsmoke OK ({total_bytes} bytes de estáticos)")


if __name__ == "__main__":
    main()
