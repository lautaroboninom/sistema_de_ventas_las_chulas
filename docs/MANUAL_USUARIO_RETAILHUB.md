# Manual de Usuario RetailHub

Version: 1.0
Fecha de actualizacion: 2026-04-09
Alcance: operacion funcional actual (sin asumir funcionalidades pendientes)

## 1) Introduccion
Este manual describe como operar RetailHub en su estado actual, enfocando en tareas diarias de tienda y administracion basica.

Objetivos del manual:
- Guiar operacion diaria de mostrador y backoffice.
- Estandarizar flujos y criterios de validacion.
- Reducir errores operativos recurrentes.
- Explicar que partes dependen de configuracion externa.

## 2) Alcance y reglas de uso

### 2.1 Alcance funcional cubierto
Este documento cubre las rutas activas de frontend:
- `/login`
- `/pos`
- `/productos`
- `/compras`
- `/ventas`
- `/promociones`
- `/garantias`
- `/inventario`
- `/reportes`
- `/online`
- `/config`
- `/config/paginas`

Tambien cubre:
- Recuperacion de acceso (`/recuperar`, `/restablecer`).
- Restricciones por rol/permisos.
- Checklist de apertura y cierre.
- Incidencias comunes.

### 2.2 Regla de alcance
Si una funcion depende de credenciales externas, certificados o alta de terceros, se marca explicitamente como:
- `No disponible / depende de configuracion externa`

Este criterio aplica principalmente a:
- Facturacion ARCA en modo productivo real.
- Integracion Tienda Nube (credenciales, OAuth, webhooks).

## 3) Perfiles de uso y permisos

### 3.1 Perfiles base
- `admin`: acceso amplio a operacion y configuracion, con restricciones puntuales segun permisos tecnicos.
- `empleado`: acceso operativo base (POS, productos, ventas) y acciones limitadas.

### 3.2 Permisos relevantes por modulo
- `page.pos`: acceso a POS.
- `page.productos`: acceso a productos.
- `page.compras`: acceso a compras.
- `page.ventas`: acceso a ventas.
- `page.promociones`: acceso a promociones.
- `page.online`: acceso a online.
- `page.config`: acceso a configuracion.
- `action.inventario.conteo`: habilita conteos ciclicos.
- `action.promociones.editar`: habilita crear/editar promociones.
- `action.ventas.override_precio`: habilita override de precio en POS.
- `action.ventas.anular`: habilita anulacion directa.
- `action.ventas.devolver`: habilita devoluciones.
- `action.ventas.cambiar`: habilita cambios.
- `action.ventas.devolver.override_garantia`: habilita override fuera de garantia.
- `action.postventa.credito_tienda`: habilita credito tienda.
- `action.facturacion.emitir`: habilita emision/reintento de factura.
- `action.facturacion.nota_credito`: habilita nota de credito.
- `action.caja.cierre_asistido`: habilita cierre asistido con control de diferencias.
- `action.config.editar`: habilita editar parametros de negocio.
- `action.config.online_credentials`: habilita editar credenciales sensibles ARCA/Tienda Nube.

### 3.3 Comportamientos esperados ante falta de permisos
- Pantalla no autorizada: redireccion a `/403`.
- Accion no permitida: boton oculto, bloqueado o reemplazado por solicitud de aprobacion.

## 4) Acceso y navegacion

## 4.1 Ingreso al sistema (`/login`)
Objetivo:
- Iniciar sesion y entrar a la ruta inicial configurada.

Prerrequisitos:
- Usuario activo con email y contraseña vigentes.
- Backend accesible desde la URL donde corre el frontend.

Pasos:
1. Abrir pantalla de login.
2. Ingresar usuario (email) y contraseña.
3. Presionar `Ingresar`.

Resultado esperado:
- Redireccion a inicio operativo (normalmente `/pos` o ruta inicial configurada).

