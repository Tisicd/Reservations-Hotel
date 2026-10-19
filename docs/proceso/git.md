# Proceso de trabajo en Git

- **Ramas:** `main` siempre ejecutable. Trabajo en `feat/<fase>-<tema>` (p. ej. `feat/f1-availability-holds`), `fix/…`, `docs/…`.
- **Commits (Conventional Commits):** `feat(availability): hold atómico con CHECK`, `test(reservation): crash entre pasos`, `docs(adr): ADR-0005 aceptado`, `chore(ci): import-linter`.
- **Pull requests** (aunque trabajes solo): uno por tarea (T1.1…), con la plantilla del repo. CI debe pasar: ruff, import-linter, tests.
- **Docs como código:** todo cambio de arquitectura/contrato incluye su ADR o actualización de doc **en el mismo PR**.
- **Tags:** `f0`, `f1`, … al cerrar cada fase; `v1.0-entrega` el 25 oct.
- **Secretos:** nunca en Git (`.env` ignorado; `.env.example` sí). Revisar con `gitleaks` en CI.
- **Trabajo con el agente (OpenCode):** una tarea por sesión; el prompt incluye el ID de tarea, archivos permitidos y el test de aceptación; **tú revisas el diff y ejecutas los tests antes de fusionar**.
