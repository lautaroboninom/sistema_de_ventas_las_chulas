from django.db import connection
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import _fetchall_dicts, _set_audit_user, exec_void, exec_returning, q, require_roles


class CatalogoAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = q("SELECT id, nombre FROM catalogo_accesorios WHERE activo ORDER BY nombre")
        return Response(rows)


class IngresoAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        rows = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
              WHERE ia.ingreso_id=%s
              ORDER BY ia.id
            """,
            [ingreso_id]
        )
        return Response(rows)

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        d = request.data or {}
        # Asumimos catálogo disponible (PostgreSQL-only)
        try:
            acc_id = int(d.get("accesorio_id"))
        except (TypeError, ValueError):
            return Response({"detail": "accesorio_id requerido"}, status=400)
        acc = q("SELECT id FROM catalogo_accesorios WHERE id=%s AND activo", [acc_id], one=True)
        if not acc:
            return Response({"detail": "accesorio inválido"}, status=400)
        ref = (d.get("referencia") or "").strip() or None
        desc = (d.get("descripcion") or "").strip() or None
        _set_audit_user(request)
        new_id = exec_returning(
            """
            INSERT INTO ingreso_accesorios(ingreso_id, accesorio_id, referencia, descripcion)
            VALUES (%s,%s,%s,%s)
            RETURNING id
            """,
            [ingreso_id, acc_id, ref, desc]
        )
        row = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
              WHERE ia.id=%s
            """,
            [new_id], one=True
        )
        return Response(row, status=201)


class IngresoAccesorioDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, ingreso_id: int, item_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        _set_audit_user(request)
        exec_void(
            "DELETE FROM ingreso_accesorios WHERE ingreso_id=%s AND id=%s",
            [ingreso_id, item_id]
        )
        return Response({"ok": True})


class BuscarAccesorioPorReferenciaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        like = "%" + (request.GET.get("ref") or "").strip() + "%"
        if not like or like == "%%":
            return Response([])
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                  t.id,
                  t.estado AS estado,
                  t.presupuesto_estado,
                  t.motivo,
                  c.razon_social,
                  b.nombre AS marca,
                  m.nombre AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  d.numero_serie,
                  t.fecha_ingreso,
                  ia.referencia,
                  COALESCE(ca.nombre,'') AS accesorio_nombre
                FROM ingreso_accesorios ia
                JOIN ingresos t ON t.id = ia.ingreso_id
                JOIN devices  d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
                WHERE (LOWER(ia.referencia) LIKE LOWER(%s))
                ORDER BY t.fecha_ingreso DESC, t.id DESC;
            """,
                [like])
            rows = _fetchall_dicts(cur)
        from ..serializers import IngresoListItemSerializer
        return Response(IngresoListItemSerializer(rows, many=True).data)


class IngresoAlquilerAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        # Ver: todos los usuarios autenticados
        rows = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_alquiler_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
              WHERE ia.ingreso_id=%s
              ORDER BY ia.id
            """,
            [ingreso_id]
        )
        return Response(rows)

    def post(self, request, ingreso_id: int):
        # Modificar: solo admin/jefe/jefe_veedor
        require_roles(request, ["jefe","admin","jefe_veedor"])
        d = request.data or {}
        try:
            acc_id = int(d.get("accesorio_id"))
        except (TypeError, ValueError):
            return Response({"detail": "accesorio_id requerido"}, status=400)
        acc = q("SELECT id FROM catalogo_accesorios WHERE id=%s AND activo", [acc_id], one=True)
        if not acc:
            return Response({"detail": "accesorio inválido"}, status=400)
        ref = (d.get("referencia") or "").strip() or None
        desc = (d.get("descripcion") or "").strip() or None
        _set_audit_user(request)
        new_id = exec_returning(
            """
            INSERT INTO ingreso_alquiler_accesorios(ingreso_id, accesorio_id, referencia, descripcion)
            VALUES (%s,%s,%s,%s)
            RETURNING id
            """,
            [ingreso_id, acc_id, ref, desc]
        )
        row = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_alquiler_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
              WHERE ia.id=%s
            """,
            [new_id], one=True
        )
        return Response(row, status=201)


class IngresoAlquilerAccesorioDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, ingreso_id: int, item_id: int):
        # Modificar: solo admin/jefe/jefe_veedor
        require_roles(request, ["jefe","admin","jefe_veedor"])
        _set_audit_user(request)
        exec_void(
            "DELETE FROM ingreso_alquiler_accesorios WHERE ingreso_id=%s AND id=%s",
            [ingreso_id, item_id]
        )
        return Response({"ok": True})


__all__ = [
    'CatalogoAccesoriosView',
    'IngresoAccesoriosView',
    'IngresoAccesorioDetailView',
    'BuscarAccesorioPorReferenciaView',
    'IngresoAlquilerAccesoriosView',
    'IngresoAlquilerAccesorioDetailView',
]
