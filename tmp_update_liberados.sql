UPDATE ingresos
SET estado='entregado',
    fecha_entrega = IFNULL(fecha_entrega, NOW())
WHERE id IN (26700,26725,26748,26775,26776,26834,26980,27073,27103,27104,27232,27263,27271,27368,28283,28449,28462)
  AND estado='liberado';

