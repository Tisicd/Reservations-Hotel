# CASO 2: Plataforma de reservas basada en microservicios con alta disponibilidad

**Universidad Central del Ecuador** · Facultad de Ingeniería y Ciencias Aplicadas · Carrera de Sistemas de Información

| Campo | Valor |
|---|---|
| Componente | Algoritmos, Programación y Datos |
| Subcomponente | Programación distribuida |
| Tema específico | Patrones de diseño y tecnología |

> Nota de transcripción: el numeral "Entregable" aparece como **12** en el original (repetido tras "Documentar la solución" = 13). Aquí se numera como **14** para evitar ambigüedad.

---

## A. Objetivo del caso de estudio
Desarrollar una plataforma distribuida de reservas utilizando **Docker** y una **arquitectura de microservicios**, enfocándose en: **disponibilidad, escalabilidad, aislamiento de componentes, persistencia y recuperación ante fallos**.

El estudiante deberá demostrar cómo los contenedores pueden utilizarse para construir una plataforma distribuida capaz de **mantener sus principales funcionalidades ante fallos individuales**.

## B. Contexto o situación
Una empresa administra una plataforma de reservas para hoteles y establecimientos turísticos. Hoy es un **sistema monolítico** que administra: Clientes, Hoteles, Habitaciones, Disponibilidad, Reservas, Pagos, Confirmaciones, Notificaciones.

En temporadas de alta demanda hay problemas porque todas las funcionalidades usan los mismos recursos:
- Muchas consultas de disponibilidad afectan el procesamiento de reservas.
- Si el componente de notificaciones falla, toda la aplicación se degrada.

La empresa quiere una nueva plataforma con **microservicios y Docker** que aísle funcionalidades y facilite su **escalamiento independiente**.

## C. Instrucciones detalladas
El estudiante deberá:

### 1. Analizar los requerimientos
- Identificar los procesos principales del sistema.
- Determinar los componentes que pueden convertirse en servicios independientes.
- Identificar qué servicios son críticos para la operación.
- Clasificar los servicios según su necesidad de disponibilidad.

### 2. Diseñar los microservicios
La solución deberá contemplar: `customer-service`, `hotel-service`, `availability-service`, `reservation-service`, `payment-service`, `notification-service`.

### 3. Diseñar la arquitectura de comunicación
- Crear una arquitectura basada en servicios independientes.
- Implementar una **red Docker definida por el usuario**.
- Establecer la comunicación entre servicios.
- Definir claramente qué servicio puede comunicarse con cada componente.
- Evitar exponer innecesariamente servicios internos al exterior.

### 4. Contenerizar la plataforma
- Crear una imagen Docker para cada microservicio.
- Optimizar los Dockerfiles.
- Evitar incluir archivos innecesarios en las imágenes.
- Aplicar **Multistage Build** cuando corresponda.
- Documentar las decisiones adoptadas para optimizar las imágenes.

### 5. Implementar configuración externa
- Evitar almacenar configuraciones específicas del entorno directamente en el código.
- Utilizar **variables de entorno**.
- Documentar las variables requeridas por cada servicio.

### 6. Implementar persistencia
- Determinar qué servicios requieren almacenamiento.
- Configurar **volúmenes** para la información crítica.
- Simular la eliminación de un contenedor y verificar que la información persistente pueda recuperarse.
- Explicar la diferencia entre información persistente y efímera.

### 7. Implementar alta disponibilidad
- Identificar los servicios que representan puntos críticos.
- Ejecutar **múltiples instancias** de los servicios seleccionados.
- Proponer una **estrategia de distribución de solicitudes**.
- Simular la caída de una instancia.
- Analizar si el servicio continúa disponible.

### 8. Implementar mecanismos de salud
- Incorporar **HEALTHCHECK**.
- Definir qué condiciones determinan que un servicio esté saludable.
- Simular un servicio no saludable.
- Documentar cómo Docker identifica dicha condición.

### 9. Simular escenarios de fallo
Mínimo, ejecutar:
- **Escenario A:** caída del servicio de notificaciones.
- **Escenario B:** caída de una instancia del servicio de disponibilidad.
- **Escenario C:** reinicio del servicio de reservas.
- **Escenario D:** eliminación y recreación de un contenedor que utiliza información persistente.

Para **cada escenario** determinar:
- ¿Qué componentes resultan afectados?
- ¿Qué componentes continúan funcionando?
- ¿Qué información se pierde?
- ¿Cómo se recupera el servicio?
- ¿Qué mecanismo podría mejorar la resiliencia?

### 10. Implementar orquestación
- Utilizar **Docker Compose** para definir el entorno completo.
- Definir servicios, redes, volúmenes y configuraciones.
- Analizar posteriormente cómo la solución podría evolucionar hacia **Docker Swarm**.
- Identificar qué componentes serían candidatos para utilizar **réplicas**.

