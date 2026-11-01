# Despensa 1.0 — validación reproducible

Fecha: 2026-11-01. Migración de PR #10 integrada en `main`; publicación 1.0.0 autorizada para actualizar desde 0.16.4. No se acredita instalación ni aceptación física por publicar el manifiesto.

## Evidencia local

- Python: 297 regresiones de dominio/API, permisos, CSRF, concurrencia, idempotencia y empaquetado.
- Vitest 4: 79 pruebas de interacciones React y cliente API en 1.8.0; incluye nombre descubierto explícito y las regresiones de stock/navegación/elección y retirada manual.
- TypeScript 7: aplicación y e2e; Vite 7: compilación de producción.
- Grocy real: 9 contratos (Pack/consumo repetido, ticket/importador, foto/variante tras reinicio, otras listas/notas/completados, compra y archivado conservando historial, elección inmediata/checkbox/quitar sin worker ni escrituras Alexa).
- Chromium: 23 escenarios móviles, ingress, fallback sin JavaScript y flujos completos con Grocy real: alta/stock/foto/variante/escáner, tickets repetidos, worker Alexa/elección/descartar/reinicio, Pack y archivar/restaurar. Seis escenarios nuevos cubren anchos de 360/768/1280 px, foco en diálogos anidados/Escape/scroll, respuesta de compra perdida y caducidad de sesión.

## Refuerzo de QA del frontend

Las pruebas de componentes cubren ajuste del total restante sin formulario de consumo, alta solo en Mi despensa, archivados en Acciones, doble pulsación, escrituras inciertas sin reintento, compras desde las listas, configuración Pack/Piece y sus estados esperados, validación de factores, errores conservando formularios, propiedad de códigos/variantes, fotos tardías y permisos/limpieza de cámara. Tickets: invalidar simulación tras editar, cancelación de confirmación, bloqueo durante/después del envío y respeto de `ready_to_commit`. Sesión: retirada de datos privados, cancelación de lecturas tardías y regreso inmediato al login. Auditoría: consultas de solo lectura y recuperación tras fallo.

Estas regresiones detectaron y corrigieron tres defectos: borrar una consulta de autenticación observada podía dejar la vista anterior y recrear caché privada; el frontend ignoraba `ready_to_commit: false`; el botón de alta no aplicaba el máximo de 1000 piezas por pack (el campo HTML y el servidor ya lo limitaban).

`npm run test:coverage` mide V8 sobre el código de aplicación, excluyendo tests, helpers, declaraciones y el punto de montaje `main.tsx`. Resultado local: **76,33 % líneas, 75,27 % sentencias, 79,67 % ramas y 66,45 % funciones**. Configuración de compra y previsualización de fotos: 100 % de líneas; tickets: 96,72 %. Es cobertura de componentes/API: no incorpora los escenarios Chromium ni demuestra exhaustividad o accesibilidad completa. El informe HTML/LCOV/JSON se genera en `frontend/coverage/` y CI lo publica como artefacto `frontend-coverage`; no se incluye en Git ni en el paquete del complemento.

La ejecución local de navegador sin PHP/Grocy ejecuta 14 escenarios disponibles y omitió explícitamente los 5 de Grocy real. CI tiene configurado `GROCY_TEST_DIST` para ejecutar los 19; observar su resultado para el commit de este refuerzo antes de darlo por validado en integración.

Las pruebas antiguas que solo verificaban el HTML retirado o autorizaban eliminación permanente se sustituyen por comprobaciones del comportamiento actual. El total de tests no mide por sí solo la paridad.

## Servicios reales y sustituciones

Grocy **4.7.1**, release oficial sin modificar:
`https://github.com/grocy/grocy/releases/download/v4.7.1/grocy_4.7.1.zip`

SHA256: `c4a10e96ed76664baf465e9b27dc7a31aa08c0e3ad876afdfae4f1ff9ab2fc19`.

PHP 8.5 con pdo_sqlite, intl, mbstring, fileinfo, gd y ctype. Localmente FrankenPHP 1.13.4 / PHP 8.5.12; CI usa PHP nativo 8.5. El servidor tiene datos temporales, escucha en loopback y desactiva autenticación **solo dentro de la instancia desechable**. El código del add-on mantiene sus controles.

