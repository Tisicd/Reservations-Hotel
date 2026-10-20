# Registro de tiempo y costos (se actualiza al cerrar cada día)

| Fecha | Fase | Horas | Qué se hizo | Herramientas de IA usadas | Costo directo (USD) |
|---|---|---|---|---|---|
| 2026-10-18 | F0 | | Análisis, ADR, contratos | | |
| 2026-10-19 | F1 · T1.1 availability | 0.5 | Servicio availability: dominio, store SQL, API, worker y contenedores | OpenCode (deepseek-v4.1-flash-free) | no medido |
| 2026-10-20 | F1 → T1.3 reservation | 0.6 | Servicio reservation: saga orquestada, máquina de estados, API idempotente, worker de reconciliación y contenedores | OpenCode (deepseek-v4.1-flash-free) | no medido |
| 2026-10-20 | F1 · T1.2 payment | 1.9 | Servicio payment: PASO 0 de infra, saga de pago, API, worker y contenedores | OpenCode (deepseek-v4.1-flash-free) | no medido |
| 2026-10-20 | F1 → cierre (T1.4-T1.6) | 3.1 | Plazo de CANCELLING, customer/hotel, siembra, chequeador I1-I7 y E2E; CI y docs | OpenCode (deepseek-v4.1-flash-free) | no medido |

**Horas:** medidas como intervalo entre el primer y el último commit de cada
tarea (marcas de tiempo de Git); no incluyen pausas no registradas. Las tarifas
y el costo directo quedan pendientes de definir.

**Supuestos:** tarifa de referencia junior = _(definir)_ USD/h · el costo de infraestructura se cotiza con precios publicados vigentes al redactar el informe, con fuente.
