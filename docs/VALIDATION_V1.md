# Despensa 1.0 — validación reproducible

Fecha: 2026-11-01. Candidata en PR #10; estable 0.16.4 sin publicación ni despliegue.

## Evidencia local

- Python: 200 regresiones de dominio/API, permisos, CSRF, concurrencia, idempotencia y empaquetado.
- Vitest 4: 14 pruebas de interacciones React y cliente API.
- TypeScript 7: aplicación y e2e; Vite 7: compilación de producción.
- Grocy real: 5 contratos (Pack/consumo repetido, ticket/importador, foto/variante tras reinicio, otras listas/notas/completados, compra y archivado conservando historial).
- Chromium: 7 escenarios móviles, ingress, fallback sin JavaScript y flujos completos con Grocy real: alta/stock/foto/variante/escáner, tickets repetidos, worker Alexa/elección/descartar/reinicio, Pack y archivar/restaurar.

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
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Sin `GROCY_TEST_DIST`, los cuatro escenarios de Grocy real se marcan omitidos de forma explícita; CI lo configura y exige que corran. El comando `--check` requiere el release. Los servidores deben arrancarse desde el mismo entorno de red que el navegador.

## CI y límites

`.github/workflows/python-ci.yml` verifica frontend, contratos reales, navegador y contenedores AMD64/ARM64, arranque HTTP y espejos Python. Consultar el resultado del SHA final en la PR; esta documentación no sustituye esa observación.

La consulta de solo lectura a la instalación Grocy del usuario devolvió **HTTP 403**. No se han cambiado sus credenciales, puertos ni protecciones. No se ha actualizado el complemento ni habilitado sync en producción. Cámara Android física, servicio Alexa real y actualización Supervisor con copia de seguridad son aceptación pendiente de un despliegue futuro. Reiniciar el servicio aislado demuestra persistencia de archivos/estado del flujo, no una actualización real del add-on.
