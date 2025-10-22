import datetime as dt
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import (
    WORKDAY_END_HOUR,
    WORKDAY_START_HOUR,
    WORKDAYS,
    _holidays_between,
    _set_audit_user,
    business_minutes_between,
    exec_void,
    q,
    require_roles,
)


def _parse_range_params(request):
    tz = timezone.get_current_timezone()
    now = timezone.now()
    from_s = request.GET.get("from") or request.GET.get("desde")
    to_s = request.GET.get("to") or request.GET.get("hasta")
    if from_s:
        try:
            d = parse_date(from_s)
            since = timezone.make_aware(dt.datetime.combine(d, dt.time.min), tz)
        except Exception:
            since = now - dt.timedelta(days=30)
    else:
        since = now - dt.timedelta(days=30)
    if to_s:
        try:
            d = parse_date(to_s)
            until = timezone.make_aware(dt.datetime.combine(d, dt.time.max), tz)
        except Exception:
            until = now
    else:
        until = now
    return since, until


def _sql_ym(expr: str) -> str:
    return f"to_char({expr}, 'YYYY-MM')"


def _sql_mins(a_expr: str, b_expr: str) -> str:
    # En PostgreSQL restar dos DATE devuelve integer (días), lo que rompe EXTRACT(EPOCH ...).
    # Casteamos ambos operandos a timestamp para obtener un intervalo y medir en minutos.
    return f"EXTRACT(EPOCH FROM ({b_expr}::timestamp - {a_expr}::timestamp)) / 60.0"


def _sql_now_minus_days(days: int) -> str:
    return f"NOW() - INTERVAL '{int(days)} day'"


def _filters_join_where(req):
    joins = []
    wh = []
    params = []
    t_id = req.GET.get("tecnico_id")
    m_id = req.GET.get("marca_id")
    tipo = (req.GET.get("tipo_equipo") or "").strip()
    if t_id:
        try:
            params.append(int(t_id))
            wh.append(" i.asignado_a = %s ")
        except Exception:
            pass
    if m_id or tipo:
        joins.append(" JOIN devices d ON d.id=i.device_id ")
        joins.append(" LEFT JOIN models m ON m.id=d.model_id ")
    if m_id:
        try:
            params.append(int(m_id))
            wh.append(" d.marca_id = %s ")
        except Exception:
            pass
    if tipo:
        params.append(tipo)
        wh.append(" UPPER(TRIM(m.tipo_equipo)) = UPPER(TRIM(%s)) ")
    join_sql = "".join(joins)
    where_sql = (" AND " + " AND ".join(wh)) if wh else ""
    return join_sql, where_sql, params


def _pctiles(values, percent_list=(50, 75, 90, 95)):
    arr = sorted([float(v) for v in values if v is not None])
    n = len(arr)
    out = {f"p{p}": None for p in percent_list}
    if n == 0:
        return out | {"avg": None, "count": 0}
    def pct(p):
        if n == 1:
            return arr[0]
        k = (p/100.0) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            return arr[f]
        d0 = arr[f] * (c - k)
        d1 = arr[c] * (k - f)
        return d0 + d1
    out.update({f"p{p}": pct(p) for p in percent_list})
    out["avg"] = sum(arr) / n
    out["count"] = n
    return out


class MetricasConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        work_start = int(request.GET.get("work_start") or WORKDAY_START_HOUR)
        work_end = int(request.GET.get("work_end") or WORKDAY_END_HOUR)
        workdays = list(WORKDAYS)
        cfg = {
            "holidays_country": "AR",
            "workday_start_hour": work_start,
            "workday_end_hour": work_end,
            "workdays": workdays,
            "sla_excluir_derivados_default": True,
            "source": "env+nager",
        }
        return Response(cfg)


class FeriadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        try:
            rows = q("SELECT fecha, nombre FROM feriados ORDER BY fecha ASC") or []
        except Exception:
            rows = []
        return Response(rows)
    def post(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        d = request.data or {}
        fecha = (d.get("fecha") or "").strip()
        nombre = (d.get("nombre") or "").strip() or "Feriado"
        if not fecha:
            return Response({"detail": "fecha requerida (YYYY-MM-DD)"}, status=400)
        try:
            if cache is not None:  # silence linter
                pass
            if hasattr(connection, 'vendor') and connection.vendor == 'postgresql':
                q("INSERT INTO feriados (fecha, nombre) VALUES (%s, %s) ON CONFLICT (fecha) DO UPDATE SET nombre=EXCLUDED.nombre", [fecha, nombre])
            else:
                q("INSERT INTO feriados (fecha, nombre) VALUES (%s, %s) ON DUPLICATE KEY UPDATE nombre=VALUES(nombre)", [fecha, nombre])
            cache.clear()
            return Response({"ok": True})
        except Exception as ex:
            return Response({"detail": str(ex)}, status=400)
    def delete(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        fecha = (request.GET.get("fecha") or "").strip()
        if not fecha:
            return Response({"detail": "fecha requerida (YYYY-MM-DD)"}, status=400)
        try:
            q("DELETE FROM feriados WHERE fecha=%s", [fecha])
            cache.clear()
        except Exception:
            pass
        return Response({"ok": True})


class MetricasSeriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        since, until = _parse_range_params(request)
        join_dm, where_i, where_params = _filters_join_where(request)

        # buckets mensuales
        months = []
        y, m = since.year, since.month
        while y < until.year or (y == until.year and m <= until.month):
            months.append(f"{y:04d}-{m:02d}")
            if m == 12:
                y += 1; m = 1
            else:
                m += 1
        data = {k: {
            "entregados": 0,
            "_mttr_sum_min": 0,
            "_mttr_n": 0,
            "_mttr_vals": [],
            "sla_diag_total": 0,
            "sla_diag_dentro": 0,
            "aprob_emitidos": 0,
            "aprob_aprobados": 0,
            "t_emitir_min_sum": 0,
            "t_emitir_n": 0,
            "t_emitir_hours_vals": [],
            "t_aprobar_min_sum": 0,
            "t_aprobar_n": 0,
            "t_aprobar_hours_vals": [],
            "tat_days_vals": [],
        } for k in months}

        # Entregados por mes
        ym_e = _sql_ym('e.ts')
        entreg_sql = (
            f"SELECT {ym_e} AS ym, COUNT(*) AS c\n"
            "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
            f"{where_i}\n"
            "GROUP BY ym"
        )
        entreg_rows = q(entreg_sql, [since, until, *where_params]) or []
        for r in entreg_rows:
            k = r.get("ym")
            if k in data:
                data[k]["entregados"] = r.get("c", 0)

        # MTTR por mes (por reparado)
        ym_rep = _sql_ym('d.reparado_ts')
        rep_rows = q((
            f"SELECT {ym_rep} AS ym, r.reparar_ts, d.reparado_ts\n"
            "FROM (SELECT ingreso_id, MIN(ts) AS reparar_ts FROM ingreso_events WHERE a_estado='reparar' GROUP BY ingreso_id) r\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS reparado_ts FROM ingreso_events WHERE a_estado='reparado' GROUP BY ingreso_id) d\n"
            "  ON d.ingreso_id=r.ingreso_id\n"
            "JOIN ingresos i ON i.id=d.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE d.reparado_ts BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        for r in rep_rows:
            k = r.get("ym")
            if k in data and r.get("reparar_ts") and r.get("reparado_ts"):
                mins = max(0, int((r["reparado_ts"] - r["reparar_ts"]).total_seconds() // 60))
                data[k]["_mttr_sum_min"] += mins
                data[k]["_mttr_n"] += 1
                try:
                    data[k]["_mttr_vals"].append(mins / 60.0 / 24.0)
                except Exception:
                    pass

        # SLA diag por mes
        holi = _holidays_between((since - dt.timedelta(days=7)).date(), (until + dt.timedelta(days=7)).date())
        ym_ing = _sql_ym('i.fecha_ingreso')
        sla_rows = q((
            f"SELECT {ym_ing} AS ym, i.fecha_ingreso, COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "LEFT JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' GROUP BY ingreso_id) di\n"
            "  ON di.ingreso_id=i.id\n"
            "WHERE i.fecha_ingreso BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        for r in sla_rows:
            k = r.get("ym")
            if k not in data:
                continue
            fi = r.get("fecha_ingreso"); dtg = r.get("diag_ts")
            if fi and dtg:
                data[k]["sla_diag_total"] += 1
                if business_minutes_between(fi, dtg, holidays=holi) <= 24 * 60:
                    data[k]["sla_diag_dentro"] += 1

        # Presupuestos por mes (emitidos/aprobados y tiempos)
        ym_emit = _sql_ym('q.fecha_emitido')
        emit_rows = q((
            f"SELECT {ym_emit} AS ym, q.fecha_emitido, q.fecha_aprobado, q.ingreso_id\n"
            "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        for r in emit_rows:
            k = r.get("ym")
            if k not in data:
                continue
            data[k]["aprob_emitidos"] += 1
            fei = r.get("fecha_emitido"); fa = r.get("fecha_aprobado")
            # diag -> emitir: buscar diag_ts
            di = q("SELECT COALESCE(MIN(ts), NULL) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' AND ingreso_id=%s", [r.get("ingreso_id")], one=True)
            diag_ts = di and di.get("ts")
            if diag_ts and fei:
                data[k]["t_emitir_min_sum"] += int(max(0, (fei - diag_ts).total_seconds() // 60))
                data[k]["t_emitir_n"] += 1
                try:
                    data[k]["t_emitir_hours_vals"].append(max(0.0, (fei - diag_ts).total_seconds() / 3600.0))
                except Exception:
                    pass
            if fa:
                data[k]["aprob_aprobados"] += 1
                data[k]["t_aprobar_min_sum"] += int(max(0, (fa - fei).total_seconds() // 60))
                data[k]["t_aprobar_n"] += 1

        # Distribución mensual: emitir->aprobar (horas)
        mins_emit_aprob = _sql_mins('q.fecha_emitido','q.fecha_aprobado')
        aprobar_rows = q((
            f"SELECT {ym_emit} AS ym, {mins_emit_aprob} AS mins\n"
            "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s AND q.fecha_aprobado IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        for r in aprobar_rows:
            k = r.get("ym")
            if k in data:
                data[k]["t_aprobar_hours_vals"].append(max(0.0, (r.get("mins") or 0) / 60.0))

        # TAT (Ingreso -> Entregado) por mes (días calendario)
        tat_rows = q((
            f"SELECT {ym_e} AS ym, i.fecha_ingreso, e.ts AS entregado_ts\n"
            "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        for r in tat_rows:
            k = r.get("ym")
            if k not in data:
                continue
            fi = r.get("fecha_ingreso"); et = r.get("entregado_ts")
            if fi and et and et >= fi:
                data[k]["tat_days_vals"].append((et - fi).total_seconds() / 86400.0)

        series = []
        for k in months:
            series.append({
                "period": k,
                "entregados": data[k]["entregados"],
                "mttr_dias": (data[k]["_mttr_sum_min"] / 60 / 24 / data[k]["_mttr_n"]) if data[k]["_mttr_n"] else None,
                "mttr_percentiles": _pctiles(data[k]["_mttr_vals"], (25,50,75,90,95)) if data[k]["_mttr_vals"] else {"p25": None, "p50": None, "p75": None, "p90": None, "p95": None, "avg": None, "count": 0},
                "sla_diag_24h": {
                    "total": data[k]["sla_diag_total"],
                    "dentro": data[k]["sla_diag_dentro"],
                    "cumplimiento": (data[k]["sla_diag_dentro"] / data[k]["sla_diag_total"]) if data[k]["sla_diag_total"] else 0.0,
                },
                "aprob_presupuestos": {
                    "emitidos": data[k]["aprob_emitidos"],
                    "aprobados": data[k]["aprob_aprobados"],
                    "tasa": (data[k]["aprob_aprobados"] / data[k]["aprob_emitidos"]) if data[k]["aprob_emitidos"] else 0.0,
                    "t_emitir_horas": (data[k]["t_emitir_min_sum"] / 60 / data[k]["t_emitir_n"]) if data[k]["t_emitir_n"] else None,
                    "t_aprobar_horas": (data[k]["t_aprobar_min_sum"] / 60 / data[k]["t_aprobar_n"]) if data[k]["t_aprobar_n"] else None,
                    "t_emitir_percentiles": _pctiles(data[k]["t_emitir_hours_vals"], (25,50,75,90,95)) if data[k]["t_emitir_hours_vals"] else {"p25": None, "p50": None, "p75": None, "p90": None, "p95": None, "avg": None, "count": 0},
                    "t_aprobar_percentiles": _pctiles(data[k]["t_aprobar_hours_vals"], (25,50,75,90,95)) if data[k]["t_aprobar_hours_vals"] else {"p25": None, "p50": None, "p75": None, "p90": None, "p95": None, "avg": None, "count": 0},
                },
                "tat_dias": (sum(data[k]["tat_days_vals"]) / len(data[k]["tat_days_vals"])) if data[k]["tat_days_vals"] else None,
                "tat_percentiles": _pctiles(data[k]["tat_days_vals"], (25,50,75,90,95)) if data[k]["tat_days_vals"] else {"p25": None, "p50": None, "p75": None, "p90": None, "p95": None, "avg": None, "count": 0},
            })

        # Yearly agregados
        yearly = {}
        for it in series:
            y = it["period"].split("-")[0]
            yy = yearly.setdefault(y, {
                "period": y,
                "entregados": 0,
                "mttr_sum": 0.0,
                "mttr_n": 0,
                "sla_total": 0,
                "sla_dentro": 0,
                "emitidos": 0,
                "aprobados": 0,
                "t_emitir_sum": 0.0,
                "t_emitir_n": 0,
                "t_aprobar_sum": 0.0,
                "t_aprobar_n": 0,
            })
            yy["entregados"] += (it.get("entregados") or 0)
            if it.get("mttr_dias") is not None:
                yy["mttr_sum"] += it["mttr_dias"]
                yy["mttr_n"] += 1
            sla = it.get("sla_diag_24h", {})
            yy["sla_total"] += sla.get("total", 0)
            yy["sla_dentro"] += sla.get("dentro", 0)
            ap = it.get("aprob_presupuestos", {})
            yy["emitidos"] += ap.get("emitidos", 0)
            yy["aprobados"] += ap.get("aprobados", 0)
            if ap.get("t_emitir_horas") is not None:
                yy["t_emitir_sum"] += ap["t_emitir_horas"]
                yy["t_emitir_n"] += 1
            if ap.get("t_aprobar_horas") is not None:
                yy["t_aprobar_sum"] += ap["t_aprobar_horas"]
                yy["t_aprobar_n"] += 1
        series_year = []
        for y, v in sorted(yearly.items()):
            series_year.append({
                "period": y,
                "entregados": v["entregados"],
                "mttr_dias": (v["mttr_sum"] / v["mttr_n"]) if v["mttr_n"] else None,
                "sla_diag_24h": {
                    "total": v["sla_total"],
                    "dentro": v["sla_dentro"],
                    "cumplimiento": (v["sla_dentro"] / v["sla_total"]) if v["sla_total"] else 0.0,
                },
                "aprob_presupuestos": {
                    "emitidos": v["emitidos"],
                    "aprobados": v["aprobados"],
                    "tasa": (v["aprobados"] / v["emitidos"]) if v["emitidos"] else 0.0,
                    "t_emitir_horas": (v["t_emitir_sum"] / v["t_emitir_n"]) if v["t_emitir_n"] else None,
                    "t_aprobar_horas": (v["t_aprobar_sum"] / v["t_aprobar_n"]) if v["t_aprobar_n"] else None,
                },
            })

        resp = {"range": {"from": since, "to": until}, "monthly": series, "yearly": series_year}

        # Agrupaciones para export (técnico, marca, tipo, cliente)
        group = (request.GET.get("group") or "").strip().lower()
        if group == "tecnico":
            ym_e = _sql_ym('e.ts'); ym_qap = _sql_ym('q.fecha_aprobado')
            bytec = q((
                f"SELECT {ym_e} AS period, i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, COUNT(*) AS entregados\n"
                "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
                f"{join_dm}\n"
                "LEFT JOIN users u ON u.id=i.asignado_a\n"
                "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, i.asignado_a, tecnico_nombre\n"
                "ORDER BY period ASC, entregados DESC\n"
            ), [since, until, *where_params]) or []
            fac_tec = q((
                f"SELECT {ym_qap} AS period, i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(q.total),2) AS facturacion\n"
                "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
                f"{join_dm}\n"
                "LEFT JOIN users u ON u.id=i.asignado_a\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, i.asignado_a, tecnico_nombre\n"
                "ORDER BY period ASC, facturacion DESC\n"
            ), [since, until, *where_params]) or []
            mo_tec = q((
                f"SELECT {ym_qap} AS period, i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_mo\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                f"{join_dm}\n"
                "LEFT JOIN users u ON u.id=i.asignado_a\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='mano_obra'"
                f"{where_i}\n"
                "GROUP BY period, i.asignado_a, tecnico_nombre\n"
                "ORDER BY period ASC, monto_mo DESC\n"
            ), [since, until, *where_params]) or []
            rep_tec = q((
                f"SELECT {ym_qap} AS period, i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_repuestos\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                f"{join_dm}\n"
                "LEFT JOIN users u ON u.id=i.asignado_a\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='repuesto'"
                f"{where_i}\n"
                "GROUP BY period, i.asignado_a, tecnico_nombre\n"
                "ORDER BY period ASC, monto_repuestos DESC\n"
            ), [since, until, *where_params]) or []
            resp.update({
                "by_tecnico_monthly": bytec,
                "facturacion_tecnico_monthly": fac_tec,
                "mo_tecnico_monthly": mo_tec,
                "repuestos_tecnico_monthly": rep_tec,
            })
        elif group == "marca":
            ym_e = _sql_ym('e.ts'); ym_qap = _sql_ym('q.fecha_aprobado')
            bym = q((
                f"SELECT {ym_e} AS period, d.marca_id AS marca_id, COALESCE(b.nombre,'') AS marca_nombre, COUNT(*) AS entregados\n"
                "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN marcas b ON b.id=d.marca_id\n"
                f"{join_dm}\n"
                "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, d.marca_id, marca_nombre\n"
                "ORDER BY period ASC, entregados DESC\n"
            ), [since, until, *where_params]) or []
            facm = q((
                f"SELECT {ym_qap} AS period, d.marca_id AS marca_id, COALESCE(b.nombre,'') AS marca_nombre, ROUND(SUM(q.total),2) AS facturacion\n"
                "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN marcas b ON b.id=d.marca_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, d.marca_id, marca_nombre\n"
                "ORDER BY period ASC, facturacion DESC\n"
            ), [since, until, *where_params]) or []
            mom = q((
                f"SELECT {ym_qap} AS period, d.marca_id AS marca_id, COALESCE(b.nombre,'') AS marca_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_mo\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN marcas b ON b.id=d.marca_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='mano_obra'"
                f"{where_i}\n"
                "GROUP BY period, d.marca_id, marca_nombre\n"
                "ORDER BY period ASC, monto_mo DESC\n"
            ), [since, until, *where_params]) or []
            repm = q((
                f"SELECT {ym_qap} AS period, d.marca_id AS marca_id, COALESCE(b.nombre,'') AS marca_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_repuestos\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN marcas b ON b.id=d.marca_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='repuesto'"
                f"{where_i}\n"
                "GROUP BY period, d.marca_id, marca_nombre\n"
                "ORDER BY period ASC, monto_repuestos DESC\n"
            ), [since, until, *where_params]) or []
            resp.update({
                "by_marca_monthly": bym,
                "facturacion_marca_monthly": facm,
                "mo_marca_monthly": mom,
                "repuestos_marca_monthly": repm,
            })
        elif group in ("tipo", "tipo_equipo"):
            ym_e = _sql_ym('e.ts'); ym_qap = _sql_ym('q.fecha_aprobado')
            byt = q((
                f"SELECT {ym_e} AS period, COALESCE(m.tipo_equipo,'') AS tipo_equipo, COUNT(*) AS entregados\n"
                "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN models m ON m.id=d.model_id\n"
                f"{join_dm}\n"
                "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, tipo_equipo\n"
                "ORDER BY period ASC, entregados DESC\n"
            ), [since, until, *where_params]) or []
            fact = q((
                f"SELECT {ym_qap} AS period, COALESCE(m.tipo_equipo,'') AS tipo_equipo, ROUND(SUM(q.total),2) AS facturacion\n"
                "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN models m ON m.id=d.model_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, tipo_equipo\n"
                "ORDER BY period ASC, facturacion DESC\n"
            ), [since, until, *where_params]) or []
            mot = q((
                f"SELECT {ym_qap} AS period, COALESCE(m.tipo_equipo,'') AS tipo_equipo, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_mo\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN models m ON m.id=d.model_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='mano_obra'"
                f"{where_i}\n"
                "GROUP BY period, tipo_equipo\n"
                "ORDER BY period ASC, monto_mo DESC\n"
            ), [since, until, *where_params]) or []
            rept = q((
                f"SELECT {ym_qap} AS period, COALESCE(m.tipo_equipo,'') AS tipo_equipo, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_repuestos\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "LEFT JOIN models m ON m.id=d.model_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='repuesto'"
                f"{where_i}\n"
                "GROUP BY period, tipo_equipo\n"
                "ORDER BY period ASC, monto_repuestos DESC\n"
            ), [since, until, *where_params]) or []
            resp.update({
                "by_tipo_monthly": byt,
                "facturacion_tipo_monthly": fact,
                "mo_tipo_monthly": mot,
                "repuestos_tipo_monthly": rept,
            })
        elif group in ("cliente", "customer"):
            ym_e = _sql_ym('e.ts'); ym_qap = _sql_ym('q.fecha_aprobado')
            byc = q((
                f"SELECT {ym_e} AS period, c.id AS cliente_id, COALESCE(c.razon_social,'') AS cliente_nombre, COUNT(*) AS entregados\n"
                "FROM ingreso_events e JOIN ingresos i ON i.id=e.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "JOIN customers c ON c.id=d.customer_id\n"
                f"{join_dm}\n"
                "WHERE e.a_estado='entregado' AND e.ts BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, c.id, cliente_nombre\n"
                "ORDER BY period ASC, entregados DESC\n"
            ), [since, until, *where_params]) or []
            facc = q((
                f"SELECT {ym_qap} AS period, c.id AS cliente_id, COALESCE(c.razon_social,'') AS cliente_nombre, ROUND(SUM(q.total),2) AS facturacion\n"
                "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "JOIN customers c ON c.id=d.customer_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s"
                f"{where_i}\n"
                "GROUP BY period, c.id, cliente_nombre\n"
                "ORDER BY period ASC, facturacion DESC\n"
            ), [since, until, *where_params]) or []
            moc = q((
                f"SELECT {ym_qap} AS period, c.id AS cliente_id, COALESCE(c.razon_social,'') AS cliente_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_mo\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "JOIN customers c ON c.id=d.customer_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='mano_obra'"
                f"{where_i}\n"
                "GROUP BY period, c.id, cliente_nombre\n"
                "ORDER BY period ASC, monto_mo DESC\n"
            ), [since, until, *where_params]) or []
            repc = q((
                f"SELECT {ym_qap} AS period, c.id AS cliente_id, COALESCE(c.razon_social,'') AS cliente_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS monto_repuestos\n"
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id\n"
                "JOIN ingresos i ON i.id=q.ingreso_id\n"
                "JOIN devices d ON d.id=i.device_id\n"
                "JOIN customers c ON c.id=d.customer_id\n"
                f"{join_dm}\n"
                "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='repuesto'"
                f"{where_i}\n"
                "GROUP BY period, c.id, cliente_nombre\n"
                "ORDER BY period ASC, monto_repuestos DESC\n"
            ), [since, until, *where_params]) or []
            resp.update({
                "by_cliente_monthly": byc,
                "facturacion_cliente_monthly": facc,
                "mo_cliente_monthly": moc,
                "repuestos_cliente_monthly": repc,
            })

        return Response(resp)


class MetricasCalibracionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        since, until = _parse_range_params(request)
        join_dm, where_i, where_params = _filters_join_where(request)

        diag_rows = q((
            "SELECT i.fecha_ingreso, COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "LEFT JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' GROUP BY ingreso_id) di\n"
            "  ON di.ingreso_id=i.id\n"
            "WHERE i.fecha_ingreso BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        holi = _holidays_between((since - dt.timedelta(days=7)).date(), (until + dt.timedelta(days=7)).date())
        diag_bmins = []
        for r in diag_rows:
            fi = r.get("fecha_ingreso"); dtg = r.get("diag_ts")
            if fi and dtg:
                diag_bmins.append(business_minutes_between(fi, dtg, holidays=holi))

        t_emit_rows = q((
            "SELECT COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts, q.fecha_emitido\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "JOIN quotes q ON q.ingreso_id=i.id\n"
            "LEFT JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' GROUP BY ingreso_id) di\n"
            "  ON di.ingreso_id=i.id\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s AND q.fecha_emitido IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        emit_hours = [max(0.0, (row["fecha_emitido"] - row["diag_ts"]).total_seconds() / 3600.0) for row in t_emit_rows if row.get("diag_ts") and row.get("fecha_emitido")]

        mins_emit_aprob = _sql_mins('q.fecha_emitido','q.fecha_aprobado')
        t_aprob_rows = q((
            f"SELECT {mins_emit_aprob} AS mins\n"
            "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s AND q.fecha_aprobado IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        apro_hours = [max(0.0, (r.get("mins") or 0) / 60.0) for r in t_aprob_rows]

        t_rep_rows = q((
            "SELECT q.fecha_aprobado, r.reparado_ts\n"
            "FROM quotes q\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS reparado_ts FROM ingreso_events WHERE a_estado='reparado' GROUP BY ingreso_id) r\n"
            "  ON r.ingreso_id=q.ingreso_id\n"
            "JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_aprobado BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        apr_rep_days = [max(0.0, (row["reparado_ts"] - row["fecha_aprobado"]).total_seconds() / 86400.0) for row in t_rep_rows if row.get("fecha_aprobado") and row.get("reparado_ts") and row.get("reparado_ts") > row.get("fecha_aprobado")]

        rep_ent_rows = q((
            "SELECT r.reparado_ts, e2.ts AS entregado_ts\n"
            "FROM (SELECT ingreso_id, MIN(ts) AS reparado_ts FROM ingreso_events WHERE a_estado='reparado' GROUP BY ingreso_id) r\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='entregado' GROUP BY ingreso_id) e2\n"
            "  ON e2.ingreso_id=r.ingreso_id\n"
            "JOIN ingresos i ON i.id=r.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE e2.ts BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        rep_ent_days = [max(0.0, (row["entregado_ts"] - row["reparado_ts"]).total_seconds() / 86400.0) for row in rep_ent_rows if row.get("reparado_ts") and row.get("entregado_ts") and row.get("entregado_ts") > row.get("reparado_ts")]

        ing_ent_rows = q((
            "SELECT i.fecha_ingreso, e2.ts AS entregado_ts\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='entregado' GROUP BY ingreso_id) e2\n"
            "  ON e2.ingreso_id=i.id\n"
            "WHERE e2.ts BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        ing_ent_days = [max(0.0, (row["entregado_ts"] - row["fecha_ingreso"]).total_seconds() / 86400.0) for row in ing_ent_rows if row.get("fecha_ingreso") and row.get("entregado_ts") and row.get("entregado_ts") > row.get("fecha_ingreso")]

        return Response({
            "range": {"from": since, "to": until},
            "diag_business_minutes": _pctiles(diag_bmins),
            "diag_to_emit_hours": _pctiles(emit_hours),
            "emit_to_approve_hours": _pctiles(apro_hours),
            "approve_to_repair_days": _pctiles(apr_rep_days),
            "repair_to_deliver_days": _pctiles(rep_ent_days),
            "ingreso_to_deliver_days": _pctiles(ing_ent_days),
        })
class MetricasResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe"])  # solo Jefe
        since, until = _parse_range_params(request)
        join_dm, where_i, where_params = _filters_join_where(request)

        # CERRADOS 7/30 días (entregado)
        seven = _sql_now_minus_days(7)
        cerrados_7d = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, COUNT(*) AS cerrados\n"
            "FROM ingreso_events e\n"
            "JOIN ingresos i ON i.id=e.ingreso_id\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            f"WHERE e.a_estado='entregado' AND e.ts >= ({seven})"
            f"{where_i}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY cerrados DESC"
        ), where_params) or []
        thirty = _sql_now_minus_days(30)
        cerrados_30d = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, COUNT(*) AS cerrados\n"
            "FROM ingreso_events e\n"
            "JOIN ingresos i ON i.id=e.ingreso_id\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            f"WHERE e.a_estado='entregado' AND e.ts >= ({thirty})"
            f"{where_i}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY cerrados DESC"
        ), where_params) or []

        # WIP por técnico
        wip = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, COUNT(*) AS wip\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            "WHERE i.estado IN ('ingresado','diagnosticado','presupuestado','reparar','reparado')"
            f"{(' AND ' + where_i[5:]) if where_i else ''}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY wip DESC"
        ), where_params) or []

        # Aging WIP (días hábiles desde ingreso hasta ahora)
        now_ts = timezone.now()
        open_rows = q((
            "SELECT i.id, i.fecha_ingreso\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "WHERE i.estado IN ('ingresado','diagnosticado','presupuestado','reparar','reparado')"
            f"{where_i}\n"
        ), where_params) or []
        holi = _holidays_between((since - dt.timedelta(days=7)).date(), (until + dt.timedelta(days=7)).date())
        buckets = {"0-2": 0, "3-5": 0, "6-10": 0, "11-15": 0, "16+": 0}
        for r in open_rows:
            fi = r.get("fecha_ingreso")
            if not fi:
                continue
            mins = business_minutes_between(fi, now_ts, holidays=holi)
            days = (mins or 0) / (60.0 * 24.0)
            if days <= 2:
                buckets["0-2"] += 1
            elif days <= 5:
                buckets["3-5"] += 1
            elif days <= 10:
                buckets["6-10"] += 1
            elif days <= 15:
                buckets["11-15"] += 1
            else:
                buckets["16+"] += 1

        # MTTR (reparar -> reparado) en rango (por reparado_ts)
        reparado_rows = q((
            "SELECT r.ingreso_id, r.reparar_ts, d.reparado_ts\n"
            "FROM (SELECT ingreso_id, MIN(ts) AS reparar_ts FROM ingreso_events WHERE a_estado='reparar' GROUP BY ingreso_id) r\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS reparado_ts FROM ingreso_events WHERE a_estado='reparado' GROUP BY ingreso_id) d\n"
            "  ON d.ingreso_id = r.ingreso_id\n"
            "JOIN ingresos i ON i.id=d.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE d.reparado_ts BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        mttr_minutes = [max(0, int((row["reparado_ts"] - row["reparar_ts"]).total_seconds() // 60)) for row in reparado_rows if row.get("reparar_ts") and row.get("reparado_ts")]
        mttr_dias = (sum(mttr_minutes) / 60 / 24 / len(mttr_minutes)) if mttr_minutes else None

        # SLA diagnóstico (ingreso -> diag) 24h hábiles, excluyendo derivados por defecto
        rows_der = q((
            "SELECT DISTINCT ed.ingreso_id AS id\n"
            "FROM equipos_derivados ed\n"
            "JOIN ingresos i ON i.id=ed.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE 1=1"
            f"{where_i}\n"
        ), where_params) or []
        derivados_ids = {r.get("id") for r in rows_der}
        ingresos_periodo = q((
            "SELECT i.id, i.fecha_ingreso, COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "LEFT JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' GROUP BY ingreso_id) di\n"
            "  ON di.ingreso_id=i.id\n"
            "WHERE i.fecha_ingreso BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        holi = _holidays_between((since - dt.timedelta(days=7)).date(), (until + dt.timedelta(days=7)).date())
        sla_total = sla_dentro = 0
        for r in ingresos_periodo:
            rid = r.get("id")
            if rid in derivados_ids:
                continue
            fi = r.get("fecha_ingreso"); dtg = r.get("diag_ts")
            if fi and dtg:
                sla_total += 1
                if business_minutes_between(fi, dtg, holidays=holi) <= 24 * 60:
                    sla_dentro += 1
        sla = {"total": sla_total, "dentro": sla_dentro, "cumplimiento": (sla_dentro / sla_total) if sla_total else 0.0}

        # Presupuestos, tiempos y facturación/MO/repuestos por técnico
        presup_emitidos = q((
            "SELECT COUNT(*) AS c FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params], one=True) or {"c": 0}
        presup_aprobados = q((
            "SELECT COUNT(*) AS c FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_aprobado BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params], one=True) or {"c": 0}
        aprob_tasa = (presup_aprobados.get("c", 0) / float(presup_emitidos.get("c", 0))) if presup_emitidos.get("c", 0) else 0.0

        t_emit_rows = q((
            "SELECT COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts, q.fecha_emitido\n"
            "FROM ingresos i\n"
            f"{join_dm}\n"
            "JOIN quotes q ON q.ingreso_id=i.id\n"
            "LEFT JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='diagnosticado' GROUP BY ingreso_id) di\n"
            "  ON di.ingreso_id=i.id\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s AND q.fecha_emitido IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        t_emit_min = [max(0, int((row["fecha_emitido"] - row["diag_ts"]).total_seconds() // 60)) for row in t_emit_rows if row.get("diag_ts") and row.get("fecha_emitido")]
        t_emit_horas = (sum(t_emit_min) / 60 / len(t_emit_min)) if t_emit_min else None

        t_aprob_rows = q((
            f"SELECT {_sql_mins('q.fecha_emitido','q.fecha_aprobado')} AS mins\n"
            "FROM quotes q JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_emitido BETWEEN %s AND %s AND q.fecha_aprobado IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        t_aprob_min = [max(0, r.get("mins") or 0) for r in t_aprob_rows]
        t_aprob_horas = (sum(t_aprob_min) / 60 / len(t_aprob_min)) if t_aprob_min else None

        t_rep_rows = q((
            "SELECT q.fecha_aprobado, r.reparado_ts\n"
            "FROM quotes q\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS reparado_ts FROM ingreso_events WHERE a_estado='reparado' GROUP BY ingreso_id) r\n"
            "  ON r.ingreso_id=q.ingreso_id\n"
            "JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE q.fecha_aprobado BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params]) or []
        reparado_antes_aprob = 0
        t_rep_min = []
        for row in t_rep_rows:
            fa = row.get("fecha_aprobado")
            rr = row.get("reparado_ts")
            if not fa or not rr:
                continue
            if rr <= fa:
                reparado_antes_aprob += 1
            else:
                t_rep_min.append(int((rr - fa).total_seconds() // 60))
        t_rep_dias = (sum(t_rep_min) / 60 / 24 / len(t_rep_min)) if t_rep_min else None

        fact_rows = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(q.total),2) AS facturacion\n"
            "FROM quotes q\n"
            "JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s"
            f"{where_i}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY facturacion DESC\n"
        ), [since, until, *where_params]) or []
        util_mo_rows = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS utilidad_mo\n"
            "FROM quote_items qi\n"
            "JOIN quotes q ON q.id=qi.quote_id\n"
            "JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='mano_obra'"
            f"{where_i}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY utilidad_mo DESC\n"
        ), [since, until, *where_params]) or []
        rep_rows = q((
            "SELECT i.asignado_a AS tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre, ROUND(SUM(qi.qty*qi.precio_u),2) AS ingreso_repuestos\n"
            "FROM quote_items qi\n"
            "JOIN quotes q ON q.id=qi.quote_id\n"
            "JOIN ingresos i ON i.id=q.ingreso_id\n"
            f"{join_dm}\n"
            "LEFT JOIN users u ON u.id=i.asignado_a\n"
            "WHERE q.estado='aprobado' AND q.fecha_aprobado BETWEEN %s AND %s AND qi.tipo='repuesto'"
            f"{where_i}\n"
            "GROUP BY i.asignado_a, tecnico_nombre\n"
            "ORDER BY ingreso_repuestos DESC\n"
        ), [since, until, *where_params]) or []

        # Derivaciones externas
        deriv_wip = q((
            "SELECT COUNT(*) AS c\n"
            "FROM equipos_derivados ed\n"
            "JOIN ingresos i ON i.id=ed.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE ed.estado IN ('derivado','en_servicio')"
            f"{where_i}\n"
        ), where_params, one=True) or {"c": 0}
        deriv_derivados = q((
            "SELECT COUNT(*) AS c\n"
            "FROM equipos_derivados ed\n"
            "JOIN ingresos i ON i.id=ed.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE ed.fecha_deriv BETWEEN %s AND %s"
            f"{where_i}\n"
        ), [since, until, *where_params], one=True) or {"c": 0}
        avg_dev_min = _sql_mins('ed.fecha_deriv','ed.fecha_entrega')
        deriv_devueltos = q((
            f"SELECT COUNT(*) AS c, AVG({avg_dev_min}) AS avg_min\n"
            "FROM equipos_derivados ed\n"
            "JOIN ingresos i ON i.id=ed.ingreso_id\n"
            f"{join_dm}\n"
            "WHERE ed.fecha_entrega BETWEEN %s AND %s AND ed.fecha_entrega IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params], one=True) or {"c": 0, "avg_min": None}
        deriv_t_deriv_a_dev_dias = ((deriv_devueltos.get("avg_min") or 0) / 60 / 24) if deriv_devueltos.get("avg_min") is not None else None
        avg_ent_min = _sql_mins('ed.fecha_entrega','ev.ts')
        deriv_dev_a_ent = q((
            f"SELECT AVG({avg_ent_min}) AS avg_min\n"
            "FROM equipos_derivados ed\n"
            "JOIN ingresos i ON i.id=ed.ingreso_id\n"
            f"{join_dm}\n"
            "JOIN (SELECT ingreso_id, MIN(ts) AS ts FROM ingreso_events WHERE a_estado='entregado' GROUP BY ingreso_id) ev\n"
            "  ON ev.ingreso_id=ed.ingreso_id\n"
            "WHERE ed.fecha_entrega BETWEEN %s AND %s AND ed.fecha_entrega IS NOT NULL"
            f"{where_i}\n"
        ), [since, until, *where_params], one=True) or {"avg_min": None}
        deriv_t_dev_a_ent_dias = ((deriv_dev_a_ent.get("avg_min") or 0) / 60 / 24) if deriv_dev_a_ent.get("avg_min") is not None else None

        return Response({
            "range": {"from": since, "to": until},
            "mttr_dias": mttr_dias,
            "sla_diag_24h": sla,
            "aprob_presupuestos": {
                "emitidos": presup_emitidos.get("c", 0),
                "aprobados": presup_aprobados.get("c", 0),
                "tasa": aprob_tasa,
                "t_emitir_horas": t_emit_horas,
                "t_aprobar_horas": t_aprob_horas,
            },
            "t_reparar_desde_aprob_dias": t_rep_dias,
            "reparado_antes_de_aprobar": reparado_antes_aprob,
            "cerrados_por_tecnico_7d": cerrados_7d,
            "cerrados_por_tecnico_30d": cerrados_30d,
            "wip_por_tecnico": wip,
            "wip_aging_buckets": buckets,
            "facturacion_por_tecnico": fact_rows,
            "utilidad_mo_por_tecnico": util_mo_rows,
            "repuestos_por_tecnico": rep_rows,
            "derivaciones": {
                "wip_externo": deriv_wip.get("c", 0),
                "derivados_periodo": deriv_derivados.get("c", 0),
                "devueltos_periodo": deriv_devueltos.get("c", 0),
                "t_deriv_a_devuelto_dias": deriv_t_deriv_a_dev_dias,
                "t_devuelto_a_entregado_dias": deriv_t_dev_a_ent_dias,
            },
        })
