-- Correcciones de marca, modelo y tipo para ingresos visibles con 'Sin Información'

-- Helper para upsert marca y modelo y aplicar al device del ingreso
-- Uso: definir @marca_name, @modelo_name, @tipo_equipo, @ingreso_id
-- Ejecuta para cada uno

-- OS 028234 -> COVIDIEN / PB560 / RESPIRADOR
SET @marca_name='COVIDIEN', @modelo_name='PB560', @tipo_equipo='RESPIRADOR', @ingreso_id=28234;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 028259 -> RESPIRONICS / EVERFLO / CONCENTRADOR DE OXIGENO
SET @marca_name='RESPIRONICS', @modelo_name='EVERFLO', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28259;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 028484 -> YAMIND / DM26 / CPAP
SET @marca_name='YAMIND', @modelo_name='DM26', @tipo_equipo='CPAP', @ingreso_id=28484;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 026773 -> MOVI-VAC / A-600 / ASPIRADOR A BATERIAS
SET @marca_name='MOVI-VAC', @modelo_name='A-600', @tipo_equipo='ASPIRADOR A BATERIAS', @ingreso_id=26773;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 027509 -> RESPIRONICS / SYNCHRONY / BPAP
SET @marca_name='RESPIRONICS', @modelo_name='SYNCHRONY', @tipo_equipo='BPAP', @ingreso_id=27509;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 027935 -> BMC / G1 / CALENTADOR HUMIDIFICADOR
SET @marca_name='BMC', @modelo_name='G1', @tipo_equipo='CALENTADOR HUMIDIFICADOR', @ingreso_id=27935;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- OS 028147 -> INOGEN / G5 / CONCENTRADOR DE OXIGENO
SET @marca_name='INOGEN', @modelo_name='G5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28147;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

