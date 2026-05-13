const UPDATE_NOTICE = {
  id: '2026-05-13-variantes-barcodes-cliente',
  title: 'Actualizacion de variantes y barcodes',
  subtitle: 'Productos',
  intro:
    'Esta actualizacion separa la edicion de variantes de la gestion de barcodes, para que un codigo viejo o invalido no bloquee cambios de talle, color, precios o stock minimo.',
  sections: [
    {
      title: 'Edicion de variantes',
      items: [
        'Guardar una variante ya no cambia ni revalida el barcode principal.',
        'El modal queda enfocado en nombre, SKU, precios, costo, stock minimo, estado y atributos.',
      ],
    },
    {
      title: 'Barcodes',
      items: [
        'Se quito el boton Generar EAN de la tabla para evitar crear codigos que no se van a usar.',
        'Los cambios de codigo quedan en Gestionar barcode: asociar, mover, generar un principal nuevo e imprimir etiquetas.',
      ],
    },
    {
      title: 'Actualizacion en cliente',
      items: [
        'Este aviso se muestra de nuevo para confirmar que el cliente esta usando el flujo corregido.',
        'Si la pantalla anterior quedo abierta en el navegador, cerrar y volver a abrir RetailHub aplica la version nueva.',
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
