# Misión: finalizar el informe del examen complexivo UCE a partir de la evidencia real del proyecto

Actúa como un asistente especializado en documentación académica de Ingeniería en Sistemas de Información, análisis de software, arquitectura de microservicios y edición profesional de documentos Word.

Tu misión es producir el informe final del examen complexivo, completo, editable y listo para revisión, utilizando el proyecto existente como fuente de evidencia y cumpliendo estrictamente la guía metodológica de la Universidad Central del Ecuador.

## 1. Contexto y rutas

La raíz del proyecto es:

`D:\github\tlhotel\reservas-platform`

La carpeta de trabajo documental es:

`D:\github\tlhotel\reservas-platform\docs\informe`

Las imágenes, capturas y evidencias visuales que deben evaluarse para su inclusión se encuentran en:

`D:\github\tlhotel\reservas-platform\docs\informe\Evidencia`

La carpeta `docs\informe` contiene los documentos de referencia y materiales de trabajo que debes inspeccionar antes de redactar.

El repositorio completo contiene el código, las pruebas, la configuración, los resultados y la documentación técnica que sustentan el caso.

Utiliza el MCP `docx-editor` para las operaciones de Word que soporte. Puedes utilizar Python y `python-docx` si están disponibles para generar o modificar el documento, insertar imágenes locales, controlar estilos y revisar la estructura. Para extraer información de PDF, utiliza las herramientas disponibles en el entorno.

No presupongas que todos los archivos de estas carpetas son correctos o están actualizados. Inspecciónalos y determina su función antes de utilizarlos.

## 2. Objetivo principal

Entregar un documento `.docx` editable que:

- Cumpla la estructura, las métricas, los criterios de evaluación y los requisitos de presentación establecidos en la guía metodológica oficial.
- Desarrolle el caso con base en la implementación real de `reservas-platform`.
- Incorpore las evidencias visuales pertinentes, ya existentes en la carpeta `Evidencia`.
- Explique la arquitectura, las decisiones técnicas, la implementación, las pruebas, los resultados, las limitaciones y las conclusiones con rigor académico.
- Pueda revisarse, corregirse y actualizarse directamente en Microsoft Word o LibreOffice.
- Incluya referencias, tablas, figuras, numeración y anexos según corresponda a la guía.
- No contenga resultados inventados, texto de relleno ni afirmaciones técnicas sin respaldo.

El informe debe ser un documento académico, no un README ampliado ni una descripción comercial del proyecto.

## 3. Fase inicial: inventario y diagnóstico

Antes de modificar o generar documentos:

1. Examina `docs\informe` de forma recursiva, identificando documentos Word, PDF, Markdown, archivos de texto, hojas de cálculo, imágenes y otros materiales relevantes.
2. Identifica expresamente la guía metodológica oficial y cualquier versión previa del informe.
3. Inspecciona el contenido de `docs\informe\Evidencia` y genera un inventario de imágenes con nombre, formato, dimensiones y descripción del contenido cuando sea posible.
4. Revisa el resto del repositorio para identificar documentación técnica, código, scripts, pruebas automatizadas, métricas, reportes, configuraciones y resultados relacionados con el caso.
5. Consulta el estado de Git y conserva todos los cambios existentes. No restaures archivos, no elimines evidencias y no sobrescribas documentos originales.
6. Si existen varias versiones de un mismo documento, determina cuál es la oficial y cuál es material de trabajo. Si no puedes distinguirlas, registra la incertidumbre y continúa con la fuente más claramente identificada como oficial.

Entrega un diagnóstico inicial conciso con los archivos encontrados, los requisitos identificados y el plan de elaboración. Después continúa con el trabajo; no te detengas esperando mi autorización para cada operación segura y reversible.

## 4. La guía metodológica es la autoridad principal

Lee la guía metodológica completa, incluidas tablas, notas, anexos y criterios de evaluación pertinentes.

Extrae y convierte sus requisitos en una matriz de cumplimiento que incluya:

- Identificador del requisito.
- Texto o descripción fiel de la exigencia.
- Ubicación obligatoria en el informe.
- Métrica o criterio de evaluación aplicable.
- Evidencia disponible para cumplirlo.
- Estado de cumplimiento.
- Acción necesaria.

