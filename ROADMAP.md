# Despensa 1.0 — cierre de migración

Estado de código: migración de PR #10 integrada en `main` (`a6cc354`). Publicación de versión 1.0.0 autorizada por el usuario, con manifiesto, frontend y notas alineados en la PR de release. La actualización de la instalación real se realiza por separado.

## Implementado y validado automáticamente

- [x] React 19, TypeScript 7, Vite 7 y Vitest 4 con lockfile y compilación dentro del contenedor.
- [x] Compra, despensa, ficha con ajuste total de existencias, tickets, variantes, fotos, revisión Alexa y auditoría. En 1.1.0 se retira el formulario separado de consumo por petición del usuario; su API protegida se conserva.
- [x] Sesión/CSRF, ingress con prefijo, errores, CSP, cámara con entrada manual y UX móvil.
- [x] Pack/Piece contra Grocy 4.7.1 real, sin convertir existencias existentes; edición de compra y cantidades personalizadas.
- [x] Operaciones de compra por fila: preservar otras listas, notas y completados.
- [x] Tickets importados una vez, comandos persistentes y verificación de estado esperado.
- [x] Variantes, fotos y listas conservadas tras reiniciar Grocy aislado.
- [x] Alexa 1.1.0: guardar elección o mantener original crea/asocia de inmediato una fila gestionable en Grocy; Quitar también funciona en sugerencias. Retiradas persistentes, bloqueo entre procesos, sin reintroducción en la primera unión y sin escrituras Alexa con sync desactivado. Checkpoint tras verificación.
- [x] Archivado/restauración conservando historial, con stock y referencias protegidos.
- [x] React como entrada de la candidata; retirar PAGE, scripts y formularios obsoletos; alternativa básica sin JavaScript.
- [x] Fuentes Python duplicadas sincronizadas y manifiesto Docker completo.
- [x] CI configurado para frontend, integración real aislada y contenedores AMD64/ARM64 con arranque.
- [x] Frontend 1.11.0: 91 tests Vitest y 27 escenarios de navegador, con cobertura V8 en CI. Incluye ajuste de existencias sin formulario de consumo, alta solo en Mi despensa y archivados desde Acciones, además de sesión/caché, tickets, validaciones y foco móvil.

La evidencia y comandos reproducibles están en [VALIDATION_V1.md](docs/VALIDATION_V1.md); el resultado CI debe observarse para el SHA final, nunca inferirse de esta lista.

## Mejoras 1.2.0

- [x] Estilos comunes de alta, cámara, duplicados y archivos; revisar disposición móvil.
- [x] Open Beauty Facts adicional, manteniendo Food/Products; nombres propuestos sin autoescritura y ausencia de producto separada de caída de servicio.

## Mejoras 1.3.0

- [x] Ficha sin formulario de añadir a la compra; conservar información y stock, con compras desde las listas.
- [x] Consulta universal v3 con redirecciones confiables, atribución correcta y respaldo directo Food/Products/Beauty.

## Revisión Día 6 y recuperación 1.6.0

- [x] Alias por producto con varios nombres, protección de borrado obsoleto y gestión de productos ausentes.
- [x] Estado del worker visible y notas exactas revisables sin cambiar existencias ni fusionar filas.
- [x] Descubrimiento CI de pruebas anidadas, espejos y versiones alineados.
- [ ] Usuario actualiza la instalación y resuelve la nota conflictiva; no se da por comprobada la sincronización real tras publicar.

## Mejoras 1.7.0

- [x] Sugerencias actualizadas con altas, cambios de nombre y archivados, sin reasignar decisiones guardadas.
- [x] Aviso inmediato tras cambios locales, eventos HA y polling de respaldo; vista cada cinco segundos.
- [x] Contrato y navegador Grocy para un producto nuevo sugerido sin nuevo ciclo del worker.

## Aceptación de un despliegue futuro

- [x] Lecturas de Grocy instalado 4.7.1 y esquema de unidades/conversiones/lista/referencias, usando su acceso interno y clave existentes. Entidad HA/Alexa: pendientes con uid/summary/status válidos; sin escrituras ni cambios de seguridad.
- [ ] Copia HA y actualización de prueba conservando ledger, fotos, variantes, comandos, colas y checkpoints de esa instalación. Reiniciar Grocy aislado ya está probado; no equivale a actualizar Supervisor.
- [ ] Cámara física y permisos de Android/HA; escrituras Alexa reales de la entidad elegida. El navegador automatizado simula el dispositivo de cámara y la respuesta HA.
- [x] Usuario autoriza fusionar la migración y publicar 1.0.0 para habilitar la actualización en Home Assistant. Esta autorización no acredita la aceptación física ni instala automáticamente el complemento.

