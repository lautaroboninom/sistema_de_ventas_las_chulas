Colocá acá tus logos originales para referencia interna:

- logo-empresa.png — Logo corporativo (se usa dentro de la UI si se necesita).
- logo-app.png — Logo base para la app instalable y favicon.

Luego corré desde la carpeta `web/`:

```
npm run icons
```

Ese comando genera en `public/icons/` las variantes requeridas:
- logo-app-16.png, logo-app-32.png (favicons)
- logo-app-180.png (apple touch)
- logo-app-192.png, logo-app-512.png (PWA)
- logo-app-512-maskable.png (PWA maskable)

