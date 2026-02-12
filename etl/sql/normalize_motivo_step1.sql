ALTER TABLE ingresos MODIFY COLUMN motivo TEXT NOT NULL;
UPDATE ingresos SET motivo='reparación' WHERE motivo='reparaci�n';
