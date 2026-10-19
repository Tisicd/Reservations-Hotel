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

## Checklist de trazabilidad (requisito → evidencia)

| # | Requisito | Evidencia esperada |
|---|---|---|
| 1 | Análisis de requerimientos | `docs/01-analisis.md` (procesos, criticidad, clasificación) |
| 2 | 6 microservicios | carpetas `services/*` |
| 3 | Red definida por el usuario, exposición mínima | `compose.yaml` (redes) + `docs/arquitectura.md` |
| 4 | Imágenes optimizadas, multistage | Dockerfiles + `docs/imagenes.md` (tamaños) |
| 5 | Config externa | `.env.example` + tabla de variables por servicio |
| 6 | Persistencia + demo de borrado | volúmenes + test automatizado escenario D |
| 7 | Múltiples instancias + balanceo | `availability-service` x N tras balanceador |
| 8 | HEALTHCHECK | healthchecks en Dockerfile/compose + test servicio no saludable |
| 9 | Escenarios A-D con 5 preguntas c/u | tests automatizados + `docs/fallos.md` |
| 10 | Compose + análisis Swarm | `compose.yaml` + `docs/swarm.md` |
| 11 | Pruebas de rendimiento 1 vs N | script de carga + tabla de resultados |
| 12 | Seguridad | `docs/seguridad.md` + secrets/env |
| 13 | Documentación | carpeta `docs/` + README |
| 14 | Entregable funcional | `docker compose up` levanta todo |
