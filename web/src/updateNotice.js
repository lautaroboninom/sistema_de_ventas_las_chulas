const UPDATE_NOTICE = {
  id: '2026-05-20-atributos-unificados-variantes-compras-lista',
  title: 'Actualizacion de atributos en variantes',
  subtitle: 'Productos y Compras',
  intro:
    'Esta actualizacion unifica la seleccion de atributos de variantes para que el mismo criterio se use en Productos, Compras y las altas masivas.',
  sections: [
    {
      title: 'Seleccion consistente',
      items: [
        'Nueva variante, los modales de Compras y el generador masivo ahora muestran la misma forma de elegir atributo y valor.',
        'Cuando ya existen valores conocidos, se pueden reutilizar desde sugerencias rapidas para evitar duplicados por mayusculas o escritura distinta.',
      ],
    },
    {
      title: 'Valores nuevos',
      items: [
        'Si hace falta cargar un valor nuevo para un atributo, el sistema ahora lo deja marcado de forma explicita antes de guardar.',
        'Esto ayuda a distinguir mejor cuando se esta usando un valor existente y cuando se va a crear uno nuevo en el catalogo.',
      ],
    },
    {
      title: 'Actualizacion en cliente',
      items: [
        'Este aviso se muestra de nuevo para confirmar que el cliente ya esta usando el flujo unificado de atributos.',
        'En Compras, la busqueda rapida para dar de alta ahora muestra primero los productos y despues las variantes para que sea mas natural arrancar desde el articulo base.',
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