## Fuera del alcance de la migración

Combinación automática o con dependencias no migrables, eliminación de historial sin confirmación explícita, migración automática de stock Pack antiguo y sincronización de cantidades o estados de compra con Alexa. Se mantienen auditoría y protecciones; no son funciones destructivas pendientes de activar.


## Mejoras 1.8.0

- [x] Productos sin stock en ámbar con etiqueta visible; no depende de cantidad en compra.
- [x] Eliminación irreversible solo para archivados sin historial ni dependencias; revisar, escribir nombre y revalidar, con journal contra repetición.
- [x] Historial interno para Atrás en secciones/diálogos anidados y solicitud explícita de pantalla completa cuando el host lo permite.
- [ ] Aceptación física Android/HA tras la actualización del usuario.


## Mejoras 1.9.0

- [x] Diferencias persistentes por pareja de productos, con deshacer y sin ocultar otras parejas de un grupo.
- [x] Combinación nativa de Grocy bajo revisión, destino elegido, stock/historia/referencias verificadas y comandos sin repetición.
- [x] Alta de producto desde compra/Alexa publicada en 1.11.0 (PR #24).


## Mejoras 1.10.0

- [x] Confirmaciones correctas en verde y retirada del botón pantalla completa.
- [x] Borrado de movimientos de archivados autorizado expresamente; aviso y confirmación, con stock/dependencias/importaciones pendientes protegidas.
- [x] Alta desde compras/Alexa en 1.11.0; revisión de tickets preparada en 1.12.0.

- [x] Umbral de aviso visual por producto (0 por defecto), comparación inclusiva y desactivación individual, sin cambios de compra/stock.


## Mejoras 1.11.0

- [x] Alta contextual desde compra/Alexa sin candidatos, nombre editable, cero stock y asociación automática con cantidad/nota conservadas.
- [x] Vínculo por ID limitado a episodio, confirmación de producto existente y recuperación de asociación sin duplicar alta ni fila.
- [x] 1.12.0: selección/alta/unidades de cada línea de ticket, asociaciones por supermercado y cantidad final calculada de solo lectura.


## Mejoras 1.13.0

- [x] Endpoint de consultas Alexa separado, verificado y desactivado por defecto; modelo es-ES preparado.
- [x] Reconocimiento de foto completa tras código sin resultados, acción explícita y sugerencia editable; conservar alta manual.
- [ ] Configurar con el usuario Amazon Developer, skill/usuario autorizados y ruta Cloudflare del listener 8100; validar voz en Echo físico.
- [ ] Validar una fotografía real del usuario contra su cuenta OpenAI tras la actualización. Las pruebas sustituyen el proveedor y no consumen su API.

## Corrección 1.14.0

- [x] Tomar una foto nueva del frontal/etiqueta para IA, con botón específico, sin reutilizar la imagen del código de barras.


## Mejora 1.15.0

- [x] Icono de filtro en Mi despensa: todos, falta de stock y lista de compra; búsqueda combinada, umbrales/avisos y actualización de compra.


## Mejora 1.16.0

- [x] Buscar imagen y código por nombre con IA en el alta, con fuentes, comprobación GTIN/catálogo y selección explícita.
- [x] Reconocer una foto sin código previo, aplicar el nombre y buscar; mantener alta manual/foto propia si no hay coincidencias.
- [ ] Aceptación instalada de búsquedas reales con el modelo/clave del usuario; las pruebas automatizadas sustituyen proveedores y no consumen API.


## Mejora 1.17.0 — 2026-11-02

- [x] Eliminar directamente con Sí/No y consecuencias visibles, sin paso de archivado ni nombre escrito.
- [x] +/− de despensa para stock, pulsaciones agrupadas y cantidad absoluta en compra sin esperar sincronización.
- [x] Más candidatos de duplicados por orden, puntuación, formato y erratas; decisiones manuales.
- [x] Retirar foto para IA, buscar por nombre conservando código y seleccionar Piece por defecto.
- [ ] Aceptación instalada de tiempos de respuesta/cámara de códigos y búsqueda pagada real.

- [x] Detalles desplegables de sincronización Alexa; filas pendientes/obsoletas/duplicadas arriba y resaltadas, sin atribuciones falsas en fallos globales.


## Mejora 1.18.0

- [x] Buscador por nombre en la compra, con comprados/pendientes Alexa, coincidencias/total y avisos conservados.


## Corrección 1.19.0

- [x] Validación de identidad completa tras alta/asociación contextual con nombre editado; compra confirmada no se reimporta.
- [x] Identificación de producto rechazado en avisos, incluso comprado o elección antes oculta.
- [ ] Confirmar el siguiente ciclo de la instalación del usuario después de actualizar; no se han modificado sus listas durante el diagnóstico.


## Mejora 1.20.0

- [x] Editar cantidad como enlace con lápiz, alineado bajo cantidad/nombre y controles estables en móvil.


## Mejora 1.21.0

- [x] Tabla de alias con dos selectores, búsqueda, edición protegida y eliminar fila.
- [x] Buscar/elegir foto por nombre desde producto existente, con sustitución explícita y código/stock conservados.
- [x] Botón para cámara nativa de tickets, conservando selector de archivos y revisión.
- [ ] Aceptación instalada de cámara nativa Android y búsqueda pagada real.


## Mejora 1.22.0

- [x] Cámara directa con vista previa, repetición, aceptación y cierre/liberación; archivos/PDF alternativos.
- [x] Todas las filas de alias conocidas visibles; al reasignar gana la nueva relación sin duplicados.
- [x] Retirar vista/navegación/restauración de productos archivados.
- [ ] Verificar permisos de la cámara directa en el teléfono real después de actualizar.


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

1.26: generic-photo search from product details implemented for loose foods without a barcode or OpenAI request; retained explicit selection, license/source credit and existing-photo guards. The user screenshot after 1.25 shows a completed search with no verified catalog candidates, distinct from the old HTTP 400. Installed generic-photo acceptance remains separate from isolated tests.


## Quantity-first receipt review — 1.27.0

1.27 implements advisory monetary totals, default carry-bag omission and removal of frontend automatic-name product selection. Unmapped rows require an explicit choice; saved valid mappings still work. Keep stock/unit/quantity and one-shot import guards. Installed acceptance follows update; no real receipt was committed.


## OpenAI photo search — 1.28.0

1.28: one OpenAI photo-only search in product details, editable search text, cited public manufacturer/retailer pages, private sanitized previews and explicit local saving/source attribution. No GTIN prerequisite for photos. Existing source-site protections may make individual pages unavailable; installed provider acceptance remains an explicit user search after updating.


## Catálogo completo en compra — 1.29.0

Selector con sugeridos y resto del catálogo activo, búsqueda por nombre y elección manual explícita fuera del ranking. Evidencia manual por ID en la cola existente, limitada a nombre/generación del episodio; comprobar nombre del producto activo antes de guardar. No cambia la selección automática, no crea alias ni toca stock. Conservar fila/cantidad/nota, bloqueos de duplicados, CSRF, locks y journal. Productos ausentes/archivados quedan obsoletos; una nueva aparición limpia únicamente la prueba manual del episodio anterior. Validación aislada y CI final en la PR; actualización instalada pendiente del usuario.


## Pausa de sincronización — 1.30.0

Backoff de fallos 2/4/8/16/30 minutos, respetando intervalos mayores, reinicio tras éxito, persistencia en salud existente e in-memory fallback. Eventos no saltan la pausa; acciones manuales siguen disponibles y el siguiente ciclo lee snapshots nuevos. Mostrar próxima hora y mantener diagnóstico/error original durante esperas previstas; vigilar worker obsoleto tras el plazo y margen. No deshabilitar Alexa Devices, cambiar configuración de HA, vaciar colas/checkpoints ni repetir comandos inciertos. Validación aislada/CI en la PR; actualización y aceptación instalada posteriores por el usuario.


## Aviso de pausa con relojes distintos — 1.31.0

La API añade retry_after_seconds (0..3600) y conserva los campos existentes. SyncPause usa duración y dataUpdatedAt del navegador para descontar una respuesta cacheada; al vencer espera confirmación nueva. No usar next_retry_at absoluto como fecha de próximo intento, no reiniciar el plazo al renderizar y no afirmar recuperación automática. Payload antiguo/inválido muestra tiempo sin confirmar. Temporizador con limpieza al vencer/desmontar; sin nuevas peticiones ni mutaciones. Se conserva scheduler y no se cambia el reloj de HA.

El usuario autoriza un botón de intento manual en el aviso. POST /shopping/sync ejecuta un ciclo habilitado y revisado con CSRF, UUID/journal y locks no bloqueantes. No forzar con sync desactivado ni reenviar mutaciones automáticamente; mantener todas las guardas de identidad/checkpoint. El worker observa la revisión del estado de salud de un ciclo manual para reanudar/reprogramar sin que eventos normales salten la pausa.


- 1.32.0: full-snapshot inbound-first reconciliation, verified synonym bindings, durable suggested selections and explicit Alexa completed cleanup. Installed acceptance remains pending an upgrade and an available Alexa entity; never use stale unavailable data as a deletion snapshot.
