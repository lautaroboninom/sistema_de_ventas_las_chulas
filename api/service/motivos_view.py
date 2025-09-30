from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Reutilizamos la corrección existente
from .views import _fix_text_value


def _q(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        if cur.description:
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            if one:
                return rows[0] if rows else None
            return rows
        return None


def _fix_mojibake(val: str) -> str:
    s = _fix_text_value(val)
    try:
        # Casos típicos de mojibake UTF-8 visto como Latin-1: 'Ã', 'Â', etc.
        if any(ch in s for ch in ("Ã", "Â", "â", "€", "™")):
            return s.encode("latin1").decode("utf-8")
    except Exception:
        pass
    return s


def _get_motivo_enum_values() -> list:
    try:
        if connection.vendor == "postgresql":
            rows = _q(
                """
                SELECT e.enumlabel AS v
                  FROM pg_type t
                  JOIN pg_enum e ON e.enumtypid = t.oid
                 WHERE t.typname = 'motivo_ingreso'
                """
            ) or []
            vals = [r.get("v") for r in rows]
        else:
            row = _q(
                """
                SELECT COLUMN_TYPE AS ct
                  FROM information_schema.columns
                 WHERE table_schema = DATABASE()
                   AND table_name = 'ingresos'
                   AND column_name = 'motivo'
                """,
                one=True,
            )
            vals = []
            if row and (row.get("ct") or "").lower().startswith("enum("):
                ct = row["ct"][5:-1]
                for p in ct.split(","):
                    v = p.strip().strip("'")
                    if v:
                        vals.append(v)
        vals = [_fix_mojibake(v) for v in (vals or []) if v]
        if vals:
            return vals
    except Exception:
        pass
    # Fallback estable con acentos correctos
    return [
        "urgente control",
        "reparación",
        "service preventivo",
        "baja alquiler",
        "reparación alquiler",
        "devolución demo",
        "otros",
    ]


class CatalogoMotivosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vals = _get_motivo_enum_values()
        vals = sorted(set(vals), key=lambda x: (x != "urgente control", x))
        return Response([{ "value": v, "label": v } for v in vals])

