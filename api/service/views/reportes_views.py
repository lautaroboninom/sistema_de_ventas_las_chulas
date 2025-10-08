from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import _set_audit_user, exec_void, q, require_roles
from ..pdf import render_remito_salida_pdf


class RemitoSalidaPdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "recepcion","jefe_veedor"])
        _set_audit_user(request)

        cur_row = q("SELECT resolucion, estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not cur_row:
            return Response(status=404)
        if not cur_row["resolucion"] and cur_row["estado"] != 'liberado':
            return Response({"detail": "No se puede liberar sin resolución"}, status=409)

        exec_void(
            """
          UPDATE ingresos
             SET estado = 'liberado'
           WHERE id=%s AND estado <> 'entregado'
        """,
            [ingreso_id],
        )

        pdf_bytes, fname = render_remito_salida_pdf(ingreso_id, printed_by=getattr(request.user, "nombre", ""))
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp


__all__ = ['RemitoSalidaPdfView']
