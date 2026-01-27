# Metricas - guia de lectura

## Objetivo
Esta guia explica que muestra cada vista de metricas (tecnicos y clientes) y para que sirve cada indicador.

## Filtros y controles
- Rango de fechas: desde/hasta define el periodo de analisis.
- Rangos rapidos: 7, 30, 90 dias y YTD (desde inicio del anio).
- Filtros: tecnico, marca y tipo de equipo.
- SLA: opcion para excluir derivados del calculo de SLA.
- Presets: guardar y reutilizar combinaciones de filtros.
- Exportaciones: CSV/Excel para trabajo externo.

## Vista Tecnicos
### Resumen
- MTTR promedio: dias desde iniciar reparacion hasta estado reparado. Menor es mejor.
- SLA diagnostico < 24h: porcentaje de diagnosticos dentro de 24h habiles.
- Aprobacion presupuestos: aprobados / emitidos en el periodo.
- Entregados (periodo): total de equipos con fecha_entrega en el rango.
- Tiempo emitir presupuesto: horas promedio desde diagnostico a emision.
- Tiempo aprobar presupuesto: horas promedio desde emision a aprobacion.
- WIP total: suma de equipos en curso por tecnico.
- Derivados externos (WIP): equipos en estado derivado/en_servicio.
- Derivados / Devueltos (periodo): volumen de derivaciones en el rango.
- Derivacion a devuelto / Devuelto a entregado: tiempos promedio en dias.

### WIP aging
Distribucion de antiguedad del WIP en rangos (0-2, 3-5, 6-10, 11-15, 16+ dias). Ayuda a detectar colas y cuellos de botella.

### Tablas
- Cerrados por tecnico (7 y 30 dias): ranking de productividad reciente.
- WIP por tecnico: carga operativa actual.
- Facturacion aprobada, utilidad MO, repuestos: impacto economico por tecnico.

### Tendencias y graficos
- Entregados por mes: volumen mensual (click para ir al historico de entregas).
- MTTR y TAT: tiempos medios mensuales. TAT = ingreso -> entrega.
- MTTR percentiles: dispersion del tiempo de reparacion (P25/P50/P75/P90/P95).
- Tiempos de presupuesto: emitir y aprobar por mes.
- Mini-sparks: lectura rapida del ultimo valor de cada serie.

### Calibracion (percentiles)
Percentiles de tiempos clave (diagnostico, emision, aprobacion, entrega). Sirve para fijar objetivos realistas y detectar colas largas.

## Vista Clientes
### Resumen
- Entregados: volumen total del periodo (fecha_entrega).
- Facturacion: total cobrado en el periodo.
- Mano de obra y repuestos: composicion del total.
- Clientes activos: cantidad de clientes con actividad.
- Top 5: porcentaje de facturacion concentrada en los principales clientes.

### Top clientes
Rankings por entregados y por facturacion (top 8). Ayuda a priorizar cuentas y dimensionar impacto.

### Tendencias
Lineas de entregados para los top 3 clientes del periodo. Muestra estabilidad y estacionalidad.

### Ranking por facturacion
Tabla con entregados, facturacion, mano de obra, repuestos y porcentaje de participacion.

## Notas de interpretacion
- Los valores cambian con filtros aplicados.
- Si el periodo incluye meses incompletos, las series pueden mostrar picos o bajas.
- Las tablas se ordenan por valor para facilitar comparacion.
- Entregados se calcula por fecha_entrega, no por eventos.

## Exportaciones
- CSV y Excel para analisis externo.
- En tecnicos: series mensuales/anuales y detalle por tecnico/marca/tipo.
