SELECT id, HEX(SUBSTRING(nombre,1,4)) as hex4, nombre FROM marcas ORDER BY nombre LIMIT 20;
