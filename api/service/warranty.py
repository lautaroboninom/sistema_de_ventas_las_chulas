import datetime as _dt
from typing import Optional, Dict, Any, Tuple

from django.db import connection


def _norm_serial(s: str) -> str:
    try:
        import re

        s = str(s or "").strip().upper()
        s = re.sub(r"[\s\-_/]", "", s)
        return s
    except Exception:
        return (s or "").strip().upper()


def _read_device_warranty_expiry(numero_serie: str) -> Tuple[Optional[_dt.date], Optional[Dict[str, Any]]]:
    """Obtiene `devices.garantia_vence` para el N/S (normalizado) si existe."""
    if not numero_serie:
        return None, None
    ns_key = _norm_serial(numero_serie)
    if not ns_key:
        return None, None
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, garantia_vence
                  FROM devices
                 WHERE REPLACE(REPLACE(UPPER(numero_serie),' ',''),'-','') = %s
                 LIMIT 1
                """,
                [ns_key],
            )
            row = cur.fetchone()
            if not row:
                return None, None
            dev_id, vence = row[0], row[1]
            if not vence:
                return None, None
            try:
                vence_iso = vence.isoformat()
            except Exception:
                vence_iso = str(vence)
            return vence, {
                "source": "device",
                "device_id": int(dev_id),
                "garantia_vence": vence_iso,
            }
    except Exception:
        return None, None


def _rule_days_for(brand_id: Optional[int], model_id: Optional[int], serial_norm: str) -> Optional[int]:
    """Obtiene días de garantía desde `warranty_rules` si existe alguna regla activa.

    Prioridad: model_id > brand_id > serial_prefix. Devuelve None si no hay reglas.
    """
    try:
        with connection.cursor() as cur:
            # 1) Por modelo
            if model_id is not None:
                cur.execute(
                    """
                    SELECT days FROM warranty_rules
                     WHERE activo = TRUE AND model_id = %s
                     ORDER BY id DESC LIMIT 1
                    """,
                    [int(model_id)],
                )
                r = cur.fetchone()
                if r:
                    return int(r[0])
            # 2) Por marca
            if brand_id is not None:
                cur.execute(
                    """
                    SELECT days FROM warranty_rules
                     WHERE activo = TRUE AND brand_id = %s AND model_id IS NULL
                     ORDER BY id DESC LIMIT 1
                    """,
                    [int(brand_id)],
                )
                r = cur.fetchone()
                if r:
                    return int(r[0])
            # 3) Por prefijo de serie
            if serial_norm:
                cur.execute(
                    """
                    SELECT days FROM warranty_rules
                     WHERE activo = TRUE AND serial_prefix IS NOT NULL
                       AND %s LIKE (serial_prefix || '%')
                     ORDER BY length(serial_prefix) DESC, id DESC LIMIT 1
                    """,
                    [serial_norm],
                )
                r = cur.fetchone()
                if r:
                    return int(r[0])
    except Exception:
        return None
    return None


def compute_warranty(
    numero_serie: str,
    brand_id: Optional[int] = None,
    model_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Cálculo de garantía de fábrica.

    - Días: se toma desde `warranty_rules` (si existe), sino 365.
    - Fuente: si el device tiene `garantia_vence`, se usa como fuente de verdad.
    - Si no hay vencimiento persistido, no se puede inferir garantía automáticamente.
    """
    today = _dt.date.today()
    serial_norm = _norm_serial(numero_serie)

    # Días por regla (si existe), sino default 365
    days = _rule_days_for(brand_id, model_id, serial_norm)
    if days is None:
        days = 365

    vence, meta = _read_device_warranty_expiry(numero_serie)
    if vence:
        en_garantia = today <= vence
        return {
            "garantia": bool(en_garantia),
            "vence_el": vence,
            "fecha_venta": None,
            "days": days,
            "meta": meta or {"source": "device"},
        }

    return {
        "garantia": None,
        "vence_el": None,
        "fecha_venta": None,
        "days": days,
        "meta": {"source": "unknown"},
    }

