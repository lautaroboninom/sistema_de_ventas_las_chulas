-- Asegurar conexión en UTF-8 completo (evita perder tildes al ejecutar desde Windows)
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Inserta tipos de equipo (si faltan) en marca_tipos_equipo usando la primera marca disponible
SET @brand_id := (SELECT id FROM marcas ORDER BY id LIMIT 1);

-- Si no hay marcas, no hace nada
SET @brand_id := IFNULL(@brand_id, 0);

-- Helper: inserta si no existe en ninguna marca (evita duplicados globales)
-- Para MySQL 8, usamos INSERT .. SELECT .. WHERE NOT EXISTS

-- Lista de tipos
INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ACUMULADOR DE OXÍGENO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ACUMULADOR DE OXÍGENO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ALARGUE DE SENSOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ALARGUE DE SENSOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ALTO FLUJO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ALTO FLUJO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ANALIZADOR DE OXÍGENO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ANALIZADOR DE OXÍGENO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ARTROSCOPIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ARTROSCOPIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ASPIRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ASPIRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ASPIRADOR A BATERÍAS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ASPIRADOR A BATERÍAS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BALANZA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BALANZA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BATERÍA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BATERÍA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PACK DE BATERÍAS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PACK DE BATERÍAS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BLENDER DE OXÍGENO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BLENDER DE OXÍGENO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BOMBA DE ALIMENTACIÓN', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BOMBA DE ALIMENTACIÓN'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BOMBA DE ASPIRACIÓN DE DRENAJE', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BOMBA DE ASPIRACIÓN DE DRENAJE'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BOMBA DE INFUSIÓN', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BOMBA DE INFUSIÓN'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BOMBA SACA LECHE', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BOMBA SACA LECHE'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'BPAP', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('BPAP'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'AUTO BPAP', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('AUTO BPAP'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CABEZALES DE BOMBA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CABEZALES DE BOMBA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CABLE DE CONEXIÓN 12V', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CABLE DE CONEXIÓN 12V'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CABLE TRANSMISION DATOS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CABLE TRANSMISION DATOS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CALENTADOR HUMIDIFICADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CALENTADOR HUMIDIFICADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CAPNÓGRAFO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CAPNÓGRAFO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CAPNÓMETRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CAPNÓMETRO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CARDIODESFIBRILADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CARDIODESFIBRILADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CARGADOR DE BATERÍAS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CARGADOR DE BATERÍAS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CENTRAL DE MONITOREO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CENTRAL DE MONITOREO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COLCHÓN DE AIRE', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COLCHÓN DE AIRE'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COLPOSCOPIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COLPOSCOPIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COMPRESOR DE COLCHÓN ANTI ESCARAS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COMPRESOR DE COLCHÓN ANTI ESCARAS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COMPRESOR DE CONCENTRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COMPRESOR DE CONCENTRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COMPRESOR DE RESPIRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COMPRESOR DE RESPIRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CONCENTRADOR DE OXÍGENO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CONCENTRADOR DE OXÍGENO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CONCENTRADOR DE OXÍGENO PORTÁTIL', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CONCENTRADOR DE OXÍGENO PORTÁTIL'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'COUGH ASIST', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('COUGH ASIST'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CPAP', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CPAP'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'AUTO CPAP', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('AUTO CPAP'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CRANEOMOTRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CRANEOMOTRO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'CUNA PEDIATRICA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('CUNA PEDIATRICA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'DETECTOR FETAL', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('DETECTOR FETAL'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ELECTROBISTURÍ', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ELECTROBISTURÍ'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ELECTROCARDIÓGRAFO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ELECTROCARDIÓGRAFO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ELECTROCOAGULADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ELECTROCOAGULADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ELECTRODO PASIVO ELECTROBISTURÍ', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ELECTRODO PASIVO ELECTROBISTURÍ'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ESPIRÓMETRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ESPIRÓMETRO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ESTABILIZADOR DE TENSIÓN', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ESTABILIZADOR DE TENSIÓN'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ESTUFA DE LABORATORIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ESTUFA DE LABORATORIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'FERULA DE TORONTO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('FERULA DE TORONTO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'FLOWMETER', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('FLOWMETER'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'FRONTOLUZ', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('FRONTOLUZ'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'FUENTE DE ALIMENTACIÓN', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('FUENTE DE ALIMENTACIÓN'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'FUENTE DE FIBRA ÓPTICA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('FUENTE DE FIBRA ÓPTICA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'GENERADOR DE MARCAPASOS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('GENERADOR DE MARCAPASOS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'GENERADOR DE OZONO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('GENERADOR DE OZONO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'GRUPO CONTROL DE SERVOCUNA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('GRUPO CONTROL DE SERVOCUNA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'GRUPO MOTOR DE INCUBADORA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('GRUPO MOTOR DE INCUBADORA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'HOLTER', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('HOLTER'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'IMPRESORA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('IMPRESORA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'INCUBADOR DE MONITORES BIOLÓGICOS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('INCUBADOR DE MONITORES BIOLÓGICOS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'INCUBADORA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('INCUBADORA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'INCUBADORA DE TRANSPORTE', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('INCUBADORA DE TRANSPORTE'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'LÁMPARA DE ODONTOLOGÍA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('LÁMPARA DE ODONTOLOGÍA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'LARINGOSCÓPIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('LARINGOSCÓPIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'LÁSER INFRAROJO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('LÁSER INFRAROJO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'LUMINOTERAPIA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('LUMINOTERAPIA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MAGNETO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MAGNETO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MANGUERA DE ALTA PRESIÓN', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MANGUERA DE ALTA PRESIÓN'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MANÓMETRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MANÓMETRO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MARCAPASO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MARCAPASO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MESA DE ANESTESIA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MESA DE ANESTESIA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MOCHILA O2 425L', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MOCHILA O2 425L'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MÓDULO DE ENTRADA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MÓDULO DE ENTRADA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR AUXILIAR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR AUXILIAR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR CARDÍACO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR CARDÍACO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR DE APNEA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR DE APNEA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR DE PRESIÓN NO INVASIVO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR DE PRESIÓN NO INVASIVO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR DE SEG ELÉCTRICA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR DE SEG ELÉCTRICA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR FETAL', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR FETAL'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR MULTIPARAMÉTRICO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR MULTIPARAMÉTRICO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MONITOR PRE PARTO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MONITOR PRE PARTO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MOTO NEBULIZADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MOTO NEBULIZADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'MOTORES CON TURBINA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('MOTORES CON TURBINA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'NEBULIZADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('NEBULIZADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'OTOSCOPIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('OTOSCOPIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'OXICAPNÓGRAFO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('OXICAPNÓGRAFO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'OXÍMETRO DE PULSO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('OXÍMETRO DE PULSO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PALETAS DE DESFIBRILADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PALETAS DE DESFIBRILADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PANEL DE SERVOCUNA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PANEL DE SERVOCUNA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PEDAL DE ELECTROBISTURÍ', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PEDAL DE ELECTROBISTURÍ'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PIE PORTASUEROS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PIE PORTASUEROS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PIE RODANTE DE MONITOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PIE RODANTE DE MONITOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PLACA INDIFERENTE DE ELECTROBISTURI', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PLACA INDIFERENTE DE ELECTROBISTURI'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'POLÍGRAFO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('POLÍGRAFO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PORTA FUELLE DE RESPIRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PORTA FUELLE DE RESPIRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PROLONGADOR DE SENSOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PROLONGADOR DE SENSOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'PUNTA DE ASPIRADOR ULTRASÓNICO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('PUNTA DE ASPIRADOR ULTRASÓNICO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'RECTOSCOPIO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('RECTOSCOPIO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'REGULADOR DE MOCHILA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('REGULADOR DE MOCHILA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'RESPIRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('RESPIRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SELLADORA DE BOLSAS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SELLADORA DE BOLSAS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SENSOR DE GOTA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SENSOR DE GOTA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SENSOR DE OXÍMETRO DE PULSO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SENSOR DE OXÍMETRO DE PULSO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SENSOR DE TEMPERATURA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SENSOR DE TEMPERATURA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SENSOR DE FLUJO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SENSOR DE FLUJO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SERVOCUNA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SERVOCUNA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SIERRA ORTOPÉDICA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SIERRA ORTOPÉDICA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SOPORTE DE PALETAS DESFIBRILADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SOPORTE DE PALETAS DESFIBRILADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'SWICH TPLINK', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('SWICH TPLINK'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TAPA DE CALENTADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TAPA DE CALENTADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TAPA DE CONCENTRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TAPA DE CONCENTRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TAPA DE HUMIDIFICADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TAPA DE HUMIDIFICADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TAPA DE RESPIRADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TAPA DE RESPIRADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TENSIÓMETRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TENSIÓMETRO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TERMINALES DE SENSOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TERMINALES DE SENSOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TRANSFORMADOR', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TRANSFORMADOR'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'TUBO DE OXÍGENO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('TUBO DE OXÍGENO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'ULTRASONIDO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('ULTRASONIDO'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'UPS', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('UPS'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'VÁLVULA AHORRADORA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('VÁLVULA AHORRADORA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'VALVULA DE MESA DE ANESTESIA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('VALVULA DE MESA DE ANESTESIA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'VALVULA DE PEEP', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('VALVULA DE PEEP'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'VALVULA ESPIROMETRÍA', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('VALVULA ESPIROMETRÍA'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'VALVULA REDUCTORA DE PRESION', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('VALVULA REDUCTORA DE PRESION'));

INSERT INTO marca_tipos_equipo (marca_id, nombre, activo)
SELECT @brand_id, 'OTRO', TRUE FROM DUAL
WHERE @brand_id <> 0 AND NOT EXISTS (SELECT 1 FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER('OTRO'));
