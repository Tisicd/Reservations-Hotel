# Preparación de la defensa (26–29 oct; defensa 28–30 oct, por confirmar)

## Objetivo
Poder explicar **cada decisión y cada prueba** sin leer, y recuperarse si la demo falla.

## Plan por día
| Día | Foco | Salida |
|---|---|---|
| 26 | Entender las pruebas: ejecutar cada una, predecir el resultado **antes** de correrla, explicar por qué pasa | Tabla "prueba → qué demuestra → qué pasaría si falla" |
| 27 | Banco de preguntas (abajo) respondidas en voz alta y cronometradas | Respuestas de 1 min |
| 28 | Ensayo completo de la demo desde cero (`make clean && make up`) + plan B | Guion de 10 min |
| 29 | Ensayo de preguntas hostiles y de fallos en vivo | Lista de dudas cerradas |

## Banco de preguntas (a ampliar con lo que se implemente)
1. ¿Por qué microservicios y no un monolito modular? ¿Cuándo **no** lo recomendarías?
2. ¿Cómo garantizas que no hay sobreventa? ¿Qué pasa si dos usuarios reservan el último cupo?
3. ¿Qué es la idempotencia y dónde la aplicaste? ¿Qué pasa si el cliente reintenta?
4. ¿Qué pasa si el pago se cobra pero la respuesta se pierde?
5. ¿Qué es una saga? ¿Por qué orquestada? ¿Qué es una compensación?
6. ¿Qué es el outbox y qué problema resuelve? ¿Garantiza que no haya duplicados?
7. ¿Por qué un solo PostgreSQL? ¿Cuál es el riesgo? ¿Qué probaste?
8. ¿Escalar réplicas mejora la escritura? ¿Qué midieron las pruebas?
9. ¿Qué diferencia hay entre `docker stop` y `docker kill`? ¿Qué no simulan?
10. ¿Por qué hexagonal "ligera"? ¿Qué verifica `import-linter`?
11. ¿Qué cambiarías para producción? ¿Qué no resuelve Compose?
12. ¿Réplica de BD vs. backup vs. PITR?
13. ¿Qué haría Swarm/Kubernetes distinto?
14. ¿Cuáles son los costos y cómo escalarían?
15. ¿Qué hizo la IA y qué verificaste tú? ¿Cómo sabes que el código es correcto?

## Plan B de la demo
Video corto de la ejecución + capturas de reportes en `docs/resultados/` + datos semilla restaurables con `make restore`.
