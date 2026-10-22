# F4a — Cierre: protocolo, tabla resumen y hallazgos

Fecha: 2026-10-22 · Rama: `feat/f4a-caos` · Contrato: `docs/prompts/F4a-caos.md`

## Protocolo ejecutado

```
make clean-all
make build
make up          # ver nota: seed requiere puertos dev -> se usó make up-dev
make seed
make chaos REPEAT=3
```

**Nota de entorno (con evidencia):** `make up` no publica el puerto admin 8081;
`make seed` usa `ADMIN_URL=127.0.0.1:8081` y falló con
`No se pudo conectar a http://127.0.0.1:8081/svc/hotel/hotels`. Se ejecutó
`make up-dev` (publica 8081/8088) y después `make seed`. El arnés y el seed
dependen del perfil dev; conviene documentarlo o publicar solo el admin en local.

Salida final: **27/27 ejecuciones con `hard_fail=False`**. `make invariants` →
`OK: 0 violaciones`. Stack final `healthy`. `make images`: **0 imágenes nuevas**
(IDs idénticos antes/después; `Compare-Object` sin diferencias).

## Tabla resumen (REPEAT=3)

| Escenario | Integridad (invariantes + no pérdida) | RTO medido (s) r1/r2/r3 | Objetivo | ¿Cumplido? | Reps consistentes | Hallazgo |
|---|---|---|---|---|---|---|
| A / api | OK | 0.64 / 0.72 / 0.64 | 300 s | sí | sí | fail-open: reservas al 100 % |
| A / worker | OK | 1.18 / 1.17 / 0.81 | 300 s | sí | sí | backlog 3–4 → 0 tras volver |
| B / kill | OK | **2.42** / 0.36 / 0.33 | 2 s | r1 **no**, r2–r3 sí | **parcial** | 1ª caída tras arranque más lenta (2.42 s) |
| B / kill9 | OK | 0.21 / 0.21 / 0.20 | 2 s | sí | sí | raw 96.4 % vs reintento 100 % |
| C / kill9 | OK | 6.84 / 6.77 / 7.17 | 30 s | sí | sí | 20/20 CONFIRMED, 1 cargo |
| C / stop | OK | 15.48 / 15.30 / 14.85 | 30 s | sí | sí | 20/20 CONFIRMED, 1 cargo |
| D / stop | OK | 0.08 / 0.06 / 0.06 | 120 s | sí | sí | 503 fail-closed, sin reinicios |
| E2 / drop | OK | n/a (síncrona) | 30 s | sí (estado final) | sí | 20/20 CONFIRMED, 0 MANUAL_REVIEW |
| S / stop | OK | 0.11 / 0.12 / 0.14 | 30 s | sí | sí | TTD≈0.08–0.1 s; Health.Log en informe |

RTO "n/a" en E2: la API es síncrona (`SAGA_SYNC_WAIT_SECONDS=5`); al responder
201 la reserva ya está `CONFIRMED`. Se reporta el tiempo a estado final en el
informe E2.

## Hallazgos (sin ocultar)

1. **B/kill repetición 1: RTO 2.42 s > objetivo 2 s.** Las repeticiones 2–3
   bajan a ~0.33–0.36 s. Posible causa: primera detección/expulsión de la réplica
   por nginx tras el arranque. Se reporta como incumplimiento puntual, no se
   ajusta el objetivo.
2. **E2: límite `limit_conn conn 10` del gateway.** 20 solicitudes concurrentes
   → 10×201 y 10×503 (nginx). No es un defecto de reconciliación ni un atasco en
   `PAYMENT_UNKNOWN` (ver `docs/resultados/chaos_E2_hallazgo.md`). Se retira la
   atribución previa al `pip install`.
3. **Documentación del protocolo:** `make up` + `make seed` no funciona en limpio
   porque el seed necesita el puerto admin dev (8081). Usar `make up-dev` o
   publicar el admin en local.

## Correcciones al arnés (no para "hacer pasar" pruebas)

- Exportar `classify_error` (las pruebas unitarias del arnés fallaban por
  `ImportError`).
- Añadir `recreate(svc)` y `health_log(svc)`.
- Definir `snapshot_before` en E2 (antes: `NameError`).
- Noches únicas por ejecución en C y E2 (antes: inventario agotado →
  `REJECTED_NO_INVENTORY`, no un defecto del pago).
- Inicializar `hard_fail_reason`/`close_error` en D y S.
- Escenario S: contar 2xx durante la caída, medir TTD y adjuntar `Health.Log`;
  el `RestartCount` pasa a informativo (es una aserción de D, no de S).
- B: comparación crudo vs reintento (raw 96.4 %, retry 100 %) y aserción de
  reintento ≥ 99 %; la aserción "éxito ≥ baseline−1 pp" queda **solo para A**
  (en B es esperable una caída transitoria al matar una réplica).
- Informes: las 5 preguntas ahora incluyen cifras (éxito %, errores, p95,
  pendientes del outbox, RTO).
