const UPDATE_NOTICE = {
  id: '2026-08-18-pos-simple-y-tiendanube-seguro',
  title: 'Pantalla de venta mas simple y productos de Tienda Nube mas seguros',
  subtitle: 'POS, Productos y Online',
  intro:
    'Esta actualizacion trae dos cosas: la pantalla de venta quedo mas facil de leer desde el mostrador, y se corrigio el problema por el cual un producto podia desaparecer de Tienda Nube al borrar variantes viejas.',
  sections: [
    {
      title: 'El carrito',
      items: [
        'Cada prenda se ve como un renglon limpio, con el talle y el color en etiquetas faciles de leer en lugar del codigo tecnico de antes.',
        'Cuando escaneas algo, el renglon se ilumina un instante para que veas que entro bien sin tener que buscarlo con la vista.',
        'El carrito ya reserva su lugar aunque este vacio, asi la pantalla no se mueve cuando cargas la primera prenda.',
      ],
    },
    {
      title: 'El total y el cobro',
      items: [
        'El total de la venta ahora se ve grande en la barra de abajo, junto al boton de confirmar.',
        'Si cobras en efectivo podes anotar cuanto te dieron y el sistema te calcula el vuelto solo.',
        'Los medios de pago pasaron a ser botones: tocas Efectivo, Debito o el que uses y listo.',
        'El detalle de promociones y facturacion sigue estando, pero escondido detras de Ver detalle para no llenar la pantalla.',
      ],
    },
    {
      title: 'Menos ruido',
      items: [
        'Cliente y notas, Borradores en espera y Caja ahora se abren y cierran, asi solo ves lo que estas usando.',
        'La caja se cierra sola en la pantalla cuando la abris a la manana, y se despliega cuando queda cerrada.',
        'La busqueda manual de productos aparece solo cuando la pedis, porque el dia a dia se trabaja con el lector.',
        'Sacamos la lista de ventas recientes del POS: esa informacion la seguis viendo completa en la seccion Ventas.',
      ],
    },
    {
      title: 'Ya no se borra el producto de la web',
      items: [
        'Cuando eliminas la ultima variante de un producto, el producto ya no se borra de Tienda Nube: queda despublicado, conservando sus fotos, su descripcion y su direccion web.',
        'Si al producto todavia le quedan variantes activas, se elimina solo la variante y la publicacion se rearma sola con las que quedan.',
      ],
    },
    {
      title: 'Agregar un atributo a un producto que ya existe',
      items: [
        'En Productos, al editar un producto vas a ver "Agregar atributo a este producto".',
        'Te pregunta que valor tienen las variantes actuales (por ejemplo, que todas eran Negro) y crea unicamente las combinaciones que faltan.',
        'Asi no quedan variantes viejas en cero conviviendo con las nuevas.',
      ],
    },
    {
      title: 'Avisos cuando algo no se puede publicar',
      items: [
        'Si algunas variantes de un producto no tienen los mismos atributos que el resto, ahora el producto igual se publica con las que si se pueden, y el sistema te avisa cuales quedaron afuera y que les falta.',
        'Los errores de sincronizacion que antes pasaban en silencio ahora aparecen en Online, en "Fallidos pendientes", y se pueden reintentar.',
        'La correccion de productos ya no se corta en los primeros de la lista: recorre todo el catalogo, incluidas las variantes cargadas mas recientemente.',
      ],
    },
  ],
  actions: [
    {
      label: 'Ir al POS',
      to: '/pos',
    },
    {
      label: 'Ir a productos',
      to: '/productos',
    },
    {
      label: 'Ir a Online',
      to: '/online',
    },
  ],
};

export default UPDATE_NOTICE;
