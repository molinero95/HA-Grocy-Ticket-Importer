# Despensa 1.0 — validación reproducible

Fecha: 2026-11-01. Candidata en PR #10; estable 0.16.4 sin publicación ni despliegue.

## Evidencia local

- Python: 200 regresiones de dominio/API, permisos, CSRF, concurrencia, idempotencia y empaquetado.
- Vitest 4: 67 pruebas de interacciones React y cliente API (53 añadidas en el refuerzo de QA).
- TypeScript 7: aplicación y e2e; Vite 7: compilación de producción.
- Grocy real: 5 contratos (Pack/consumo repetido, ticket/importador, foto/variante tras reinicio, otras listas/notas/completados, compra y archivado conservando historial).
- Chromium: 13 escenarios móviles, ingress, fallback sin JavaScript y flujos completos con Grocy real: alta/stock/foto/variante/escáner, tickets repetidos, worker Alexa/elección/descartar/reinicio, Pack y archivar/restaurar. Seis escenarios nuevos cubren anchos de 360/768/1280 px, foco en diálogos anidados/Escape/scroll, respuesta de compra perdida y caducidad de sesión.

## Refuerzo de QA del frontend

Las pruebas de componentes cubren consumo preciso, reposición parcial, doble pulsación, escrituras inciertas sin reintento, compras en unidades verificadas, configuración Pack/Piece y sus estados esperados, validación de factores, errores conservando formularios, propiedad de códigos/variantes, fotos tardías y permisos/limpieza de cámara. Tickets: invalidar simulación tras editar, cancelación de confirmación, bloqueo durante/después del envío y respeto de `ready_to_commit`. Sesión: retirada de datos privados, cancelación de lecturas tardías y regreso inmediato al login. Auditoría: consultas de solo lectura y recuperación tras fallo.

Estas regresiones detectaron y corrigieron tres defectos: borrar una consulta de autenticación observada podía dejar la vista anterior y recrear caché privada; el frontend ignoraba `ready_to_commit: false`; el botón de alta no aplicaba el máximo de 1000 piezas por pack (el campo HTML y el servidor ya lo limitaban).

`npm run test:coverage` mide V8 sobre el código de aplicación, excluyendo tests, helpers, declaraciones y el punto de montaje `main.tsx`. Resultado local: **74,83 % líneas, 74,76 % sentencias, 76,93 % ramas y 62,45 % funciones**. Consumo, compras, configuración de compra y previsualización de fotos: 100 % de líneas; tickets: 96,72 %. Es cobertura de componentes/API: no incorpora los escenarios Chromium ni demuestra exhaustividad o accesibilidad completa. El informe HTML/LCOV/JSON se genera en `frontend/coverage/` y CI lo publica como artefacto `frontend-coverage`; no se incluye en Git ni en el paquete del complemento.

La ejecución local de navegador sin PHP/Grocy pasó los 9 escenarios disponibles y omitió explícitamente los 4 de Grocy real. CI tiene configurado `GROCY_TEST_DIST` para ejecutar los 13; observar su resultado para el commit de este refuerzo antes de darlo por validado en integración.

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

Sin `GROCY_TEST_DIST`, los cuatro escenarios de Grocy real se marcan omitidos de forma explícita; CI lo configura y exige que corran. El comando `--check` requiere el release. Los servidores deben arrancarse desde el mismo entorno de red que el navegador.

## CI y límites

`.github/workflows/python-ci.yml` verifica frontend, contratos reales, navegador y contenedores AMD64/ARM64, arranque HTTP y espejos Python. Consultar el resultado del SHA final en la PR; esta documentación no sustituye esa observación.

Las lecturas de la instalación propia ya responden **HTTP 200**, usando la clave y el puerto interno existentes: Grocy 4.7.1, PHP 8.5.12, SQLite 3.53.4 y esquema DB 257. Se comprobaron unidades Piece/Pack/Kilogram y endpoints de conversiones, productos, compra y referencias de recetas/plan. La entidad HA/Alexa configurada devuelve pendientes con `summary`, `uid` y `status`. No se registran sus nombres ni contenidos en el repositorio.

El primer intento por el proxy ingress devolvía 403; no era una incompatibilidad de Grocy. Se resolvió usando el servicio ya configurado, sin cambiar credenciales, puertos, opciones ni protecciones. No hubo escrituras sobre Grocy o Alexa, actualización del complemento ni activación del sync. Cámara Android física, escrituras Alexa reales y actualización Supervisor con copia de seguridad son aceptación pendiente de un despliegue futuro. Reiniciar el servicio aislado demuestra persistencia de archivos/estado del flujo, no una actualización real del add-on.

CI de la implementación y correcciones de infraestructura (`92034c8`): [ejecución push correcta](https://github.com/molinero95/HA-Grocy-Ticket-Importer/actions/runs/41256121395), incluidos frontend, 5 contratos, 7 navegadores y construcción/arranque AMD64/ARM64. Los cambios posteriores de documentación se vuelven a verificar en la PR.
