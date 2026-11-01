# Despensa 1.0 — cierre de migración

Estado de código: candidata implementada en PR #10, rama `feature/despensa-v1-react`. Sin versión nueva, fusión ni despliegue. `main` sigue en 0.16.4.

## Implementado y validado automáticamente

- [x] React 19, TypeScript 7, Vite 7 y Vitest 4 con lockfile y compilación dentro del contenedor.
- [x] Paridad de compra, despensa, producto, consumo, tickets, variantes, fotos, revisión Alexa y auditoría.
- [x] Sesión/CSRF, ingress con prefijo, errores, CSP, cámara con entrada manual y UX móvil.
- [x] Pack/Piece contra Grocy 4.7.1 real, sin convertir existencias existentes; edición de compra y cantidades personalizadas.
- [x] Operaciones de compra por fila: preservar otras listas, notas y completados.
- [x] Tickets importados una vez, comandos persistentes y verificación de estado esperado.
- [x] Variantes, fotos y listas conservadas tras reiniciar Grocy aislado.
- [x] Alexa: cola persistente, mantener original y asociación explícita sin duplicados, checkpoint tras verificación.
- [x] Archivado/restauración conservando historial, con stock y referencias protegidos.
- [x] React como entrada de la candidata; retirar PAGE, scripts y formularios obsoletos; alternativa básica sin JavaScript.
- [x] Fuentes Python duplicadas sincronizadas y manifiesto Docker completo.
- [x] CI configurado para frontend, integración real aislada y contenedores AMD64/ARM64 con arranque.

La evidencia y comandos reproducibles están en [VALIDATION_V1.md](docs/VALIDATION_V1.md); el resultado CI debe observarse para el SHA final, nunca inferirse de esta lista.

## Aceptación de un despliegue futuro

- [x] Lecturas de Grocy instalado 4.7.1 y esquema de unidades/conversiones/lista/referencias, usando su acceso interno y clave existentes. Entidad HA/Alexa: pendientes con uid/summary/status válidos; sin escrituras ni cambios de seguridad.
- [ ] Copia HA y actualización de prueba conservando ledger, fotos, variantes, comandos, colas y checkpoints de esa instalación. Reiniciar Grocy aislado ya está probado; no equivale a actualizar Supervisor.
- [ ] Cámara física y permisos de Android/HA; escrituras Alexa reales de la entidad elegida. El navegador automatizado simula el dispositivo de cámara y la respuesta HA.
- [ ] Solo tras esas comprobaciones: decisión separada sobre fusión, versión y publicación. No autorizadas durante esta ejecución.

## Fuera del alcance de la migración

Consolidación/eliminación permanente de productos, migración automática de stock Pack antiguo y sincronización de cantidades o estados de compra con Alexa. Se mantienen auditoría y protecciones; no son funciones destructivas pendientes de activar.