### 11. Realizar pruebas de rendimiento
- Generar solicitudes concurrentes sobre el servicio de disponibilidad.
- Medir tiempos de respuesta.
- Comparar el comportamiento con **una y varias instancias**.
- Identificar posibles cuellos de botella.

### 12. Analizar seguridad
- Determinar qué servicios deben estar expuestos externamente.
- Mantener los servicios internos dentro de redes apropiadas.
- Evitar almacenar credenciales directamente en las imágenes.
- Proponer mecanismos para administrar información sensible.

### 13. Documentar la solución
- Arquitectura de microservicios.
- Diseño de persistencia.
- Dockerfiles.
- Archivo `compose.yaml`.
- Estrategia de alta disponibilidad.
- Resultados de pruebas.
- Análisis de fallos.

### 14. Entregable
Solución funcional en la que los principales componentes del comercio electrónico puedan **ejecutarse como contenedores independientes, comunicarse mediante una red Docker y mantener la información mediante almacenamiento persistente**.

Debe permitir ejecutar la plataforma como conjunto de microservicios Docker independientes, con: comunicación mediante redes Docker, persistencia para datos críticos, mecanismos de salud y **una estrategia demostrable de recuperación ante fallos**. Se debe demostrar mediante pruebas que **la falla de un componente no implica necesariamente la interrupción completa de la plataforma**.

---

## Anexo de trazabilidad (14 puntos)

| # | Requisito | Evidencia concreta | ✔ |
|---|---|---|---|
| 1 | Análisis de requerimientos | `docs/fases/F0-negocio-y-resiliencia.md` (procesos, invariantes I1–I7, criticidad), `docs/04-arquitectura.md`; no existe `01-analisis.md` (se usó F0) | ✔ |
| 2 | 6 microservicios | `services/{customer,hotel,availability,reservation,payment,notification}/`, `compose.yaml`, `docs/04-arquitectura.md` | ✔ |
| 3 | Red Docker definida por el usuario y exposición mínima | `compose.yaml` (`edge-net`, `backend-net`/`data-net` internas), `docs/seguridad.md`; `tests/infra/test_gateway.py`, `tests/e2e/test_public_flow.py` | ✔ |
| 4 | Imágenes optimizadas y multistage | Dockerfiles de `services/*`; `docs/imagenes.md` (174–176 MB, monoetapa 198 MB, contexto 1,73 vs 60,76 kB) | ✔ |
| 5 | Configuración externa y variables documentadas | `.env.example`, `docs/variables.md`, `scripts/check_vars.py`, `make check-docs` (62 usadas, todas documentadas) | ✔ |
| 6 | Persistencia y demostración de borrado/recreación | `compose.yaml` volumen `pgdata`; `chaos_D_stop_1.md` (recreación real), `chaos_E1_*.md`, `chaos_E3_*.md`; `proceso/backup-restore.md`; ADR-0002 | ✔ |
| 7 | Múltiples instancias y balanceo | `availability` x3 (`perf_P1.md`, `perf_P1_analisis.md`), `chaos_B_kill_*.md`; ADR-0007 (DNS/upstream) | ✔ |
| 8 | HEALTHCHECK y servicio no saludable | Dockerfiles/compose (`interval=5s timeout=5s retries=12`), `chaos_S_stop_1.md` (TTD 93,21 s), `chaos_S2_stop_1.md` | ✔ |
| 9 | Escenarios A–D con las 5 preguntas | `chaos_A_api_*.md`, `chaos_A_worker_*.md`, `chaos_B_*.md`, `chaos_C_*.md`, `chaos_D_stop_1.md`, `docs/fallos.md` | ✔ |
| 10 | Docker Compose y análisis de Swarm | `compose.yaml`, `compose.dev.yaml`, `docs/swarm.md` (no implementado; análisis y fragmento ilustrativo) | ✔ |
| 11 | Pruebas de rendimiento 1 vs N y cuellos | `perf_P1.md`/`perf_P1_analisis.md` (189→394 rps, 2,09×), `perf_P3.md`, `perf_P3b.md`, `perf_P4.md`, `REPORTE.md` | ✔ |
| 12 | Análisis de seguridad | `docs/seguridad.md`; `tests/e2e/test_public_flow.py` (rutas internas 403/404); `perf_P4.md` (141/45 429); `resultados/seguridad-trivy.txt` (47 HIGH/0 CRITICAL), gitleaks 0 | ✔ |
| 13 | Documentación de la solución | `docs/` (arquitectura, ADR, contratos, manual, seguridad, producción, swarm, imágenes, variables), `README.md`, `docs/informe/INFORME.md` | ✔ |
| 14 | Entregable funcional | `make build && make up && make seed`, `make e2e` (11 pruebas), `make smoke`, `make invariants`; ensayo desde cero en `docs/resultados/ensayo-desde-cero.md` | ✔ |

**Nota:** la columna ✔ significa que existe el archivo **y** se ejecutó el
comando o prueba que lo respalda en este repositorio (local/CI). Lo que no se
pudo ejecutar se declara en `RELEASE.md` y en el propio informe.
