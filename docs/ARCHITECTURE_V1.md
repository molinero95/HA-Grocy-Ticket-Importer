# Despensa 1.0 — arquitectura

## Límites

- `ha_grocy_ticket_importer/frontend/`: React/TypeScript, TanStack Query, cámara, formularios y vistas. `frontend` es un enlace. Sin claves Grocy/OpenAI.
- `web.py`: un solo origen, ingress, sesión/CSRF, estáticos compilados, API y fallback HTML mínimo. React en `/`, alias `/react/`, fallback `/basic`.
- `api_*.py`: validación de entrada y respuestas JSON; lock de mutaciones y errores.
- Dominio Python: catálogo/compra/stock, conversión de unidades, importación y ledger, fotos, variantes, identidad Alexa y checkpoints.
- Docker: Node 22 + npm 11 compila frontend; runtime Python/Gunicorn detrás de nginx de ingress. CI construye y arranca ambas arquitecturas soportadas.

Grocy controla el catálogo, stock y lista. Las SQLite locales contienen metadatos, registros de importación/comandos y revisión, nunca un inventario alternativo. Se conservan las rutas de almacenamiento HA.

## Escrituras y recuperación

Stock y unidades se validan contra estado fresco. Compra por ID de fila verificado mantiene notas y no afecta otras listas/completados. Pack se convierte a stock una sola vez con `quantity_unit_conversions`; no se escriben campos de factor calculados de Grocy. Cambiar compra solo afecta al futuro.

`stock_commands.py` reserva el UUID en SQLite antes de la llamada remota, guarda respuesta confirmada y rechaza repetición incierta. No promete transacción distribuida. Tickets combinan hash del archivo simulado, marcador de envío y ledger de líneas. Conservar todos los marcadores pendientes tras cortes.

`catalog_lifecycle.py` cambia `active` sin DELETE ni consumo: cero stock y ausencia de dependencias para archivar, restauración reversible. Consolidación es solo auditoría.

El worker Alexa valida identidades, proyecta elecciones explícitas, preflight, asocia notas por ID conservando cantidad/texto, relee ambos sistemas y confirma checkpoint solo tras converger. No toca stock ni activa sincronización por defecto.

## Persistencia y pruebas

No borrar ledger, fotos, catálogo de variantes, colas por entidad, checkpoints v1/v2 ni comandos al actualizar. Espejos raíz/add-on continúan sincronizados; eliminarlos exigiría cambiar el empaquetado de forma independiente.

`tests/grocy_instance.py` arranca release oficial verificado en directorio temporal; `real_stack_server.py` conecta los módulos de producción y el importador subprocess, sustituyendo únicamente OpenAI, proveedor de fotos y HA. Sus rutas auxiliares no se incluyen en Docker. Contratos y Playwright ejecutan flujos y reinicio con Grocy real. Véase `VALIDATION_V1.md`.
