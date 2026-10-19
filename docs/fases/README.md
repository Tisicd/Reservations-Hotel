# Fases del proyecto

| Fase | Fechas | Alcance | Compuerta de salida | Archivo |
|---|---|---|---|---|
| **F0** Arquitectura, negocio y resiliencia | 18–19 oct | ADR, estructura, capas, contratos, estados, matriz de fallos, RTO/RPO | **G0** | [F0](F0-negocio-y-resiliencia.md) |
| **F1** Flujo crítico | 19–21 oct | `availability`, `payment`, `reservation`, `customer`/`hotel` mínimos, chequeador de invariantes | Tests de concurrencia, idempotencia, pago, recuperación en verde | [F1](F1-flujo-critico.md) |
| **F2** Integración | 21–22 oct | `notification` + outbox/relay, gateway, réplicas de lectura, healthchecks | **G1** (jue 22, mediodía): decide RabbitMQ y congela alcance | *(se crea al iniciar)* |
| **F3** Frontend mínimo | 22 oct (timebox 4 h) | Una pantalla: buscar → reservar → resultado + línea de tiempo | Demo del flujo completo en el navegador | *(se crea al iniciar)* |
| **F4** Fallos, carga y reportes | 23–24 oct | Esc. A–D, E1–E4, k6, backup/restore, `make report` | Reportes con 5 preguntas y RTO/RPO medidos | *(se crea al iniciar)* |
| **F5** Documentación y entrega | 24–25 oct | Informe escrito, manual, costos, ensayo desde cero, tag `v1.0-entrega` | Tercero reproduce con el README | *(se crea al iniciar)* |
| **F6** Preparación de defensa | 26–29 oct | Entender cada prueba, banco de preguntas, guion de demo, ensayos de fallo | Defensa (28–30 oct, por confirmar) | [informe/defensa.md](../informe/defensa.md) |

**Regla:** cada fase termina con (1) tests en verde, (2) docs/ADR actualizados, (3) registro de tiempo/costos al día, (4) tag `fN` en Git.