Se ejecutan APIs Grocy auténticas, SQLite y migraciones oficiales, importador Python subprocess, worker Alexa, conversiones, historial y reinicio con los mismos datos. No hay fixtures que sustituyan las llamadas a Grocy en la suite real.

Se sustituyen extracción pagada OpenAI, descubrimiento público de foto y API HA todo con respuestas ficticias locales. La cámara usa MediaStream/BarcodeDetector simulado. No hay datos de usuario, mensajes a personas ni cambios en stock real.

## Reproducción

```bash
python -m pip install Flask python-dotenv websocket-client pillow
python -m unittest discover -v -p 'test_*.py'
python tests/download_grocy.py /tmp/despensa-grocy-4.7.1
export GROCY_TEST_DIST=/tmp/despensa-grocy-4.7.1
# PHP 8.5 en PATH; opcional: GROCY_TEST_PHP=/ruta/a/frankenphp
python tests/real_stack_server.py --check
cd frontend
npm ci
npm test
npm run test:coverage
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Sin `GROCY_TEST_DIST`, los cinco escenarios de Grocy real se marcan omitidos de forma explícita; CI lo configura y exige que corran. El comando `--check` requiere el release. Los servidores deben arrancarse desde el mismo entorno de red que el navegador.

## CI y límites

`.github/workflows/python-ci.yml` verifica frontend, contratos reales, navegador y contenedores AMD64/ARM64, arranque HTTP y espejos Python. Consultar el resultado del SHA final en la PR; esta documentación no sustituye esa observación.

Las lecturas de la instalación propia ya responden **HTTP 200**, usando la clave y el puerto interno existentes: Grocy 4.7.1, PHP 8.5.12, SQLite 3.53.4 y esquema DB 257. Se comprobaron unidades Piece/Pack/Kilogram y endpoints de conversiones, productos, compra y referencias de recetas/plan. La entidad HA/Alexa configurada devuelve pendientes con `summary`, `uid` y `status`. No se registran sus nombres ni contenidos en el repositorio.

El primer intento por el proxy ingress devolvía 403; no era una incompatibilidad de Grocy. Se resolvió usando el servicio ya configurado, sin cambiar credenciales, puertos, opciones ni protecciones. No hubo escrituras sobre Grocy o Alexa, actualización del complemento ni activación del sync. Cámara Android física, escrituras Alexa reales y actualización Supervisor con copia de seguridad son aceptación pendiente de un despliegue futuro. Reiniciar el servicio aislado demuestra persistencia de archivos/estado del flujo, no una actualización real del add-on.

CI de la implementación y correcciones de infraestructura (`92034c8`): [ejecución push correcta](https://github.com/molinero95/HA-Grocy-Ticket-Importer/actions/runs/41256121395), incluidos frontend, 5 contratos, 7 navegadores y construcción/arranque AMD64/ARM64. Los cambios posteriores de documentación se vuelven a verificar en la PR.


## Catálogos y controles 1.2.0

Pruebas nuevas verifican Open Beauty Facts tras fallos de Food/Products, 404 frente a servicio caído, código exacto, nombre sin foto, preferencia de foto en otra fuente, hosts/puertos seguros, metadata y CSP. La consulta pública directa del EAN 4006000082295 devuelve foto desde Open Beauty Facts y nombre «Nivea» (incompleto, editable); no se altera inventario ni se usa la cuenta de Home Assistant. Las pruebas automatizadas sustituyen esas fuentes y no dependen de su disponibilidad.

Chromium comprueba el alta con nombre opcional, controles de 44px, resultado de duplicado, botones de auditoría y estilo del selector nativo de archivo; capturas móviles revisadas. La selección de archivos sigue siendo nativa y conserva formatos/límites de subida.

## Consulta universal y ficha 1.3.0

La búsqueda usa primero Open Facts v3 con `product_type=all`; solo sigue redirecciones HTTPS a Food, Products y Beauty y atribuye el origen final. Se comprueban estados v3 y compatibilidad de respaldo v2, códigos incorrectos, datos incompletos, JSON inválido, caídas, ausencia 404 sin consultas redundantes y redirecciones no confiables. La consulta pública del EAN 4006000082295 redirige a Beauty y devuelve foto y nombre «Nivea»; son datos públicos, sin escrituras sobre Grocy/HA.

Se retiran ProductShopping y sus pruebas aisladas al eliminar el formulario de compra de la ficha. La regresión de ficha verifica que ajustar existencias no llama a compras; se conservan pruebas del carrito de Mi despensa y de la API protegida. El flujo Chromium real configura Pack, cierra la ficha, añade dos piezas desde el inventario y verifica stock cero antes de retirar/archivar/restaurar. Los contratos Python reales conservan la prueba de conversión exacta de dos packs a ocho piezas.

## Revisión Día 6 (1.6.0)

La instalación 1.5.0 tiene sync habilitado y el listener conectado. Logs públicos del complemento muestran repetidamente el conflicto `A Grocy note conflicts with a canonical product`; una lectura privada confirma una nota exacta entre las filas activas. No se guardan nombres/contenido de esas filas en código, documentación o artefactos. No se modifica configuración, estado persistente o listas reales durante el diagnóstico. PR #18 figura cerrada sin integrar.

Las nuevas regresiones reproducen el bloqueo, exigen resolución explícita y verifican conservación de ID/cantidad/nota antes de reanudar ambas direcciones. Se añade contrato Grocy real y escenario móvil de revisión, pruebas de API/CSRF y editor de alias. `tests/__init__.py` permite que unittest descubra las regresiones añadidas en Día 6; las pruebas de eventos pasan de funciones no descubiertas a unittest. CI comprueba también los espejos de alias/estado y su empaquetado. La versión instalada solo se considera recuperada después de la actualización y revisión por el usuario.

## Catálogo dinámico y aviso local 1.7.0

Las pruebas cambian productos después de crear la propuesta: altas, renombrados y archivados deben actualizar las opciones en la siguiente lectura, con estado previo conservado si falla el catálogo. Elegir un candidato nuevo revalida el catálogo sin esperar al worker; una fila ya asociada no puede producir una segunda fila al cambiar su elección. Un contrato y escenario de navegador con Grocy real crean primero una nota sin coincidencia, dan de alta su producto y guardan la asociación con la misma fila/cantidad, sin ejecutar otro ciclo del worker.

Un test de hilo/archivo verifica que un marcador de otra entidad no despierta el listener y que el marcador correcto sí lo hace sin esperar el intervalo de 120 s. Las pruebas API comprueban que solo mutaciones confirmadas solicitan sincronización; lecturas, previews, errores y rechazos no lo hacen. La notificación no ejecuta llamadas remotas en la petición HTTP. La entrega de eventos de Alexa y su latencia real siguen requiriendo observación de la instalación actualizada.


## Archivados y navegación 1.8.0

Trece regresiones Python nuevas cubren las referencias de cada cascada, stock desconocido/NaN, archivos locales corruptos, variantes, tickets, colas/alias/checkpoints de otras entidades, CSRF, nombre y snapshot obsoletos, respuesta perdida y repetición del mismo comando. No borran datos de usuario. El nuevo contrato Grocy elimina un archivado desechable con código/conversión y comprueba que stock, historia y listas ajenos son idénticos; bloquea otro archivado con movimientos históricos.

Componentes: confirmación exacta, auditoría fallida y recuperación de lectura, bloqueo tras escritura incierta, caché de archivados, estado sin stock independiente de compra y soporte de fullscreen. Chromium añade Atrás por secciones/cámara/diálogos, sustitución alta→ficha, cierre manual sin paso vacío y captura ámbar móvil sin desbordamiento; un flujo Grocy usa la ficha real para eliminar y verifica ausencia tras recargar. Sin Grocy local se ejecutan 17 escenarios y se omiten explícitamente 6; CI ejecuta los 23.

El historial es del mismo documento y conserva URL/prefijo ingress, sin acceder al documento padre. Android físico y permisos fullscreen del iframe de HA requieren aceptación externa. La API genérica de Grocy no dispone de DELETE condicional atómico: los bloqueos protegen escritores de Despensa/worker, no ediciones simultáneas desde Grocy u otras aplicaciones.

La comprobación de existencias de archivados lee `objects/stock` completo: Grocy rechaza `stock/products/{id}` para productos inactivos. Ninguna fila es cero verificado; cualquier lote o cantidad no finita bloquea el borrado.
