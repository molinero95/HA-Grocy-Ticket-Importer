# Despensa 1.0 — matriz de paridad

La candidata sirve React en `/`, alias `/react/`, con compras sin JavaScript en `/basic`. La versión instalada y `main` no se modifican. Esta matriz describe código probado, no un despliegue.

| Flujo anterior | React y API | Evidencia |
| --- | --- | --- |
| Compra inicial, comprado, retirar, limpiar completados | Lista de Grocy, filas por ID, errores y recarga de consultas | Python; navegador móvil/ingress; contrato real de otras listas/notas/completados |
| Despensa y carrito/cantidad | Búsqueda nombre/EAN, pasos kg/pieza, sin recarga ni salto | Vitest; Chromium móvil; Grocy real |
| Crear producto / duplicados | Alta con stock cero, enlace al existente, conversión Pack verificada | Python; navegador real con alta y Pack |
| Editar nombre / stock / unidades | Conserva descripción/foto/compra; estado esperado; compra futura independiente | Python; contratos reales; compra de 2 packs = 8 piezas |
| Consumir y reponer | ID canónico, precisión, operación persistente, resultado parcial seguro | Python de fallos/repetición; consumo real e idempotencia |
| Códigos y variantes | Propiedad auditada; ficha y escáner; edición de variante conserva EAN | Python; navegador y persistencia real |
| Fotos | Búsqueda exacta validada y subida saneada, URL compartida/versionada | Python; navegador; archivo servido tras reinicio real |
| Tickets | Subir/revisar/simular/confirmar; ledger y marcadores contra duplicados | Python; importador real en subprocess; segundo ticket no duplica stock |
| Alexa | Sugerencias, elección y mantener original; asociación explícita de nota y checkpoint | Python de conflictos/fallos; navegador con worker real y HA desechable |
| Auditoría / duplicados | Exportación y vista de solo lectura | Python; conserva protección de consolidación |
| Ciclo de producto | Archivado y restauración reversibles, cero stock y referencias verificadas | Python y Grocy real: historial idéntico antes/después |
| Autenticación standalone / ingress | Login/logout, CSRF, caducidad y caché limpia; prefijos de assets/API | Python, Vitest y Chromium ingress |
| Acceso sin JavaScript | Página básica autenticada con controles de compra y CSRF | Python y Chromium con JavaScript desactivado |
| Empaquetado | React compilado, runtime completo, espejos Python | CI AMD64/ARM64: build y arranque de contenedor |

Refuerzo del frontend: 67 pruebas Vitest y 13 escenarios Chromium configurados. Incluye regresiones de sesión/caché tardía, tickets no listos para importar, escrituras únicas ante doble pulsación/respuesta perdida, factores Pack, conflictos de variantes y navegación por teclado. Cobertura y alcance exacto en [VALIDATION_V1.md](VALIDATION_V1.md).

La antigua eliminación permanente podía borrar historia mediante cascadas de Grocy: se sustituye por archivado reversible. La consolidación sigue en auditoría, igual que la función estable protegida; no existe autorización para fusionar productos de usuario.

## Retirada del código anterior

Retirados `PAGE`, scripts incrustados y rutas antiguas de formularios de aplicación completa. `web.py` solo compone auth, ingress, estáticos, API y alternativa básica. No se retiran bases de datos, fotos, opciones, registros de comandos, historiales ni checkpoints. Los espejos Python se conservan por compatibilidad del empaquetado y se verifican byte a byte.

## Límites de la evidencia

Véase [VALIDATION_V1.md](VALIDATION_V1.md). Grocy es el release oficial 4.7.1 sin modificar, con datos temporales. Solo OpenAI, búsqueda pública de fotos y HA todo se sustituyen en esas pruebas. Las lecturas adicionales del Grocy instalado confirman 4.7.1 y el esquema utilizado, y la entidad HA/Alexa devuelve pendientes válidos. No se prueba cámara física, actualización Supervisor ni escrituras sobre la cuenta Alexa real. No publicar ni afirmar aceptación de despliegue hasta resolver esas comprobaciones externas.
