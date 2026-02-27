from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import ValidationError, PermissionDenied

from .helpers import q, exec_void, exec_returning, require_roles, _set_audit_user


class WarrantyRulesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _set_audit_user(request)
        brand_id = request.GET.get("brand_id")
        model_id = request.GET.get("model_id")
        prefix = (request.GET.get("serial_prefix") or "").strip()
        activo = request.GET.get("activo")

        wh, params = [], []
        if brand_id:
            wh.append("brand_id = %s")
            params.append(brand_id)
        if model_id:
            wh.append("model_id = %s")
            params.append(model_id)
        if prefix:
            wh.append("serial_prefix ILIKE %s")
            params.append(prefix + "%")
        if activo is not None:
            val = str(activo).strip().lower() in ("1","true","t","yes","y")
            wh.append("activo = %s")
            params.append(val)
        where = (" WHERE " + " AND ".join(wh)) if wh else ""
        rows = q(
            f"""
            SELECT id, brand_id, model_id, serial_prefix, days, notas, activo,
                   created_by, created_at, updated_by, updated_at
            FROM warranty_rules
            {where}
            ORDER BY id DESC
            """,
            params,
        )
        return Response(rows)

    def post(self, request):
        require_roles(request, ["admin", "jefe", "jefe_veedor"])  # admin, jefe y jefe_veedor
        _set_audit_user(request)
        d = request.data or {}
        brand_id = d.get("brand_id")
        model_id = d.get("model_id")
        serial_prefix = (d.get("serial_prefix") or "").strip() or None
        days = d.get("days")
        notas = (d.get("notas") or "").strip() or None

        if days is None:
            raise ValidationError("days es requerido (entero)")
        try:
            days_i = int(days)
            if days_i <= 0:
                raise ValueError()
        except Exception:
            raise ValidationError("days debe ser entero positivo")

        if model_id is not None:
            # validar modelo
            ok = q("SELECT 1 FROM models WHERE id=%s", [model_id], one=True)
            if not ok:
                raise ValidationError("model_id inválido")
        if brand_id is not None:
            ok = q("SELECT 1 FROM marcas WHERE id=%s", [brand_id], one=True)
            if not ok:
                raise ValidationError("brand_id inválido")

        new_id = exec_returning(
            """
            INSERT INTO warranty_rules(brand_id, model_id, serial_prefix, days, notas, activo, created_by)
            VALUES (%s,%s,%s,%s,%s, TRUE, current_setting('app.user_id', true)::INT)
            RETURNING id
            """,
            [brand_id, model_id, serial_prefix, days_i, notas],
        )
        row = q("SELECT * FROM warranty_rules WHERE id=%s", [new_id], one=True)
        return Response(row, status=201)


class WarrantyRuleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, rule_id: int):
        require_roles(request, ["admin", "jefe", "jefe_veedor"])  # admin, jefe y jefe_veedor
        _set_audit_user(request)
        d = request.data or {}
        sets, params = [], []
        if "days" in d:
            try:
                di = int(d.get("days"))
                if di <= 0:
                    raise ValueError()
            except Exception:
                raise ValidationError("days debe ser entero positivo")
            sets.append("days=%s")
            params.append(di)
        if "notas" in d:
            sets.append("notas = NULLIF(%s,'')")
            params.append((d.get("notas") or "").strip())
        if "activo" in d:
            sets.append("activo=%s")
            params.append(bool(d.get("activo")))
        if not sets:
            return Response({"ok": True, "updated": 0})
        sets.append("updated_at = NOW()")
        sets.append("updated_by = current_setting('app.user_id', true)::INT")
        params.append(rule_id)
        exec_void(f"UPDATE warranty_rules SET {', '.join(sets)} WHERE id=%s", params)
        row = q("SELECT * FROM warranty_rules WHERE id=%s", [rule_id], one=True)
        return Response(row)

    def delete(self, request, rule_id: int):
        require_roles(request, ["admin", "jefe", "jefe_veedor"])  # soft delete -> activo=false
        _set_audit_user(request)
        exec_void(
            "UPDATE warranty_rules SET activo=FALSE, updated_at=NOW(), updated_by=current_setting('app.user_id', true)::INT WHERE id=%s",
            [rule_id],
        )
        return Response({"ok": True})


__all__ = ["WarrantyRulesView", "WarrantyRuleDetailView"]
