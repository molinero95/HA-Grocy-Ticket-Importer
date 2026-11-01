# Despensa — decisiones vigentes

Última revisión: 2026-11-01. Consolida las decisiones del producto y sustituye los estados históricos de implementación de PR #2/#5. La migración se desarrolla en PR #10; no autoriza fusionar, publicar ni cambiar `main`.

## Navegación y compras

- Inicio: **Lista de la compra**; otras pestañas: **Mi despensa** y **Acciones**.
- La lista predeterminada de Grocy es la única lista de compra del producto. Marcar comprado o retirar no altera existencias.
- Carrito «Añadir» para productos ausentes, después «− cantidad +», y carrito otra vez al llegar a cero. Actualización sin recarga ni salto de scroll; errores visibles, columnas estables en móvil y alternativa HTML sin JavaScript.
- Máximo dos decimales. Pasos de 0,10 kg y 1 pieza. La cantidad almacenada por Grocy está en unidades de stock; una compra de packs se convierte exactamente una vez.
- Operaciones por ID de fila, solo lista 1; preservar notas, completados y listas independientes.

## Catálogo y existencias

- Añadir producto crea solo productos nuevos: comprobar nombre/código, enlazar la ficha existente ante duplicado, nunca incrementar su stock. Alta con código opcional y cero existencias permitido.
- Ficha con edición de nombre, unidad, configuración de compra, cantidades, foto, códigos y variantes. No existe una acción independiente «Asociar código».
- **Pack compra / Piece stock y consumo**. Un pack de 5 añade 5 piezas. Las conversiones se verifican en Grocy antes de escribir stock; se descubren los IDs reales de unidades. Mostrar piezas por pack solo para Pack.
- Cambiar compras afecta únicamente a compras futuras. Nunca reinterpretar automáticamente stock existente ni una fila de compra. Renombrar conserva descripción, fotos y configuración. Cambiar unidad de stock exige cero conocido y configuración compatible.
- Ajustar stock requiere cantidad esperada y guarda directamente, sin pantalla de confirmación adicional.
- Consumir cantidad precisa, opcionalmente reponerla en compra. Registro persistente de comandos, sin repetición automática ante resultado incierto. Un fallo de reposición se comunica como éxito parcial del consumo.
- **Ciclo seguro: archivar/restaurar**, conservando ID, historial y metadatos. Archivar exige cero stock conocido y ausencia de referencias activas; restaurar cambia únicamente `active`. La eliminación permanente con cascadas y la consolidación de productos no forman parte de esta migración.
- Auditoría y vista de duplicados son de solo lectura. Consolidar productos reales requiere un plan y autorización explícita distintos; no se inventa una migración automática para cerrar el desarrollo.

## Fotos, variantes y tickets

- Buscar foto por código exacto al escanear/escribir; guardar solo URL validada por servidor y host HTTPS permitido. No consultar por producto en cada carga. Foto inexistente/servicio caído no bloquea el alta o asociación; conservar foto personalizada existente.
- Subida local saneada y sin metadatos privados; URL versionada compartida por compra, despensa y ficha. Persistir fotos en el almacenamiento existente.
- Un genérico es un ID canónico de Grocy y posee todo su stock. Variantes añaden nombre, supermercado, marca, EAN y factor descriptivo. Comprobar propiedad del código en ambos registros; editar variante no cambia su EAN ni crea otro producto inadvertidamente. El factor canónico de compra controla las conversiones; el factor de variante no migra stock.
- Tickets PDF/JPG/PNG: extraer, revisar nombres/piezas por pack, simular, confirmar bytes exactos y persistir historial contra duplicados. La simulación no escribe en Grocy. Conservar marcadores pendientes ante cortes.

## Alexa

- Solo entidad `todo.*` configurada y lista predeterminada de Grocy; pendientes de Alexa, sin históricos/completados. Desactivado por defecto.
- Entidad configurada con sync desactivado permite actualizar la cola local en modo lectura. Una elección no modifica remotamente hasta un ciclo explícitamente habilitado.
- Primer ciclo v2 une sin borrar; siguientes propagan altas/bajas por ID canónico y checkpoint confirmado. No sincronizar cantidades, unidades, completados ni renombrar Alexa.
- Nombres ambiguos/desconocidos conservan nota. **Mantener original** descarta la sugerencia de forma persistente sin convertirla.
- **Selección explícita validada** puede asociar su nota existente al producto elegido en el siguiente ciclo habilitado: misma fila, cantidad, nota y lista; sin duplicar ni fusionar filas. Revalidar identidad y campos antes de escribir; colisión con otra fila canónica o edición concurrente detiene el ciclo.
- Releer ambas listas tras cambios y guardar checkpoint solo tras convergencia. Elección obsoleta bloquea; colas y checkpoints separados por entidad. Conservar archivos v1 sin reinterpretación automática.

## Seguridad y entrega

React 19, TypeScript 7, Vite 7 y Vitest 4 en el mismo origen que Flask. Credenciales solo en servidor, ingress HA o sesión standalone, CSRF en todas las mutaciones, CSP y errores en español. No exponer puertos ni relajar autenticación para probar.

La candidata de la rama sirve React en `/` y conserva `/react/` como alias; `/basic` mantiene compras sin JavaScript. Se ha eliminado el frontend completo duplicado después de comprobar paridad contra Grocy 4.7.1 aislado. Esto NO despliega nada en Home Assistant.

Conservar todos los datos persistentes y módulos Python espejo. Validación automatizada y límites constan en `docs/VALIDATION_V1.md`. La prueba de la instalación HA real devuelve 403; aceptación de despliegue, cámara física y servicio Alexa real siguen siendo comprobaciones externas. No afirmar que se han realizado ni publicar antes de completarlas.