Distingue entre requisitos obligatorios, recomendaciones y criterios de evaluación.

No sustituyas las métricas de la guía por indicadores habituales de ingeniería de software. No agregues secciones obligatorias que contradigan la guía ni elimines apartados exigidos por ella.

Si una exigencia no puede interpretarse con certeza, documenta la ambigüedad. Si el informe actual contradice la guía, prevalece la guía.

## 5. Investigación del proyecto y trazabilidad

Inspecciona el código, la documentación, los archivos de configuración y las pruebas antes de describir cualquier comportamiento del sistema.

Utiliza los elementos reales del proyecto para verificar, cuando corresponda:

- Objetivo y alcance del caso.
- Arquitectura y responsabilidades de cada microservicio.
- Tecnologías y configuración de ejecución.
- Modelo de datos y separación de bases de datos.
- Flujos de reserva, disponibilidad, pagos y notificaciones.
- Manejo de errores, idempotencia, concurrencia y recuperación.
- Pruebas unitarias, integración, extremo a extremo, smoke y validación de invariantes.
- Resultados de rendimiento, escalabilidad, resiliencia y recuperación.
- Indicadores, métricas y limitaciones documentadas.
- Reproducibilidad de la ejecución y procedimientos de validación.

Estos son aspectos que debes investigar, no afirmaciones que debas dar por verdaderas automáticamente. Confirma cuáles existen realmente y cuáles son pertinentes para la guía.

Utiliza las pruebas y reportes verificables como fuente de resultados. Si una prueba no puede repetirse, diferencia claramente entre un resultado histórico documentado y una comprobación realizada durante esta tarea.

No ejecutes pruebas destructivas, no borres volúmenes ni bases de datos y no interrumpas procesos existentes. Evita operaciones que alteren los datos o el comportamiento del sistema solo para obtener capturas.

## 6. Elaboración del documento

A partir del diagnóstico, crea una versión nueva del informe y desarrolla todos los apartados requeridos por la guía.

Reglas de redacción:

- Escribe en español académico, claro, técnico y natural.
- Mantén una terminología consistente en todo el documento.
- Explica las decisiones técnicas y su relación con el problema estudiado.
- Prioriza la exposición analítica: problema, método, implementación, evidencia, resultados e interpretación, según la estructura que exija la guía.
- No repitas innecesariamente la misma información entre secciones.
- No presentes como implementación real una propuesta futura o una capacidad no terminada.
- No inventes cifras, resultados, bibliografía, autores, citas, fechas ni declaraciones institucionales.
- Conserva los datos válidos del material de origen, verificándolos cuando sea posible.
- Identifica claramente las limitaciones técnicas y las condiciones bajo las cuales se obtuvieron los resultados.
- Cuando falte información esencial, utiliza una marca explícita como `[PENDIENTE DE VERIFICACIÓN: descripción concreta]` en vez de inventarla.

La extensión debe responder a la guía y a la profundidad que requiera el caso. No alargues artificialmente el documento.

## 7. Integración de las imágenes existentes

Examina todas las imágenes de `docs\informe\Evidencia` y determina cuáles aportan evidencia real al informe.

Para cada imagen seleccionada:

1. Identifica qué demuestra y verifica que su contenido sea coherente con el texto.
2. Relaciónala con el requisito de la guía o con el apartado que sustenta.
3. Insértala en el lugar más pertinente del documento.
4. Ajusta su tamaño manteniendo la proporción y una resolución legible.
5. Añade una numeración y un pie de figura descriptivo y académico.
6. Incluye una referencia explícita a la figura desde el texto principal.
7. Añade la fuente o procedencia cuando corresponda y esté documentada.
8. Comprueba que la figura no quede separada de su pie, recortada, distorsionada o fuera de los márgenes.

No insertes todas las imágenes de forma indiscriminada. Prioriza las que demuestren aspectos relevantes y evita duplicados o capturas redundantes.

No alteres las capturas para simular resultados. Si necesitas recortar márgenes de una imagen para mejorar la legibilidad, conserva intacto el original y trabaja sobre una copia.

