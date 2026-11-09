# Despensa 1.0 — matriz de paridad

La versión 1.0.0 sirve React en `/`, alias `/react/`, con compras sin JavaScript en `/basic`. Migración integrada en `main` y publicación autorizada para habilitar la actualización desde 0.16.4. Esta matriz describe código probado, no un despliegue.

| Flujo anterior | React y API | Evidencia |
| --- | --- | --- |
| Compra inicial, comprado, retirar, limpiar completados | Lista de Grocy, filas por ID, errores y recarga de consultas | Python; navegador móvil/ingress; contrato real de otras listas/notas/completados |
| Despensa y carrito/cantidad | Búsqueda nombre/EAN, pasos kg/pieza, sin recarga ni salto | Vitest; Chromium móvil; Grocy real |
| Crear producto / duplicados | Alta con stock cero, enlace al existente, conversión Pack verificada | Python; navegador real con alta y Pack |
| Editar nombre / stock / unidades | Conserva descripción/foto/compra; estado esperado; compra futura independiente | Python; contratos reales; compra de 2 packs = 8 piezas |
| Existencias / consumo | Ficha 1.3.0: sin formulario de añadir a la compra y con un único ajuste de cantidad total restante; formulario separado retirado. API de consumo conservada | Vitest de ajuste descendente; Grocy real, Python de consumo/repetición |
| Códigos y variantes | Propiedad auditada; ficha y escáner; edición de variante conserva EAN | Python; navegador y persistencia real |
| Fotos | Búsqueda universal v3 exacta con respaldo Food/Products/Beauty y redirecciones confiables y subida saneada, URL compartida/versionada; nombre propuesto explícitamente en alta | Python; navegador; archivo servido tras reinicio real |
| Tickets | Subir/revisar/simular/confirmar; ledger y marcadores contra duplicados | Python; importador real en subprocess; segundo ticket no duplica stock |
| Alias y salud Alexa | Candidatos recalculados con el catálogo activo, aviso local al worker; gestión por producto, varios alias, borrado por estado esperado, notas exactas revisables y estado sanitizado | Python, API, Vitest, Chromium y conservación de fila/cantidad/stock en Grocy real |
| Alexa | Elección/mantener original materializan fila inmediata; Quitar siempre visible, incluso en sugerencias; retirada persistente y checkpoint verificado | Python de duplicados/conflictos/fallos, contrato Grocy real y navegador con worker/HA desechable |
| Auditoría / duplicados | Auditoría exportable, diferencias persistentes/deshacer y combinación nativa revisada | Python; preserva lotes/historia/referencias y bloquea dependencias no migrables |
| Ciclo de producto | Archivado/restauración reversibles; borrado 1.8.0 solo de archivados sin stock ni dependencias, con revisión, nombre exacto y aceptación explícita si se borran movimientos | Python y Grocy real: historial idéntico antes/después |
| Autenticación standalone / ingress | Login/logout, CSRF, caducidad y caché limpia; prefijos de assets/API | Python, Vitest y Chromium ingress |
| Acceso sin JavaScript | Página básica autenticada con controles de compra y CSRF | Python y Chromium con JavaScript desactivado |
| Empaquetado | React compilado, runtime completo, espejos Python | CI AMD64/ARM64: build y arranque de contenedor |

Frontend 1.11.0: 91 pruebas Vitest y 27 escenarios Chromium configurados. Alta solo en Mi despensa; archivados en Acciones, sin acceso de alta duplicado. Incluye regresiones de sesión/caché tardía, tickets no listos para importar, escrituras únicas ante doble pulsación/respuesta perdida, factores Pack, conflictos de variantes y navegación por teclado. Cobertura y alcance exacto en [VALIDATION_V1.md](VALIDATION_V1.md).

La antigua eliminación permanente podía borrar historia mediante cascadas de Grocy. El archivado reversible sigue siendo la opción para productos con historial; desde 1.8.0 solo se permite eliminar una ficha archivada sin stock, historia ni dependencias tras auditar las cascadas. Desde 1.9.0 el usuario autoriza implementar combinación explícita compatible mediante la transacción nativa de Grocy; no se autoriza al agente a combinar datos de producción.

## Retirada del código anterior

Retirados `PAGE`, scripts incrustados y rutas antiguas de formularios de aplicación completa. `web.py` solo compone auth, ingress, estáticos, API y alternativa básica. No se retiran bases de datos, fotos, opciones, registros de comandos, historiales ni checkpoints. Los espejos Python se conservan por compatibilidad del empaquetado y se verifican byte a byte.

## Límites de la evidencia

