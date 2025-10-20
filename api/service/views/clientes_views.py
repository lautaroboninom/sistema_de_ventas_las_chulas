from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import exec_void, q, require_roles


class CustomersListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(q("SELECT id, razon_social FROM customers ORDER BY razon_social;"))


class ClientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "recepcion"])
        return Response(q("SELECT * FROM customers ORDER BY razon_social"))

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        if not (d.get("razon_social") and d.get("cod_empresa")):
            raise ValidationError("razon_social y cod_empresa son requeridos")
        exec_void(
            """INSERT INTO customers(razon_social, cod_empresa, telefono, telefono_2, email)
             VALUES (%(rs)s, %(ce)s, %(tel)s, %(tel2)s, %(email)s)""",
            {"rs": d["razon_social"], "ce": d["cod_empresa"], "tel": d.get("telefono"), "tel2": d.get("telefono_2"), "email": d.get("email")},
        )
        return Response({"ok": True})


class ClienteDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, cid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        rs = (d.get("razon_social") or "").strip()
        ce = (d.get("cod_empresa") or "").strip()
        if not (rs and ce):
            raise ValidationError("razon_social y cod_empresa son requeridos")
        try:
            exec_void(
                """
                UPDATE customers
                   SET razon_social = %(rs)s,
                       cod_empresa  = %(ce)s,
                       telefono     = %(tel)s,
                       telefono_2   = %(tel2)s,
                       email        = %(email)s
                 WHERE id = %(id)s
                """,
                {
                    "id": cid,
                    "rs": rs,
                    "ce": ce,
                    "tel": d.get("telefono"),
                    "tel2": d.get("telefono_2"),
                    "email": d.get("email"),
                },
            )
            return Response({"ok": True})
        except Exception as e:
            raise ValidationError(str(e) or "No se pudo actualizar el cliente")

    def delete(self, request, cid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        refs = q(
            """
            SELECT
              (SELECT COUNT(*) FROM devices d WHERE d.customer_id = %s) AS cnt_devices,
              (SELECT COUNT(*)
                 FROM ingresos t
                 JOIN devices d ON d.id = t.device_id
                WHERE d.customer_id = %s) AS cnt_ingresos
            """,
            [cid, cid], one=True
        ) or {"cnt_devices": 0, "cnt_ingresos": 0}
        if refs["cnt_devices"] or refs["cnt_ingresos"]:
            return Response(
                {"detail": f"No se puede eliminar: el cliente tiene {refs['cnt_devices']} equipos y {refs['cnt_ingresos']} ingresos asociados."},
                status=409
            )
        try:
            exec_void("DELETE FROM customers WHERE id = %(id)s", {"id": cid})
            return Response({"ok": True})
        except Exception:
            return Response({"detail": "No se pudo eliminar por restricciones de integridad."}, status=409)


__all__ = [
    'CustomersListView',
    'ClientesView',
    'ClienteDeleteView',
]
