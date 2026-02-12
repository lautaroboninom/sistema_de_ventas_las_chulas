ALTER TABLE ingresos MODIFY COLUMN motivo TEXT NOT NULL;
UPDATE ingresos SET motivo='reparación' WHERE motivo='reparaci�n';
UPDATE ingresos SET motivo='reparación alquiler' WHERE motivo='reparaci�n alquiler';
-- mantener 'otros' cuando no hay equivalencia
ALTER TABLE ingresos MODIFY COLUMN motivo ENUM('reparación','service preventivo','baja alquiler','reparación alquiler','urgente control','devolución demo','otros') NOT NULL;
