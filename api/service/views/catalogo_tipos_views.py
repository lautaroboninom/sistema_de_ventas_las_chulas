from django.db import connection
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import exec_void, q, require_roles


class TiposEquipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = q(
            """
            SELECT DISTINCT TRIM(
                REPLACE(
                  REPLACE(
                    REPLACE(
                      REPLACE(nombre, 'OXIGENO', 'OXÍGENO'),
                    'BATERIAS','BATERÍAS'),
                  'BATERIA','BATERÍA'),
                'BATERAS','BATERÍAS')
            ) AS nombre
            FROM marca_tipos_equipo
            WHERE activo = TRUE
            ORDER BY 1
            """
        ) or []
        return Response([{ 'id': i+1, 'nombre': r.get('nombre') } for i, r in enumerate(rows)])

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        d = request.data or {}
        new_name = (d.get("nombre") or "").strip()
        old_name = (d.get("rename_from") or "").strip()
        if not new_name:
            return Response({"detail": "nombre requerido"}, status=400)

        # Repackage of legacy behavior: rename (if provided) across all marcas,
        # then ensure presence of the new name for at least one marca.
        if old_name and old_name.lower() != new_name.lower():
            exec_void(
                """
                INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                SELECT marca_id, %s, activo
                FROM marca_tipos_equipo
                WHERE UPPER(nombre)=UPPER(%s)
                ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                """,
                [new_name, old_name],
            )
            exec_void("DELETE FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER(%s)", [old_name])

            exec_void(
                "UPDATE models SET tipo_equipo=%s WHERE UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))",
                [new_name, old_name],
            )
            return Response({"ok": True, "renamed": True})

        row = q("SELECT id FROM marcas ORDER BY id LIMIT 1", one=True)
        if not row:
            return Response({"detail": "No hay marcas disponibles para registrar el tipo"}, status=400)
        marca_id = row.get("id")
        exec_void(
            """
            INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
            VALUES (%s,%s,TRUE)
            ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
            """,
            [marca_id, new_name],
        )
        return Response({"ok": True, "created": True})

    def delete(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        nombre = (request.GET.get("nombre") or "").strip()
        if not nombre:
            return Response({"detail": "nombre requerido"}, status=400)
        exec_void("DELETE FROM marca_tipos_equipo WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", [nombre])
        exec_void(
            "UPDATE models SET tipo_equipo=NULL WHERE UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))",
            [nombre],
        )
        return Response({"ok": True})