Errores frecuentes y resolucion:
- `Backend no disponible en /api`: verificar servicios backend y red local.
- `Credenciales invalidas`: reintentar; si persiste, solicitar reset de contraseña.

## 4.2 Recuperar contraseña (`/recuperar`)
Objetivo:
- Solicitar enlace de restablecimiento.

Prerrequisitos:
- Cuenta de email existente en el sistema.

Pasos:
1. Entrar a `Recuperar contraseña`.
2. Ingresar email.
3. Enviar solicitud.

Resultado esperado:
- Mensaje de envio exitoso (sin exponer si el email existe).

Errores frecuentes y resolucion:
- Sin mail recibido: revisar spam, dominio, y pedir reenvio desde administracion.

## 4.3 Restablecer contraseña (`/restablecer`)
Objetivo:
- Definir nueva contraseña desde token.

Prerrequisitos:
- Link valido con token.
- Contraseña nueva de al menos 8 caracteres.

Pasos:
1. Abrir link de restablecimiento.
2. Ingresar nueva contraseña y confirmacion.
3. Guardar.

Resultado esperado:
- Confirmacion y redireccion a login.

Errores frecuentes y resolucion:
- `Link invalido`: solicitar nuevo enlace.
- `Contraseñas no coinciden`: corregir y reenviar.

## 4.4 Navegacion principal y menu lateral
Objetivo:
- Moverse entre modulos segun permisos.

Prerrequisitos:
- Sesion activa.

Pasos:
1. Usar menu lateral para abrir modulo.
2. En mobile, abrir/cerrar menu desde boton superior.

Resultado esperado:
- Solo se ven modulos habilitados para el usuario.

Errores frecuentes y resolucion:
- Faltan opciones de menu: validar rol/permisos del usuario.
- Acceso denegado en ruta directa: revisar permisos efectivos y politica de rol.

## 5) Operacion diaria

## 5.1 POS operativo (`/pos`)
Objetivo:
- Registrar ventas de mostrador con control de caja, promociones y medios de pago.

Prerrequisitos:
- Permiso `page.pos`.
- Caja abierta para confirmar venta.
- Catalogo con variantes activas.

Pasos principales:
1. Cargar items por scanner (`barcode` o `SKU`) o busqueda manual.
2. Ajustar cantidades, y si aplica, override de precio (requiere permiso).
3. Definir cobro:
   - medio base (`cash`, `debit`, `transfer`, `credit`, `store_credit`)
   - cuenta/caja asociada.
4. Si aplica, activar pago mixto (`split tender`) y completar tramos.
5. Completar datos opcionales de cliente, documento, cupones y notas.
6. Confirmar cotizacion y total.
7. Presionar `Confirmar venta`.

Resultado esperado:
- Venta confirmada con numero de ticket.
- Actualizacion de stock.
- Estado de factura visible en resumen de venta.

Atajos operativos:
- `F2`: foco scanner.
- `F8`: guardar draft rapido.
- `F9`: confirmar venta.
- `Ctrl+Backspace`: limpiar carrito.

Subflujo: borradores:
1. Cargar items.
2. Guardar nuevo borrador o actualizar el actual.
3. Recuperar borrador desde lista `Borradores en espera`.

Subflujo: caja:
1. Apertura: ingresar efectivo inicial y abrir caja.
2. Cierre: cargar conteo final y cerrar.
3. Si usuario tiene `action.caja.cierre_asistido`, puede registrar diferencia e incidencia.

Errores frecuentes y resolucion:
- `Sin apertura de caja`: abrir caja antes de confirmar venta.
- `La suma de pagos mixtos no coincide`: corregir montos de split.
- `Falta seleccionar credito tienda`: asignar credito en cada tramo `store_credit`.
- Scanner no agrega item: verificar SKU/barcode valido y existencia de variante activa.

## 5.2 Ventas, devoluciones y facturacion (`/ventas`)
Objetivo:
- Consultar ventas y ejecutar postventa: anulaciones, devoluciones, cambios y facturacion.

