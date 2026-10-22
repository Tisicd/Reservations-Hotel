# F4a — Auditoría de evidencia (FASE 1)

Fecha: 2026-10-21 · Rama: `feat/f4a-caos` · Contrato: `docs/prompts/F4a-caos.md`

> Regla de esta auditoría: cada afirmación "hecho" lleva el comando ejecutado y su
> salida, o `archivo:línea`. Lo que no existe se marca ✘.

## Estado de Git (PASO 0)

```
$ git log --oneline -6 feat/f4a-caos
762f17d test(chaos): escenario E2 y arnes completo (A-D,E2,S)
68a827b test(chaos): F2 - escenarios C y D
e76e62d test(chaos): hito 1 - arnes de caos y escenarios A y B
f0f57f1 chore: base para caos
0a69c6a chore(docker): Phase 2 - control construction of images
89e1c6b docs: diagnóstico de imágenes Docker

$ git log --oneline -2 main
0a69c6a chore(docker): Phase 2 - control construction of images
89e1c6b docs: diagnóstico de imágenes Docker

$ git log --oneline -2 chore/docker-imagenes
0a69c6a chore(docker): Phase 2 - control construction of images
89e1c6b docs: diagnóstico de imágenes Docker
```

- La rama de imágenes (`main` = `chore/docker-imagenes`) contiene **solo** trabajo de
  imágenes (0a69c6a).
- El caos vive en `feat/f4a-caos` (f0f57f1…762f17d). El commit HEAD estaba mal
  titulado (`feat(docker-imagenes)…`) aunque solo contenía archivos de caos; se
  corrigió el mensaje con `git commit --amend` (hash 276460c → 762f17d). No se
  perdió ningún commit.

## Tabla requisito → estado → evidencia

