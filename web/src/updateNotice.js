const UPDATE_NOTICE = {
  id: '2026-05-07-atributos-tiendanube-agrupada',
  title: 'Actualizacion de atributos y Tienda Nube',
  subtitle: 'Productos, variantes y sincronizacion online',
  intro:
    'Esta actualizacion ayuda a cargar talles, colores y otros atributos sin duplicarlos, y corrige la forma en que los productos se envian a Tienda Nube.',
  sections: [
    {
      title: 'Carga de atributos mas simple',
      items: [
        'Cuando se carga un valor como Negro, negro o NEGRO, RetailHub lo reconoce como el mismo valor.',
        'Si se escribe algo parecido a un valor que ya existe, el sistema avisa antes de crear uno nuevo.',
        'En Productos y Variantes ahora aparecen ayudas, opciones sugeridas y botones para elegir valores ya cargados.',
        'Esto evita colores, talles o atributos duplicados por mayusculas, acentos, espacios o errores de tipeo.',
      ],
    },
    {
      title: 'Productos en Tienda Nube',
      items: [
        'RetailHub ahora envia a Tienda Nube un solo producto con sus variantes adentro.',
        'Por ejemplo, una remera con Color y Talle queda como un producto unico, no como varios productos separados.',
        'Color, Talle y otros atributos se sincronizan como opciones de la variante en Tienda Nube.',
        'RetailHub usa el SKU de cada variante para reconocer que variante corresponde actualizar.',
      ],
    },
    {
      title: 'Que tienen que hacer',
      items: [
        'Para productos nuevos o variantes nuevas, no hay que hacer ningun paso extra: RetailHub lo prepara automaticamente.',
        'Para corregir productos que ya estaban creados separados en Tienda Nube, entrar a Online (Tienda Nube) y tocar Corregir productos en Tienda Nube.',
        'Si despues de corregir quedan pendientes, tocar Reintentar fallidos en la misma pantalla.',
        'Mientras se hace la correccion, no borrar ni editar manualmente los productos duplicados desde Tienda Nube.',
      ],
    },
    {
      title: 'Importante',
      items: [
        'RetailHub no borra productos viejos de Tienda Nube. Primero verifica que todas las variantes queden bien vinculadas.',
        'Si la correccion esta completa, los productos viejos se despublican para que no se vean duplicados en la tienda.',
        'Si alguna variante no se pudo vincular, el sistema deja el producto viejo publicado y muestra el pendiente para revisar.',
      ],
    },
  ],
  actions: [
    {
      label: 'Ir a Online (Tienda Nube)',
      to: '/online',
    },
  ],
};

export default UPDATE_NOTICE;