Prerrequisitos:
- Permiso `page.ventas`.
- Segun accion, permisos adicionales:
  - `action.ventas.anular`
  - `action.ventas.devolver`
  - `action.ventas.cambiar`
  - `action.ventas.devolver.override_garantia`
  - `action.postventa.credito_tienda`
  - `action.facturacion.emitir`
  - `action.facturacion.nota_credito`

Pasos:
1. Filtrar ventas por fecha, estado, canal, medio de pago o busqueda libre.
2. Seleccionar venta para abrir detalle.
3. Revisar:
   - estado de venta
   - estado fiscal (factura, CAE, numero comprobante)
   - ventanas de garantia y cantidades pendientes.
4. Ejecutar accion:
   - `Anular venta`
   - `Devolucion parcial` o `Devolucion total`
   - `Cambio 1:1`
   - `Emitir / reintentar factura`
   - `Emitir nota de credito`
5. Registrar motivo operativo en campo de razon.

Resultado esperado:
- La accion queda registrada y visible en detalle.
- En devoluciones/cambios se actualizan cantidades pendientes.
- En facturacion cambia estado fiscal de la venta.

Reglas operativas importantes:
- Lineas de promo tipo `X por Y` pueden bloquear devolucion monetaria y permitir solo cambio 1:1.
- Fuera de garantia requiere override explicito y motivo (si permiso lo habilita).
- Cuando no hay permiso de anulacion/devolucion monetaria, puede quedar habilitada la solicitud por mail.

Errores frecuentes y resolucion:
- `No tienes permiso`: gestionar permiso o solicitar accion por flujo de aprobacion.
- `Fuera de garantia`: usar override con motivo si esta permitido.
- Factura en `retry/manual_review`: corregir configuracion fiscal y reintentar.

Nota de disponibilidad externa:
- Facturacion ARCA real puede estar `No disponible / depende de configuracion externa` si faltan certificados, CUIT, puntos de venta o alta formal.

## 5.3 Cambios y devoluciones vigentes (`/garantias`)
Objetivo:
- Consultar rapidamente tickets con garantia vigente para cambio de talle o rotura.

Prerrequisitos:
- Ruta visible para usuarios con acceso a ventas.

Pasos:
1. Buscar por numero de venta, cliente o orden.
2. Filtrar por tipo de garantia (`size`, `breakage`, `all`).
3. Opcional: consultar ticket escaneando/ingresando codigo.
4. Seleccionar fila para ver detalle de lineas.

Resultado esperado:
- Visualizacion de vigencia, fecha de vencimiento y cantidad pendiente por ticket.

Errores frecuentes y resolucion:
- `No hay tickets con garantia activa`: validar rango y tipo de busqueda.
- Ticket no encontrado: validar formato de codigo de venta/orden.

## 6) Gestion comercial

## 6.1 Productos y variantes (`/productos`)
Objetivo:
- Administrar catalogo local (productos, atributos, variantes, barcodes y stock).

Prerrequisitos:
- Permiso `page.productos`.
- Para edicion: `action.config.editar`.

Pasos:
1. Crear producto (nombre, prefijo SKU, imagen opcional).
2. Crear atributo (ej: talle, color).
3. Crear variante individual:
   - producto base
   - SKU/barcode
   - proveedor opcional para EAN
   - precios local/online
   - costo, stock inicial, stock minimo
   - atributos de variante.
4. Crear variantes masivas por combinaciones:
   - seleccionar producto base
   - definir atributos multivalor (ej: color y talle)
   - generar combinaciones automaticas
   - completar grilla por variante (stock, barcode, precios, costo, stock minimo)
   - guardar lote (con resultado por fila: ok/error).
5. Gestionar barcodes:
   - generar
   - asociar
   - marcar principal
   - imprimir etiquetas (A4 o termica).
6. Editar y limpiar catalogo:
   - editar producto
   - editar variante (SKU, barcode, atributos, precios, activo)
   - editar atributo (nombre, code, orden, activo)
   - eliminar variante/atributo con politica hard/soft segun uso historico.
