-- Normalización de marca / modelo / tipo para los 40 "no entregados"
-- Criterio: tipo_equipo toma el texto de "Equipo" provisto; modelo del campo Modelo; marca del campo Marca.
-- Unificación mínima: AIR SEP -> AIRSEP; LONG FIAN -> LONGFIAN.

-- Helper: asegura marca y modelo y los aplica al device del ingreso
-- Variables: @marca_name, @modelo_name, @tipo_equipo, @ingreso_id
-- NOTA: no tocamos numero_serie/n_de_control aquí.

-- 27122 • MEDITECH • G3G • MONITOR MULTIPARAMETRICO
SET @marca_name='MEDITECH', @modelo_name='G3G', @tipo_equipo='MONITOR MULTIPARAMETRICO', @ingreso_id=27122;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27494 • LONGFIAN • JAY-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='LONGFIAN', @modelo_name='JAY-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=27494;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27509 (ya ajustado): RESPIRONICS • SYNCHRONY • BPAP
SET @marca_name='RESPIRONICS', @modelo_name='SYNCHRONY', @tipo_equipo='BPAP', @ingreso_id=27509;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27637 • MEDITECH • G3D • MONITOR MULTIPARAMETRICO
SET @marca_name='MEDITECH', @modelo_name='G3D', @tipo_equipo='MONITOR MULTIPARAMETRICO', @ingreso_id=27637;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 26773 (ya ajustado): MOVI-VAC • A-600 • ASPIRADOR A BATERIAS
SET @marca_name='MOVI-VAC', @modelo_name='A-600', @tipo_equipo='ASPIRADOR A BATERIAS', @ingreso_id=26773;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27536 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=27536;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27935 (ya ajustado): BMC • G1 • CALENTADOR HUMIDIFICADOR
SET @marca_name='BMC', @modelo_name='G1', @tipo_equipo='CALENTADOR HUMIDIFICADOR', @ingreso_id=27935;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27998 • LONGFIAN • JAY-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='LONGFIAN', @modelo_name='JAY-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=27998;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27069 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=27069;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28053 • KANGAROO • 324 • BOMBA DE ALIMENTACION
SET @marca_name='KANGAROO', @modelo_name='324', @tipo_equipo='BOMBA DE ALIMENTACION', @ingreso_id=28053;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28074 • LONGFIAN • JAY-5Q • CONCENTRADOR DE OXIGENO
SET @marca_name='LONGFIAN', @modelo_name='JAY-5Q', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28074;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28075 • LONGFIAN • JAY-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='LONGFIAN', @modelo_name='JAY-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28075;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28079 • SILFAB • N33 • ASPIRADOR
SET @marca_name='SILFAB', @modelo_name='N33', @tipo_equipo='ASPIRADOR', @ingreso_id=28079;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27369 • BMC • GII T25S • BPAP
SET @marca_name='BMC', @modelo_name='GII T25S', @tipo_equipo='BPAP', @ingreso_id=27369;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 27229 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=27229;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28147 (ya ajustado) • INOGEN • G5 • CONCENTRADOR DE OXIGENO
SET @marca_name='INOGEN', @modelo_name='G5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28147;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28200 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28200;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28159 • LEEX • 1M8 • MONITOR MULTIPARAMETRICO
SET @marca_name='LEEX', @modelo_name='1M8', @tipo_equipo='MONITOR MULTIPARAMETRICO', @ingreso_id=28159;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28228 • BMC • G2S • CPAP
SET @marca_name='BMC', @modelo_name='G2S', @tipo_equipo='CPAP', @ingreso_id=28228;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28229 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28229;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28234 (ya ajustado): COVIDIEN • PB560 • RESPIRADOR
SET @marca_name='COVIDIEN', @modelo_name='PB560', @tipo_equipo='RESPIRADOR', @ingreso_id=28234;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28235 • RESPIRONICS • EVERFLO • CONCENTRADOR DE OXIGENO
SET @marca_name='RESPIRONICS', @modelo_name='EVERFLO', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28235;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28221 • KONSUNG • (modelo desconocido) • ASPIRADOR A BATERIAS
SET @marca_name='KONSUNG', @modelo_name='(SIN MODELO)', @tipo_equipo='ASPIRADOR A BATERIAS', @ingreso_id=28221;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28273 • BMC • YH-600B PRO • POLIGRAFO
SET @marca_name='BMC', @modelo_name='YH-600B PRO', @tipo_equipo='POLIGRAFO', @ingreso_id=28273;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28251 • SILFAB • N33 • ASPIRADOR
SET @marca_name='SILFAB', @modelo_name='N33', @tipo_equipo='ASPIRADOR', @ingreso_id=28251;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28393 • SILFAB • N-33A • ASPIRADOR
SET @marca_name='SILFAB', @modelo_name='N-33A', @tipo_equipo='ASPIRADOR', @ingreso_id=28393;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28400 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28400;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28455 • NELLCOR • BEDSIDE • OXIMETRO DE PULSO
SET @marca_name='NELLCOR', @modelo_name='BEDSIDE', @tipo_equipo='OXIMETRO DE PULSO', @ingreso_id=28455;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28460 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28460;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28399 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28399;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28514 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28514;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28473 • BMC • G2S • CPAP
SET @marca_name='BMC', @modelo_name='G2S', @tipo_equipo='CPAP', @ingreso_id=28473;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28478 • KONSUNG • KSOC-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='KONSUNG', @modelo_name='KSOC-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28478;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28479 • KONSUNG • KSOC-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='KONSUNG', @modelo_name='KSOC-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28479;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28480 • KONSUNG • KSOC-5 • CONCENTRADOR DE OXIGENO
SET @marca_name='KONSUNG', @modelo_name='KSOC-5', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28480;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28488 • BMC • POLYWATCH • POLIGRAFO
SET @marca_name='BMC', @modelo_name='POLYWATCH', @tipo_equipo='POLIGRAFO', @ingreso_id=28488;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28487 • BMC • POLYWATCH • POLIGRAFO
SET @marca_name='BMC', @modelo_name='POLYWATCH', @tipo_equipo='POLIGRAFO', @ingreso_id=28487;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28484 (ya ajustado) • YAMIND • DM26 • CPAP
SET @marca_name='YAMIND', @modelo_name='DM26', @tipo_equipo='CPAP', @ingreso_id=28484;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

-- 28513 • AIRSEP • NEW LIFE • CONCENTRADOR DE OXIGENO
SET @marca_name='AIRSEP', @modelo_name='NEW LIFE', @tipo_equipo='CONCENTRADOR DE OXIGENO', @ingreso_id=28513;
INSERT IGNORE INTO marcas(nombre) VALUES(@marca_name);
SET @marca_id=(SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(@marca_name) LIMIT 1);
INSERT IGNORE INTO models(marca_id,nombre,tipo_equipo) VALUES(@marca_id,@modelo_name,@tipo_equipo);
UPDATE models SET tipo_equipo=@tipo_equipo WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name);
SET @model_id=(SELECT id FROM models WHERE marca_id=@marca_id AND UPPER(nombre)=UPPER(@modelo_name) LIMIT 1);
UPDATE devices d JOIN ingresos t ON t.device_id=d.id SET d.marca_id=@marca_id, d.model_id=@model_id WHERE t.id=@ingreso_id;

