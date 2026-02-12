SELECT COUNT(*) FROM staging_estado_entrega; SELECT estado_nombre, COUNT(*) c FROM staging_estado_entrega GROUP BY estado_nombre ORDER BY c DESC LIMIT 10;