7. Ajustar stock por variante desde grilla.

Resultado esperado:
- Variante activa con identidad comercial (SKU/barcode), precios y stock consistente.

Errores frecuentes y resolucion:
- Atributo repetido en variante: corregir filas de atributos.
- Barcode invalido/no asociable: usar EAN-13 valido o generar automatico.
- Sin permiso de edicion: queda modo lectura.

Nota online:
- Estado de sync Tienda Nube en esta pantalla puede mostrar alertas.
- Si no hay credenciales integradas: `No disponible / depende de configuracion externa`.

## 6.2 Compras y proveedores (`/compras`)
Objetivo:
- Registrar ingresos de mercaderia con trazabilidad de costo y sugerencia de precio.

Prerrequisitos:
- Permiso `page.compras`.
- Variantes existentes (o usar alta rapida desde modal).

Pasos:
1. Completar datos de compra:
   - proveedor
   - fecha
   - moneda (`ARS` o `USD`)
   - tipo de cambio si moneda es USD
   - comprobante y notas.
2. Cargar items:
   - al enfocar el buscador, se muestran sugerencias iniciales
   - buscar por nombre/SKU/barcode con filtrado en tiempo real
   - sugerencias mixtas de variantes y productos
   - definir cantidad y costo unitario
   - revisar costo ARS y precio sugerido
   - definir precio final.
3. Si eliges producto (sin variante), abrir `Agregar producto y variante` para:
   - crear variante
   - seleccionar variante existente del producto
   - editar producto/variante sin salir de Compras
   - usar generador masivo por combinaciones.
4. Registrar compra.
5. Consultar lista de proveedores y autocompletar.

Resultado esperado:
- Compra registrada con numero.
- Actualizacion de stock y costo promedio por variante.

Errores frecuentes y resolucion:
- Variante no encontrada: crear variante desde modal rapido.
- Tipo de cambio faltante en USD: completar `fx` antes de registrar.
- Margen negativo no deseado: revisar costo y precio final.

## 6.3 Promociones (`/promociones`)
Objetivo:
- Configurar promociones por porcentaje o `X por Y`, con prioridad y reglas de combinacion.

Prerrequisitos:
- Permiso `page.promociones`.
- Para editar: `action.promociones.editar`.

Pasos:
1. Buscar y seleccionar promocion existente o crear nueva.
2. Definir datos base:
   - nombre
   - tipo (`percent_off` o `x_for_y`)
   - prioridad (menor aplica primero)
   - canal (`local`, `online`, `both`)
   - modo (`automatic`, `coupon`, `both`)
   - vigencia.
3. Configurar reglas por tipo:
   - `% descuento`: porcentaje y alcance por productos o todo catalogo.
   - `X por Y`: modo `sku` o `mix`, cantidades `buy_qty`/`pay_qty`, SKUs si corresponde.
4. Guardar.

Resultado esperado:
- Promocion disponible para cotizacion/venta segun reglas.

Errores frecuentes y resolucion:
- Cupon vacio con modo cupon: completar `coupon_code`.
- Reglas incoherentes en X por Y: validar `buy_qty` y `pay_qty`.
- Sin permiso de edicion: formulario no editable.

## 6.4 Inventario ciclico (`/inventario`)
Objetivo:
- Ejecutar conteos ciclicos, cerrar diferencias con motivo y registrar incidencias.

Prerrequisitos:
- Permisos: `page.productos` + `action.inventario.conteo`.

Pasos:
1. Crear conteo nuevo:
   - alcance (`low_stock`, `all`, `custom`)
   - motivo
   - incluir inactivas opcional.
2. Abrir conteo desde lista por estado.
3. Cargar cantidades contadas item por item.
4. Completar motivo de ajuste cuando hay diferencia.
5. Opcional:
   - aplicar ajustes de stock
   - generar incidencias por diferencias altas.
