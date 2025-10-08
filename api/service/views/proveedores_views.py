from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import exec_void, exec_returning, q, require_roles


class ProveedoresExternosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        sql = (
            "SELECT id, nombre, contacto, telefono, email, direccion, notas "
            "FROM proveedores_externos ORDER BY nombre"
        )
        return Response(q(sql))

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        data = request.data or {}

        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("nombre requerido")

        def _clean(key):
            if key not in data:
                return None, False
            val = data.get(key)
            if val is None:
                return None, True
            sval = str(val).strip()
            if not sval:
                return None, True
            return sval, True

        contacto, contacto_set = _clean("contacto")
        telefono, telefono_set = _clean("telefono")
        email, email_set = _clean("email")
        if email and email_set:
            email = email.lower()
        direccion, direccion_set = _clean("direccion")
        notas, notas_set = _clean("notas")

        existing = q(
            "SELECT id FROM proveedores_externos WHERE LOWER(nombre)=LOWER(%s)",
            [nombre],
            one=True,
        )

        if existing:
            sets = ["nombre=%s"]
            params = [nombre]
            if contacto_set:
                if contacto is None:
                    sets.append("contacto=NULL")
                else:
                    sets.append("contacto=%s")
                    params.append(contacto)
            if telefono_set:
                if telefono is None:
                    sets.append("telefono=NULL")
                else:
                    sets.append("telefono=%s")
                    params.append(telefono)
            if email_set:
                if email is None:
                    sets.append("email=NULL")
                else:
                    sets.append("email=%s")
                    params.append(email)
            if direccion_set:
                if direccion is None:
                    sets.append("direccion=NULL")
                else:
                    sets.append("direccion=%s")
                    params.append(direccion)
            if notas_set:
                if notas is None:
                    sets.append("notas=NULL")
                else:
                    sets.append("notas=%s")
                    params.append(notas)
            params.append(existing["id"])
            exec_void(
                f"UPDATE proveedores_externos SET {', '.join(sets)} WHERE id=%s",
                params,
            )
            return Response({"ok": True, "id": existing["id"], "updated": True})

        params = [
            nombre,
            contacto,
            telefono,
            email,
            direccion,
            notas,
        ]
        try:
            pid = exec_returning(
                "INSERT INTO proveedores_externos (nombre, contacto, telefono, email, direccion, notas)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                params,
            )
            return Response({"ok": True, "id": pid, "created": True})
        except Exception:
            existing = q(
                "SELECT id FROM proveedores_externos WHERE LOWER(nombre)=LOWER(%s)",
                [nombre],
                one=True,
            )
            if existing:
                return Response({"ok": True, "id": existing["id"], "updated": False})
            raise

    def delete(self, request, pid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        # Evitar error 500 por FK: bloquear si hay derivaciones asociadas
        row = q("SELECT COUNT(*) AS n FROM equipos_derivados WHERE proveedor_id = %s", [pid], one=True)
        nrefs = (row or {}).get("n", 0) or 0
        if nrefs > 0:
            return Response(
                {"ok": False, "detail": f"No se puede eliminar: proveedor referenciado por {nrefs} derivaciones"},
                status=409,
            )
        exec_void("DELETE FROM proveedores_externos WHERE id = %(id)s", {"id": pid})
        return Response({"ok": True})


__all__ = ['ProveedoresExternosView']
