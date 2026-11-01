# Despensa — decisiones vigentes

Última revisión: 2026-11-01. Consolida las decisiones del producto y sustituye los estados históricos de implementación de PR #2/#5. PR #10 integrada en `main` por petición del usuario; posteriormente autoriza publicar 1.0.0 para que Home Assistant ofrezca la actualización. La instalación real y su aceptación se verifican por separado.

## Navegación y compras

- Inicio: **Lista de la compra**; otras pestañas: **Mi despensa** y **Acciones**. Desde 1.1.0, **Nuevo producto** solo está en Mi despensa, con botón principal. Desde 1.11.0, las entradas de compra/Alexa permiten crear un producto contextual sin stock y asociarlo conservando fila/cantidad/nota, incluso sin candidatos. Un duplicado existente requiere aceptación explícita. La búsqueda por nombre/código es automática: barra con input y cámara, sin botón Buscar. **Productos archivados** se abre desde Acciones; no ocupa espacio en el inventario habitual ni duplica el alta.
- La lista predeterminada de Grocy es la única lista de compra del producto. Marcar comprado o retirar no altera existencias.
- Carrito «Añadir» para productos ausentes, después «− cantidad +», y carrito otra vez al llegar a cero. Actualización sin recarga ni salto de scroll; errores visibles, columnas estables en móvil y alternativa HTML sin JavaScript.
- Máximo dos decimales. Pasos de 0,10 kg y 1 pieza. La cantidad almacenada por Grocy está en unidades de stock; una compra de packs se convierte exactamente una vez.
- Operaciones por ID de fila, solo lista 1; preservar notas, completados y listas independientes.

Desde 1.8.0, Atrás usa el historial de las secciones y cierra primero los diálogos anidados; en el inicio conserva la salida normal al contenedor. El botón de pantalla completa se retira en 1.10.0 por petición del usuario. No se cambia la configuración de HA.

## Catálogo y existencias

- Mi despensa resalta en ámbar productos con cantidad igual o inferior al umbral por producto (0 por defecto). Muestra «Stock bajo» si aún quedan unidades y «Sin existencias» con cero o negativo. «No avisar de stock bajo» suprime color y etiqueta conservando el umbral; no modifica stock ni añade compras. Los archivados son neutros.
- Añadir producto crea solo productos nuevos: comprobar nombre/código, enlazar la ficha existente ante duplicado, nunca incrementar su stock. Alta con código opcional y cero existencias permitido.
- Ficha con edición de nombre, unidad, configuración de compra, existencias, foto, códigos y variantes. Desde 1.3.0 se retira el formulario de añadir a la compra: la ficha contiene información del producto y stock; los controles de compra permanecen en las listas. No existe una acción independiente «Asociar código».
- **Pack compra / Piece stock y consumo**. Un pack de 5 añade 5 piezas. Las conversiones se verifican en Grocy antes de escribir stock; se descubren los IDs reales de unidades. Mostrar piezas por pack solo para Pack.
- Cambiar compras afecta únicamente a compras futuras. Nunca reinterpretar automáticamente stock existente ni una fila de compra. Renombrar conserva descripción, fotos y configuración. Cambiar unidad de stock exige cero conocido y configuración compatible.
- Ajustar stock requiere cantidad esperada y guarda directamente, sin pantalla de confirmación adicional.
- Desde 1.1.0, la ficha muestra un único control de existencias: indicar la cantidad total que queda. Se retira «Consumir producto» por petición del usuario; tampoco se añade compra automáticamente al ajustar stock. La API de consumo y su registro persistente se conservan, sin repetición automática ni eliminación del historial.
- **Ciclo seguro: archivar/restaurar**, conservando ID, historial y metadatos. Archivar exige cero stock conocido y ausencia de referencias activas; restaurar cambia únicamente `active`. Desde 1.8.0 el usuario autoriza eliminar archivados sin uso: sin stock, movimientos/tickets ni dependencias Grocy/locales/Alexa. Revisión, nombre exacto y revalidación antes del único envío; conservar registros y no repetir resultados inciertos. En 1.10.0 el usuario autoriza borrar también los movimientos de Grocy, con aviso del número y aceptación expresa. Se conservan las filas locales de tickets ya importados y se bloquean importaciones pendientes/inciertas y dependencias activas. Desde 1.9.0 se autoriza la combinación nativa revisada de productos compatibles.
- Duplicados permite decidir por pareja: «Son diferentes» persiste hasta deshacerlo, y «Revisar combinación» permite elegir el producto que se conserva. Combinar requiere snapshot actual y nombre exacto; se usa la transacción nativa verificada de Grocy 4.7.1, con unidades/conversiones compatibles y sin vínculos locales de origen no migrables. Se preservan lotes, movimientos y referencias; la ficha conserva los metadatos elegidos. No hay combinación automática ni escrituras en producción por parte del agente.

