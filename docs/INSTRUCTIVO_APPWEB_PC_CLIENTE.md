# Instructivo Rapido - Instalar App Web en PC Cliente (No Servidor)

## Objetivo
Dejar la app de RetailHub instalada como aplicacion en una PC cliente que NO actua como servidor.

Este equipo solo necesita:
1. conectarse por Tailscale
2. entrar a la URL del sistema
3. instalar la app web desde el navegador

## Requisitos previos
- Windows 10/11.
- Internet funcionando.
- Navegador recomendado: Microsoft Edge o Google Chrome.
- Cuenta Tailscale autorizada.
- Usuario de acceso Tailscale: `laschulas.comercial@gmail.com`.
- URL de RetailHub (ejemplo actual): `https://retailhub.taila1413b.ts.net`

## Paso 1 - Instalar Tailscale
1. Abrir: `https://tailscale.com/download`
2. Descargar e instalar Tailscale para Windows.
3. Abrir Tailscale al finalizar la instalacion.

## Paso 2 - Iniciar sesion en Tailscale
1. En Tailscale, presionar `Log in` / `Iniciar sesion`.
2. Elegir ingreso con Google.
3. Iniciar sesion con el mail: `laschulas.comercial@gmail.com`.
4. Aceptar permisos/confirmaciones de Tailscale.
5. Verificar que quede estado `Connected` (conectado).

Resultado esperado:
- La PC cliente queda dentro de la red privada y puede abrir la URL del sistema.

## Paso 3 - Abrir RetailHub
1. Con Tailscale conectado, abrir el navegador.
2. Ir a la URL de RetailHub:
   - ejemplo: `https://retailhub.taila1413b.ts.net`
3. Verificar que cargue la pantalla de login del sistema.

## Paso 4 - Instalar la app web
Cuando la pagina ya cargo:

### Opcion A (boton rapido en barra de direcciones)
1. Buscar el icono de instalacion (app/monitor con flecha) en la barra de direcciones.
2. Hacer click en `Instalar`.

### Opcion B (si no aparece el icono)
En Microsoft Edge:
1. Click en `...` (menu).
2. `Aplicaciones`.
3. `Instalar este sitio como aplicacion`.

En Google Chrome:
1. Click en `...` (menu).
2. `Guardar y compartir`.
3. `Instalar pagina como aplicacion`.

Resultado esperado:
- Se crea acceso directo en escritorio/inicio.
- RetailHub abre en ventana propia como app.

## Paso 5 - Primer inicio de la app
1. Abrir `RetailHub` desde el icono creado.
2. Ingresar usuario y contrasena del sistema RetailHub.
3. Confirmar que abre normalmente (menu lateral y modulos segun permisos).

## Problemas comunes y solucion

Problema: no abre la URL o queda cargando.
- Verificar que Tailscale este `Connected`.
- Confirmar que se inicio sesion con `laschulas.comercial@gmail.com`.
- Reintentar abrir la URL en Edge/Chrome.

Problema: no aparece opcion `Instalar`.
- Usar Edge o Chrome (evitar modo incognito).
- Recargar la pagina y volver a intentar.
- Probar desde el menu del navegador (opcion B).

Problema: abre en navegador normal y no como app.
- Repetir instalacion desde `Aplicaciones` / `Instalar pagina como aplicacion`.
- Fijar acceso directo al escritorio o barra de tareas.

## Checklist final (2 minutos)
- [ ] Tailscale instalado.
- [ ] Sesion iniciada con `laschulas.comercial@gmail.com`.
- [ ] Estado Tailscale en `Connected`.
- [ ] URL de RetailHub abre correctamente.
- [ ] App web instalada y acceso directo visible.
- [ ] Login RetailHub funcionando.
