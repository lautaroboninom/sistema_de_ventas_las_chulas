const UPDATE_NOTICE = {
  id: '2026-06-09-detalle-profesional-productos-proveedores',
  title: 'Detalle completo de productos y proveedores',
  subtitle: 'Productos y Compras',
  intro:
    'Esta actualizacion ordena la informacion de cada variante para que sea mas facil identificar proveedores, articulos, compras y codigos sin recargar la tabla.',
  sections: [
    {
      title: 'Productos',
      items: [
        'La lista de variantes ahora muestra un resumen mas limpio del proveedor principal o de la ultima compra disponible.',
        'Cada variante tiene un boton Detalles para ver informacion completa sin agrandar los renglones.',
      ],
    },
    {
      title: 'Detalle de variante',
      items: [
        'El nuevo detalle muestra precios, stock, proveedor destacado, ultima compra, codigos asociados y datos de catalogo online.',
        'Tambien se ven otras variantes del mismo producto para comparar talles, colores, stock y proveedores rapidamente.',
      ],
    },
    {
      title: 'Compras',
      items: [
        'La ultima compra ahora incluye proveedor, fecha y comprobante cuando esa informacion esta disponible.',
        'Los costos siguen respetando los permisos del usuario, pero la referencia operativa del proveedor queda visible.',
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