| # | Requisito (F4a-caos.md) | Estado | Evidencia |
|---|---|---|---|
| 1 | `make test` ≥ 251 pasadas y 0 omitidas | ✔ | `make test` → `13+45+63+18+21+63+11+17 = 251 passed`, sin `skipped` ni `failed` |
| 1b | `OUTBOX_BACKLOG_OLD` implementada **y probada** | parcial | Implementada: `tests/invariants/checker.py:28,341-360,457`; conectada en `check_all`. **No hay prueba unitaria específica** de la alarma en `tests/invariants/test_checker.py` (solo `TRUNCATE notifications`) |
| 2 | `Stack`: kill/stop/start/exec_kill9/wait_healthy/restart_count/health_log/ps_snapshot | ✔ | `tests/chaos/harness.py:245,276,285,199,292` (`exec_kill9`, `wait_healthy`, `restart_count`, `container_health_log`, `ps_snapshot`) |
| 2b | Acción sobre **una** réplica de `availability` | ✔ | `tests/chaos/harness.py:700-710`: `cids[0]` + `container=cid` en `FaultSpec` |
| 2c | `recreate(svc)` = `rm -sf` + `up -d --no-build` | ✘ | No existe: `Select-String 'recreate|rm -sf'` en `harness.py` → 0 resultados |
| 2d | `TrafficGenerator` modo crudo y con reintentos (misma Idempotency-Key) | ✔ | `harness.py:366-499`; `self.mode` usado en `:451,459`; clave única por petición y reutilizada en reintentos |
| 2e | `Canary` lectura y escritura | ✔ | `harness.py:501-585` (`_probe_read`, `_probe_write`) |
| 2f | `compute_outage_windows` | ✔ | `harness.py:587-620` |
| 2g | Fases baseline→falla→recuperación→cola | ✔ | `harness.py:806-816` (A/B); C/D usan construcción→reinicio→espera |
| 2h | Finalizer restaura el stack | ✔ | `harness.py:872-884` (A/B), `:1030-1040` (C), `:1310-1322` (E2) |
| 2i | Cierre con invariantes y `assert_no_loss` | ✔ | `harness.py:859-860`, `:1002-1003`, `:1291-1292`, `:1449-1455` |
| 3 | Pruebas unitarias del propio arnés | ✘ | `pytest tests/chaos/test_harness.py` → **ImportError: cannot import name 'classify_error'**; el arnés define `_classify_error` (`harness.py:315`) |
| 4 | Escenario A con aserciones duras | ✔ | `run_scenario` (`:760`): éxito falla ≥ baseline−1 pp, outbox backlog, invariantes, no pérdida. Informe `docs/resultados/chaos_A_api_1.md`, `chaos_A_worker_1.md` |
| 4 | Escenario B | ✔ | `_fault_spec` modos `kill`/`kill9` (`:706-710`). Informes `chaos_B_kill_1.md`, `chaos_B_kill9_1.md` |
| 4 | Escenario C | ✔ | `run_scenario_C` (`:930`): reservas CONFIRMED, 1 cargo, 0 holds duplicados. Informes `chaos_C_kill9_1.md`, `chaos_C_stop_1.md` |
| 4 | Escenario D | ✔ | `run_scenario_D` (`:1082`): no pérdida, RestartCount sin cambios, 503. Informe `chaos_D_stop_1.md` |
| 4 | Escenario E2 | parcial | `run_scenario_E2` (`:1224`) existe y **sondea hasta 150 s**, pero las reservas `process_then_drop_response` no llegan todas a `CONFIRMED`: `chaos_E2_drop_1.md` → `todas_las_reservas_estables: no`, `un_cargo_por_reserva: no`, `hard_fail=True` |
| 4 | Escenario S | ✘ | `run_scenario_S` (`:1365`) existe pero **falla en ejecución**: `errors_2xx` no está definida (solo `errors_503`) y `hard_fail_reason`/`close_error` no se inicializan. **No hay** `chaos_S_*.md` |
| 5 | Informes con las 5 preguntas **con cifras** | parcial | A/B/C/D/E2 tienen sección "Las 5 preguntas", pero las respuestas 1–2 remiten a la tabla ("ver tabla de métricas") sin cifras explícitas. RTO medido vs objetivo y `cumplido: sí/no` **sí** están |
| 5b | Informe de S | ✘ | No existe (S no ejecuta) |
| 6 | `make chaos`, `SCEN`, `REPEAT`, precondición | ✔ | `Makefile:35-43`; `SCEN ?= all`, `REPEAT ?= 1`; precondición en `harness.py:301-311` + `main()` la aplica |
| 7 | `docs/fallos.md` (esqueleto) | ✘ | `Test-Path docs/fallos.md` → `False` |
| 7b | `docs/proceso/modos-de-caida.md` actualizado | ✔ | Existe y describe modos A/B y healthchecks |
| 7c | `docs/03-estado-del-proyecto.md` actualizado | ✘ | Sigue diciendo `F4 Fallos, carga y reportes | Pendiente`; comandos listan `chaos` solo como "F4 añade" |
| 8 | `make images`: 0 imágenes nuevas tras la batería | pendiente | Requiere ejecutar `make clean-all && make build && make up && make seed && make chaos REPEAT=3`; se verifica en FASE 2 y se registra en el informe de cierre |

## Conclusión de la auditoría

Lo implementado y verificado: arnés base (Stack, tráfico, canario, ventanas, fases,
finalizer, invariantes/no pérdida), precondición, `make chaos`, escenarios A–D con
informes y RTO vs objetivo.

Brechas reales a completar en FASE 2:

1. `classify_error` no exportado → las pruebas unitarias del arnés no corren.
2. Falta `recreate(svc)` y `health_log(svc)` a nivel de servicio.
3. Escenario S no ejecuta (variables sin inicializar) y no tiene informe.
4. E2 no converge a `CONFIRMED` (se analiza en FASE 3).
5. Las 5 preguntas de los informes no llevan cifras explícitas.
6. Falta `docs/fallos.md`; `docs/03-estado-del-proyecto.md` sin actualizar.
7. `OUTBOX_BACKLOG_OLD` sin prueba unitaria específica.
