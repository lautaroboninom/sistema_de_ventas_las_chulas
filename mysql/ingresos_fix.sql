-- Inserta/actualiza ingresos desde stg_ingresos con mapeos de ENUM y casting
START TRANSACTION;

INSERT INTO ingresos (
  id, device_id, estado, motivo, fecha_ingreso, fecha_servicio, ubicacion_id,
  disposicion, informe_preliminar, accesorios, remito_ingreso, recibido_por,
  comentarios, presupuesto_estado, asignado_a, etiqueta_qr,
  propietario_nombre, propietario_contacto, propietario_doc,
  descripcion_problema, trabajos_realizados, resolucion
)
SELECT
  CAST(s.id AS UNSIGNED)                                           AS id,
  CASE WHEN s.device_id REGEXP '^[0-9]+$' THEN CAST(s.device_id AS UNSIGNED) ELSE NULL END AS device_id,
  CASE LOWER(s.estado)
    WHEN 'ingreso'       THEN 'ingresado'
    WHEN 'listo_retiro'  THEN 'liberado'
    ELSE s.estado
  END                                                              AS estado,
  s.motivo                                                        AS motivo,
  CASE WHEN s.fecha_ingreso IS NULL OR s.fecha_ingreso = '' THEN NULL
       ELSE STR_TO_DATE(LEFT(s.fecha_ingreso, 19), '%Y-%m-%d %H:%i:%s') END AS fecha_ingreso,
  CASE WHEN s.fecha_servicio IS NULL OR s.fecha_servicio = '' THEN NULL
       ELSE STR_TO_DATE(LEFT(s.fecha_servicio, 19), '%Y-%m-%d %H:%i:%s') END AS fecha_servicio,
  CASE WHEN s.ubicacion_id REGEXP '^[0-9]+$' THEN CAST(s.ubicacion_id AS UNSIGNED) ELSE NULL END AS ubicacion_id,
  s.disposicion                                                   AS disposicion,
  s.informe_preliminar,
  s.accesorios,
  s.remito_ingreso,
  CASE WHEN s.recibido_por REGEXP '^[0-9]+$' THEN CAST(s.recibido_por AS UNSIGNED) ELSE NULL END AS recibido_por,
  s.comentarios,
  CASE LOWER(s.presupuesto_estado)
    WHEN 'emitido' THEN 'presupuestado'
    ELSE s.presupuesto_estado
  END                                                              AS presupuesto_estado,
  CASE WHEN s.asignado_a REGEXP '^[0-9]+$' THEN CAST(s.asignado_a AS UNSIGNED) ELSE NULL END AS asignado_a,
  NULLIF(s.etiqueta_qr, '')                                        AS etiqueta_qr,
  s.propietario_nombre,
  s.propietario_contacto,
  s.propietario_doc,
  s.descripcion_problema,
  s.trabajos_realizados,
  CASE LOWER(s.resolucion)
    WHEN 'reparado' THEN 'reparado'
    WHEN 'no_reparado' THEN 'no_reparado'
    WHEN 'no_se_encontro_falla' THEN 'no_se_encontro_falla'
    WHEN 'presupuesto_rechazado' THEN 'presupuesto_rechazado'
    ELSE NULL
  END
FROM stg_ingresos s
WHERE s.id REGEXP '^[0-9]+$' AND s.device_id REGEXP '^[0-9]+$'
ON DUPLICATE KEY UPDATE
  device_id=VALUES(device_id), estado=VALUES(estado), motivo=VALUES(motivo),
  fecha_ingreso=VALUES(fecha_ingreso), fecha_servicio=VALUES(fecha_servicio),
  ubicacion_id=VALUES(ubicacion_id), disposicion=VALUES(disposicion),
  informe_preliminar=VALUES(informe_preliminar), accesorios=VALUES(accesorios),
  remito_ingreso=VALUES(remito_ingreso), recibido_por=VALUES(recibido_por),
  comentarios=VALUES(comentarios), presupuesto_estado=VALUES(presupuesto_estado),
  asignado_a=VALUES(asignado_a), etiqueta_qr=VALUES(etiqueta_qr),
  propietario_nombre=VALUES(propietario_nombre), propietario_contacto=VALUES(propietario_contacto),
  propietario_doc=VALUES(propietario_doc), descripcion_problema=VALUES(descripcion_problema),
  trabajos_realizados=VALUES(trabajos_realizados), resolucion=VALUES(resolucion);

COMMIT;