6. Cerrar conteo.
7. Revisar resumen de cierre y reposicion sugerida.

Resultado esperado:
- Conteo cerrado con trazabilidad completa de diferencias.
- Ajustes aplicados segun opciones seleccionadas.

Errores frecuentes y resolucion:
- No permite cerrar: revisar items pendientes o motivos faltantes.
- Diferencias sin razon: completar `motivo ajuste` por item.
- Conteo equivocado: filtrar por estado/codigo y abrir el correcto.

## 6.5 Reportes retail (`/reportes`)
Objetivo:
- Analizar operacion y rentabilidad para decisiones diarias.

Prerrequisitos:
- Acceso restringido a rol `admin`.

Pasos:
1. Definir rango `desde/hasta`.
2. Actualizar reportes.
3. Revisar bloques:
   - operacion diaria (KPIs del dia)
   - alertas accionables (con `Ack`)
   - reposicion sugerida
   - analisis principal por producto o proveedor
   - detalle secundario (bajo stock, devoluciones, cierres de caja).

Resultado esperado:
- Panel consolidado para accion comercial y operativa.

Errores frecuentes y resolucion:
- Sin datos en rango: ampliar ventana de fechas.
- Falta acceso: validar rol admin.
- Alertas repetidas: usar `Ack` y verificar causa raiz en modulo origen.

## 6.6 Online Tienda Nube (`/online`)
Objetivo:
- Operar tareas de importacion/sincronizacion con Tienda Nube y gestionar fallidos.
- Corregir productos que antes quedaron separados en Tienda Nube, dejando sus variantes dentro de un unico producto.

Prerrequisitos:
- Permiso `page.online`.
- Credenciales de tienda y webhooks correctamente configurados.

Pasos:
1. Definir limite de productos.
2. Ejecutar acciones segun necesidad:
   - `Importar desde Tienda Nube`: trae productos y variantes desde Tienda Nube hacia RetailHub.
   - `Corregir productos en Tienda Nube`: agrupa en Tienda Nube las variantes que pertenecen al mismo producto de RetailHub.
   - `Sincronizar stock`: envia a Tienda Nube el stock disponible de RetailHub.
   - `Reintentar fallidos`
   - `Procesar pendientes`.
3. Monitorear paneles de resultado y resumen de fallidos por tipo.

Correccion de productos separados:
1. Entrar a `Productos y variantes` (`/productos`) y revisar que cada variante tenga SKU.
2. Entrar a `Online (Tienda Nube)` (`/online`).
3. Tocar `Corregir productos en Tienda Nube`.
4. Esperar a que termine y revisar `Fallidos pendientes`.
5. Si quedan pendientes, tocar `Reintentar fallidos`.

Para productos nuevos o variantes nuevas:
- No hace falta un paso extra. RetailHub ya queda preparado para sincronizarlos como un producto unico con variantes adentro.

Importante:
- No borrar ni editar manualmente en Tienda Nube los productos duplicados mientras se ejecuta la correccion.
- RetailHub no elimina productos viejos de Tienda Nube. Los despublica solo cuando ya pudo vincular todas las variantes correctamente.
- Si alguna variante no se pudo vincular, el producto viejo queda publicado y se muestra el pendiente para revisar.

Resultado esperado:
- Jobs procesados y estado de sincronizacion actualizado.
- Cada producto de RetailHub queda como un producto en Tienda Nube, con sus variantes adentro.

Errores frecuentes y resolucion:
- Fallidos recurrentes: revisar que las variantes tengan SKU, que no haya SKU repetidos y que Tienda Nube este conectada.
- Reintentos no resuelven: ejecutar `Proceso programado jobs` y revisar detalle de errores.
- Sin datos de tienda: completar configuracion en `/config`.

Nota de disponibilidad externa:
- Modulo online puede quedar `No disponible / depende de configuracion externa` si no existen `store_id`, `access_token`, `client_id/client_secret`, webhook secret o URL publica HTTPS valida.

