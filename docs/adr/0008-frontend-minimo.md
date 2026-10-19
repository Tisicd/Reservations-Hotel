# ADR-0008: Frontend mínimo en HTML + JS servido por nginx
**Estado:** Aceptado · **Fase:** F3

## Contexto
Swagger prueba APIs, pero una demo visual facilita la defensa. El valor está en mostrar el flujo y los estados, no en el diseño. Plazo: 0,5 día máximo.

## Decisión
Una pantalla en **HTML + JavaScript sin build**, servida por el mismo nginx: (1) buscar hotel y fechas, (2) crear/seleccionar cliente demo, (3) reservar con selector de simulación de pago (`ok`, `decline`, `respuesta perdida`…), (4) mostrar el resultado con la **línea de tiempo de estados** (`GET /reservations/{id}/events`, con polling) y el estado de la notificación.

## Alternativas
React + TypeScript + Vite: válido, pero añade etapa Node, dependencias y tiempo sin aportar a los objetivos. Se reconsidera solo si la compuerta G1 deja holgura; **el contrato API no cambia**.

## Consecuencias
(+) Sin build ni dependencias. (−) Sin componentes ni tipos; aceptable para una pantalla.
