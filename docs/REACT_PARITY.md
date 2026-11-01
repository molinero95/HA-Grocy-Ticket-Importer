# Despensa 1.0 — matriz de paridad

La versión 1.0.0 sirve React en `/`, alias `/react/`, con compras sin JavaScript en `/basic`. Migración integrada en `main` y publicación autorizada para habilitar la actualización desde 0.16.4. Esta matriz describe código probado, no un despliegue.

| Flujo anterior | React y API | Evidencia |
| --- | --- | --- |
| Compra inicial, comprado, retirar, limpiar completados | Lista de Grocy, filas por ID, errores y recarga de consultas | Python; navegador móvil/ingress; contrato real de otras listas/notas/completados |
| Despensa y carrito/cantidad | Búsqueda nombre/EAN, pasos kg/pieza, sin recarga ni salto | Vitest; Chromium móvil; Grocy real |
| Crear producto / duplicados | Alta con stock cero, enlace al existente, conversión Pack verificada | Python; navegador real con alta y Pack |
| Editar nombre / stock / unidades | Conserva descripción/foto/compra; estado esperado; compra futura independiente | Python; contratos reales; compra de 2 packs = 8 piezas |
| Existencias / consumo | Ficha 1.3.0: sin formulario de añadir a la compra y con un único ajuste de cantidad total restante; formulario separado retirado. API de consumo conservada | Vitest de ajuste descendente; Grocy real, Python de consumo/repetición |
| Códigos y variantes | Propiedad auditada; ficha y escáner; edición de variante conserva EAN | Python; navegador y persistencia real |
| Fotos | Búsqueda universal v3 exacta con respaldo Food/Products/Beauty y redirecciones confiables y subida saneada, URL compartida/versionada; nombre propuesto explícitamente en alta | Python; navegador; archivo servido tras reinicio real |
| Tickets | Subir/revisar/simular/confirmar; ledger y marcadores contra duplicados | Python; importador real en subprocess; segundo ticket no duplica stock |
| Alias y salud Alexa | Candidatos recalculados con el catálogo activo, aviso local al worker; gestión por producto, varios alias, borrado por estado esperado, notas exactas revisables y estado sanitizado | Python, API, Vitest, Chromium y conservación de fila/cantidad/stock en Grocy real |
| Alexa | Elección/mantener original materializan fila inmediata; Quitar siempre visible, incluso en sugerencias; retirada persistente y checkpoint verificado | Python de duplicados/conflictos/fallos, contrato Grocy real y navegador con worker/HA desechable |
| Auditoría / duplicados | Exportación y vista de solo lectura | Python; conserva protección de consolidación |
| Ciclo de producto | Archivado/restauración reversibles; borrado 1.8.0 solo de archivados sin stock, historial ni dependencias, con revisión y nombre exacto | Python y Grocy real: historial idéntico antes/después |
| Autenticación standalone / ingress | Login/logout, CSRF, caducidad y caché limpia; prefijos de assets/API | Python, Vitest y Chromium ingress |
| Acceso sin JavaScript | Página básica autenticada con controles de compra y CSRF | Python y Chromium con JavaScript desactivado |
| Empaquetado | React compilado, runtime completo, espejos Python | CI AMD64/ARM64: build y arranque de contenedor |

Frontend 1.8.0: 79 pruebas Vitest y 23 escenarios Chromium configurados. Alta solo en Mi despensa; archivados en Acciones, sin acceso de alta duplicado. Incluye regresiones de sesión/caché tardía, tickets no listos para importar, escrituras únicas ante doble pulsación/respuesta perdida, factores Pack, conflictos de variantes y navegación por teclado. Cobertura y alcance exacto en [VALIDATION_V1.md](VALIDATION_V1.md).

La antigua eliminación permanente podía borrar historia mediante cascadas de Grocy. El archivado reversible sigue siendo la opción para productos con historial; desde 1.8.0 solo se permite eliminar una ficha archivada sin stock, historia ni dependencias tras auditar las cascadas. La consolidación sigue en auditoría, igual que la función estable protegida; no existe autorización para fusionar productos de usuario.

## Retirada del código anterior

Retirados `PAGE`, scripts incrustados y rutas antiguas de formularios de aplicación completa. `web.py` solo compone auth, ingress, estáticos, API y alternativa básica. No se retiran bases de datos, fotos, opciones, registros de comandos, historiales ni checkpoints. Los espejos Python se conservan por compatibilidad del empaquetado y se verifican byte a byte.

## Límites de la evidencia

Véase [VALIDATION_V1.md](VALIDATION_V1.md). Grocy es el release oficial 4.7.1 sin modificar, con datos temporales. Solo OpenAI, búsqueda pública de fotos y HA todo se sustituyen en esas pruebas. Las lecturas adicionales del Grocy instalado confirman 4.7.1 y el esquema utilizado, y la entidad HA/Alexa devuelve pendientes válidos. No se prueba cámara física, actualización Supervisor ni escrituras sobre la cuenta Alexa real. La publicación 1.0.0 autorizada no acredita esas comprobaciones externas.
