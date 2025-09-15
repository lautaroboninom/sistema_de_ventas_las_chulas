-- Ajuste de numeración posterior a la importación
-- Garantiza que el próximo AUTO_INCREMENT de ingresos sea >= 27868
SET @cur := (SELECT IFNULL(MAX(id),0) + 1 FROM ingresos);
SET @next := GREATEST(@cur, 27868);
SET @sql := CONCAT('ALTER TABLE ingresos AUTO_INCREMENT=', @next);
PREPARE s1 FROM @sql; EXECUTE s1; DEALLOCATE PREPARE s1;