Véase [VALIDATION_V1.md](VALIDATION_V1.md). Grocy es el release oficial 4.7.1 sin modificar, con datos temporales. Solo OpenAI, búsqueda pública de fotos y HA todo se sustituyen en esas pruebas. Las lecturas adicionales del Grocy instalado confirman 4.7.1 y el esquema utilizado, y la entidad HA/Alexa devuelve pendientes válidos. No se prueba cámara física, actualización Supervisor ni escrituras sobre la cuenta Alexa real. La publicación 1.0.0 autorizada no acredita esas comprobaciones externas.

Desde 1.10.0 se permite borrar el historial de movimientos de un archivado tras aceptación expresa; se mantienen las protecciones de stock/dependencias/importaciones inciertas y el ledger local de tickets completados. Se retira pantalla completa y se corrige el color de éxito.

Aviso de existencias 1.10.0: umbral por producto 0/enabled por defecto, desactivación individual, metadatos persistentes y lectura/cantidad/compra de Grocy idénticas tras editar avisos.

Desde 1.11.0 la revisión de compra/Alexa ofrece creación contextual sin stock y asociación inmediata, incluso sin candidatos; conserva ID/cantidad/nota y permite recuperar resultados parciales sin repetir el alta. El alta general sigue en Mi despensa.

Tickets 1.12.0: edición de compra/unidades/envase, selección por ID y alta al confirmar; cantidad final calculada de solo lectura y asociaciones por supermercado en el ledger existente. Simulación y preflight bloquean líneas pendientes; original monetario/hash y protección contra duplicados se conservan.

1.13.0: reconocimiento opcional de foto completa tras búsqueda pública sin nombre; vista previa local, envío explícito, nombre aplicado manualmente y código/stock conservados. Endpoint Alexa en proceso independiente sin rutas del frontend.


1.15.0 añade selector nativo accesible mediante icono en Mi despensa: todos, falta de stock o compra; respeta umbrales/avisos, búsqueda por nombre/código y cambios de cantidad. No cambia datos al filtrar.


1.16.0 añade búsqueda explícita de imagen/GTIN en alta: fuentes citadas, catálogo exacto, elección antes de guardar y protección de respuestas tardías. La foto se puede reconocer sin código previo. Pruebas de proveedor y navegador desechables; no implica aceptación del servicio pagado real.


1.17.0 sustituye la interacción previa: stock agrupado en despensa, edición absoluta de compra, borrado directo Sí/No, candidatos de duplicados más completos, foto por nombre sin captura IA y Piece por defecto. Pruebas de incertidumbre, preservación de filas/notas y cascadas Grocy 4.7.1 son obligatorias antes de fusionar.


1.18.0: búsqueda local por nombre en compra con normalización de tildes/mayúsculas, comprados y pendientes, estados de vacío correctos y conservación de avisos/consulta durante refrescos. Validación Vitest y Chromium móvil.


1.19.0: una asociación contextual explícita conserva identidad por ID con nombre editado; diagnóstico por producto afectado y visibilidad de filas compradas/elecciones ocultas. Regresión completa de worker y comprobación de identities en el contrato Grocy real.


1.20.0: Editar cantidad con lápiz, sin fondo, bajo la cantidad y con objetivo táctil de 44 px. Columna de acciones uniforme en móvil; comprobaciones de alineación a 320, 360 y 690 px.


1.21.0: alias en tabla de selectores, búsqueda y guardar/descartar/eliminar por fila; PUT atómico con estado esperado. Búsqueda de foto desde ficha por nombre, sin código obligatorio ni cambios de stock. Captura nativa de tickets separada del selector PDF; revisar antes de importar. Pruebas API, Vitest, Chromium y contrato de metadatos Grocy real; cámara física pendiente.


1.22.0 sustituye captura nativa por cámara web directa con fotograma completo/JPEG, vista previa y repetición local; probar permisos en teléfono real. Alias guardados y nombres pendientes en filas iniciales; asociaciones nuevas sustituyen duplicados en transacción. Interfaz y navegación de archivados retiradas, sin borrar datos automáticamente.


## Mejoras 1.23.0

- Combinación revisada con equivalencias, unidades, compra y stock final; guardas de referencias y fases parciales sin replay.
- Alias de tickets visibles por supermercado con búsqueda, edición y eliminación de asociaciones, sin modificar ledger ni stock.
- Ticket con cantidad directa a añadir y stock final para productos existentes, sugerencias de nombres y creación alternativa; campo envase sin ceros forzados.
- Stock rápido sin decimales de relleno y sin truncar la precisión usada como estado esperado.
- Validación aislada y CI final documentadas en la PR; aceptación de actualización real sigue pendiente del usuario.


## Diagnóstico de búsqueda IA 1.24.0

Una petición explícita, espera 90s y una invocación web; sin cambio automático de modelo ni reintentos pagados. Errores de proveedor clasificados y saneados, cuerpo de error acotado solo para reconocer códigos conocidos, logs de categorías fijas/estado/parámetro permitido. No exponer mensajes del proveedor, nombres o claves. Errores de credenciales OpenAI no caducan la sesión de Despensa. Conservar selección explícita, firma de candidatos, catálogos confiables, verificación GTIN y foto manual. Causa real del aviso genérico anterior y aceptación instalada siguen sin confirmar.