## Fotos, variantes y tickets

- Desde 1.3.0 buscar foto por código exacto primero mediante la consulta universal v3 de Open Facts; restringir redirecciones HTTPS a Food, Products y Beauty y atribuir el catálogo final. Ante errores o datos incompletos, conservar consultas directas a esos tres catálogos; un 404 universal termina la búsqueda. No habilitar Pet Food. Siempre guardar solo URL validada por servidor y host HTTPS permitido. No consultar por producto en cada carga. Foto inexistente/servicio caído no bloquea el alta o asociación; conservar foto personalizada existente.
- Desde 1.2.0, mostrar el nombre devuelto por el catálogo y permitir aplicarlo explícitamente durante el alta, sin sobrescribir el nombre escrito. Los catálogos pueden ser incompletos. Botones de formularios, revisión de duplicados y selectores nativos de archivo usan estilos comunes y objetivos táctiles de 44px.
- Subida local saneada y sin metadatos privados; URL versionada compartida por compra, despensa y ficha. Persistir fotos en el almacenamiento existente.
- Un genérico es un ID canónico de Grocy y posee todo su stock. Variantes añaden nombre, supermercado, marca, EAN y factor descriptivo. Comprobar propiedad del código en ambos registros; editar variante no cambia su EAN ni crea otro producto inadvertidamente. El factor canónico de compra controla las conversiones; el factor de variante no migra stock.
- Tickets PDF/JPG/PNG: extraer, revisar nombres/piezas por pack, simular, confirmar bytes exactos y persistir historial contra duplicados. La simulación no escribe en Grocy. Conservar marcadores pendientes ante cortes.

## Alexa

- Desde 1.7.0 las sugerencias usan el catálogo activo actual al leer la lista y al guardar la elección. Altas, renombrados y archivados actualizan opciones; conservar decisiones, descartes, retiradas y generaciones. No reasignar una fila ya asociada ni crear otra para cambiar su producto.
- Los cambios guardados en Despensa despiertan el worker mediante marcador local (250 ms), manteniendo eventos HA e intervalo configurado como respaldo. La vista refresca cada 5 s; la latencia de Alexa depende de cuándo su integración notifique a HA. Con sync desactivado no hay escrituras remotas.

- Solo entidad `todo.*` configurada y lista predeterminada de Grocy; pendientes de Alexa, sin históricos/completados. Desactivado por defecto.
- Entidad configurada con sync desactivado permite actualizar la cola local en modo lectura. El worker no escribe remotamente con sync desactivado. Una acción manual explícita sí actualiza Grocy de inmediato; nunca requiere habilitar sync ni escribe en Alexa por sí sola.
- Primer ciclo v2 une sin borrar; siguientes propagan altas/bajas por ID canónico y checkpoint confirmado. No sincronizar cantidades, unidades, completados ni renombrar Alexa.
- Desde 1.6.0 las notas de Grocy con nombre exacto de producto también se ofrecen para asociación explícita, preservando fila/cantidad/texto; nunca se convierten o fusionan automáticamente. La lista muestra estado sanitizado del worker. Los alias permanentes se gestionan por producto en Acciones; cada producto admite varios alias, sin renombrar Alexa. Un alias ausente de Alexa no bloquea la sincronización por referencias obsoletas.
- Nombres ambiguos/desconocidos conservan nota. **Mantener original** conserva o crea una nota real en Grocy, gestionable como comprado/quitar, y oculta la sugerencia.
- **Selección explícita validada** asocia su nota existente al guardar, o reutiliza/crea una única fila del producto en Grocy si no hay nota: misma fila, cantidad, nota y lista; sin duplicar ni fusionar filas. Revalidar identidad y campos antes de escribir; colisión con otra fila canónica o edición concurrente detiene el ciclo.
- **Quitar** está disponible también sin elegir producto. Una retirada explícita se guarda en la cola, elimina solo su fila verificada de Grocy y evita reimportarla; con sync habilitado el worker retira su origen Alexa incluso antes de la primera unión. Con sync desactivado no hay escrituras Alexa. Elecciones manuales y worker usan un bloqueo entre procesos; tras verificar la ausencia de origen, una nueva alta con el mismo nombre inicia otra revisión.
- Releer ambas listas tras cambios y guardar checkpoint solo tras convergencia. Elección obsoleta bloquea; colas y checkpoints separados por entidad. Conservar archivos v1 sin reinterpretación automática.

