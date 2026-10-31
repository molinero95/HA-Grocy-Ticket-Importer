# Despensa — Grocy Ticket Importer para Home Assistant

[![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Complemento para **Home Assistant OS** que integra [Grocy](https://grocy.info/) con una interfaz móvil en español para consultar existencias, escanear códigos de barras y digitalizar tickets de compra mediante OpenAI.

> **Estado:** versión de desarrollo. La instalación desde repositorio y la configuración nativa aún requieren validación en Home Assistant.

## Funcionalidades

- **Lista de la compra (inicio):** sincronizada con la lista predeterminada de Grocy; marcar artículos como comprados o quitarlos sin modificar el inventario.\n- **Mi despensa:** búsqueda de productos y cantidades actuales obtenidas de Grocy, con controles `− / +` directamente en cada fila para consultar y modificar la cantidad de la lista de compra. Los productos en kg cambian en pasos de 0,10 kg (100 g) y los demás en pasos de 1 unidad.
- **Ficha de producto:** editar el nombre, definir unidades por envase, consultar o cambiar la unidad de medida (cuando no hay existencias), asociar códigos de barras y buscar una foto de referencia.\n- **Corrección de existencias:** ajustar la cantidad disponible con un máximo de **dos decimales** y guardado directo, sin confirmación adicional; los ajustes se registran como movimientos en Grocy.
- **Alta de productos nuevos:** desde Acciones → Añadir producto, se comprueba nombre y código de barras; si ya existe, se enlaza a su ficha sin crear duplicados. Si es nuevo, se elige unidad de medida, código opcional y stock inicial (admite 0 y hasta dos decimales).
- **Acciones separadas:** añadir un producto nuevo, consumir una unidad, asociar un código a un producto existente e importar un ticket.
- **Escáner de cámara:** lectura EAN/UPC desde un móvil compatible, con entrada manual alternativa.
- **Tickets:** subir PDF/JPG/PNG, extraer líneas con OpenAI, revisar, simular y confirmar la importación.
- **Historial de importaciones:** SQLite persistente para evitar registrar de nuevo líneas de tickets ya importadas.

> Para cantidades de compra se admiten hasta **dos decimales**. El control rápido utiliza siempre la unidad de stock de Grocy, sin tocar las existencias; la edición avanzada puede usar otras unidades si tienen una conversión válida. Añadir a la lista no registra entrada de existencias.\n\n> «Unidades por envase» es una propiedad informativa de la ficha. Por ejemplo, indicar «4» en un pack de aromas de vainilla **no convierte automáticamente un envase en cuatro unidades de stock**. La vista previa de fotografía tampoco la guarda todavía en Grocy. La unidad de stock no puede cambiarse con existencias sin convertirlas antes, para evitar confundir unidades con kilogramos.

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
