"""Smoke del frontend servido por nginx (solo stdlib)."""

import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088").rstrip("/")
failures: list[str] = []


def fetch(path: str, method: str = "GET"):
    request = urllib.request.Request(f"{BASE}{path}", method=method)
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
    status, headers, body = fetch("/")
    check(status == 200, "GET / => 200")
    check("text/html" in headers.get("Content-Type", ""), "GET / => text/html")
    check(body.lstrip().lower().startswith(b"<!doctype html>"),
          "GET / empieza por <!doctype html>")

    for path, kind in (("/app.js", "javascript"), ("/styles.css", "text/css")):
        status, headers, _ = fetch(path)
        check(status == 200, f"GET {path} => 200")
        check(kind in headers.get("Content-Type", ""),
              f"GET {path} => Content-Type {kind}")

    _, headers, html = fetch("/")
    check("default-src 'self'" in headers.get("Content-Security-Policy", ""),
          "CSP default-src 'self'")
    check(headers.get("X-Content-Type-Options") == "nosniff", "nosniff")
    check(headers.get("X-Frame-Options") == "DENY", "X-Frame-Options DENY")
    check(headers.get("Referrer-Policy") == "no-referrer", "Referrer-Policy")
    check("no-cache" in headers.get("Cache-Control", ""), "Cache-Control no-cache")

    html_text = html.decode("utf-8", "replace").lower()
    check('style=' not in html_text, "sin estilos inline")
    check("<script>" not in html_text, "sin scripts inline")

    status, _, _ = fetch("/api/hotels")
    check(status == 200, "GET /api/hotels => 200 (listener publico)")
    status, _, _ = fetch("/svc/customer/health")
    check(status in (403, 404), "GET /svc/customer/health no expuesto")

    if failures:
        print(f"\n{len(failures)} fallo(s)")
        sys.exit(1)
    print("\nsmoke OK")


if __name__ == "__main__":
    main()