No inventes nombres de autores o fuentes para las figuras. No expongas contraseñas, tokens, claves, datos personales ni secretos de configuración. Si una captura contiene información sensible, omítela o crea una versión redactada sin modificar la evidencia original.

Si una imagen no puede interpretarse con seguridad, registra su nombre y solicita verificación mediante una marca de pendiente.

## 8. Formato profesional y edición real en Word

El entregable principal debe ser un archivo `.docx` nativo y editable, no un PDF convertido en imágenes.

Aplica las especificaciones de formato de la guía. Cuando esta no establezca algún detalle, utiliza un estilo académico uniforme y sobrio.

En particular:

- Utiliza estilos nativos de Word para títulos, subtítulos y cuerpo de texto.
- Configura márgenes, tipografía, tamaño, interlineado y espaciado de acuerdo con la guía.
- Genera una tabla de contenido automática cuando corresponda.
- Mantén numeración consistente de capítulos, tablas y figuras.
- Utiliza tablas editables de Word, evitando capturas de tablas cuando se disponga de datos estructurados.
- Configura encabezados, pies de página y numeración según las exigencias institucionales.
- Inserta las imágenes como objetos gráficos normales de Word.
- Utiliza saltos de página y de sección de forma controlada.
- Evita páginas vacías, títulos aislados, tablas cortadas y figuras excesivamente pequeñas.
- Mantén la bibliografía y las citas en el estilo que exija la guía.

Si utilizas `python-docx`, asegúrate de conservar o recrear correctamente todos los elementos necesarios. No afirmes que un campo de Word, tabla de contenido o numeración automática funciona sin comprobarlo.

## 9. Fuentes y referencias

Prioriza las fuentes reales utilizadas en el proyecto y las fuentes académicas o técnicas que el material de origen ya cite.

Comprueba que las referencias bibliográficas correspondan a documentos existentes y que los datos disponibles sean correctos.

No fabriques DOI, URL, páginas, autores, títulos ni fechas de consulta.

Si es necesaria una fuente adicional para justificar una decisión técnica, investígala solo si el entorno permite hacerlo y distingue claramente esa información externa de los resultados obtenidos en el proyecto.

Asegúrate de que las citas del texto correspondan a las referencias finales y viceversa, conforme al formato exigido.

## 10. Control de calidad antes de entregar

Una vez creado el documento:

1. Abre o vuelve a leer el `.docx` generado con las herramientas disponibles.
2. Comprueba que todos los apartados obligatorios estén presentes.
3. Revisa la matriz de cumplimiento y actualiza el estado de cada requisito.
4. Comprueba las referencias a figuras, su numeración y sus pies.
5. Comprueba las tablas, los encabezados, la numeración de páginas y la tabla de contenido, si corresponde.
6. Verifica que no haya texto de relleno, marcadores accidentales, citas sin referencia ni contradicciones entre secciones.
7. Si existe LibreOffice u otra herramienta de conversión disponible, genera una copia PDF y examina el resultado visualmente. No instales programas ni descargues ejecutables sin autorización.
8. Revisa el estado de Git para asegurarte de que no se hayan alterado accidentalmente archivos ajenos a la tarea.
9. Si una comprobación no puede realizarse, indícalo claramente en el reporte final.

## 11. Entregables

Guarda los archivos finales en `docs\informe`, sin sobrescribir los documentos de origen. Utiliza nombres claros, por ejemplo:

- `Informe_Final_Examen_Complexivo.docx`
- `Informe_Final_Examen_Complexivo.pdf`, únicamente si se puede generar y verificar.
- `Matriz_Cumplimiento_Guia.md`
- `Registro_Evidencias.md`, con las figuras utilizadas, su ubicación en el informe y el requisito que respaldan.
- `Revision_Final.md`, con los controles realizados y las limitaciones pendientes.

Adapta los nombres si ya existe una convención de nombres en la carpeta.

Al finalizar, presenta un resumen concreto de los archivos creados, los requisitos cumplidos, las evidencias incorporadas, las validaciones ejecutadas y los pendientes que realmente requieran mi intervención.

La prioridad es producir un informe fiel a la guía, técnicamente demostrable, editable y visualmente consistente. No te limites a dar recomendaciones: realiza el trabajo posible dentro del entorno y deja explícito lo que no hayas podido completar.