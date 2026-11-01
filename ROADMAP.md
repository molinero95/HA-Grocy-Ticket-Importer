# Despensa 1.0 — cierre de migración

Estado de código: migración de PR #10 integrada en `main` (`a6cc354`). Publicación de versión 1.0.0 autorizada por el usuario, con manifiesto, frontend y notas alineados en la PR de release. La actualización de la instalación real se realiza por separado.

## Implementado y validado automáticamente

- [x] React 19, TypeScript 7, Vite 7 y Vitest 4 con lockfile y compilación dentro del contenedor.
- [x] Compra, despensa, ficha con ajuste total de existencias, tickets, variantes, fotos, revisión Alexa y auditoría. En 1.1.0 se retira el formulario separado de consumo por petición del usuario; su API protegida se conserva.
- [x] Sesión/CSRF, ingress con prefijo, errores, CSP, cámara con entrada manual y UX móvil.
- [x] Pack/Piece contra Grocy 4.7.1 real, sin convertir existencias existentes; edición de compra y cantidades personalizadas.
- [x] Operaciones de compra por fila: preservar otras listas, notas y completados.
- [x] Tickets importados una vez, comandos persistentes y verificación de estado esperado.
- [x] Variantes, fotos y listas conservadas tras reiniciar Grocy aislado.
- [x] Alexa 1.1.0: guardar elección o mantener original crea/asocia de inmediato una fila gestionable en Grocy; Quitar también funciona en sugerencias. Retiradas persistentes, bloqueo entre procesos, sin reintroducción en la primera unión y sin escrituras Alexa con sync desactivado. Checkpoint tras verificación.
- [x] Archivado/restauración conservando historial, con stock y referencias protegidos.
- [x] React como entrada de la candidata; retirar PAGE, scripts y formularios obsoletos; alternativa básica sin JavaScript.
- [x] Fuentes Python duplicadas sincronizadas y manifiesto Docker completo.
- [x] CI configurado para frontend, integración real aislada y contenedores AMD64/ARM64 con arranque.
- [x] Frontend 1.11.0: 91 tests Vitest y 27 escenarios de navegador, con cobertura V8 en CI. Incluye ajuste de existencias sin formulario de consumo, alta solo en Mi despensa y archivados desde Acciones, además de sesión/caché, tickets, validaciones y foco móvil.

La evidencia y comandos reproducibles están en [VALIDATION_V1.md](docs/VALIDATION_V1.md); el resultado CI debe observarse para el SHA final, nunca inferirse de esta lista.

## Mejoras 1.2.0

- [x] Estilos comunes de alta, cámara, duplicados y archivos; revisar disposición móvil.
- [x] Open Beauty Facts adicional, manteniendo Food/Products; nombres propuestos sin autoescritura y ausencia de producto separada de caída de servicio.

## Mejoras 1.3.0

- [x] Ficha sin formulario de añadir a la compra; conservar información y stock, con compras desde las listas.
- [x] Consulta universal v3 con redirecciones confiables, atribución correcta y respaldo directo Food/Products/Beauty.

## Revisión Día 6 y recuperación 1.6.0

- [x] Alias por producto con varios nombres, protección de borrado obsoleto y gestión de productos ausentes.
- [x] Estado del worker visible y notas exactas revisables sin cambiar existencias ni fusionar filas.
- [x] Descubrimiento CI de pruebas anidadas, espejos y versiones alineados.
- [ ] Usuario actualiza la instalación y resuelve la nota conflictiva; no se da por comprobada la sincronización real tras publicar.

## Mejoras 1.7.0

- [x] Sugerencias actualizadas con altas, cambios de nombre y archivados, sin reasignar decisiones guardadas.
- [x] Aviso inmediato tras cambios locales, eventos HA y polling de respaldo; vista cada cinco segundos.
- [x] Contrato y navegador Grocy para un producto nuevo sugerido sin nuevo ciclo del worker.

## Aceptación de un despliegue futuro

- [x] Lecturas de Grocy instalado 4.7.1 y esquema de unidades/conversiones/lista/referencias, usando su acceso interno y clave existentes. Entidad HA/Alexa: pendientes con uid/summary/status válidos; sin escrituras ni cambios de seguridad.
- [ ] Copia HA y actualización de prueba conservando ledger, fotos, variantes, comandos, colas y checkpoints de esa instalación. Reiniciar Grocy aislado ya está probado; no equivale a actualizar Supervisor.
- [ ] Cámara física y permisos de Android/HA; escrituras Alexa reales de la entidad elegida. El navegador automatizado simula el dispositivo de cámara y la respuesta HA.
- [x] Usuario autoriza fusionar la migración y publicar 1.0.0 para habilitar la actualización en Home Assistant. Esta autorización no acredita la aceptación física ni instala automáticamente el complemento.

## Fuera del alcance de la migración

Combinación automática o con dependencias no migrables, eliminación de historial sin confirmación explícita, migración automática de stock Pack antiguo y sincronización de cantidades o estados de compra con Alexa. Se mantienen auditoría y protecciones; no son funciones destructivas pendientes de activar.


## Mejoras 1.8.0

- [x] Productos sin stock en ámbar con etiqueta visible; no depende de cantidad en compra.
- [x] Eliminación irreversible solo para archivados sin historial ni dependencias; revisar, escribir nombre y revalidar, con journal contra repetición.
- [x] Historial interno para Atrás en secciones/diálogos anidados y solicitud explícita de pantalla completa cuando el host lo permite.
- [ ] Aceptación física Android/HA tras la actualización del usuario.


## Mejoras 1.9.0

- [x] Diferencias persistentes por pareja de productos, con deshacer y sin ocultar otras parejas de un grupo.
- [x] Combinación nativa de Grocy bajo revisión, destino elegido, stock/historia/referencias verificadas y comandos sin repetición.
- [x] Alta de producto desde compra/Alexa publicada en 1.11.0 (PR #24).


## Mejoras 1.10.0

- [x] Confirmaciones correctas en verde y retirada del botón pantalla completa.
- [x] Borrado de movimientos de archivados autorizado expresamente; aviso y confirmación, con stock/dependencias/importaciones pendientes protegidas.
- [x] Alta desde compras/Alexa en 1.11.0; revisión de tickets preparada en 1.12.0.

- [x] Umbral de aviso visual por producto (0 por defecto), comparación inclusiva y desactivación individual, sin cambios de compra/stock.


## Mejoras 1.11.0

- [x] Alta contextual desde compra/Alexa sin candidatos, nombre editable, cero stock y asociación automática con cantidad/nota conservadas.
- [x] Vínculo por ID limitado a episodio, confirmación de producto existente y recuperación de asociación sin duplicar alta ni fila.
- [x] 1.12.0: selección/alta/unidades de cada línea de ticket, asociaciones por supermercado y cantidad final calculada de solo lectura.


## Mejoras 1.13.0

- [x] Endpoint de consultas Alexa separado, verificado y desactivado por defecto; modelo es-ES preparado.
- [x] Reconocimiento de foto completa tras código sin resultados, acción explícita y sugerencia editable; conservar alta manual.
- [ ] Configurar con el usuario Amazon Developer, skill/usuario autorizados y ruta Cloudflare del listener 8100; validar voz en Echo físico.
- [ ] Validar una fotografía real del usuario contra su cuenta OpenAI tras la actualización. Las pruebas sustituyen el proveedor y no consumen su API.
