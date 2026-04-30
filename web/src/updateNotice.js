const UPDATE_NOTICE = {
  id: '2026-04-29-productos-compras-nombres-precios',
  title: 'Novedades implementadas en productos y compras',
  subtitle: 'Actualizacion de productos, variantes y proveedores',
  intro:
    'Esta actualizacion ordena mejor los nombres de los productos y reduce pasos repetidos al cargar precios y variantes.',
  sections: [
    {
      title: 'Nombre interno y nombre del proveedor',
      items: [
        'Cada producto puede tener un nombre interno del local, que es el nombre que se usa para vender, buscar y controlar stock.',
        'La descripcion que trae el proveedor se puede guardar aparte al cargar una compra, tal como viene en la factura, remito o pedido.',
        'El nombre del proveedor queda como dato de referencia para compras y reposiciones, pero no aparece en el uso diario del mostrador.',
        'Esto permite trabajar con el nombre que usa el local aunque cada proveedor escriba sus productos de otra manera.',
      ],
    },
    {
      title: 'Precios y variantes',
      items: [
        'Ahora cada producto tiene un precio base para el local y otro para la venta online.',
        'Cuando se crean variantes por talle o color, el sistema toma ese precio base automaticamente.',
        'Si un producto siempre vale lo mismo aunque cambie el talle o el color, ya no hace falta escribir el precio una y otra vez.',
        'Cuando se cambia el precio base del producto, las variantes activas pueden quedar actualizadas con ese mismo precio.',
      ],
    },
    {
      title: 'Compras a proveedores',
      items: [
        'Al cargar una compra se puede guardar el nombre o descripcion que usa el proveedor.',
        'Ese nombre del proveedor queda como referencia de compra para identificar mejor pedidos y reposiciones.',
        'Si ya se compro antes una variante, el sistema puede recuperar la ultima descripcion del proveedor para cargar mas rapido.',
        'La carga rapida de productos desde Compras tambien incluye precio base, para que las variantes nuevas ya nazcan con el precio correcto.',
      ],
    },
    {
      title: 'Alta masiva de variantes',
      items: [
        'Al crear muchas combinaciones de talle y color, se puede definir un precio comun para todas.',
        'Las variantes creadas en lote toman el precio del producto, evitando repetir el mismo importe en cada renglon.',
      ],
    },
  ],
};

export default UPDATE_NOTICE;
