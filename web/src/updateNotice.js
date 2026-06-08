const UPDATE_NOTICE = {
  id: '2026-06-08-detalle-proveedores-articulos-productos',
  title: 'Detalle de proveedores en productos',
  subtitle: 'Productos y Compras',
  intro:
    'Esta actualizacion agrega mas detalle visible en el catalogo para identificar mejor los codigos asociados a cada variante.',
  sections: [
    {
      title: 'Productos',
      items: [
        'La lista de variantes ahora muestra el proveedor asociado a cada codigo y el numero de articulo interno del EAN cuando corresponde.',
        'Si la variante tiene varios codigos, se ven todos con su proveedor para identificar rapidamente cual pertenece a cada origen.',
      ],
    },
    {
      title: 'Gestion de codigos',
      items: [
        'El modal de Gestionar barcode tambien muestra el numero de articulo junto al proveedor.',
        'Esto evita tener que interpretar el codigo completo para saber que articulo corresponde.',
      ],
    },
    {
      title: 'Compras',
      items: [
        'Cuando existe una referencia de la ultima compra, tambien queda visible en la fila de la variante.',
        'Sirve como apoyo para reconocer el articulo del proveedor desde el catalogo.',
      ],
    },
  ],
  actions: [
    {
      label: 'Ir a productos',
      to: '/productos',
    },
  ],
};

export default UPDATE_NOTICE;
