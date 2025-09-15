ALTER TABLE ingresos MODIFY COLUMN motivo ENUM('reparaci�n','reparación','service preventivo','baja alquiler','reparaci�n alquiler','reparación alquiler','urgente control','devolución demo','otros') NOT NULL;
UPDATE ingresos SET motivo='reparación' WHERE motivo='reparaci�n';
UPDATE ingresos SET motivo='reparación alquiler' WHERE motivo='reparaci�n alquiler';
ALTER TABLE ingresos MODIFY COLUMN motivo ENUM('reparación','service preventivo','baja alquiler','reparación alquiler','urgente control','devolución demo','otros') NOT NULL;
