# Despensa — Grocy Ticket Importer para Home Assistant

[![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Para futuros agentes:** antes de cambiar código, leer [AGENTS.md](AGENTS.md) (instrucciones y seguridad), [DECISIONS.md](DECISIONS.md) (requisitos acordados) y [ROADMAP.md](ROADMAP.md) (pendientes y verificación de CI). Si hay una contradicción de comportamiento, priorizar DECISIONS.md y comprobar el código actual.

Complemento para **Home Assistant OS** que integra [Grocy](https://grocy.info/) con una interfaz móvil en español para consultar existencias, escanear códigos de barras y digitalizar tickets de compra mediante OpenAI.

> **Versión 1.13.0:** migración React integrada desde PR #10. La ficha tiene un único ajuste de existencias: indicar la cantidad total que queda. Home Assistant detecta esta versión mediante el manifiesto del complemento. Actualiza la instalación existente con copia de seguridad, sin desinstalar. Validación automatizada contra Grocy 4.7.1 aislado; cámara Android, escrituras Alexa y aceptación de la actualización real siguen pendientes.

> **Fotos de productos:** al escanear o introducir un código de barras, se usa primero la consulta universal v3 de Open Facts por código exacto. Se siguen únicamente redirecciones HTTPS a Food, Products y Beauty; las consultas directas se conservan como respaldo ante fallos o datos incompletos. Si hay nombre disponible, se muestra como sugerencia y puedes aplicarlo con «Usar este nombre», sin sustituir lo que escribes automáticamente. Las imágenes encontradas se guardan como referencias URL en la descripción del producto de Grocy y se muestran en la ficha, Mi despensa y Lista de la compra. También puedes subir una foto saneada al almacenamiento persistente del complemento. Puede haber productos sin fotografía o con nombre incompleto en esos catálogos; puedes introducir el nombre y subir una foto manualmente.

> **Controles rápidos:** los productos fuera de la lista muestran un botón `🛒 Añadir`; al pulsarlo se convierte en `− cantidad +`. Cuando la cantidad vuelve a cero, reaparece el carrito. Todo se actualiza sin recargar la página ni cambiar la posición de desplazamiento. Los cambios se envían a Grocy y se reflejan en la misma fila; si fallan, se muestra un error sin falsear la cantidad.

## Funcionalidades

- **Lista de la compra (inicio):** sincronizada con la lista predeterminada de Grocy; marcar artículos como comprados o quitarlos sin modificar el inventario.
- **Mi despensa:** búsqueda de productos y cantidades actuales obtenidas de Grocy, con controles `− / +` directamente en cada fila para consultar y modificar la cantidad de la lista de compra. Los productos en kg cambian en pasos de 0,10 kg (100 g) y los demás en pasos de 1 unidad.
- **Ficha de producto:** información y existencias, sin formulario para añadir a la compra; editar el nombre, configurar las unidades de compra/stock y piezas por pack cuando corresponda, asociar códigos de barras, guardar imágenes de referencia y modificar existencias con controles de seguridad.
- **Corrección de existencias:** ajustar la cantidad disponible con un máximo de **dos decimales** y guardado directo, sin confirmación adicional; los ajustes se registran como movimientos en Grocy.
- **Alta de productos nuevos:** desde Mi despensa → Nuevo producto, se comprueba nombre y código de barras; si ya existe, se enlaza a su ficha sin crear duplicados. Si es nuevo, se elige unidad de medida, código opcional y stock inicial (admite 0 y hasta dos decimales).
- **Gestión de productos:** añadir un producto nuevo, ajustar la cantidad total que queda desde Existencias e importar un ticket. La ficha ya no muestra «Consumir producto». La asociación de códigos se realiza desde cada ficha de producto.
- **Escáner de cámara:** lectura EAN/UPC desde un móvil compatible, con entrada manual alternativa.
- **Tickets:** subir PDF/JPG/PNG, extraer líneas con OpenAI, revisar, simular y confirmar la importación.
- **Historial de importaciones:** SQLite persistente para evitar registrar de nuevo líneas de tickets ya importadas.

> Para cantidades de compra se admiten hasta **dos decimales**. El control rápido utiliza siempre la unidad de stock de Grocy, sin tocar las existencias; las compras se gestionan desde los controles de las listas, fuera de la ficha. Añadir a la lista no registra entrada de existencias.

> **Pack y Piece:** Pack es unidad de compra; Piece es unidad de stock y consumo. Un pack de 5 debe registrar 5 piezas al comprarlo, no 1 pack como stock. **No se convierte automáticamente el stock existente** al cambiar configuraciones. Las fotos encontradas por código se guardan como referencias en la descripción del producto y la conversión Pack/Piece se comprueba contra Grocy 4.7.1 aislado. Consulta DECISIONS.md y ROADMAP.md.

## Instalar desde Home Assistant (repositorio comunitario)

El repositorio contiene `repository.yaml` y `ha_grocy_ticket_importer/config.yaml`, que Home Assistant utiliza para descubrir el complemento.

1. En Home Assistant ve a **Ajustes → Aplicaciones → Tienda → ⋮ → Repositorios** (las etiquetas pueden aparecer como «Complementos»).
2. Añade esta URL: `https://github.com/molinero95/HA-Grocy-Ticket-Importer`.
3. Busca **Grocy Ticket Importer**, instálalo y abre **Configuración**.
4. Introduce los valores descritos a continuación y guarda.
5. Inicia el complemento y usa **Abrir interfaz web**; puedes habilitar su entrada **Despensa** en la barra lateral.

### Configuración en Home Assistant

La configuración se introduce en el formulario oficial del complemento; **no es necesario crear ni subir un archivo `.env`**.

| Opción | Para qué sirve | Ejemplo |
| --- | --- | --- |
| `grocy_url` | URL de Grocy accesible desde el complemento | `http://a0d7b954-grocy:80` |
| `grocy_api_key` | Clave API generada en Grocy | Contraseña, sin valor público |
| `openai_api_key` | Clave API de OpenAI para extraer tickets | Contraseña, sin valor público |
| `grocy_location_id` | ID de la ubicación de destino en Grocy | `2` |

Las claves se gestionan mediante las opciones del complemento y se entregan al proceso en `/data/options.json`. No deben aparecer en commits, incidencias, capturas ni logs. El almacenamiento de Home Assistant **no sustituye** la protección de tu instancia: sus administradores pueden acceder a las opciones. Las opciones nuevas toman efecto al reiniciar el complemento.

El complemento se ejecuta por **Ingress**, a través de la autenticación de Home Assistant. **No abras el puerto interno 8099** en el router.

## Actualizaciones automáticas de versiones

Con el repositorio público añadido a la tienda de complementos, Home Assistant puede detectar una versión nueva cuando cambia `ha_grocy_ticket_importer/config.yaml → version`.

- Para comprobarlo, utiliza **Buscar actualizaciones** en la tienda.
- Home Assistant debería ofrecer el botón **Actualizar** sin descargar ZIP ni copiar archivos.
- Las actualizaciones automáticas se pueden activar si se desea, después de verificar que las actualizaciones manuales funcionan correctamente.

**Importante:** publicar código en GitHub no publica automáticamente una GitHub Release, y una GitHub Release no es imprescindible para que Home Assistant detecte la versión del complemento. Las versiones deben incrementarse en `config.yaml` y las pruebas de GitHub Actions deben estar verdes antes de actualizar.

## Acceso desde Android

Abre el complemento **Despensa** en la aplicación móvil de Home Assistant. La cámara necesita un navegador integrado compatible y permisos concedidos. Si no hay acceso a la cámara, puedes escribir el código de barras manualmente. Un acceso directo de Android puede estudiarse después de comprobar el comportamiento del enlace Ingress.

## Desarrollo y pruebas

React/TypeScript y API Flask; los módulos Python raíz y del paquete permanecen idénticos. CI ejecuta pruebas Python, Vitest, compilación, contratos con Grocy 4.7.1 real aislado, Chromium móvil/ingress y construcción/arranque de contenedores AMD64 y ARM64. Las pruebas nunca usan datos reales. Reproducción y límites: [VALIDATION_V1.md](docs/VALIDATION_V1.md).

## Licencia

Este proyecto se distribuye bajo la **licencia MIT**. Consulta el archivo [LICENSE](LICENSE). Las bibliotecas y servicios externos mantienen sus propias licencias y condiciones de uso.

## Privacidad y seguridad

- No subir `.env`, `.env.*`, claves API, certificados, tickets reales, fotografías personales, bases de datos SQLite ni registros de producción.
- `.gitignore` protege contra inclusiones futuras accidentales, **pero no limpia el historial de Git**.
- Antes de cambiar la visibilidad del repositorio, revisar **todos los commits antiguos y sus adjuntos** para detectar secretos o datos personales; si alguna credencial se filtró, revocarla/rotarla.
- Antes de publicar el repositorio se debe completar la auditoría del historial para evitar exponer datos personales o credenciales.

Documentación específica del complemento: [ha_grocy_ticket_importer/DOCS.md](ha_grocy_ticket_importer/DOCS.md).


## Sincronización Alexa ↔ Grocy (opcional)

La integración **Alexa Devices** de Home Assistant necesita una entidad `todo.*`
para la lista elegida. Despensa sincroniza exclusivamente esa lista y la lista
predeterminada de Grocy (ID 1). Se excluyen los artículos completados de Alexa.
Configura `alexa_shopping_list_entity` y habilita `shopping_sync_enabled`
**solo después de validar el flujo real**. Por defecto sigue desactivado.
Si configuras únicamente la entidad Alexa, el complemento ya actualiza la
cola de sugerencias de **Lista de la compra** en modo de solo lectura, aunque la
sincronización esté desactivada. Consultar sugerencias no cambia listas. Las acciones manuales **Guardar elección**, **Mantener original** y **Quitar** sí actualizan Grocy de inmediato; no necesitan activar la sincronización ni escriben directamente en Alexa.
El proceso combina eventos con comprobaciones periódicas (120 segundos por
defecto). No modifica existencias ni productos del catálogo.

### Identidades, notas y conflictos

- Los productos se identifican por su **ID canónico de Grocy**, no por su nombre.
  Las coincidencias exactas y únicas pueden asociarse a ese ID; los nombres
  desconocidos o ambiguos se mantienen como **notas de texto libre**.
- En **Lista de la compra → Elegir producto**, una elección manual permite asociar
  un nombre ambiguo a un producto. El nombre original de Alexa no se renombra.
  Al guardar se asocia su nota existente al producto elegido, conservando ID de fila, cantidad y texto original. Si no hay nota, se reutiliza o crea una sola fila del producto. La lista se actualiza y permite marcar comprado o quitar sin esperar al worker.
- **Mantener original** conserva o crea una nota real en Grocy y oculta la sugerencia. **Quitar** está disponible también antes de elegir producto. La retirada queda registrada para evitar que el worker la reintroduzca; solo se propaga a Alexa cuando sync está habilitado.
  Una colisión con otra fila del producto seleccionado o una edición concurrente
  detiene el ciclo; no se duplican ni fusionan artículos.
- El primer ciclo del nuevo sincronizador une las listas sin borrar artículos, salvo retiradas manuales explícitas registradas.
  Los siguientes propagan altas y eliminaciones por identidad tras un
  checkpoint confirmado. Antes de borrar una entrada de Grocy se vuelve a
  verificar su ID, cantidad y nota. Si cambian, se detiene la operación.
- Se comprueban de nuevo ambas listas después de escribir y solo entonces se
  guarda el checkpoint. Las interrupciones no avanzan el estado. Una elección
  obsoleta o un cambio inesperado de identidad bloquea el ciclo hasta revisarlo.
- No se sincronizan cantidades, unidades, estados de compra ni cambios de nombre.
  Una eliminación de la lista no borra productos ni modifica inventario.

### Persistencia y migración

Cada entidad Alexa tiene su propio checkpoint v2 en
`/data/shopping-sync-<hash>-identity-v2.json` y su cola de revisión en
`/config/alexa-match-queue-<hash>.sqlite3`. Los nombres de archivo se
derivan de un hash del identificador de la entidad; no se registra su contenido.
Los archivos v1 y la cola antigua **se conservan sin migración automática**.
Al actualizar desde v1, el primer ciclo v2 vuelve a ser una unión conservadora;
puede reintroducir una nota que se había eliminado anteriormente. Las elecciones
manuales de la cola antigua deberán revisarse de nuevo, evitando asignarlas
accidentalmente a otra lista Alexa. Incluye ambos directorios en la copia de
seguridad de Home Assistant.

**Antes del despliegue:** comprobar las escrituras de la entidad Home Assistant/Alexa
y la actualización con copia de seguridad. Sus lecturas y el esquema de Grocy
instalado ya responden correctamente. Grocy 4.7.1, reinicio y flujos de extremo
a extremo ya se validan con datos desechables; no equivalen a esa instalación.

## Productos genéricos y variantes

Un artículo de Grocy es el **producto genérico** (por ejemplo, «Leche entera»).
En su ficha pueden registrarse variantes por supermercado con nombre, marca,
EAN/UPC y unidades por compra. El escáner de cámara introduce el código.
Todas las variantes pertenecen al **mismo ID de Grocy**, por lo que comparten
existencias. La asociación exige comprobar la propiedad del código en Grocy y
en la base local, y rechaza conflictos sin fusionar artículos.

El metadato se conserva en `/config/generic_catalog.sqlite3`. En
**Acciones → Detectar duplicados** se puede descargar una auditoría JSON de
solo lectura con productos, códigos, unidades, existencias, referencias de
compra y variantes. Es necesaria una revisión y autorización explícita antes
de consolidar productos existentes. No subas exportaciones reales a GitHub.

**Limitación:** las unidades por compra de cada variante son informativas;
no modifican todavía la conversión de Grocy ni la importación de tickets.
No se migran existencias automáticamente. El editor y su persistencia están probados en la suite aislada; verificar
la actualización de la instalación real al instalar esta versión.

## Despensa 1.13.0

React 19, TypeScript 7, Vite 7 y Vitest 4. Frontend canónico en
`ha_grocy_ticket_importer/frontend/`; `frontend/` es un enlace. El contenedor
compila y sirve React en `/`, con alias `/react/` y compras básicas sin
JavaScript en `/basic`. El frontend HTML/JS anterior está retirado.
La versión del manifiesto es 1.13.0; Home Assistant ofrece actualizar la instalación existente al refrescar la tienda. La publicación no instala automáticamente el complemento.

Para desarrollo local, `npm ci`, `npm test` y `npm run build` en `frontend/`.
Configura `FRONTEND_DIST_DIR` con la ruta absoluta a `frontend/dist` para Flask.
La [guía de validación](docs/VALIDATION_V1.md) incluye la suite completa contra
Grocy oficial con datos temporales y los límites de cámara/HA/Alexa reales.

Se preservan fotos, historial de tickets, variantes, colas y checkpoints Alexa.
El registro `stock-commands.sqlite3` reside junto al historial (configurable con
`STOCK_COMMAND_DB`); nunca borrarlo para repetir un resultado incierto. Si el
consumo se confirma y falla la reposición, añadir solo la compra pendiente.

La búsqueda por nombre o código funciona al escribir; la barra solo tiene el campo de texto y la cámara. El botón **Nuevo producto** se encuentra solo en Mi despensa. La ficha permite **Archivar** productos sin existencias ni dependencias y
**Restaurar** desde Acciones → Productos archivados. Archivar/restaurar conserva historial e identidad. Duplicados permite marcar diferencias o revisar una combinación nativa.
No hay migración automática de stock Pack antiguo ni combinación automática de productos.
Consulta la [matriz de paridad](docs/REACT_PARITY.md) y [ROADMAP](ROADMAP.md).

## Alias y estado de Alexa (1.6.0)

En **Acciones → Alias de Alexa**, selecciona un producto para ver y añadir varios alias. Los productos ausentes o archivados tienen una sección para retirar sus alias. Los alias conservan el nombre original en Alexa; no modifican inventario.

La lista muestra si el worker ha fallado o no ha confirmado una sincronización reciente. Si una nota de Grocy coincide exactamente con un producto, abre **Elegir producto** en esa fila y guarda la asociación, o quita únicamente el artículo original. La asociación conserva ID, cantidad y texto. Un producto ya presente o notas duplicadas no se fusionan. La sincronización reanudará su ciclo después de resolver el conflicto; la actualización no modifica automáticamente tus listas.

## Sugerencias actualizadas y sincronización reactiva (1.7.0)

Las sugerencias se recalculan al consultar la lista con el catálogo activo: incluyen nuevos productos, cambios de nombre y archivados. Crear un producto actualiza las sugerencias antes de terminar la búsqueda opcional de fotos. Las decisiones guardadas y retiradas se conservan; una elección obsoleta se muestra para revisión.

Un cambio guardado desde Despensa despierta al sincronizador mediante un aviso local comprobado cada 250 ms. Los eventos de Home Assistant también lo despiertan; el intervalo configurado (120 segundos por defecto) queda como respaldo. La pantalla refresca cada 5 segundos. Para cambios hechos en Alexa, primero Home Assistant debe recibir el cambio de su integración. No se modifican tus opciones al actualizar ni se activan escrituras con sync deshabilitado.


## Existencias, archivados y navegación (1.8.0)

Mi despensa destaca en ámbar los productos sin stock y muestra **Sin existencias**, aunque ya estén en la lista de compra. Los archivados mantienen su estilo neutro.

Para eliminar un producto sin uso: **Acciones → Productos archivados → ficha → Revisar eliminación**. Solo se permite con stock cero, sin referencias de compra, recetas, productos dependientes, variantes o Alexa. La revisión explica cada impedimento. Escribe el nombre exacto para confirmar el borrado irreversible de la ficha, códigos y configuración de unidades. Se comprueba otra vez antes de enviar. Desde 1.10.0, si tiene movimientos de Grocy, se muestra cuántos y hay que aceptar expresamente su eliminación irreversible. Los registros locales de tickets ya importados, fotos y checkpoints se conservan; importaciones pendientes o inciertas bloquean el borrado. Ante un resultado incierto, comprueba Grocy y vuelve a abrir la ficha; no reenvíes la misma operación.

**Atrás** cierra primero el diálogo/cámara y vuelve entre las secciones visitadas. En el inicio se conserva la salida normal al contenedor. El botón de pantalla completa se ha retirado en 1.10.0 por petición del usuario; se conserva la navegación interna.

La auditoría de borrado cubre las cascadas de Grocy 4.7.1 y serializa los escritores de Despensa con su worker. Grocy no ofrece un borrado condicional transaccional: evita editar ese producto directamente en Grocy u otras aplicaciones mientras confirmas la eliminación.

La eliminación solo se habilita en Grocy 4.7.1, cuya cascada está verificada; otras versiones conservan el archivado hasta revisar sus reglas de borrado.


## Resolver duplicados (1.9.0)

En **Acciones → Revisar duplicados y auditoría**, cada pareja ofrece **Son diferentes**: guarda esa decisión por ID para no volver a sugerirla, incluso tras renombrar. En **Productos marcados como diferentes** puedes deshacerla. Con tres productos, descartar una pareja conserva las demás.

**Revisar combinación** permite elegir **Producto que conservarás**. Se mantienen su nombre, descripción, foto y configuración, y Grocy reúne los lotes, historial, códigos y referencias del otro producto. Es irreversible: revisa los datos y escribe el nombre exacto del producto que conservarás. Las existencias de ambos se conservan, sin consumo ni ajustes ficticios.

La combinación está verificada para Grocy 4.7.1 y unidades/conversiones compatibles. Si el origen tiene tickets importados, variantes locales, alias o vínculos Alexa, debes conservar ese producto como destino o resolver esas dependencias antes. También se bloquean jerarquías, tara, campos personalizados de origen, cantidades desconocidas y filas de ambos productos en la lista de compra predeterminada. La revisión explica los bloqueos. No se modifican registros locales para forzar una combinación.

Ante una respuesta incierta, comprueba ambos productos en Grocy antes de volver a intentarlo; la misma operación no se reenvía. Evita editar esos productos desde otras aplicaciones durante la confirmación.


En 1.10.0 las confirmaciones de «Son diferentes», deshacer y otras acciones correctas se muestran en verde. El rojo queda para avisos de error o acciones destructivas.


## Umbral y avisos por producto (1.10.0)

En la ficha, **Umbral de aviso de stock** permite indicar una cantidad mínima: por defecto **0**. Mi despensa muestra amarillo cuando la cantidad es igual o inferior al umbral, con **Stock bajo** si queda producto y **Sin existencias** al llegar a cero.

Marca **No avisar de stock bajo** para desactivar el color y las etiquetas de ese producto, incluso sin existencias; el umbral se conserva por si reactivas los avisos. Guarda los cambios con **Guardar umbral**. Es solo un aviso visual: no modifica existencias ni añade compras automáticamente.


## Crear productos desde Alexa o la compra (1.11.0)

Cada artículo de texto ofrece **Crear producto para «…»**, aunque no haya ninguna sugerencia. Se abre el formulario con su nombre rellenado; puedes cambiarlo y elegir unidad/código/envase. Desde esta vía se crea **sin existencias** y queda asociado automáticamente al mismo artículo, conservando su cantidad y nota. Después puedes marcarlo comprado o quitarlo.

Si el nombre/código ya pertenece a un producto, no se duplica ni cambia su stock: revisa el producto existente y pulsa **Asociar este producto**. Si el producto se creó pero no se pudo confirmar la asociación, se conserva y el formulario permite **Revisar estado** antes de completarla; no vuelve a crear el producto ni reescribe una fila ya asociada.

El vínculo usa el ID del producto para esa aparición del artículo de Alexa, incluso con nombre canónico distinto, sin renombrar Alexa. Una nueva aparición tras desaparecer inicia otra revisión. Para nombres alternativos permanentes sigue disponible Acciones → Alias de Alexa.


## Revisión completa de tickets (1.12.0)

Tras escanear, corrige **Cantidad del ticket**, **Unidad de stock** y **Piezas por envase**, o selecciona un **Producto de Despensa** existente. Su configuración de compra se muestra en la revisión. Para un artículo nuevo, elige **Crear producto nuevo al importar** y escribe su nombre. El alta ocurre al confirmar, nunca al simular.

**Cantidad final calculada** es de solo lectura y cambia al editar: 2 envases de 6 añaden 12 piezas. Se conserva el coste original de cada línea y el total del ticket; corregir unidades no cambia el importe pagado. Las cantidades pesadas admiten tres decimales.

**Recordar este artículo para este supermercado** guarda el vínculo después de importar correctamente. Un texto distinto puede apuntar al mismo producto, sin renombrarlo; cada supermercado tiene sus propias asociaciones. En el siguiente ticket se selecciona el producto recordado. Si falta, está archivado o cambia su configuración, debes revisarlo. Cambiar una línea invalida la simulación; las líneas pendientes de revisión bloquean la confirmación. El historial de importaciones sigue impidiendo duplicar existencias.


## Voz y reconocimiento de productos (1.13.0)

El endpoint de Alexa está implementado para consultas de existencias, alias y productos con stock bajo. Se ejecuta en un proceso separado y está **desactivado por defecto**. La configuración de Amazon y Cloudflare se hará después; publicar esta versión no activa el acceso. Consulta [la guía de la skill](docs/ALEXA_SKILL.md) y el [modelo español](docs/alexa/interaction-model-es-ES.json).

Si un código no está asociado a tu catálogo, **Dar de alta este código** abre el formulario con ese código y la imagen completa capturada por el escáner. Cuando los catálogos públicos no devuelven un nombre o fallan, aparece **Identificar con una foto**. Puedes conservar esa toma o fotografiar el frontal del envase y su etiqueta. **Analizar foto con OpenAI** envía la fotografía completa, sin recortarla al código, y muestra una sugerencia editable. **Usar nombre sugerido** aplica únicamente el nombre al formulario; guardar el producto sigue siendo una acción separada.

La foto permanece en memoria del navegador hasta el envío explícito. Se sanea sin EXIF, se limita a 8 MiB/25 megapíxeles y se redimensiona manteniendo el encuadre. Se usa la clave OpenAI existente; la solicitud de análisis puede generar consumo en esa cuenta. No se trata de una búsqueda web ni de una verificación del EAN: el modelo interpreta lo visible y puede equivocarse. El código y los factores de compra se conservan. Puedes seguir introduciendo el nombre manualmente.