## 7) Configuracion

## 7.1 Configuracion general (`/config`)
Objetivo:
- Administrar parametros de negocio, facturacion, integraciones y cuentas de cobro.

Prerrequisitos:
- Permiso `page.config`.
- Para editar negocio: `action.config.editar`.
- Para credenciales sensibles: `action.config.online_credentials`.

Pasos:
1. Revisar y editar bloque `Negocio y operacion`:
   - nombre comercial
   - condicion IVA
   - impresoras
   - prefijos EAN
   - dias de garantia
   - margen compras por defecto.
2. Revisar bloque `Facturacion (ARCA)`:
   - entorno
   - CUIT
   - puntos de venta
   - tipo de comprobante
   - paths de certificado/clave
   - facturacion online automatica.
3. Revisar bloque `Integracion Tienda Nube`:
   - store_id, client_id, client_secret
   - access_token
   - webhook_secret
   - flujo tecnico OAuth (reautorizar y aplicar token).
4. Gestionar `Cuentas de cobro` (label, metodo, provider, orden, activa).
5. Guardar.

Resultado esperado:
- Parametros consistentes y persistidos para operacion.

Errores frecuentes y resolucion:
- Usuario en modo lectura: solicitar permisos de configuracion.
- Credenciales enmascaradas sin reemplazo: ingresar nuevo valor y guardar.
- Cuentas de cobro desordenadas: ajustar `sort_order` y volver a guardar.

Notas de disponibilidad externa:
- ARCA real: `No disponible / depende de configuracion externa` hasta completar alta formal, certificados y asociaciones.
- Tienda Nube real: `No disponible / depende de configuracion externa` hasta completar OAuth/credenciales y webhooks.

## 7.2 Usuarios y permisos personalizados (dentro de `/config`)
Objetivo:
- Crear usuarios, activar/desactivar y ajustar permisos finos.

Prerrequisitos:
- Perfil con capacidad de edicion de configuracion.

Pasos:
1. Crear usuario (nombre, email, rol).
2. En listado, usar menu de acciones por usuario:
   - activar/desactivar
   - permisos personalizados
   - reenviar mail
   - eliminar.
3. En editor de permisos:
   - buscar permiso
   - elegir efecto (`inherit`, `allow`, `deny`)
   - guardar o resetear.

Resultado esperado:
- Usuario operativo con permisos efectivos segun politica de rol + overrides.

Errores frecuentes y resolucion:
- Permiso bloqueado por rol: no editable por politica; ajustar rol si corresponde.
- Usuario admin sin granularidad editable: comportamiento esperado por politica.

## 7.3 Configuracion de paginas (`/config/paginas`)
Objetivo:
- Personalizar branding y textos visibles de navegacion.

Prerrequisitos:
- Permiso `page.config`.

Pasos:
1. Definir:
   - nombre de app
   - subtitulo login
   - nombre legal footer
   - titulo de seccion menu
   - ruta inicial.
2. Editar etiquetas de menu.
3. Editar titulos por pagina.
4. Guardar y recargar si hace falta.

Resultado esperado:
- Cambios visibles en login, sidebar y titulos de pagina.

Errores frecuentes y resolucion:
- Cambios no visibles: recargar sesion/navegador y verificar guardado exitoso.
- Ruta inicial invalida: seleccionar una de las rutas permitidas.

## 8) Procedimientos transversales

## 8.1 Checklist de apertura de turno
1. Ingresar al sistema con usuario operativo.
2. Confirmar conectividad (sin errores de backend en login).
3. Abrir caja en `/pos` con monto inicial real.
4. Verificar scanner (prueba de lectura SKU/barcode).
5. Verificar que hay variantes activas y stock consultable.
6. Si hay canal online activo, revisar `fallidos pendientes` en `/online`.
7. Confirmar permisos de cada perfil en puestos de trabajo.

Resultado esperado:
- Punto de venta listo para operar sin bloqueos iniciales.

