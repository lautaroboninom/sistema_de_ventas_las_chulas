-- Marcar como entregados TODOS los 'liberado' que NO estén en la lista de 40 no-entregados provistos
SET @now := NOW();
UPDATE ingresos
SET estado='entregado',
    fecha_entrega = IFNULL(fecha_entrega, @now)
WHERE estado='liberado'
  AND ubicacion_id IN (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('taller'))
  AND id NOT IN (
    27122,27494,27509,27637,26773,27536,27935,27998,27069,28053,
    28074,28075,28079,27369,27229,28147,28200,28159,28228,28229,
    28234,28235,28221,28273,28251,28393,28400,28259,28455,28460,
    28399,28514,28473,28478,28479,28480,28488,28487,28484,28513
  );