Ticket 1.24.0: omisión explícita por línea (sin producto/stock/alias) con total original conservado y estado terminal omitted contra reimportación. Pendientes inciertos no se pueden omitir para saltar sus guardas. Filas amarillas y motivos concretos sustituyen la simulación deshabilitada sin explicación; resumen y acceso a primera fila, motivos REVIEW del servidor por índice y stock desfasado comprobado antes de escribir. Omitidas diferenciadas en gris; catálogo ausente explicado globalmente.


## Compatibilidad de búsqueda 1.25.0

Tras log instalado HTTP 400/parameter tools, adaptar la petición de GPT-4.1/GPT-4o a web_search_preview sin filters; mantener web_search filtrado para familias nuevas. No cambiar modelo ni repetir solicitudes pagadas. La variante preview carece de filtro remoto: sitios en instrucciones y admisión local estricta de fuentes/citas/GTIN/API exacta, sin URLs arbitrarias. El subcampo rechazado y el éxito de una nueva consulta instalada no se deducen del log resumido. Conservar el resto de 1.24 (omisiones, filas amarillas y diagnósticos).


## Generic product photos — 1.26.0

1.26: product details add explicit unpaid generic-photo search by saved name. Generic results are labeled without a barcode, ignored after context changes and only persisted on selection. Existing packaged-product discovery remains unchanged. The refreshed photo shows author, license and source; local uploads suppress the previous public-photo credit.


## Quantity-first receipt review — 1.27.0

1.27 removes auto product selection and its unit-confirmation workaround. Unmapped rows show a disabled placeholder and pending reason; suggestions/full catalog/new/skip remain. Carry bags remain skipped across mapping initialization and can be explicitly included. Monetary mismatches are informational while stock review, simulation and confirmation remain mandatory. This user-approved policy supersedes older references to mandatory monetary reconciliation.


## OpenAI photo search — 1.28.0

1.28: remove the separate generic search action. One Buscar foto con IA button uses the photo-only endpoint for saved products. Search query may change independently from the saved product name and invalidates old results; late replies/product/photo changes still discard selections. Render local authenticated preview URLs, no invented barcode, explicit save/replace and a source link after refresh. Creation keeps its separate existing exact-code workflow.


## Catálogo completo en compra — 1.29.0

Selector con sugeridos y resto del catálogo activo, búsqueda por nombre y elección manual explícita fuera del ranking. Evidencia manual por ID en la cola existente, limitada a nombre/generación del episodio; comprobar nombre del producto activo antes de guardar. No cambia la selección automática, no crea alias ni toca stock. Conservar fila/cantidad/nota, bloqueos de duplicados, CSRF, locks y journal. Productos ausentes/archivados quedan obsoletos; una nueva aparición limpia únicamente la prueba manual del episodio anterior. Validación aislada y CI final en la PR; actualización instalada pendiente del usuario.


## Pausa de sincronización — 1.30.0

Backoff de fallos 2/4/8/16/30 minutos, respetando intervalos mayores, reinicio tras éxito, persistencia en salud existente e in-memory fallback. Eventos no saltan la pausa; acciones manuales siguen disponibles y el siguiente ciclo lee snapshots nuevos. Mostrar próxima hora y mantener diagnóstico/error original durante esperas previstas; vigilar worker obsoleto tras el plazo y margen. No deshabilitar Alexa Devices, cambiar configuración de HA, vaciar colas/checkpoints ni repetir comandos inciertos. Validación aislada/CI en la PR; actualización y aceptación instalada posteriores por el usuario.


## Aviso de pausa con relojes distintos — 1.31.0

La API añade retry_after_seconds (0..3600) y conserva los campos existentes. SyncPause usa duración y dataUpdatedAt del navegador para descontar una respuesta cacheada; al vencer espera confirmación nueva. No usar next_retry_at absoluto como fecha de próximo intento, no reiniciar el plazo al renderizar y no afirmar recuperación automática. Payload antiguo/inválido muestra tiempo sin confirmar. Temporizador con limpieza al vencer/desmontar; sin nuevas peticiones ni mutaciones. Se conserva scheduler y no se cambia el reloj de HA.

El usuario autoriza un botón de intento manual en el aviso. POST /shopping/sync ejecuta un ciclo habilitado y revisado con CSRF, UUID/journal y locks no bloqueantes. No forzar con sync desactivado ni reenviar mutaciones automáticamente; mantener todas las guardas de identidad/checkpoint. El worker observa la revisión del estado de salud de un ciclo manual para reanudar/reprogramar sin que eventos normales salten la pausa.
