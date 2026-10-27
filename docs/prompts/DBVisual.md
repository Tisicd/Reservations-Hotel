# Tarea: preparar la inspección visual y las evidencias de las bases de datos de reservas-platform

Actúa como ingeniero senior de bases de datos, arquitectura de microservicios y documentación técnica para una defensa universitaria.

## Objetivo

Inspecciona el proyecto completo y prepara los recursos necesarios para visualizar las seis bases de datos PostgreSQL, explicar su estructura y generar evidencias fiables para el informe y la presentación del proyecto.

El repositorio es la fuente de verdad. Aprovecha el contexto del código, las migraciones o scripts SQL, Docker Compose, pruebas, documentación y configuración existentes.

## Fase 1. Inspección sin modificaciones

1. Revisa `git status`, la estructura del repositorio, `docker-compose` o archivos Compose, configuración PostgreSQL, inicialización, scripts SQL, migraciones, modelos, repositorios, servicios y documentación.
2. Identifica las seis bases de datos reales, sus tablas, columnas, tipos, claves primarias, claves foráneas, restricciones, índices y secuencias.
3. Comprueba cómo se inicializan y persisten las bases de datos, qué puertos se publican y qué comandos de inspección ya existen.
4. Distingue las relaciones físicas dentro de cada base de datos de las referencias lógicas entre microservicios.
5. Identifica los datos que podrían contener información sensible y las precauciones necesarias para las capturas.
6. No supongas nombres de tablas o columnas: verifícalos en el esquema real.
7. Presenta un diagnóstico breve y un plan de ejecución antes de realizar cambios.

## Fase 2. Inspección del esquema real

Si el entorno está levantado, utiliza consultas de solo lectura para contrastar el esquema documentado con PostgreSQL. Si no está levantado, inspecciona los archivos fuente y prepara comandos reproducibles sin iniciar servicios innecesariamente.

Obtén, cuando sea posible:
- Inventario de bases de datos y tablas.
- Columnas, tipos y nulabilidad.
- Claves primarias y foráneas.
- Índices y restricciones.
- Tamaño de las bases de datos.
- Conteos agregados de registros útiles para demostrar el funcionamiento.

No ejecutes operaciones de escritura, reinicios destructivos, limpieza de volúmenes ni migraciones sobre los datos existentes. No interfieras con las pruebas ni con los workers en ejecución.

## Fase 3. Preparación de documentación y diagramas

Crea una carpeta de documentación nueva y coherente con la estructura existente, por ejemplo `docs/database-evidence/`, salvo que el proyecto ya tenga una ubicación apropiada.

Prepara:

1. `README.md`: guía de inspección y visualización.
2. Un inventario real de las seis bases de datos.
3. Un archivo SQL de solo lectura con consultas de demostración verificadas contra el esquema real.
4. DDL o scripts de extracción del esquema, sin credenciales ni datos personales.
5. Un diagrama ER por base de datos, siempre que se pueda generar con herramientas disponibles.
6. Un diagrama lógico global que muestre los seis servicios, sus bases de datos y las referencias entre ellos. No inventes claves foráneas entre bases separadas.
7. Una guía para abrir el proyecto en DBeaver Community, configurar la conexión local y visualizar/exportar diagramas.
8. Una sección para el informe académico que explique la separación de datos, las relaciones físicas y lógicas, y las decisiones de arquitectura.
9. Una lista de evidencias visuales que debo capturar manualmente si no puedes generar las capturas desde el entorno.

Prioriza herramientas ya instaladas y formatos que puedan editarse o exportarse. No añadas dependencias innecesarias. Si no hay un generador de diagramas disponible, prepara una fuente compatible con Mermaid u otro formato presente en el proyecto y documenta cómo exportarla.

## Fase 4. Consultas de demostración

Prepara consultas verificadas para mostrar, según las tablas existentes:
- Clientes y hoteles.
- Habitaciones e inventario de disponibilidad.
- Reservas y sus estados.
- Holds y expiraciones.
- Pagos, intentos y ledger, si existen.
- Outbox, eventos y notificaciones, si existen.
- Integridad lógica y relaciones entre servicios mediante consultas compatibles con la arquitectura.

Las consultas deben ser de solo lectura, limitar los resultados y ordenar la información de forma útil para una presentación. No muestres contraseñas, hashes de contraseñas, tokens, secretos, datos personales innecesarios ni información sensible del proveedor simulado.

No inventes columnas ni prometas que una consulta funciona sin validarla.

## Fase 5. DBeaver y entorno local

Documenta los parámetros de conexión obtenidos de la configuración real del proyecto. No inventes credenciales.

Si el puerto PostgreSQL local es 5433, documenta ese puerto solo después de verificarlo. Explica cómo localizar de forma segura la contraseña en el entorno local, sin copiarla a los documentos.

No instales software global, no descargues ejecutables ni cambies configuraciones del sistema sin mi aprobación. Si DBeaver no está instalado, proporciona los pasos manuales.

## Fase 6. Validación y entrega

1. Comprueba que todos los diagramas y consultas coincidan con el esquema real.
2. Ejecuta únicamente verificaciones no destructivas y seguras.
3. No cambies la lógica de negocio ni el comportamiento de los microservicios para cumplir esta tarea.
4. No modifiques archivos existentes si no es necesario; prioriza crear documentación y artefactos nuevos.
5. No sobrescribas ni elimines trabajo existente. No hagas commits, push, reset, clean ni otras operaciones Git destructivas.
6. No expongas secretos en archivos, registros, terminales capturados o diagramas.
7. Si una tarea no se puede completar por falta de herramientas, permisos o servicios activos, indica exactamente qué falta y deja una alternativa reproducible.

Al terminar, entrega un resumen con:
- Archivos creados o modificados.
- Seis bases de datos y tablas verificadas.
- Diagramas generados y formato.
- Consultas probadas.
- Comandos para reproducir el proceso.
- Evidencias pendientes de captura manual.
- Limitaciones y riesgos encontrados.

Diferencia claramente lo que ejecutaste y verificaste de lo que solamente documentaste o dejaste preparado.