const UPDATE_NOTICE = {
  id: '2026-05-12-correcciones-generales-sumar-stock',
  title: 'Correcciones generales (Etiquetas, edición de variantes y eliminación de productos) y suma de stock con variantes existentes',
  subtitle: 'Variantes',
  intro:
    'Esta actualizacion corrije el error al guardar cambios en variantes, agrega la opción de eliminar variantes y ocultar productos no utilizados. También agrega la opción de modificar stock cuando se crea una variante ya existente desde productos.',
  sections: [
    {
      title: 'Correción de guardado de variantes',
      items: [
        'Se corrigió el error al guardar cambios en variantes.',
        'Ahora se guardan correctamente los cambios realizados en las variantes de los productos.',
      ],
    },
    //{
      //title: 'Creación de variantes ya existente desde Productos',
      //items: [
       // 'Antes si se creaba una variante con la opción de crear combinaciónes, el sismtea bloqueba la variatne que se quería crear.',
        //'Ahora, al detectar queuna variante ya existe, el sistema te permite sumar el stock de la nueva variante a la variante existente, para no tener que volverlo a cagar desde Compras o desde el producto.',
      //],
    //},
    {
      title: 'Correción de etiqueta',
      items: [
        'Se cambio el layout de la etiqueta para que el nombre y el precio se puedan ver mas claros.',
        'Se achico el tamaño del código y se sacó el código explícito.',
      ],
    },
  ]
};

export default UPDATE_NOTICE;
