# Despensa — Grocy Ticket Importer para Home Assistant

[![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Para futuros agentes:** antes de cambiar código, leer [AGENTS.md](AGENTS.md) (instrucciones y seguridad), [DECISIONS.md](DECISIONS.md) (requisitos acordados) y [ROADMAP.md](ROADMAP.md) (pendientes y verificación de CI). Si hay una contradicción de comportamiento, priorizar DECISIONS.md y comprobar el código actual.

Complemento para **Home Assistant OS** que integra [Grocy](https://grocy.info/) con una interfaz móvil en español para consultar existencias, escanear códigos de barras y digitalizar tickets de compra mediante OpenAI.

> **Versión 1.0.0:** migración React integrada desde PR #10. Home Assistant detecta esta versión mediante el manifiesto del complemento. Actualiza la instalación existente con copia de seguridad, sin desinstalar. Validación automatizada contra Grocy 4.7.1 aislado; cámara Android, escrituras Alexa y aceptación de la actualización real siguen pendientes.

> **Fotos de productos:** al escanear o introducir un código de barras, se consulta Open Food Facts automáticamente. Las imágenes encontradas se guardan como referencias URL en la descripción del producto de Grocy y se muestran en la ficha, Mi despensa y Lista de la compra. También puedes subir una foto saneada al almacenamiento persistente del complemento. Puede haber productos sin fotografía.

> **Controles rápidos:** los productos fuera de la lista muestran un botón `🛒 Añadir`; al pulsarlo se convierte en `− cantidad +`. Cuando la cantidad vuelve a cero, reaparece el carrito. Todo se actualiza sin recargar la página ni cambiar la posición de desplazamiento. Los cambios se envían a Grocy y se reflejan en la misma fila; si fallan, se muestra un error sin falsear la cantidad.

## Funcionalidades

- **Lista de la compra (inicio):** sincronizada con la lista predeterminada de Grocy; marcar artículos como comprados o quitarlos sin modificar el inventario.
- **Mi despensa:** búsqueda de productos y cantidades actuales obtenidas de Grocy, con controles `− / +` directamente en cada fila para consultar y modificar la cantidad de la lista de compra. Los productos en kg cambian en pasos de 0,10 kg (100 g) y los demás en pasos de 1 unidad.
- **Ficha de producto:** editar el nombre, configurar las unidades de compra/stock y piezas por pack cuando corresponda, asociar códigos de barras, guardar imágenes de referencia y modificar existencias con controles de seguridad.
- **Corrección de existencias:** ajustar la cantidad disponible con un máximo de **dos decimales** y guardado directo, sin confirmación adicional; los ajustes se registran como movimientos en Grocy.
- **Alta de productos nuevos:** desde Acciones → Añadir producto, se comprueba nombre y código de barras; si ya existe, se enlaza a su ficha sin crear duplicados. Si es nuevo, se elige unidad de medida, código opcional y stock inicial (admite 0 y hasta dos decimales).
- **Acciones separadas:** añadir un producto nuevo, consumir una cantidad elegida (con opción de añadir la misma cantidad a la lista de la compra) e importar un ticket. La asociación de códigos se realiza desde cada ficha de producto.
- **Escáner de cámara:** lectura EAN/UPC desde un móvil compatible, con entrada manual alternativa.
- **Tickets:** subir PDF/JPG/PNG, extraer líneas con OpenAI, revisar, simular y confirmar la importación.
- **Historial de importaciones:** SQLite persistente para evitar registrar de nuevo líneas de tickets ya importadas.

> Para cantidades de compra se admiten hasta **dos decimales**. El control rápido utiliza siempre la unidad de stock de Grocy, sin tocar las existencias; la edición avanzada puede usar otras unidades si tienen una conversión válida. Añadir a la lista no registra entrada de existencias.

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
cola de **Acciones → Coincidencias Alexa** en modo de solo lectura, aunque la
sincronización esté desactivada. Esto permite revisar sugerencias sin añadir,
eliminar ni modificar artículos en Alexa o Grocy.
El proceso combina eventos con comprobaciones periódicas (120 segundos por
defecto). No modifica existencias ni productos del catálogo.

### Identidades, notas y conflictos

- Los productos se identifican por su **ID canónico de Grocy**, no por su nombre.
  Las coincidencias exactas y únicas pueden asociarse a ese ID; los nombres
  desconocidos o ambiguos se mantienen como **notas de texto libre**.
- En **Acciones → Coincidencias Alexa**, una elección manual permite asociar
  un nombre ambiguo a un producto. El nombre original de Alexa no se renombra.
  En el siguiente ciclo habilitado puede asociar su nota existente al producto
  elegido, conservando ID de fila, cantidad y texto original.
- **Mantener original** descarta la sugerencia sin modificar remotamente la nota.
  Una colisión con otra fila del producto seleccionado o una edición concurrente
  detiene el ciclo; no se duplican ni fusionan artículos.
- El primer ciclo del nuevo sincronizador une las listas sin borrar artículos.
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

## Despensa 1.0.0

React 19, TypeScript 7, Vite 7 y Vitest 4. Frontend canónico en
`ha_grocy_ticket_importer/frontend/`; `frontend/` es un enlace. El contenedor
compila y sirve React en `/`, con alias `/react/` y compras básicas sin
JavaScript en `/basic`. El frontend HTML/JS anterior está retirado.
La versión del manifiesto es 1.0.0; Home Assistant ofrece actualizar desde 0.16.4 al refrescar la tienda. La publicación no instala automáticamente el complemento.

Para desarrollo local, `npm ci`, `npm test` y `npm run build` en `frontend/`.
Configura `FRONTEND_DIST_DIR` con la ruta absoluta a `frontend/dist` para Flask.
La [guía de validación](docs/VALIDATION_V1.md) incluye la suite completa contra
Grocy oficial con datos temporales y los límites de cámara/HA/Alexa reales.

Se preservan fotos, historial de tickets, variantes, colas y checkpoints Alexa.
El registro `stock-commands.sqlite3` reside junto al historial (configurable con
`STOCK_COMMAND_DB`); nunca borrarlo para repetir un resultado incierto. Si el
consumo se confirma y falla la reposición, añadir solo la compra pendiente.

La ficha permite **Archivar** productos sin existencias ni dependencias y
**Restaurar** desde Ver archivados. Conserva historial e identidad; no borra ni
consume stock. Detectar duplicados sigue siendo una auditoría de solo lectura.
No hay migración automática de stock Pack antiguo ni consolidación de productos.
Consulta la [matriz de paridad](docs/REACT_PARITY.md) y [ROADMAP](ROADMAP.md).
