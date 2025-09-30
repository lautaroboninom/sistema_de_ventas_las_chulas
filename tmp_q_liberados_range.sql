SELECT t.id, c.cod_empresa, COALESCE(m.nombre,'') AS modelo, COALESCE(b.nombre,'') AS marca,
       d.numero_serie, c.razon_social, t.estado, DATE(t.fecha_ingreso) AS fecha_ingreso,
       DATE(t.fecha_entrega) AS fecha_entrega, COALESCE(l.nombre,'') AS ubicacion
FROM ingresos t
JOIN devices d ON d.id=t.device_id
JOIN customers c ON c.id=d.customer_id
LEFT JOIN marcas b ON b.id=d.marca_id
LEFT JOIN models m ON m.id=d.model_id
LEFT JOIN locations l ON l.id=t.ubicacion_id
WHERE t.estado='liberado' AND LOWER(l.nombre)=LOWER('taller')
  AND t.id BETWEEN 26700 AND 28550
ORDER BY t.id;