## Seguridad y entrega

React 19, TypeScript 7, Vite 7 y Vitest 4 en el mismo origen que Flask. Credenciales solo en servidor, ingress HA o sesión standalone, CSRF en todas las mutaciones, CSP y errores en español. No exponer puertos ni relajar autenticación para probar.

La versión 1.0.0 sirve React en `/` y conserva `/react/` como alias; `/basic` mantiene compras sin JavaScript. Se ha eliminado el frontend completo duplicado después de comprobar paridad contra Grocy 4.7.1 aislado. Publicar la versión en el manifiesto permite detectar la actualización; no acredita una instalación en Home Assistant.

Conservar todos los datos persistentes y módulos Python espejo. Validación automatizada y límites constan en `docs/VALIDATION_V1.md`. Las lecturas de Grocy instalado y la entidad HA/Alexa real ya responden correctamente sin cambios de seguridad. Actualización Supervisor, cámara física y escrituras Alexa reales siguen siendo aceptación de despliegue externa. Publicación 1.0.0 autorizada por el usuario sin dar por realizadas esas comprobaciones; mantener copia HA y sincronización desactivada hasta validar sus escrituras reales.


## Revisión de tickets 1.12.0

- Cantidad de compra editable separada de cantidad/precio monetarios originales: preservar coste por línea y total. Cantidad final de stock calculada, de solo lectura; piezas enteras y pesos con hasta tres decimales.
- Selección explícita por ID canónico o alta al confirmar. La configuración actual del producto existente controla Pack/Piece; nunca se modifica desde el ticket. Simular no crea productos ni existencias.
- Asociaciones por supermercado + texto original normalizado, en tabla aditiva del ledger existente, solo después de importar correctamente. No usar coincidencia difusa; múltiples textos pueden apuntar al mismo ID. Revisar targets ausentes/archivados y cambios de unidad/conversión.
- Cambiar cualquier línea exige nueva simulación. REVIEW/pending bloquean confirmación y preflight, manteniendo bloqueo compartido con worker, marcadores contra repetición y deduplicación por hash original.


## Voz y fotografía completa 1.13.0

- Endpoint Alexa aislado en proceso/puerto 8100, solo consultas y desactivado por defecto. Requiere skill y usuario Amazon autorizados, firma SHA-256, cadena de confianza y timestamp firmado. No relajar la autenticación/CSRF del panel. Configurar Cloudflare/Amazon después con el usuario.
- Consultar stock real por ID/alias; aclarar ambigüedades, conservar unidades Piece/kg y respetar umbrales/opt-out. Error de consulta no equivale a cero. No efectuar escrituras Grocy/Alexa desde voz.
- Búsqueda pública por código primero. Si no hay nombre o el servicio falla, ofrecer análisis explícito de fotografía completa; conservar encuadre, sanear EXIF y memoria acotada. La sugerencia visual no es búsqueda web ni verifica identidad/EAN. Aplicar nombre manualmente; no alterar código, stock ni conversiones.
- Usar clave OpenAI existente, `store=false`, sin reintentos automáticos y sin persistir fotografías del reconocimiento. Los catálogos, fotos locales e historiales previos permanecen.
