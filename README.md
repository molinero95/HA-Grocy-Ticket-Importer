# Despensa — Grocy Ticket Importer para Home Assistant

[![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Para futuros agentes:** antes de cambiar código, leer [AGENTS.md](AGENTS.md) (instrucciones y seguridad), [DECISIONS.md](DECISIONS.md) (requisitos acordados) y [ROADMAP.md](ROADMAP.md) (pendientes y verificación de CI). Si hay una contradicción de comportamiento, priorizar DECISIONS.md y comprobar el código actual.

Complemento para **Home Assistant OS** que integra [Grocy](https://grocy.info/) con una interfaz móvil en español para consultar existencias, escanear códigos de barras y digitalizar tickets de compra mediante OpenAI.

> **Estado:** versión de desarrollo en GitHub; el complemento ya ha sido detectado por Home Assistant, pero cada actualización y cambio de Grocy requiere validación. No considerar el pipeline verde sin comprobar una ejecución concreta.

> **Fotos de productos:** al escanear o introducir un código de barras, se consulta Open Food Facts automáticamente. Las imágenes encontradas se guardan como referencias URL en la descripción del producto de Grocy y se muestran en la ficha, Mi despensa y Lista de la compra. No se suben archivos de imagen a Grocy y puede haber productos sin fotografía.\n\n> **Controles rápidos:** los productos fuera de la lista muestran un botón `🛒 Añadir`; al pulsarlo se convierte en `− cantidad +`. Cuando la cantidad vuelve a cero, reaparece el carrito. Todo se actualiza sin recargar la página ni cambiar la posición de desplazamiento. Los cambios se envían a Grocy y se reflejan en la misma fila; si fallan, se muestra un error sin falsear la cantidad.\n\n## Funcionalidades

- **Lista de la compra (inicio):** sincronizada con la lista predeterminada de Grocy; marcar artículos como comprados o quitarlos sin modificar el inventario.\n- **Mi despensa:** búsqueda de productos y cantidades actuales obtenidas de Grocy, con controles `− / +` directamente en cada fila para consultar y modificar la cantidad de la lista de compra. Los productos en kg cambian en pasos de 0,10 kg (100 g) y los demás en pasos de 1 unidad.
- **Ficha de producto:** editar el nombre, configurar las unidades de compra/stock y piezas por pack cuando corresponda, asociar códigos de barras, guardar imágenes de referencia y modificar existencias con controles de seguridad.\n- **Corrección de existencias:** ajustar la cantidad disponible con un máximo de **dos decimales** y guardado directo, sin confirmación adicional; los ajustes se registran como movimientos en Grocy.
- **Alta de productos nuevos:** desde Acciones → Añadir producto, se comprueba nombre y código de barras; si ya existe, se enlaza a su ficha sin crear duplicados. Si es nuevo, se elige unidad de medida, código opcional y stock inicial (admite 0 y hasta dos decimales).
- **Acciones separadas:** añadir un producto nuevo, consumir una cantidad elegida (con opción de añadir la misma cantidad a la lista de la compra) e importar un ticket. La asociación de códigos se realiza desde cada ficha de producto.
- **Escáner de cámara:** lectura EAN/UPC desde un móvil compatible, con entrada manual alternativa.
- **Tickets:** subir PDF/JPG/PNG, extraer líneas con OpenAI, revisar, simular y confirmar la importación.
- **Historial de importaciones:** SQLite persistente para evitar registrar de nuevo líneas de tickets ya importadas.

> Para cantidades de compra se admiten hasta **dos decimales**. El control rápido utiliza siempre la unidad de stock de Grocy, sin tocar las existencias; la edición avanzada puede usar otras unidades si tienen una conversión válida. Añadir a la lista no registra entrada de existencias.\n\n> **Pack y Piece:** Pack es unidad de compra; Piece es unidad de stock y consumo. Un pack de 5 debe registrar 5 piezas al comprarlo, no 1 pack como stock. **No se convierte automáticamente el stock existente** al cambiar configuraciones. Las fotos encontradas por código se guardan como referencias en la descripción del producto y la conversión Pack/Piece sigue pendiente de validación integral en Grocy. Consulta DECISIONS.md y ROADMAP.md.

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

Código Python para la integración de Grocy y la interfaz Flask; archivos empaquetados en `ha_grocy_ticket_importer/`. GitHub Actions prueba el código con Python 3.11 y 3.13, valida los scripts JavaScript, comprueba que el código fuente y el empaquetado coincidan y construye la imagen del complemento.

```bash
python -m unittest discover -v -p 'test_*.py'
```

No ejecuta llamadas reales a Grocy ni a OpenAI en los tests automatizados.

## Licencia

Este proyecto se distribuye bajo la **licencia MIT**. Consulta el archivo [LICENSE](LICENSE). Las bibliotecas y servicios externos mantienen sus propias licencias y condiciones de uso.

## Privacidad y seguridad

- No subir `.env`, `.env.*`, claves API, certificados, tickets reales, fotografías personales, bases de datos SQLite ni registros de producción.
- `.gitignore` protege contra inclusiones futuras accidentales, **pero no limpia el historial de Git**.
- Antes de cambiar la visibilidad del repositorio, revisar **todos los commits antiguos y sus adjuntos** para detectar secretos o datos personales; si alguna credencial se filtró, revocarla/rotarla.
- Antes de publicar el repositorio se debe completar la auditoría del historial para evitar exponer datos personales o credenciales.

Documentación específica del complemento: [ha_grocy_ticket_importer/DOCS.md](ha_grocy_ticket_importer/DOCS.md).


## Sincronización Alexa ↔ Grocy (experimental, v0.7.11)

La integración **Alexa Devices** de Home Assistant debe estar configurada y mostrar una entidad de lista de compra. La sincronización trabaja exclusivamente con la lista principal de Alexa y la lista predeterminada de Grocy (ID 1). No sincroniza otras listas de Alexa, el historial completado ni las existencias del inventario.

El complemento solicita `homeassistant_api: true` para utilizar el token de Supervisor y comunicarse con Home Assistant internamente; no es necesario copiar tokens a GitHub. La configuración `shopping_sync_enabled` está **desactivada por defecto**. El proceso de sincronización se inicia al arrancar el complemento solo cuando esta opción está activada y revisa los cambios cada 120 segundos.

**No activar aún en producción:** la integración de escritura de Grocy y el formato de respuesta del servicio de listas de Home Assistant requieren una prueba de extremo a extremo. La PR #2 es experimental y no se ha desplegado. La versión instalada puede seguir siendo 0.7.10.

### Comportamiento previsto

- Primer ciclo: combina los artículos pendientes de ambas listas sin borrar los existentes.
- Ciclos posteriores: detecta altas y eliminaciones mediante un registro de nombres normalizados; evita duplicados por mayúsculas, espacios y tildes.
- Un artículo de Alexa sin producto en el catálogo de Grocy se añade como nota de compra, sin generar stock ni crear un producto.
- Si una escritura falla, no se avanza el registro persistente; se vuelve a comprobar el estado remoto en el siguiente intento.
- **Limitaciones actuales:** la identidad es por nombre, no por ID; no se sincronizan cantidades, unidades, compras completadas ni renombrados. Los nombres duplicados equivalentes producen error de validación para evitar pérdidas. El borrado propagado elimina la entrada de la lista, no el producto del catálogo.

El estado se guarda en `/data/shopping-sync.json`. Conservar este archivo durante las actualizaciones; eliminarlo provoca una nueva unión inicial y puede reintroducir artículos. Ver [DOCS.md](ha_grocy_ticket_importer/DOCS.md) y [ROADMAP.md](ROADMAP.md) antes de activar la función.


**Selección de lista Alexa:** configura `alexa_shopping_list_entity` con el identificador `todo.*` de la lista deseada (por ejemplo, desde Herramientas para desarrolladores → Estados). Es obligatorio cuando `shopping_sync_enabled` está activado; vacío por defecto. Cada entidad tiene su propio archivo de estado para no reutilizar eliminaciones de otra lista. Cambiar de lista inicia una nueva unión inicial sin borrar los artículos existentes.

## Productos genéricos y variantes (desarrollo, pendiente de publicación)

Cada artículo de Grocy puede ser el **producto genérico** (por ejemplo, «Leche entera»).
En su ficha se pueden registrar variantes por supermercado con nombre, marca,
código EAN/UPC y unidades por compra. El escáner de cámara sirve para introducir
el código. Todas las variantes se asocian al **mismo ID de producto en Grocy**:
no se crea stock separado y registrar una variante no modifica las existencias.

Antes de guardar, Despensa comprueba la propiedad del código en Grocy y en su
catálogo local. Si otro producto ya lo tiene, se rechaza sin fusionar artículos.
El catálogo auxiliar se conserva en `/config/generic_catalog.sqlite3` (volumen
`app_config` del complemento); debe incluirse en las copias de seguridad.
La ficha solo muestra variantes añadidas explícitamente: **no se migran ni
consolidan productos existentes automáticamente**.

En **Acciones → Detectar duplicados** hay una descarga de auditoría JSON de
solo lectura con productos, códigos, unidades, stock, referencias de la lista
de compra y variantes. Revisa y conserva esa exportación antes de cualquier
consolidación manual. No subas exportaciones reales a GitHub.

**Limitación actual:** el factor de unidades por compra de la variante es
metadato; no modifica automáticamente la conversión de unidades ni la
importación de tickets. La asociación de Alexa por identidad, los casos
ambiguos y la validación de extremo a extremo siguen pendientes.
No actives nuevas opciones de sincronización basándote únicamente en esta
funcionalidad.

### Coincidencias ambiguas de Alexa (desarrollo)

Cuando la sincronización Alexa está activada, se calculan sugerencias de
catálogo para los nombres no exactos. Las coincidencias dudosas se guardan
en `/config/alexa-match-queue.sqlite3` y aparecen en
**Acciones → Coincidencias Alexa**. Se puede seleccionar explícitamente
un candidato, pero **esa selección es una propuesta**: todavía no
transforma una nota en un artículo de Grocy, no cambia existencias y no
modifica el registro de sincronización. Los nombres originales se conservan.
Las propuestas desaparecen de la vista cuando el artículo ya no está
pendiente en Alexa, sin borrar el historial de revisión.
