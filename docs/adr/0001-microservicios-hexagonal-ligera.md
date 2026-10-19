# ADR-0001: Microservicios con arquitectura hexagonal ligera
**Estado:** Aceptado · **Fase:** F0

## Contexto
El monolito mezcla funciones con riesgos distintos (inventario, reservas, pagos, notificaciones) y comparte recursos: una caída o un pico en una función degrada a las demás. El enunciado exige aislamiento, escalado independiente y recuperación ante fallos. Además hay 7 días, una persona y un agente de IA: la arquitectura debe ser **verificable**, no solo elegante.

## Decisión
- 6 microservicios (`customer`, `hotel`, `availability`, `reservation`, `payment`, `notification`), cada uno dueño exclusivo de su BD.
- Dentro de cada servicio con lógica de negocio real (`availability`, `reservation`, `payment`, `notification`): **hexagonal ligera** con 4 capas: `domain` · `application` · `infrastructure` · `api`.
- `customer` y `hotel`: **CRUD modular** (`api` + `service` + `models`), sin puertos ni capas adicionales.
- Regla de dependencia: `api` e `infrastructure` → `application` → `domain`. `domain` no importa frameworks. Se verifica automáticamente con `import-linter` en CI.
- **Ligera** significa: un puerto (`Protocol`) solo donde existe una frontera real con más de una implementación o un doble de prueba útil. Sin repositorios genéricos, sin Unit of Work, sin interfaces "por si acaso".
- Contratos HTTP explícitos entre servicios; **no se comparten modelos ni librerías de dominio**. Cada cliente HTTP declara sus propios DTO en `infrastructure/clients`.

## Alternativas descartadas
| Alternativa | Por qué no |
|---|---|
| Monolito modular | No cumple el aislamiento ni el escalado independiente exigidos; no permite demostrar fallos parciales |
| Hexagonal completa en los 6 servicios | Capas sin valor en CRUD; más código que probar y defender |
| Capas clásicas (controller/service/repo) | La lógica quedaría acoplada a FastAPI/SQL; la máquina de estados y la saga serían difíciles de probar sin BD |
| Librería compartida de modelos | Acopla despliegues y versiones; contradice la independencia de servicios |

## Consecuencias
(+) Saga y máquina de estados se prueban sin BD ni HTTP. (+) Arquitectura defendible y verificable por herramienta. (−) Más ficheros que un CRUD plano; se limita aplicando la regla de "puerto solo con frontera real". (−) Los DTO se duplican entre servicios: es el costo deliberado del desacoplamiento.