## 8.2 Checklist de cierre de turno
1. Confirmar que no quedan ventas en proceso (carrito vacio en POS).
2. Revisar ventas del dia y operaciones de postventa pendientes.
3. Ejecutar cierre de caja con conteo final.
4. Registrar motivo de diferencia si corresponde (cierre asistido).
5. Revisar resumen de cierres y alertas en `/reportes`.
6. Si hay integracion online, correr reintento de fallidos si aplica.
7. Cerrar sesion.

Resultado esperado:
- Caja cerrada con trazabilidad y estado operativo limpio para el siguiente turno.

## 8.3 Incidencias frecuentes y respuesta rapida

Incidencia: `No se puede confirmar venta por caja cerrada`
- Causa probable: no hay apertura activa.
- Accion: abrir caja en POS y volver a cotizar/confirmar.

Incidencia: `Pago mixto con diferencia`
- Causa probable: suma de tramos distinta al total.
- Accion: corregir montos hasta diferencia cero.

Incidencia: `No se puede devolver por garantia vencida`
- Causa probable: ventana de garantia superada.
- Accion: usar override con motivo si el usuario tiene permiso; si no, escalar.

Incidencia: `Facturacion en retry/manual_review`
- Causa probable: datos ARCA incompletos, error temporal o dato fiscal faltante.
- Accion: corregir configuracion fiscal y reintentar emision.

Incidencia: `Fallidos online persistentes`
- Causa probable: credenciales invalidas, SKU no conciliado, problemas API.
- Accion: revisar `/config`, ejecutar `Reintentar fallidos`, luego `Proceso programado jobs`.

Incidencia: `No veo una pantalla o boton`
- Causa probable: falta de permiso.
- Accion: validar permisos efectivos y overrides en gestion de usuarios.

Incidencia: `ARCA/Tienda Nube no operativos`
- Causa probable: integracion externa incompleta.
- Accion: tratar como `No disponible / depende de configuracion externa` hasta completar alta tecnica.

## 9) Glosario operativo

Estados de venta:
- `confirmed`: venta confirmada.
- `partial_return`: venta con devolucion parcial.
- `returned`: venta devuelta totalmente.
- `cancelled`: venta anulada.

Estados fiscales ARCA (por venta):
- `pending`: pendiente de emision/confirmacion.
- `authorized`: autorizado con CAE.
- `rejected`: rechazado.
- `retry`: requiere reintento.
- `manual_review`: requiere revision manual.
- `not_required`: no requiere comprobante fiscal.

Estados de inventario:
- `draft`: borrador.
- `in_progress`: en progreso.
- `closed`: cerrado.
- `cancelled`: cancelado.

Terminos comunes:
- `Override`: habilitacion excepcional con motivo obligatorio.
- `Split tender`: cobro mixto en varios medios/cuentas.
- `Store credit`: saldo a favor de cliente.
- `Ack`: confirmacion de lectura/gestion de alerta.
- `Fallback`: comportamiento por defecto ante falta de configuracion explicita.

## 10) Referencias y anexos

Documentacion funcional/tecnica relacionada:
- `docs/README.md` (indice documental)
- `docs/PENDIENTES.md`
- `docs/CHECKLIST_TIENDANUBE_PASO_A_PASO.md`
- `docs/CHECKLIST_ARCA_PASO_A_PASO.md`
- `docs/ARCA_OPERACION.md`
- `docs/AUDITORIA_FLUJO_ARCA_2026-04-02.md`
- `docs/INSTALACION_CLIENTE_WINDOWS.md`
- `docs/SEGURIDAD_ROTACION_SECRETOS.md`

## 11) Criterios de mantenimiento del manual
- Actualizar este archivo ante cualquier cambio de flujo en UI o permisos.
- Evitar documentar como operativo cualquier flujo dependiente de alta externa incompleta.
- Mantener consistencia con rutas reales, nombres de botones y estados de backend/frontend.
