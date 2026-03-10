import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import math
import mimetypes
import os
import random
import string
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import user_has_permission
from .helpers import _set_audit_user, exec_returning, exec_void, q, require_roles

security_logger = logging.getLogger("security.integrations")


TWO_DEC = Decimal('0.01')
FOUR_DEC = Decimal('0.0001')

PAYMENT_MODIFIERS = {
    'cash': Decimal('-10.00'),
    'debit': Decimal('0.00'),
    'transfer': Decimal('0.00'),
    'credit': Decimal('10.00'),
}
INVOICE_REQUIRED_METHODS = {'debit', 'transfer', 'credit'}
DEFAULT_ACCOUNT_BY_METHOD = {
    'cash': 'cash',
    'debit': 'payway',
    'credit': 'payway',
    'transfer': 'transfer_1',
}
DEFAULT_PRODUCT_BRAND = 'Las Chulas'
PRODUCT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
PRODUCT_IMAGE_ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
PRODUCT_IMAGE_CT_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}
PROMO_TYPE_PERCENT = 'percent_off'
PROMO_TYPE_X_FOR_Y = 'x_for_y'
PROMO_TYPE_EXTERNAL = 'external'
PROMO_CHANNELS = {'local', 'online', 'both'}
PROMO_ACTIVATION_MODES = {'automatic', 'coupon', 'both'}
PROMO_BOGO_MODES = {'sku', 'mix'}
PRICING_SOURCES = {'local_engine', 'tiendanube'}

DEFAULT_UI_PAGE_SETTINGS = {
    'app_name': 'Las Chulas',
    'app_tagline': 'Sistema retail de indumentaria',
    'footer_legal_name': 'Las Chulas',
    'sidebar_section_title': 'Operaciones',
    'default_route': '/pos',
    'nav_labels': {
        'pos': 'POS',
        'productos': 'Productos',
        'compras': 'Compras',
        'ventas': 'Ventas',
        'promociones': 'Promociones',
        'garantias': 'Cambios y devoluciones',
        'reportes': 'Reportes',
        'online': 'Online',
        'config_general': 'Config general',
        'config_paginas': 'Config paginas',
    },
    'page_titles': {
        'pos': 'POS mostrador',
        'productos': 'Productos y variantes',
        'compras': 'Compras',
        'ventas': 'Ventas, devoluciones y facturacion',
        'promociones': 'Promociones',
        'garantias': 'Cambios y devoluciones vigentes',
        'reportes': 'Reportes retail',
        'online': 'Online (Tienda Nube)',
        'config': 'Configuracion',
        'config_paginas': 'Configuracion de paginas',
    },
}
VALID_DEFAULT_ROUTES = {'/pos', '/productos', '/compras', '/ventas', '/promociones', '/garantias', '/online', '/config'}


def _default_ui_page_settings():
    return json.loads(json.dumps(DEFAULT_UI_PAGE_SETTINGS))


def _normalize_ui_page_settings(raw, strict=False):
    base = _default_ui_page_settings()
    data = _json(raw)
    if not data:
        return base

    for key in ('app_name', 'app_tagline', 'footer_legal_name', 'sidebar_section_title'):
        val = _clean_text(data.get(key))
        if val is not None:
            base[key] = val

    default_route = _clean_text(data.get('default_route'))
    if default_route:
        if not default_route.startswith('/'):
            default_route = f'/{default_route}'
        if default_route not in VALID_DEFAULT_ROUTES:
            if strict:
                raise ValidationError('default_route invalido')
            default_route = '/pos'
        if default_route in VALID_DEFAULT_ROUTES:
            base['default_route'] = default_route

    nav = data.get('nav_labels')
    if isinstance(nav, dict):
        for key in base['nav_labels'].keys():
            val = _clean_text(nav.get(key))
            if val is not None:
                base['nav_labels'][key] = val

    titles = data.get('page_titles')
    if isinstance(titles, dict):
        for key in base['page_titles'].keys():
            val = _clean_text(titles.get(key))
            if val is not None:
                base['page_titles'][key] = val

    return base


def _clean_text(val):
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _to_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return val != 0
    return str(val).strip().lower() in ('1', 'true', 'si', 'yes', 'on')


def _product_image_ext(uploaded):
    ext = os.path.splitext(str(getattr(uploaded, 'name', '') or ''))[1].lower()
    if ext in PRODUCT_IMAGE_ALLOWED_EXTS:
        return ext
    ctype = str(getattr(uploaded, 'content_type', '') or '').split(';', 1)[0].strip().lower()
    mapped = PRODUCT_IMAGE_CT_TO_EXT.get(ctype)
    if mapped:
        return mapped
    raise ValidationError('Formato de imagen no soportado. Usa JPG, PNG, WEBP o GIF')


def _save_product_image(producto_id, uploaded):
    size = getattr(uploaded, 'size', None)
    if size is not None and int(size) > PRODUCT_IMAGE_MAX_BYTES:
        raise ValidationError('La imagen supera el maximo de 5 MB')
    ext = _product_image_ext(uploaded)
    rel_path = f"retail/productos/{int(producto_id)}/{uuid.uuid4().hex}{ext}"
    return default_storage.save(rel_path, uploaded)


def _delete_product_image(path):
    rel_path = _clean_text(path)
    if not rel_path:
        return
    try:
        if default_storage.exists(rel_path):
            default_storage.delete(rel_path)
    except Exception:
        # Limpieza best effort: no bloquear respuestas por error de borrado.
        return


def _product_image_url(request, producto_id, image_path):
    if not _clean_text(image_path):
        return None
    rel_url = f'/api/retail/productos/{producto_id}/imagen/'
    return request.build_absolute_uri(rel_url) if request else rel_url


def _decorate_producto_row(request, row, keep_path=False):
    if not row:
        return row
    image_path = _clean_text(row.get('image_path'))
    row['image_url'] = _product_image_url(request, row.get('id'), image_path)
    if not keep_path:
        row.pop('image_path', None)
    return row


def _to_int(val, label, allow_none=False):
    if val is None or (isinstance(val, str) and val.strip() == ''):
        if allow_none:
            return None
        raise ValidationError(f'{label} requerido')
    try:
        return int(val)
    except (TypeError, ValueError):
        raise ValidationError(f'{label} invalido')


def _to_decimal(val, label, allow_none=False):
    if val is None or (isinstance(val, str) and val.strip() == ''):
        if allow_none:
            return None
        raise ValidationError(f'{label} requerido')
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    try:
        return Decimal(str(val).strip().replace(',', '.'))
    except InvalidOperation:
        raise ValidationError(f'{label} invalido')


def _money(val):
    return _to_decimal(val, 'monto').quantize(TWO_DEC, rounding=ROUND_HALF_UP)


def _pct(val):
    return _to_decimal(val, 'porcentaje').quantize(TWO_DEC, rounding=ROUND_HALF_UP)


def _safe_pct(numerator, denominator):
    den = _to_decimal(denominator or 0, 'denominador', allow_none=True) or Decimal('0')
    if den <= 0:
        return None
    num = _to_decimal(numerator or 0, 'numerador', allow_none=True) or Decimal('0')
    return ((num / den) * Decimal('100')).quantize(TWO_DEC, rounding=ROUND_HALF_UP)


def _percentile(values, percentile):
    vals = sorted(float(v) for v in (values or []) if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    p = max(0.0, min(1.0, float(percentile)))
    pos = (len(vals) - 1) * p
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] + (vals[hi] - vals[lo]) * frac


def _json(raw):
    if isinstance(raw, dict):
        return raw
    if raw in (None, ''):
        return {}
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode('utf-8', errors='ignore')
    try:
        data = json.loads(str(raw))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _user_role(request):
    return (getattr(getattr(request, 'user', None), 'rol', '') or '').strip().lower()


def _require_staff(request):
    require_roles(request, ['admin', 'empleado'])


def _require_admin(request):
    require_roles(request, ['admin'])


def _can_view_costs(request):
    return _user_role(request) == 'admin' or user_has_permission(request, 'action.reportes.ver_costos')


def _can_override_price(request):
    return _user_role(request) == 'admin' or user_has_permission(request, 'action.ventas.override_precio')


def _can_override_return_warranty(request):
    return _user_role(request) == 'admin' or user_has_permission(request, 'action.ventas.devolver.override_garantia')


def _can_manage_promotions(request):
    return _user_role(request) == 'admin' or user_has_permission(request, 'action.promociones.editar')


def _can_exchange_sale(request):
    return _user_role(request) == 'admin' or user_has_permission(request, 'action.ventas.cambiar')


def _parse_dates(request):
    today = timezone.localdate()
    since = (request.query_params.get('desde') or request.query_params.get('from') or (today - dt.timedelta(days=30)).isoformat()).strip()
    until = (request.query_params.get('hasta') or request.query_params.get('to') or today.isoformat()).strip()
    try:
        since_date = dt.date.fromisoformat(since)
        until_date = dt.date.fromisoformat(until)
    except ValueError:
        raise ValidationError('Rango de fechas invalido. Usa YYYY-MM-DD')
    if until_date < since_date:
        raise ValidationError('hasta debe ser mayor o igual a desde')
    return since_date.isoformat(), until_date.isoformat()


def _load_settings():
    row = q('SELECT * FROM retail_settings WHERE id=1', one=True) or {}
    size_days = int(row.get('return_warranty_size_days') or 30)
    breakage_days = int(row.get('return_warranty_breakage_days') or 90)
    purchase_markup = _to_decimal(row.get('purchase_default_markup_pct') or 100, 'purchase_default_markup_pct', allow_none=True) or Decimal('100')
    if size_days <= 0:
        size_days = 30
    if breakage_days <= 0:
        breakage_days = 90
    if purchase_markup < 0:
        purchase_markup = Decimal('100')
    return {
        'arca_env': row.get('arca_env') or 'homologacion',
        'arca_cuit': row.get('arca_cuit') or '',
        'arca_pto_vta_store': row.get('arca_pto_vta_store') or 1,
        'arca_pto_vta_online': row.get('arca_pto_vta_online') or (row.get('arca_pto_vta_store') or 1),
        'tiendanube_store_id': row.get('tiendanube_store_id'),
        'tiendanube_access_token': row.get('tiendanube_access_token') or '',
        'tiendanube_webhook_secret': row.get('tiendanube_webhook_secret') or '',
        'auto_invoice_online_paid': bool(row.get('auto_invoice_online_paid')),
        'purchase_default_markup_pct': purchase_markup.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
        'return_warranty_size_days': size_days,
        'return_warranty_breakage_days': breakage_days,
        'ui_page_settings': _normalize_ui_page_settings(row.get('ui_page_settings')),
    }


_SENSITIVE_SETTINGS_FIELDS = (
    'tiendanube_client_secret',
    'tiendanube_access_token',
    'tiendanube_webhook_secret',
    'arca_key_path',
    'arca_cert_path',
)


def _mask_secret_value(value):
    raw = _clean_text(value)
    if not raw:
        return None
    if len(raw) <= 4:
        return '*' * len(raw)
    return f"{'*' * (len(raw) - 4)}{raw[-4:]}"


def _sanitize_retail_settings_response(row):
    out = dict(row or {})
    for field in _SENSITIVE_SETTINGS_FIELDS:
        raw = out.pop(field, None)
        configured = bool(_clean_text(raw))
        out[f'{field}_configured'] = configured
        out[f'{field}_masked'] = _mask_secret_value(raw) if configured else None
    return out


def _create_job(provider, job_type, payload, status='pending', last_error=None):
    return exec_returning(
        '''
        INSERT INTO integration_jobs (provider, job_type, status, payload, last_error, next_retry_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING id
        ''',
        [provider, job_type, status, json.dumps(payload or {}), last_error, timezone.now() if status in ('pending', 'failed') else None],
    )


def _random_suffix(size=4):
    return ''.join(random.choice(string.digits) for _ in range(size))


def _product_name(product_id):
    row = q('SELECT id, name, sku_prefix FROM retail_products WHERE id=%s', [product_id], one=True)
    if not row:
        raise ValidationError('Producto no encontrado')
    return row


def _attribute_by_ref(attribute_id=None, attribute_code=None):
    row = None
    if attribute_id:
        row = q('SELECT id, code, name FROM retail_variant_attributes WHERE id=%s AND active=TRUE', [attribute_id], one=True)
    elif attribute_code:
        row = q('SELECT id, code, name FROM retail_variant_attributes WHERE LOWER(code)=LOWER(%s) AND active=TRUE', [attribute_code], one=True)
    if not row:
        raise ValidationError('Atributo invalido en option_values')
    return row


def _normalize_option_value(value):
    s = _clean_text(value)
    if not s:
        return None
    return s.casefold()


def _normalize_option_values(data):
    raw = data.get('option_values') or data.get('opciones') or []
    if isinstance(raw, dict):
        raw = [{'attribute_code': k, 'value': v} for k, v in raw.items()]
    if not isinstance(raw, list):
        raise ValidationError('option_values debe ser lista o mapa')

    normalized = []
    used_attributes = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValidationError('Cada opcion debe ser objeto')
        attr = _attribute_by_ref(
            attribute_id=_to_int(item.get('attribute_id'), 'attribute_id', allow_none=True),
            attribute_code=_clean_text(item.get('attribute_code')),
        )
        if attr['id'] in used_attributes:
            raise ValidationError(f"Atributo repetido en la variante: {attr['name']}")
        used_attributes.add(attr['id'])

        val = _normalize_option_value(item.get('value'))
        if not val:
            raise ValidationError('option_values.value requerido')
        normalized.append(
            {
                'attribute_id': attr['id'],
                'attribute_code': str(attr['code']).strip().lower(),
                'attribute_name': attr['name'],
                'value': val,
            }
        )

    normalized.sort(key=lambda x: (str(x['attribute_code']).lower(), str(x['value']).lower()))
    signature = '|'.join([f"{x['attribute_code']}={x['value']}" for x in normalized])
    return normalized, signature


def _ensure_payment_account(payload, payment_method):
    account_id = _to_int(payload.get('payment_account_id'), 'payment_account_id', allow_none=True)
    account_code = _clean_text(payload.get('payment_account_code'))
    row = None
    if account_id:
        row = q(
            'SELECT id, code, label, payment_method, active FROM retail_payment_accounts WHERE id=%s',
            [account_id],
            one=True,
        )
    elif account_code:
        row = q(
            'SELECT id, code, label, payment_method, active FROM retail_payment_accounts WHERE LOWER(code)=LOWER(%s)',
            [account_code],
            one=True,
        )
    else:
        default_code = DEFAULT_ACCOUNT_BY_METHOD.get(payment_method)
        if default_code:
            row = q(
                'SELECT id, code, label, payment_method, active FROM retail_payment_accounts WHERE code=%s',
                [default_code],
                one=True,
            )

    if not row:
        raise ValidationError('Cuenta/caja de cobro invalida')
    if not row.get('active'):
        raise ValidationError('Cuenta/caja inactiva')
    account_method = _clean_text(row.get('payment_method'))
    if account_method and payment_method and account_method.lower() != str(payment_method).lower():
        raise ValidationError('Cuenta/caja incompatible con el medio de pago')
    return row


def _sale_number(venta_id):
    today = timezone.localdate().strftime('%Y%m%d')
    return f"VTA-{today}-{int(venta_id):06d}"


def _draft_number(draft_id):
    today = timezone.localdate().strftime('%Y%m%d')
    return f"DRF-{today}-{int(draft_id):06d}"


def _load_sale_payments(sale_id, fallback_sale=None):
    sid = _to_int(sale_id, 'sale_id', allow_none=True)
    rows = []
    if sid:
        rows = q(
            '''
            SELECT sp.id, sp.sale_id, sp.payment_method, sp.payment_account_id,
                   sp.amount_ars, sp.metadata, sp.created_at,
                   COALESCE(pa.code,'') AS payment_account_code,
                   COALESCE(pa.label,'') AS payment_account_label
            FROM retail_sale_payments sp
            LEFT JOIN retail_payment_accounts pa ON pa.id=sp.payment_account_id
            WHERE sp.sale_id=%s
            ORDER BY sp.id
            ''',
            [sid],
        ) or []
    if rows:
        return rows
    if not fallback_sale:
        return []
    return [
        {
            'id': None,
            'sale_id': fallback_sale.get('id'),
            'payment_method': fallback_sale.get('payment_method'),
            'payment_account_id': fallback_sale.get('payment_account_id'),
            'payment_account_code': fallback_sale.get('payment_account_code'),
            'payment_account_label': fallback_sale.get('payment_account_label'),
            'amount_ars': fallback_sale.get('total_ars'),
            'metadata': {},
            'created_at': fallback_sale.get('created_at'),
        }
    ]


def _normalize_payments(payload, quote):
    raw = (payload or {}).get('payments')
    if raw is None:
        payment_account = _ensure_payment_account(payload or {}, quote['payment_method'])
        amount = _to_decimal(quote['total_ars'], 'total_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        item = {
            'method': quote['payment_method'],
            'account_id': payment_account['id'],
            'account_code': payment_account['code'],
            'account_label': payment_account['label'],
            'amount_ars': amount,
            'metadata': {},
        }
        return [item], item

    if not isinstance(raw, list) or not raw:
        raise ValidationError('payments debe ser una lista no vacia')

    rows = []
    total = Decimal('0.00')
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValidationError(f'payments[{idx}] debe ser objeto')
        method = _normalize_payment_method(item.get('method') or item.get('payment_method'))
        account = _ensure_payment_account(
            {
                'payment_account_id': item.get('account_id') or item.get('payment_account_id'),
                'payment_account_code': item.get('account_code') or item.get('payment_account_code'),
            },
            method,
        )
        amount = _money(item.get('amount_ars'))
        if amount <= 0:
            raise ValidationError(f'payments[{idx}].amount_ars debe ser mayor a 0')
        metadata = _json(item.get('metadata')) or {}
        row = {
            'method': method,
            'account_id': account['id'],
            'account_code': account['code'],
            'account_label': account['label'],
            'amount_ars': amount.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
            'metadata': metadata if isinstance(metadata, dict) else {},
        }
        rows.append(row)
        total += row['amount_ars']

    expected = _to_decimal(quote['total_ars'], 'total_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    if total.quantize(TWO_DEC, rounding=ROUND_HALF_UP) != expected:
        raise ValidationError('La suma de payments debe coincidir exactamente con total_ars')

    primary = sorted(
        rows,
        key=lambda item: (item['amount_ars'], item['method'] == quote['payment_method']),
        reverse=True,
    )[0]
    return rows, primary


def _persist_sale_payments(sale_id, payments):
    for row in payments or []:
        amount = _to_decimal(row.get('amount_ars') or 0, 'amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        exec_void(
            '''
            INSERT INTO retail_sale_payments(
              sale_id, payment_method, payment_account_id, amount_ars, metadata
            )
            VALUES (%s,%s,%s,%s,%s::jsonb)
            ''',
            [
                sale_id,
                _normalize_payment_method(row.get('method') or row.get('payment_method')),
                _to_int(row.get('account_id') or row.get('payment_account_id'), 'payment_account_id'),
                amount,
                json.dumps(_json(row.get('metadata')) or {}, ensure_ascii=False),
            ],
        )


def _split_amount_across_payments(payments, total_amount):
    amount = _to_decimal(total_amount, 'total_amount').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    rows = []
    prepared = []
    base_total = Decimal('0.00')
    for row in payments or []:
        val = _to_decimal(row.get('amount_ars') or 0, 'amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if val <= 0:
            continue
        prepared.append((row, val))
        base_total += val
    if not prepared:
        return rows

    if base_total == amount:
        return [{'payment': row, 'amount_ars': val} for row, val in prepared]

    assigned = Decimal('0.00')
    for idx, (row, val) in enumerate(prepared):
        if idx == len(prepared) - 1:
            part = (amount - assigned).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        else:
            ratio = (val / base_total) if base_total > 0 else Decimal('0')
            part = (amount * ratio).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            assigned += part
        if part <= 0:
            continue
        rows.append({'payment': row, 'amount_ars': part})
    return rows


def _open_cash_session(lock=False):
    sql = 'SELECT * FROM retail_cash_sessions WHERE status=\'open\' ORDER BY id DESC LIMIT 1'
    if lock:
        sql += ' FOR UPDATE'
    return q(sql, one=True)


def _load_producto(producto_id, request=None, keep_path=False):
    row = q(
        '''
        SELECT p.id, p.name, p.description, p.category_id, p.brand, p.season, p.active, p.sku_prefix,
               p.default_cost_ars, p.image_path, p.created_at, p.updated_at,
               COALESCE(c.name, '') AS category_name
        FROM retail_products p
        LEFT JOIN retail_categories c ON c.id = p.category_id
        WHERE p.id=%s
        ''',
        [producto_id],
        one=True,
    )
    if not row:
        return None
    return _decorate_producto_row(request, row, keep_path=keep_path)


def _load_variante(variante_id, include_costs=False):
    row = q(
        '''
        SELECT v.id, v.product_id, p.name AS producto, COALESCE(p.brand,'') AS marca,
               COALESCE(p.category_id,0) AS category_id, COALESCE(c.name,'') AS category_name,
               v.option_signature, v.display_name, v.sku, v.barcode_internal,
               v.price_store_ars, v.price_online_ars, v.cost_avg_ars, v.stock_on_hand,
               v.stock_reserved, v.stock_min, v.active,
               v.tiendanube_product_id, v.tiendanube_variant_id,
               v.created_at, v.updated_at
        FROM retail_product_variants v
        JOIN retail_products p ON p.id=v.product_id
        LEFT JOIN retail_categories c ON c.id=p.category_id
        WHERE v.id=%s
        ''',
        [variante_id],
        one=True,
    )
    if not row:
        return None
    options = q(
        '''
        SELECT ov.attribute_id, a.code AS attribute_code, a.name AS attribute_name, ov.option_value
        FROM retail_variant_option_values ov
        JOIN retail_variant_attributes a ON a.id=ov.attribute_id
        WHERE ov.variant_id=%s
        ORDER BY a.sort_order, a.code
        ''',
        [variante_id],
    ) or []
    row['option_values'] = options
    if not include_costs:
        row['cost_avg_ars'] = None
    return row


class RetailProductosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        qtxt = (request.query_params.get('q') or '').strip()
        active = (request.query_params.get('active') or '').strip().lower()
        params = []
        filters = []
        if qtxt:
            params.extend([f'%{qtxt}%', f'%{qtxt}%'])
            filters.append('(p.name ILIKE %s OR COALESCE(p.brand,\'\') ILIKE %s)')
        if active in ('1', 'true', 'si', 'yes'):
            filters.append('p.active=TRUE')
        if active in ('0', 'false', 'no'):
            filters.append('p.active=FALSE')
        where = f"WHERE {' AND '.join(filters)}" if filters else ''
        rows = q(
            f'''
            SELECT p.id, p.name, p.description, p.category_id, COALESCE(c.name,'') AS category_name,
                   p.brand, p.season, p.active, p.sku_prefix, p.default_cost_ars, p.image_path,
                   p.created_at, p.updated_at,
                   COALESCE(v.cnt,0) AS variantes
            FROM retail_products p
            LEFT JOIN retail_categories c ON c.id=p.category_id
            LEFT JOIN (
              SELECT product_id, COUNT(*) AS cnt
              FROM retail_product_variants
              GROUP BY product_id
            ) v ON v.product_id = p.id
            {where}
            ORDER BY p.name, p.id
            ''',
            params,
        ) or []
        if not _can_view_costs(request):
            for row in rows:
                row['default_cost_ars'] = None
        for row in rows:
            _decorate_producto_row(request, row)
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        name = _clean_text(data.get('name') or data.get('nombre'))
        if not name:
            raise ValidationError('name requerido')
        category_id = _to_int(data.get('category_id'), 'category_id', allow_none=True)
        brand = DEFAULT_PRODUCT_BRAND
        season = _clean_text(data.get('season') or data.get('temporada'))
        description = _clean_text(data.get('description') or data.get('descripcion'))
        sku_prefix = _clean_text(data.get('sku_prefix'))
        default_cost = _money(data.get('default_cost_ars') or 0)
        image_file = request.FILES.get('image') or request.FILES.get('imagen')
        created_image_path = None
        try:
            pid = exec_returning(
                '''
                INSERT INTO retail_products(name, description, category_id, brand, season, active, sku_prefix, default_cost_ars)
                VALUES (%s,%s,%s,%s,%s,TRUE,%s,%s)
                RETURNING id
                ''',
                [name, description, category_id, brand, season, sku_prefix, default_cost],
            )
            if image_file:
                created_image_path = _save_product_image(pid, image_file)
                exec_void('UPDATE retail_products SET image_path=%s WHERE id=%s', [created_image_path, pid])
            return Response(_load_producto(pid, request=request), status=201)
        except Exception:
            if created_image_path:
                _delete_product_image(created_image_path)
            raise


class RetailProductoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def patch(self, request, producto_id):
        _require_staff(request)
        _set_audit_user(request)
        producto = _load_producto(producto_id, request=request, keep_path=True)
        if not producto:
            return Response({'detail': 'Producto no encontrado'}, status=404)

        data = request.data or {}
        updates = []
        params = []
        old_image_path = _clean_text(producto.get('image_path'))
        next_image_path = old_image_path
        uploaded_image_path = None

        if 'name' in data or 'nombre' in data:
            name = _clean_text(data.get('name') or data.get('nombre'))
            if not name:
                raise ValidationError('name no puede ser vacio')
            updates.append('name=%s')
            params.append(name)
        if 'description' in data or 'descripcion' in data:
            updates.append('description=%s')
            params.append(_clean_text(data.get('description') or data.get('descripcion')))
        if 'category_id' in data:
            updates.append('category_id=%s')
            params.append(_to_int(data.get('category_id'), 'category_id', allow_none=True))
        if 'season' in data or 'temporada' in data:
            updates.append('season=%s')
            params.append(_clean_text(data.get('season') or data.get('temporada')))
        if 'active' in data:
            updates.append('active=%s')
            params.append(bool(data.get('active')))
        if 'sku_prefix' in data:
            updates.append('sku_prefix=%s')
            params.append(_clean_text(data.get('sku_prefix')))
        if 'default_cost_ars' in data:
            updates.append('default_cost_ars=%s')
            params.append(_money(data.get('default_cost_ars')))
        image_file = request.FILES.get('image') or request.FILES.get('imagen')
        if image_file:
            uploaded_image_path = _save_product_image(producto_id, image_file)
            next_image_path = uploaded_image_path
            updates.append('image_path=%s')
            params.append(uploaded_image_path)
        else:
            clear_image = data.get('clear_image')
            if clear_image is None:
                clear_image = data.get('remove_image')
            if clear_image is not None and _to_bool(clear_image):
                next_image_path = None
                updates.append('image_path=%s')
                params.append(None)

        if not updates:
            raise ValidationError('Sin cambios para aplicar')

        try:
            params.append(producto_id)
            exec_void(f"UPDATE retail_products SET {', '.join(updates)} WHERE id=%s", params)
        except Exception:
            if uploaded_image_path:
                _delete_product_image(uploaded_image_path)
            raise

        if old_image_path and old_image_path != next_image_path:
            _delete_product_image(old_image_path)

        row = _load_producto(producto_id, request=request)
        return Response(row)


class RetailProductoImagenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, producto_id):
        _require_staff(request)
        row = _load_producto(producto_id, request=request, keep_path=True)
        if not row:
            return Response({'detail': 'Producto no encontrado'}, status=404)

        image_path = _clean_text(row.get('image_path'))
        if not image_path:
            return Response({'detail': 'Producto sin imagen'}, status=404)
        if not default_storage.exists(image_path):
            return Response({'detail': 'Imagen no disponible'}, status=404)

        content_type, _ = mimetypes.guess_type(image_path)
        fp = default_storage.open(image_path, 'rb')
        return FileResponse(fp, content_type=content_type or 'application/octet-stream')


class RetailAtributosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        rows = q(
            '''
            SELECT id, name, code, applies_to_category_id, active, sort_order, created_at, updated_at
            FROM retail_variant_attributes
            ORDER BY sort_order, code
            '''
        ) or []
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        name = _clean_text(data.get('name') or data.get('nombre'))
        code = _clean_text(data.get('code') or data.get('codigo'))
        if not name or not code:
            raise ValidationError('name y code son requeridos')
        category_id = _to_int(data.get('applies_to_category_id'), 'applies_to_category_id', allow_none=True)
        sort_order = _to_int(data.get('sort_order') or 100, 'sort_order')
        aid = exec_returning(
            '''
            INSERT INTO retail_variant_attributes(name, code, applies_to_category_id, active, sort_order)
            VALUES (%s,%s,%s,TRUE,%s)
            RETURNING id
            ''',
            [name, code, category_id, sort_order],
        )
        row = q('SELECT * FROM retail_variant_attributes WHERE id=%s', [aid], one=True)
        return Response(row, status=201)


def _autogen_sku(product_row):
    prefix = _clean_text(product_row.get('sku_prefix')) or f"P{product_row['id']}"
    count_row = q('SELECT COUNT(*)::int AS cnt FROM retail_product_variants WHERE product_id=%s', [product_row['id']], one=True) or {'cnt': 0}
    seq = int(count_row['cnt']) + 1
    base = f"{prefix}-{seq:03d}"
    probe = base
    while q('SELECT id FROM retail_product_variants WHERE LOWER(sku)=LOWER(%s)', [probe], one=True):
        probe = f"{base}-{_random_suffix(2)}"
    return probe


def _autogen_barcode(product_row):
    base = f"LC-{product_row['id']}-{int(timezone.now().timestamp())}"
    probe = base
    while q('SELECT id FROM retail_product_variants WHERE LOWER(barcode_internal)=LOWER(%s)', [probe], one=True):
        probe = f"{base}-{_random_suffix(2)}"
    return probe


class RetailVariantesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        qtxt = (request.query_params.get('q') or '').strip()
        only_active = (request.query_params.get('active') or '').strip().lower()
        limit = _to_int(request.query_params.get('limit') or 0, 'limit', allow_none=True)
        params = []
        filters = []
        if qtxt:
            params.extend([f'%{qtxt}%', f'%{qtxt}%', f'%{qtxt}%'])
            filters.append('(v.sku ILIKE %s OR v.barcode_internal ILIKE %s OR p.name ILIKE %s)')
        if only_active in ('1', 'true', 'si', 'yes'):
            filters.append('v.active=TRUE')
        if only_active in ('0', 'false', 'no'):
            filters.append('v.active=FALSE')
        where = f"WHERE {' AND '.join(filters)}" if filters else ''
        limit_sql = ''
        if limit and int(limit) > 0:
            limit_sql = 'LIMIT %s'
            params.append(max(1, min(int(limit), 300)))

        rows = q(
            f'''
            SELECT v.id, v.product_id, p.name AS producto, COALESCE(p.brand,'') AS marca,
                   p.image_path AS product_image_path,
                   v.option_signature, v.display_name, v.sku, v.barcode_internal,
                   v.price_store_ars, v.price_online_ars, v.cost_avg_ars,
                   v.stock_on_hand, v.stock_reserved, v.stock_min,
                   v.active, v.created_at, v.updated_at,
                   v.tiendanube_product_id, v.tiendanube_variant_id
            FROM retail_product_variants v
            JOIN retail_products p ON p.id=v.product_id
            {where}
            ORDER BY p.name, v.id
            {limit_sql}
            ''',
            params,
        ) or []

        if not _can_view_costs(request):
            for row in rows:
                row['cost_avg_ars'] = None
        for row in rows:
            row['product_image_url'] = _product_image_url(request, row.get('product_id'), row.get('product_image_path'))
            row.pop('product_image_path', None)

        variant_ids = [r['id'] for r in rows]
        opt_rows = []
        if variant_ids:
            opt_rows = q(
                '''
                SELECT ov.variant_id, a.code AS attribute_code, a.name AS attribute_name, ov.option_value
                FROM retail_variant_option_values ov
                JOIN retail_variant_attributes a ON a.id=ov.attribute_id
                WHERE ov.variant_id = ANY(%s)
                ORDER BY ov.variant_id, a.sort_order, a.code
                ''',
                [variant_ids],
            ) or []
        by_variant = {}
        for opt in opt_rows:
            by_variant.setdefault(opt['variant_id'], []).append(opt)
        for row in rows:
            row['option_values'] = by_variant.get(row['id'], [])

        return Response(rows)

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        product_id = _to_int(data.get('product_id'), 'product_id')
        product_row = _product_name(product_id)

        option_values, signature = _normalize_option_values(data)
        if not signature:
            raise ValidationError('Debe informar option_values para la variante')

        if q('SELECT id FROM retail_product_variants WHERE product_id=%s AND LOWER(option_signature)=LOWER(%s)', [product_id, signature], one=True):
            raise ValidationError('Ya existe una variante con esa combinacion de atributos')

        sku = _clean_text(data.get('sku')) or _autogen_sku(product_row)
        barcode = _clean_text(data.get('barcode_internal')) or _autogen_barcode(product_row)
        display_name = _clean_text(data.get('display_name')) or f"{product_row['name']} ({signature})"
        price_store = _money(data.get('price_store_ars') or data.get('precio_local_ars') or 0)
        price_online = _money(data.get('price_online_ars') or data.get('precio_online_ars') or price_store)
        cost_avg = _money(data.get('cost_avg_ars') or data.get('costo_promedio_ars') or product_row.get('default_cost_ars') or 0)
        stock_on_hand = _to_int(data.get('stock_on_hand') or 0, 'stock_on_hand')
        stock_min = _to_int(data.get('stock_min') or 0, 'stock_min')

        vid = exec_returning(
            '''
            INSERT INTO retail_product_variants(
              product_id, option_signature, display_name, sku, barcode_internal,
              price_store_ars, price_online_ars, cost_avg_ars,
              stock_on_hand, stock_reserved, stock_min, active
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,TRUE)
            RETURNING id
            ''',
            [
                product_id,
                signature,
                display_name,
                sku,
                barcode,
                price_store,
                price_online,
                cost_avg,
                stock_on_hand,
                stock_min,
            ],
        )

        for opt in option_values:
            exec_void(
                '''
                INSERT INTO retail_variant_option_values(variant_id, attribute_id, option_value)
                VALUES (%s,%s,%s)
                ''',
                [vid, opt['attribute_id'], opt['value']],
            )

        if stock_on_hand != 0:
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'manual_adjustment',%s,%s,%s,'variant_create',%s,'Stock inicial variante',%s)
                ''',
                [vid, stock_on_hand, stock_on_hand, cost_avg, vid, getattr(request.user, 'id', None)],
            )

        return Response(_load_variante(vid, include_costs=True), status=201)


class RetailVarianteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def patch(self, request, variante_id):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        existing = _load_variante(variante_id, include_costs=True)
        if not existing:
            return Response({'detail': 'Variante no encontrada'}, status=404)

        updates = []
        params = []
        if 'display_name' in data:
            updates.append('display_name=%s')
            params.append(_clean_text(data.get('display_name')))
        if 'sku' in data:
            sku = _clean_text(data.get('sku'))
            if not sku:
                raise ValidationError('sku invalido')
            updates.append('sku=%s')
            params.append(sku)
        if 'barcode_internal' in data:
            barcode = _clean_text(data.get('barcode_internal'))
            if not barcode:
                raise ValidationError('barcode_internal invalido')
            updates.append('barcode_internal=%s')
            params.append(barcode)
        if 'price_store_ars' in data:
            updates.append('price_store_ars=%s')
            params.append(_money(data.get('price_store_ars')))
        if 'price_online_ars' in data:
            updates.append('price_online_ars=%s')
            params.append(_money(data.get('price_online_ars')))
        if 'cost_avg_ars' in data:
            updates.append('cost_avg_ars=%s')
            params.append(_money(data.get('cost_avg_ars')))
        if 'stock_min' in data:
            updates.append('stock_min=%s')
            params.append(_to_int(data.get('stock_min'), 'stock_min'))
        if 'active' in data:
            updates.append('active=%s')
            params.append(bool(data.get('active')))

        if updates:
            params.append(variante_id)
            exec_void(f"UPDATE retail_product_variants SET {', '.join(updates)} WHERE id=%s", params)

        if 'option_values' in data or 'opciones' in data:
            option_values, signature = _normalize_option_values(data)
            if not signature:
                raise ValidationError('option_values invalido')
            duplicate = q(
                'SELECT id FROM retail_product_variants WHERE product_id=%s AND LOWER(option_signature)=LOWER(%s) AND id<>%s',
                [existing['product_id'], signature, variante_id],
                one=True,
            )
            if duplicate:
                raise ValidationError('Ya existe una variante con esa combinacion')
            exec_void('DELETE FROM retail_variant_option_values WHERE variant_id=%s', [variante_id])
            for opt in option_values:
                exec_void(
                    'INSERT INTO retail_variant_option_values(variant_id, attribute_id, option_value) VALUES (%s,%s,%s)',
                    [variante_id, opt['attribute_id'], opt['value']],
                )
            exec_void('UPDATE retail_product_variants SET option_signature=%s WHERE id=%s', [signature, variante_id])

        stock_adjust = _to_int(data.get('stock_adjust_qty'), 'stock_adjust_qty', allow_none=True)
        if stock_adjust is not None and stock_adjust != 0:
            note = _clean_text(data.get('stock_adjust_note')) or 'Ajuste manual'
            row = q('SELECT id, stock_on_hand, cost_avg_ars FROM retail_product_variants WHERE id=%s FOR UPDATE', [variante_id], one=True)
            new_stock = int(row['stock_on_hand']) + int(stock_adjust)
            if new_stock < 0:
                raise ValidationError('Stock insuficiente para aplicar ajuste')
            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, variante_id])
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'manual_adjustment',%s,%s,%s,'variant_adjust',%s,%s,%s)
                ''',
                [
                    variante_id,
                    stock_adjust,
                    new_stock,
                    row.get('cost_avg_ars') or Decimal('0'),
                    variante_id,
                    note,
                    getattr(request.user, 'id', None),
                ],
            )

        return Response(_load_variante(variante_id, include_costs=True))


class RetailVarianteEscanearView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, codigo):
        _require_staff(request)
        code = (codigo or '').strip()
        if not code:
            raise ValidationError('codigo requerido')
        row = q(
            '''
            SELECT v.id
            FROM retail_product_variants v
            WHERE LOWER(v.barcode_internal)=LOWER(%s) OR LOWER(v.sku)=LOWER(%s)
            LIMIT 1
            ''',
            [code, code],
            one=True,
        )
        if not row:
            return Response({'detail': 'Variante no encontrada'}, status=404)
        return Response(_load_variante(row['id'], include_costs=_can_view_costs(request)))

def _load_compra(compra_id, include_costs=False):
    head = q(
        '''
        SELECT p.id, p.supplier_id, s.name AS supplier_name,
               p.invoice_number, p.purchase_date, p.currency_code, p.fx_rate_ars,
               p.notes, p.created_by, p.created_at, p.updated_at,
               COALESCE(u.nombre,'') AS created_by_name
        FROM retail_purchases p
        JOIN retail_suppliers s ON s.id=p.supplier_id
        LEFT JOIN users u ON u.id=p.created_by
        WHERE p.id=%s
        ''',
        [compra_id],
        one=True,
    )
    if not head:
        return None
    items = q(
        '''
        SELECT pi.id, pi.purchase_id, pi.variant_id, pi.quantity,
               pi.unit_cost_currency, pi.unit_cost_ars, pi.suggested_markup_pct,
               pi.unit_price_suggested_ars, pi.unit_price_final_ars,
               pi.real_margin_pct, pi.line_total_ars,
               v.sku, v.barcode_internal, v.option_signature,
               rp.name AS producto
        FROM retail_purchase_items pi
        JOIN retail_product_variants v ON v.id=pi.variant_id
        JOIN retail_products rp ON rp.id=v.product_id
        WHERE pi.purchase_id=%s
        ORDER BY pi.id
        ''',
        [compra_id],
    ) or []
    if not include_costs:
        for item in items:
            item['unit_cost_currency'] = None
            item['unit_cost_ars'] = None
            item['suggested_markup_pct'] = None
            item['unit_price_suggested_ars'] = None
            item['unit_price_final_ars'] = None
            item['real_margin_pct'] = None
            item['line_total_ars'] = None
    head['items'] = items
    return head


class RetailComprasConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        row = q('SELECT purchase_default_markup_pct FROM retail_settings WHERE id=1', one=True) or {}
        markup = _to_decimal(row.get('purchase_default_markup_pct') or 100, 'purchase_default_markup_pct', allow_none=True) or Decimal('100')
        if markup < 0:
            markup = Decimal('100')
        return Response(
            {
                'purchase_default_markup_pct': markup.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'formula': 'markup_on_cost',
            }
        )


class RetailComprasProveedoresView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        search = _clean_text(request.query_params.get('q'))
        limit = _to_int(request.query_params.get('limit') or 100, 'limit', allow_none=True) or 100
        if limit <= 0:
            limit = 100
        limit = min(limit, 500)

        where_sql = ''
        params = []
        if search:
            where_sql = 'WHERE LOWER(s.name) LIKE %s'
            params.append(f'%{search.lower()}%')
        params.append(limit)

        rows = q(
            f'''
            SELECT s.id,
                   s.name,
                   s.active,
                   COUNT(p.id)::int AS purchases_count,
                   MAX(p.purchase_date) AS last_purchase_date
            FROM retail_suppliers s
            LEFT JOIN retail_purchases p ON p.supplier_id=s.id
            {where_sql}
            GROUP BY s.id, s.name, s.active
            ORDER BY LOWER(s.name), s.id
            LIMIT %s
            ''',
            params,
        ) or []
        return Response(rows)


class RetailComprasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}

        supplier_id = _to_int(data.get('supplier_id'), 'supplier_id', allow_none=True)
        supplier_name = _clean_text(data.get('supplier_name') or data.get('proveedor'))
        if not supplier_id and not supplier_name:
            raise ValidationError('supplier_id o supplier_name requerido')

        if not supplier_id:
            row = q('SELECT id FROM retail_suppliers WHERE LOWER(name)=LOWER(%s)', [supplier_name], one=True)
            if row:
                supplier_id = row['id']
            else:
                supplier_id = exec_returning(
                    'INSERT INTO retail_suppliers(name, active) VALUES (%s, TRUE) RETURNING id',
                    [supplier_name],
                )

        purchase_date = _clean_text(data.get('purchase_date') or data.get('fecha')) or timezone.localdate().isoformat()
        currency = (_clean_text(data.get('currency_code') or data.get('moneda')) or 'ARS').upper()
        if currency not in ('ARS', 'USD'):
            raise ValidationError('currency_code invalido (ARS/USD)')
        fx_rate = _to_decimal(data.get('fx_rate_ars') or data.get('tipo_cambio_ars'), 'fx_rate_ars', allow_none=True)
        if currency == 'USD' and (fx_rate is None or fx_rate <= 0):
            raise ValidationError('fx_rate_ars requerido para compras en USD')
        if currency == 'ARS':
            fx_rate = None

        items = data.get('items') or []
        if not isinstance(items, list) or not items:
            raise ValidationError('items requerido')
        cfg = q('SELECT purchase_default_markup_pct FROM retail_settings WHERE id=1', one=True) or {}
        suggested_markup_pct = _to_decimal(cfg.get('purchase_default_markup_pct') or 100, 'purchase_default_markup_pct', allow_none=True) or Decimal('100')
        if suggested_markup_pct < 0:
            suggested_markup_pct = Decimal('100')
        suggested_markup_pct = suggested_markup_pct.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        suggested_ratio = (Decimal('1.00') + (suggested_markup_pct / Decimal('100.00')))

        purchase_id = exec_returning(
            '''
            INSERT INTO retail_purchases(
              supplier_id, invoice_number, purchase_date, currency_code, fx_rate_ars, notes, created_by
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            ''',
            [
                supplier_id,
                _clean_text(data.get('invoice_number') or data.get('nro_comprobante')),
                purchase_date,
                currency,
                fx_rate,
                _clean_text(data.get('notes') or data.get('observaciones')),
                getattr(request.user, 'id', None),
            ],
        )

        for item in items:
            if not isinstance(item, dict):
                raise ValidationError('Cada item debe ser objeto')
            variant_id = _to_int(item.get('variant_id'), 'variant_id')
            qty = _to_int(item.get('quantity') or item.get('cantidad'), 'quantity')
            if qty <= 0:
                raise ValidationError('quantity debe ser mayor a 0')

            unit_cost_currency = _to_decimal(item.get('unit_cost_currency') or item.get('costo_unit_moneda') or item.get('costo_unitario'), 'unit_cost_currency')
            if unit_cost_currency < 0:
                raise ValidationError('unit_cost_currency no puede ser negativo')
            unit_cost_ars = unit_cost_currency if currency == 'ARS' else (unit_cost_currency * fx_rate)
            unit_cost_ars = unit_cost_ars.quantize(FOUR_DEC, rounding=ROUND_HALF_UP)
            unit_price_suggested_ars = (unit_cost_ars * suggested_ratio).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            unit_price_final_ars = _money(
                item.get('unit_price_final_ars')
                or item.get('precio_final_ars')
                or item.get('precio_final')
            )
            if unit_price_final_ars < 0:
                raise ValidationError('unit_price_final_ars no puede ser negativo')
            real_margin_pct = _safe_pct(unit_price_final_ars - unit_cost_ars, unit_cost_ars)
            line_total = (unit_cost_ars * Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)

            variant = q(
                'SELECT id, stock_on_hand, cost_avg_ars FROM retail_product_variants WHERE id=%s FOR UPDATE',
                [variant_id],
                one=True,
            )
            if not variant:
                raise ValidationError(f'Variante inexistente: {variant_id}')

            current_stock = int(variant['stock_on_hand'])
            current_cost = _to_decimal(variant.get('cost_avg_ars') or 0, 'cost_avg_ars')
            new_stock = current_stock + qty
            if new_stock <= 0:
                new_cost = unit_cost_ars
            else:
                weighted = (Decimal(current_stock) * current_cost) + (Decimal(qty) * unit_cost_ars)
                new_cost = (weighted / Decimal(new_stock)).quantize(FOUR_DEC, rounding=ROUND_HALF_UP)

            exec_void(
                '''
                INSERT INTO retail_purchase_items(
                  purchase_id, variant_id, quantity,
                  unit_cost_currency, unit_cost_ars, suggested_markup_pct,
                  unit_price_suggested_ars, unit_price_final_ars, real_margin_pct,
                  line_total_ars
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''',
                [
                    purchase_id,
                    variant_id,
                    qty,
                    unit_cost_currency,
                    unit_cost_ars,
                    suggested_markup_pct,
                    unit_price_suggested_ars,
                    unit_price_final_ars,
                    real_margin_pct,
                    line_total,
                ],
            )
            exec_void(
                'UPDATE retail_product_variants SET stock_on_hand=%s, cost_avg_ars=%s, price_store_ars=%s WHERE id=%s',
                [new_stock, new_cost, unit_price_final_ars, variant_id],
            )
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'purchase',%s,%s,%s,'purchase',%s,'Ingreso de mercaderia',%s)
                ''',
                [variant_id, qty, new_stock, unit_cost_ars, purchase_id, getattr(request.user, 'id', None)],
            )

        return Response(_load_compra(purchase_id, include_costs=True), status=201)


class RetailCompraDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, compra_id):
        _require_staff(request)
        row = _load_compra(compra_id, include_costs=_can_view_costs(request))
        if not row:
            return Response({'detail': 'Compra no encontrada'}, status=404)
        return Response(row)


def _cash_summary(session_id):
    rows = q(
        '''
        SELECT cm.direction, cm.payment_method, pa.code AS payment_account_code,
               COALESCE(pa.label,'') AS payment_account_label,
               SUM(cm.amount_ars)::numeric(14,2) AS total_ars
        FROM retail_cash_session_movements cm
        LEFT JOIN retail_payment_accounts pa ON pa.id=cm.payment_account_id
        WHERE cm.cash_session_id=%s
        GROUP BY cm.direction, cm.payment_method, pa.code, pa.label
        ORDER BY cm.direction, cm.payment_method, pa.code
        ''',
        [session_id],
    ) or []

    total_in = Decimal('0')
    total_out = Decimal('0')
    for row in rows:
        amount = _to_decimal(row.get('total_ars') or 0, 'total_ars')
        if row.get('direction') == 'out':
            total_out += amount
        else:
            total_in += amount
    return {
        'rows': rows,
        'expected_total_ars': (total_in - total_out).quantize(TWO_DEC, rounding=ROUND_HALF_UP),
    }


def _load_caja(caja_id):
    row = q(
        '''
        SELECT cs.*,
               COALESCE(uo.nombre,'') AS opened_by_name,
               COALESCE(uc.nombre,'') AS closed_by_name
        FROM retail_cash_sessions cs
        LEFT JOIN users uo ON uo.id=cs.opened_by
        LEFT JOIN users uc ON uc.id=cs.closed_by
        WHERE cs.id=%s
        ''',
        [caja_id],
        one=True,
    )
    if not row:
        return None
    row['summary'] = _cash_summary(caja_id)
    return row


class RetailCajaAperturaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        if _open_cash_session(lock=True):
            raise ValidationError('Ya hay una caja abierta')
        data = request.data or {}
        opening_amount = _money(data.get('opening_amount_cash_ars') or 0)
        caja_id = exec_returning(
            '''
            INSERT INTO retail_cash_sessions(
              status, opened_at, opened_by, opening_note, opening_amount_cash_ars
            )
            VALUES ('open', NOW(), %s, %s, %s)
            RETURNING id
            ''',
            [getattr(request.user, 'id', None), _clean_text(data.get('opening_note')), opening_amount],
        )
        cash_account = q('SELECT id FROM retail_payment_accounts WHERE code=\'cash\'', one=True)
        if opening_amount > 0:
            exec_void(
                '''
                INSERT INTO retail_cash_session_movements(
                  cash_session_id, movement_type, direction, payment_method,
                  payment_account_id, amount_ars, notes, created_by
                )
                VALUES (%s,'opening','in','cash',%s,%s,%s,%s)
                ''',
                [caja_id, cash_account['id'] if cash_account else None, opening_amount, 'Apertura de caja', getattr(request.user, 'id', None)],
            )
        return Response(_load_caja(caja_id), status=201)


class RetailCajaCierreView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        session = _open_cash_session(lock=True)
        if not session:
            raise ValidationError('No hay caja abierta')
        summary = _cash_summary(session['id'])
        data = request.data or {}
        counted_total = _to_decimal(data.get('closing_counted_total_ars'), 'closing_counted_total_ars', allow_none=True)
        expected_total = summary['expected_total_ars']
        diff = None
        if counted_total is not None:
            diff = (counted_total - expected_total).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        exec_void(
            '''
            UPDATE retail_cash_sessions
            SET status='closed',
                closed_at=NOW(),
                closed_by=%s,
                closing_note=%s,
                closing_expected_total_ars=%s,
                closing_counted_total_ars=%s,
                difference_total_ars=%s
            WHERE id=%s
            ''',
            [
                getattr(request.user, 'id', None),
                _clean_text(data.get('closing_note')),
                expected_total,
                counted_total,
                diff,
                session['id'],
            ],
        )
        return Response(_load_caja(session['id']))


class RetailCajaActualView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        row = _open_cash_session(lock=False)
        if not row:
            return Response({'open': False, 'session': None})
        return Response({'open': True, 'session': _load_caja(row['id'])})


class RetailCajaDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, caja_id):
        _require_staff(request)
        row = _load_caja(caja_id)
        if not row:
            return Response({'detail': 'Caja no encontrada'}, status=404)
        return Response(row)


class RetailCajaCuentasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        rows = q(
            '''
            SELECT id, code, label, payment_method, provider, active, sort_order
            FROM retail_payment_accounts
            WHERE active=TRUE
            ORDER BY sort_order, id
            '''
        ) or []
        return Response(rows)


def _parse_sales_query(request):
    since, until = _parse_dates(request)
    q_text = _clean_text(request.query_params.get('q'))
    channel = _clean_text(request.query_params.get('channel'))
    if channel:
        channel = channel.lower()
        if channel not in ('local', 'online'):
            raise ValidationError('channel invalido (local|online)')

    payment_method = _clean_text(request.query_params.get('payment_method'))
    if payment_method:
        payment_method = payment_method.lower()
        if payment_method not in ('cash', 'debit', 'transfer', 'credit'):
            raise ValidationError('payment_method invalido (cash|debit|transfer|credit)')

    statuses = []
    status_raw = _clean_text(request.query_params.get('status'))
    if status_raw:
        for token in status_raw.split(','):
            st = token.strip().lower()
            if not st:
                continue
            if st not in ('confirmed', 'cancelled', 'partial_return', 'returned'):
                raise ValidationError(f'estado invalido: {st}')
            statuses.append(st)

    limit = _to_int(request.query_params.get('limit') or 50, 'limit')
    offset = _to_int(request.query_params.get('offset') or 0, 'offset')

    return {
        'since': since,
        'until': until,
        'q': q_text,
        'channel': channel,
        'payment_method': payment_method,
        'statuses': statuses,
        'limit': max(1, min(limit, 500)),
        'offset': max(0, offset),
    }


class RetailVentasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        filters = _parse_sales_query(request)

        where = ['s.created_at::date BETWEEN %s AND %s']
        params = [filters['since'], filters['until']]

        if filters['q']:
            like = f"%{filters['q']}%"
            where.append(
                """
                (
                  s.sale_number ILIKE %s OR
                  COALESCE(s.source_order_id,'') ILIKE %s OR
                  COALESCE(s.customer_snapshot->>'name','') ILIKE %s
                )
                """
            )
            params.extend([like, like, like])

        if filters['channel']:
            where.append('s.channel=%s')
            params.append(filters['channel'])

        if filters['payment_method']:
            where.append('s.payment_method=%s')
            params.append(filters['payment_method'])

        if filters['statuses']:
            where.append('s.status = ANY(%s)')
            params.append(filters['statuses'])

        where_sql = ' AND '.join(where)

        rows = q(
            f'''
            SELECT s.id, s.sale_number, s.created_at, s.channel, s.status,
                   s.payment_method, s.total_ars, s.requires_invoice,
                   s.promotion_discount_total_ars, s.pricing_source,
                   COALESCE(pa.code,'') AS payment_account_code,
                   COALESCE(pa.label,'') AS payment_account_label,
                   COALESCE((s.customer_snapshot->>'name'),'') AS customer_name,
                   COALESCE(s.source_order_id,'') AS source_order_id,
                   COALESCE(u.nombre,'') AS created_by_name,
                   COALESCE(i.status,'not_required') AS invoice_status,
                   COALESCE((SELECT SUM(si.quantity) FROM retail_sale_items si WHERE si.sale_id=s.id),0)::int AS items_qty,
                   COALESCE((SELECT SUM(si.quantity - si.returned_qty) FROM retail_sale_items si WHERE si.sale_id=s.id),0)::int AS pending_return_qty
            FROM retail_sales s
            LEFT JOIN retail_payment_accounts pa ON pa.id=s.payment_account_id
            LEFT JOIN users u ON u.id=s.created_by
            LEFT JOIN retail_invoices i ON i.sale_id=s.id
            WHERE {where_sql}
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT %s OFFSET %s
            ''',
            [*params, filters['limit'], filters['offset']],
        ) or []

        total_row = q(
            f'''
            SELECT COUNT(*)::int AS cnt
            FROM retail_sales s
            WHERE {where_sql}
            ''',
            params,
            one=True,
        ) or {'cnt': 0}

        return Response(
            {
                'filters': {
                    'desde': filters['since'],
                    'hasta': filters['until'],
                    'q': filters['q'],
                    'channel': filters['channel'],
                    'payment_method': filters['payment_method'],
                    'status': filters['statuses'],
                },
                'paging': {
                    'limit': filters['limit'],
                    'offset': filters['offset'],
                    'total': int(total_row.get('cnt') or 0),
                },
                'rows': rows,
            }
        )


class RetailVentaDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, venta_id):
        _require_staff(request)
        row = _load_venta(venta_id, include_costs=_can_view_costs(request))
        if not row:
            return Response({'detail': 'Venta no encontrada'}, status=404)
        return Response(row)


class RetailGarantiaTicketView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, codigo):
        _require_staff(request)
        sale_id = _find_sale_by_ticket_code(codigo)
        if not sale_id:
            return Response({'detail': 'Ticket no encontrado'}, status=404)
        row = _load_venta(sale_id, include_costs=_can_view_costs(request))
        if not row:
            return Response({'detail': 'Ticket no encontrado'}, status=404)
        return Response({'query': _clean_text(codigo), 'sale': row, 'warranty': row.get('warranty')})


class RetailGarantiasActivasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        cfg = _load_settings()
        size_days = _warranty_days(cfg, 'return_warranty_size_days', 30)
        breakage_days = _warranty_days(cfg, 'return_warranty_breakage_days', 90)
        ticket_q = _clean_text(request.query_params.get('q'))
        warranty_type = (_clean_text(request.query_params.get('tipo')) or 'all').lower()
        if warranty_type not in ('all', 'size', 'breakage'):
            raise ValidationError('tipo invalido (all|size|breakage)')

        limit = _to_int(request.query_params.get('limit') or 50, 'limit')
        offset = _to_int(request.query_params.get('offset') or 0, 'offset')
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where = [
            "s.status <> 'cancelled'",
            '(COALESCE(pend.pending_qty,0) > 0)',
        ]
        params = []
        if ticket_q:
            like = f"%{ticket_q}%"
            where.append(
                '''
                (
                  s.sale_number ILIKE %s OR
                  COALESCE(s.source_order_id,'') ILIKE %s OR
                  COALESCE(s.customer_snapshot->>'name','') ILIKE %s
                )
                '''
            )
            params.extend([like, like, like])

        if warranty_type == 'size':
            where.append('(s.created_at::date + (%s * INTERVAL \'1 day\'))::date >= CURRENT_DATE')
            params.append(size_days)
        elif warranty_type == 'breakage':
            where.append('(s.created_at::date + (%s * INTERVAL \'1 day\'))::date >= CURRENT_DATE')
            params.append(breakage_days)
        else:
            where.append(
                '''
                (
                  (s.created_at::date + (%s * INTERVAL '1 day'))::date >= CURRENT_DATE
                  OR
                  (s.created_at::date + (%s * INTERVAL '1 day'))::date >= CURRENT_DATE
                )
                '''
            )
            params.extend([size_days, breakage_days])

        where_sql = ' AND '.join(where)

        rows = q(
            f'''
            SELECT s.id, s.sale_number, s.source_order_id, s.created_at, s.status, s.channel,
                   s.payment_method, s.total_ars,
                   COALESCE(pa.code,'') AS payment_account_code,
                   COALESCE(pa.label,'') AS payment_account_label,
                   COALESCE((s.customer_snapshot->>'name'),'') AS customer_name,
                   COALESCE(pend.pending_qty,0)::int AS pending_return_qty
            FROM retail_sales s
            LEFT JOIN retail_payment_accounts pa ON pa.id=s.payment_account_id
            LEFT JOIN (
              SELECT si.sale_id, SUM(si.quantity - si.returned_qty)::int AS pending_qty
              FROM retail_sale_items si
              GROUP BY si.sale_id
            ) pend ON pend.sale_id=s.id
            WHERE {where_sql}
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT %s OFFSET %s
            ''',
            [*params, limit, offset],
        ) or []
        for row in rows:
            row['warranty'] = _sale_warranty_info(row, sale_items=None, settings_row=cfg)

        total_row = q(
            f'''
            SELECT COUNT(*)::int AS cnt
            FROM retail_sales s
            LEFT JOIN (
              SELECT si.sale_id, SUM(si.quantity - si.returned_qty)::int AS pending_qty
              FROM retail_sale_items si
              GROUP BY si.sale_id
            ) pend ON pend.sale_id=s.id
            WHERE {where_sql}
            ''',
            params,
            one=True,
        ) or {'cnt': 0}

        return Response(
            {
                'filters': {
                    'q': ticket_q,
                    'tipo': warranty_type,
                },
                'paging': {
                    'limit': limit,
                    'offset': offset,
                    'total': int(total_row.get('cnt') or 0),
                },
                'rows': rows,
            }
        )


def _normalize_channel(raw):
    value = (_clean_text(raw) or 'local').lower()
    if value not in ('local', 'online'):
        raise ValidationError('channel invalido (local|online)')
    return value


def _normalize_payment_method(raw):
    value = (_clean_text(raw) or '').lower()
    if value not in PAYMENT_MODIFIERS:
        raise ValidationError('payment_method invalido (cash|debit|transfer|credit)')
    return value


def _normalize_pricing_source(raw, channel):
    value = (_clean_text(raw) or '').lower()
    if not value:
        return 'local_engine'
    if value not in PRICING_SOURCES:
        raise ValidationError('pricing_source invalido (local_engine|tiendanube)')
    if channel == 'local' and value != 'local_engine':
        raise ValidationError('pricing_source tiendanube solo aplica para canal online')
    return value


def _normalize_coupon_codes(payload):
    data = payload if isinstance(payload, dict) else {}
    out = []
    seen = set()

    def push(code):
        txt = _clean_text(code)
        if not txt:
            return
        for token in str(txt).split(','):
            t = token.strip()
            if not t:
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(t)

    push(data.get('coupon_code') or data.get('cupon'))
    many = data.get('coupon_codes')
    if isinstance(many, list):
        for item in many:
            push(item)
    elif many is not None:
        push(many)
    return out


def _load_active_promotions(channel, coupon_codes):
    coupon_keys = [str(c).strip().lower() for c in (coupon_codes or []) if _clean_text(c)]
    rows = q(
        '''
        SELECT p.*,
               COALESCE(pp.product_ids, ARRAY[]::BIGINT[]) AS product_ids,
               COALESCE(pv.variant_ids, ARRAY[]::BIGINT[]) AS variant_ids
        FROM retail_promotions p
        LEFT JOIN LATERAL (
          SELECT array_agg(rpp.product_id ORDER BY rpp.product_id) AS product_ids
          FROM retail_promotion_products rpp
          WHERE rpp.promotion_id=p.id
        ) pp ON TRUE
        LEFT JOIN LATERAL (
          SELECT array_agg(rpv.variant_id ORDER BY rpv.variant_id) AS variant_ids
          FROM retail_promotion_variants rpv
          WHERE rpv.promotion_id=p.id
        ) pv ON TRUE
        WHERE p.active=TRUE
          AND p.channel_scope IN ('both', %s)
          AND (p.valid_from IS NULL OR p.valid_from <= NOW())
          AND (p.valid_until IS NULL OR p.valid_until >= NOW())
          AND (
            p.activation_mode IN ('automatic', 'both')
            OR (
              p.activation_mode = 'coupon'
              AND LOWER(COALESCE(p.coupon_code,'')) = ANY(%s)
            )
          )
        ORDER BY p.priority ASC, p.id ASC
        ''',
        [channel, coupon_keys],
    ) or []

    out = []
    for row in rows:
        product_ids = row.get('product_ids') or []
        variant_ids = row.get('variant_ids') or []
        pids = set()
        vids = set()
        for pid in product_ids:
            try:
                pids.add(int(pid))
            except (TypeError, ValueError):
                continue
        for vid in variant_ids:
            try:
                vids.add(int(vid))
            except (TypeError, ValueError):
                continue
        out.append(
            {
                'id': int(row['id']),
                'name': _clean_text(row.get('name')) or f"Promo {int(row['id'])}",
                'promo_type': _clean_text(row.get('promo_type')) or PROMO_TYPE_PERCENT,
                'priority': int(row.get('priority') or 100),
                'coupon_code': _clean_text(row.get('coupon_code')),
                'combinable': bool(row.get('combinable')),
                'bogo_mode': _clean_text(row.get('bogo_mode')),
                'buy_qty': int(row.get('buy_qty') or 0),
                'pay_qty': int(row.get('pay_qty') or 0),
                'discount_pct': _to_decimal(row.get('discount_pct') or 0, 'discount_pct', allow_none=True) or Decimal('0'),
                'applies_to_all_products': bool(row.get('applies_to_all_products')),
                'product_ids': pids,
                'variant_ids': vids,
            }
        )
    return out


def _promo_matches_line(promo, line):
    ptype = (_clean_text(promo.get('promo_type')) or PROMO_TYPE_PERCENT).lower()
    bogo_mode = (_clean_text(promo.get('bogo_mode')) or '').lower()
    if ptype == PROMO_TYPE_X_FOR_Y and bogo_mode == 'mix':
        return True
    if ptype == PROMO_TYPE_X_FOR_Y and bogo_mode == 'sku':
        return int(line.get('variant_id') or 0) in (promo.get('variant_ids') or set())
    if bool(promo.get('applies_to_all_products')):
        return True
    return int(line.get('product_id') or 0) in (promo.get('product_ids') or set())


def _sync_line_price_state(line):
    qty = int(line.get('quantity') or 0)
    if qty <= 0:
        line['unit_price_current_ars'] = Decimal('0.00')
        return
    line_pre = _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    line['line_pre_modifier_ars'] = line_pre
    line['unit_price_current_ars'] = (line_pre / Decimal(qty)).quantize(FOUR_DEC, rounding=ROUND_HALF_UP)


def _build_promo_application(promo, total_discount, line_rows, metadata=None):
    total = _to_decimal(total_discount or 0, 'discount_amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    if total <= 0:
        return None
    return {
        'promotion_id': promo.get('id'),
        'source': 'local_engine',
        'promotion_name': promo.get('name') or '',
        'promo_type': promo.get('promo_type') or PROMO_TYPE_PERCENT,
        'priority': int(promo.get('priority') or 100),
        'coupon_code': _clean_text(promo.get('coupon_code')),
        'discount_amount_ars': total,
        'metadata': metadata or {},
        'lines': line_rows,
    }


def _apply_percent_promo(lines, promo):
    pct = _to_decimal(promo.get('discount_pct') or 0, 'discount_pct').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    if pct <= 0:
        return None

    total_discount = Decimal('0.00')
    line_rows = []
    for line in lines:
        if not _promo_matches_line(promo, line):
            continue
        eligible = max(0, int(line['quantity']) - int(line.get('locked_units') or 0))
        if eligible <= 0:
            continue
        unit = _to_decimal(line.get('unit_price_current_ars') or 0, 'unit_price_current_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP)
        if unit <= 0:
            continue

        line_discount = (unit * Decimal(eligible) * pct / Decimal('100.00')).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        cap = _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if line_discount > cap:
            line_discount = cap
        if line_discount <= 0:
            continue

        line['line_pre_modifier_ars'] = (cap - line_discount).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        line['promotion_discount_ars'] = (_to_decimal(line.get('promotion_discount_ars') or 0, 'promotion_discount_ars') + line_discount).quantize(
            TWO_DEC, rounding=ROUND_HALF_UP
        )
        if not bool(promo.get('combinable')):
            line['locked_units'] = min(int(line['quantity']), int(line.get('locked_units') or 0) + eligible)
        _sync_line_price_state(line)

        total_discount += line_discount
        line_rows.append(
            {
                'line_key': int(line['line_key']),
                'variant_id': int(line['variant_id']),
                'applied_qty': eligible,
                'discount_amount_ars': line_discount,
                'metadata': {'kind': 'percent_off', 'discount_pct': str(pct)},
            }
        )

    return _build_promo_application(
        promo,
        total_discount,
        line_rows,
        metadata={'kind': 'percent_off', 'discount_pct': str(pct)},
    )


def _apply_x_for_y_sku(lines, promo):
    buy_qty = int(promo.get('buy_qty') or 0)
    pay_qty = int(promo.get('pay_qty') or 0)
    if buy_qty <= 0 or pay_qty < 0 or pay_qty >= buy_qty:
        return None
    free_per_group = buy_qty - pay_qty
    total_discount = Decimal('0.00')
    line_rows = []

    for line in lines:
        if not _promo_matches_line(promo, line):
            continue
        eligible = max(0, int(line['quantity']) - int(line.get('locked_units') or 0))
        groups = eligible // buy_qty
        if groups <= 0:
            continue
        discount_units = groups * free_per_group
        participants = groups * buy_qty
        unit = _to_decimal(line.get('unit_price_current_ars') or 0, 'unit_price_current_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP)
        if unit <= 0:
            continue

        line_discount = (unit * Decimal(discount_units)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        cap = _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if line_discount > cap:
            line_discount = cap
        if line_discount <= 0:
            continue

        line['line_pre_modifier_ars'] = (cap - line_discount).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        line['promotion_discount_ars'] = (_to_decimal(line.get('promotion_discount_ars') or 0, 'promotion_discount_ars') + line_discount).quantize(
            TWO_DEC, rounding=ROUND_HALF_UP
        )
        if not bool(promo.get('combinable')):
            line['locked_units'] = min(int(line['quantity']), int(line.get('locked_units') or 0) + participants)
        _sync_line_price_state(line)

        total_discount += line_discount
        line_rows.append(
            {
                'line_key': int(line['line_key']),
                'variant_id': int(line['variant_id']),
                'applied_qty': discount_units,
                'discount_amount_ars': line_discount,
                'metadata': {'kind': 'x_for_y_sku', 'buy_qty': buy_qty, 'pay_qty': pay_qty, 'participants': participants},
            }
        )

    return _build_promo_application(
        promo,
        total_discount,
        line_rows,
        metadata={'kind': 'x_for_y_sku', 'buy_qty': buy_qty, 'pay_qty': pay_qty},
    )


def _apply_x_for_y_mix(lines, promo):
    buy_qty = int(promo.get('buy_qty') or 0)
    pay_qty = int(promo.get('pay_qty') or 0)
    if buy_qty <= 0 or pay_qty < 0 or pay_qty >= buy_qty:
        return None
    free_per_group = buy_qty - pay_qty

    unit_rows = []
    for line in lines:
        if not _promo_matches_line(promo, line):
            continue
        eligible = max(0, int(line['quantity']) - int(line.get('locked_units') or 0))
        if eligible <= 0:
            continue
        unit_price = _to_decimal(line.get('unit_price_current_ars') or 0, 'unit_price_current_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP)
        for _ in range(eligible):
            unit_rows.append({'line_key': int(line['line_key']), 'variant_id': int(line['variant_id']), 'unit_price': unit_price})

    total_units = len(unit_rows)
    groups = total_units // buy_qty
    if groups <= 0:
        return None

    discount_units = groups * free_per_group
    participants = groups * buy_qty
    unit_rows.sort(key=lambda row: (row['unit_price'], row['line_key'], row['variant_id']))
    discounted = unit_rows[:discount_units]
    involved = unit_rows[:participants]

    discount_by_line = {}
    discount_qty_by_line = {}
    involved_qty_by_line = {}

    for row in discounted:
        lk = int(row['line_key'])
        discount_by_line[lk] = (discount_by_line.get(lk) or Decimal('0.00')) + _to_decimal(row['unit_price'], 'unit_price')
        discount_qty_by_line[lk] = int(discount_qty_by_line.get(lk) or 0) + 1
    for row in involved:
        lk = int(row['line_key'])
        involved_qty_by_line[lk] = int(involved_qty_by_line.get(lk) or 0) + 1

    total_discount = Decimal('0.00')
    line_rows = []
    by_key = {int(line['line_key']): line for line in lines}
    for line_key, line_discount_raw in discount_by_line.items():
        line = by_key.get(int(line_key))
        if not line:
            continue
        line_discount = _to_decimal(line_discount_raw or 0, 'line_discount').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        cap = _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if line_discount > cap:
            line_discount = cap
        if line_discount <= 0:
            continue

        line['line_pre_modifier_ars'] = (cap - line_discount).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        line['promotion_discount_ars'] = (_to_decimal(line.get('promotion_discount_ars') or 0, 'promotion_discount_ars') + line_discount).quantize(
            TWO_DEC, rounding=ROUND_HALF_UP
        )
        if not bool(promo.get('combinable')):
            line['locked_units'] = min(
                int(line['quantity']),
                int(line.get('locked_units') or 0) + int(involved_qty_by_line.get(int(line_key)) or 0),
            )
        _sync_line_price_state(line)

        total_discount += line_discount
        line_rows.append(
            {
                'line_key': int(line['line_key']),
                'variant_id': int(line['variant_id']),
                'applied_qty': int(discount_qty_by_line.get(int(line_key)) or 0),
                'discount_amount_ars': line_discount,
                'metadata': {
                    'kind': 'x_for_y_mix',
                    'buy_qty': buy_qty,
                    'pay_qty': pay_qty,
                    'participants': int(involved_qty_by_line.get(int(line_key)) or 0),
                },
            }
        )

    return _build_promo_application(
        promo,
        total_discount,
        line_rows,
        metadata={'kind': 'x_for_y_mix', 'buy_qty': buy_qty, 'pay_qty': pay_qty},
    )


def _apply_local_promotions(lines, promotions):
    out = []
    for promo in promotions:
        ptype = _clean_text(promo.get('promo_type')) or PROMO_TYPE_PERCENT
        bogo_mode = _clean_text(promo.get('bogo_mode'))
        app = None
        if ptype == PROMO_TYPE_PERCENT:
            app = _apply_percent_promo(lines, promo)
        elif ptype == PROMO_TYPE_X_FOR_Y:
            if bogo_mode == 'mix':
                app = _apply_x_for_y_mix(lines, promo)
            else:
                app = _apply_x_for_y_sku(lines, promo)
        if app:
            out.append(app)
    return out


def _get_items(payload):
    items = payload.get('items') or []
    if not isinstance(items, list) or not items:
        raise ValidationError('items requerido')
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError('Cada item debe ser objeto')
        variant_id = _to_int(item.get('variant_id'), 'variant_id')
        qty = _to_int(item.get('quantity') or item.get('qty') or item.get('cantidad'), 'quantity')
        if qty <= 0:
            raise ValidationError('quantity debe ser mayor a 0')
        override = _to_decimal(item.get('unit_price_override_ars'), 'unit_price_override_ars', allow_none=True)
        unit_price_net = _to_decimal(
            item.get('unit_price_net_ars') or item.get('unit_price_paid_ars') or item.get('unit_price_external_ars'),
            'unit_price_net_ars',
            allow_none=True,
        )
        line_discount = _to_decimal(item.get('line_discount_ars'), 'line_discount_ars', allow_none=True)
        parsed.append(
            {
                'variant_id': variant_id,
                'quantity': qty,
                'unit_price_override_ars': override,
                'unit_price_net_ars': unit_price_net,
                'line_discount_ars': line_discount,
            }
        )
    return parsed


def _build_quote(request, payload, lock_variants=False):
    channel = _normalize_channel(payload.get('channel'))
    payment_method = _normalize_payment_method(payload.get('payment_method'))
    pricing_source = _normalize_pricing_source(payload.get('pricing_source'), channel)
    coupon_codes = _normalize_coupon_codes(payload)
    items = _get_items(payload)

    variants = {}
    for item in items:
        sql = 'SELECT * FROM retail_product_variants WHERE id=%s'
        if lock_variants:
            sql += ' FOR UPDATE'
        row = q(sql, [item['variant_id']], one=True)
        if not row:
            raise ValidationError(f"Variante inexistente: {item['variant_id']}")
        if not bool(row.get('active')):
            raise ValidationError(f"Variante inactiva: {item['variant_id']}")
        variants[item['variant_id']] = row

    modifier_pct = PAYMENT_MODIFIERS[payment_method] if pricing_source == 'local_engine' and channel == 'local' else Decimal('0.00')
    modifier_ratio = (Decimal('1.00') + (modifier_pct / Decimal('100.00')))

    subtotal = Decimal('0.00')
    lines = []
    any_override = False

    for idx, item in enumerate(items, start=1):
        variant = variants[item['variant_id']]
        qty = int(item['quantity'])
        if lock_variants and int(variant['stock_on_hand']) < qty:
            raise ValidationError(f"Stock insuficiente para variante {variant['id']}")

        list_price = _to_decimal(variant['price_store_ars'] if channel == 'local' else variant['price_online_ars'], 'price')
        if pricing_source == 'tiendanube':
            unit_price = _to_decimal(item.get('unit_price_net_ars'), 'unit_price_net_ars', allow_none=True) or list_price
        else:
            if item['unit_price_override_ars'] is not None:
                if not _can_override_price(request):
                    raise PermissionDenied('No autorizado para override de precio')
                unit_price = _to_decimal(item['unit_price_override_ars'], 'unit_price_override_ars')
                any_override = True
            else:
                unit_price = list_price

        line_subtotal = (unit_price * Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        subtotal += line_subtotal
        lines.append(
            {
                'line_key': idx,
                'variant_id': variant['id'],
                'product_id': variant['product_id'],
                'quantity': qty,
                'unit_price_list_ars': list_price.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_base_ars': unit_price.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_current_ars': unit_price.quantize(FOUR_DEC, rounding=ROUND_HALF_UP),
                'unit_cost_snapshot_ars': _to_decimal(variant.get('cost_avg_ars') or 0, 'cost_avg_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP),
                'line_subtotal_ars': line_subtotal,
                'line_pre_modifier_ars': line_subtotal,
                'line_total_ars': line_subtotal,
                'promotion_discount_ars': Decimal('0.00'),
                'locked_units': 0,
            }
        )

    subtotal = subtotal.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    applied_promotions = []
    if pricing_source == 'local_engine':
        promotions = _load_active_promotions(channel, coupon_codes)
        applied_promotions = _apply_local_promotions(lines, promotions)
    else:
        inferred_total = Decimal('0.00')
        promo_lines = []
        for line, src in zip(lines, items):
            explicit_discount = _to_decimal(src.get('line_discount_ars'), 'line_discount_ars', allow_none=True)
            if explicit_discount is None:
                list_total = (_to_decimal(line['unit_price_list_ars'], 'unit_price_list_ars') * Decimal(line['quantity'])).quantize(
                    TWO_DEC, rounding=ROUND_HALF_UP
                )
                explicit_discount = (list_total - _to_decimal(line['line_pre_modifier_ars'], 'line_pre_modifier_ars')).quantize(
                    TWO_DEC, rounding=ROUND_HALF_UP
                )
            if explicit_discount < 0:
                explicit_discount = Decimal('0.00')
            line['promotion_discount_ars'] = explicit_discount.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            line['line_subtotal_ars'] = (
                _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars') + line['promotion_discount_ars']
            ).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            if line['promotion_discount_ars'] > 0:
                inferred_total += line['promotion_discount_ars']
                promo_lines.append(
                    {
                        'line_key': int(line['line_key']),
                        'variant_id': int(line['variant_id']),
                        'applied_qty': int(line['quantity']),
                        'discount_amount_ars': line['promotion_discount_ars'],
                        'metadata': {'kind': 'external_line_discount'},
                    }
                )
        inferred_total = inferred_total.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if inferred_total > 0:
            applied_promotions.append(
                {
                    'promotion_id': None,
                    'source': 'tiendanube',
                    'promotion_name': 'Descuentos Tienda Nube',
                    'promo_type': PROMO_TYPE_EXTERNAL,
                    'priority': 100,
                    'coupon_code': ','.join(coupon_codes) if coupon_codes else None,
                    'discount_amount_ars': inferred_total,
                    'metadata': {'kind': 'tiendanube_external', 'coupon_codes': coupon_codes},
                    'lines': promo_lines,
                }
            )
        subtotal = Decimal('0.00')
        for line in lines:
            subtotal += _to_decimal(line.get('line_subtotal_ars') or 0, 'line_subtotal_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        subtotal = subtotal.quantize(TWO_DEC, rounding=ROUND_HALF_UP)

    promotion_discount_total = Decimal('0.00')
    total = Decimal('0.00')
    for line in lines:
        line_pre = _to_decimal(line.get('line_pre_modifier_ars') or 0, 'line_pre_modifier_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        promo_discount = _to_decimal(line.get('promotion_discount_ars') or 0, 'promotion_discount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if promo_discount < 0:
            promo_discount = Decimal('0.00')
        if promo_discount > _to_decimal(line['line_subtotal_ars'], 'line_subtotal_ars'):
            promo_discount = _to_decimal(line['line_subtotal_ars'], 'line_subtotal_ars')
        line['promotion_discount_ars'] = promo_discount
        line['line_pre_modifier_ars'] = line_pre
        line_total = (line_pre * modifier_ratio).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        line['line_total_ars'] = line_total
        line['unit_price_final_ars'] = (
            line_total / Decimal(max(1, int(line['quantity'])))
        ).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        promotion_discount_total += promo_discount
        total += line_total

    promotion_discount_total = promotion_discount_total.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    subtotal_after_promotions = (subtotal - promotion_discount_total).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    if subtotal_after_promotions < 0:
        subtotal_after_promotions = Decimal('0.00')
    total = total.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    modifier_amount = (total - subtotal_after_promotions).quantize(TWO_DEC, rounding=ROUND_HALF_UP)

    out_lines = []
    for line in lines:
        out_lines.append(
            {
                'line_key': int(line['line_key']),
                'variant_id': int(line['variant_id']),
                'quantity': int(line['quantity']),
                'unit_price_list_ars': _to_decimal(line['unit_price_list_ars'], 'unit_price_list_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_base_ars': _to_decimal(line['unit_price_base_ars'], 'unit_price_base_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_final_ars': _to_decimal(line['unit_price_final_ars'], 'unit_price_final_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_cost_snapshot_ars': _to_decimal(line['unit_cost_snapshot_ars'], 'unit_cost_snapshot_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP),
                'line_subtotal_ars': _to_decimal(line['line_subtotal_ars'], 'line_subtotal_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'promotion_discount_ars': _to_decimal(line['promotion_discount_ars'], 'promotion_discount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'line_total_ars': _to_decimal(line['line_total_ars'], 'line_total_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
            }
        )

    promo_out = []
    for promo in applied_promotions:
        promo_out.append(
            {
                'promotion_id': promo.get('promotion_id'),
                'source': promo.get('source') or 'local_engine',
                'promotion_name': promo.get('promotion_name') or '',
                'promo_type': promo.get('promo_type') or PROMO_TYPE_PERCENT,
                'priority': int(promo.get('priority') or 100),
                'coupon_code': _clean_text(promo.get('coupon_code')),
                'discount_amount_ars': _to_decimal(promo.get('discount_amount_ars') or 0, 'discount_amount_ars').quantize(
                    TWO_DEC, rounding=ROUND_HALF_UP
                ),
                'metadata': promo.get('metadata') or {},
                'lines': promo.get('lines') or [],
            }
        )

    return {
        'channel': channel,
        'payment_method': payment_method,
        'pricing_source': pricing_source,
        'coupon_codes': coupon_codes,
        'modifier_pct': modifier_pct,
        'modifier_amount_ars': modifier_amount,
        'subtotal_ars': subtotal,
        'promotion_discount_total_ars': promotion_discount_total,
        'subtotal_after_promotions_ars': subtotal_after_promotions,
        'total_ars': total,
        'invoice_required': payment_method in INVOICE_REQUIRED_METHODS,
        'items': out_lines,
        'applied_promotions': promo_out,
        'any_override': any_override,
    }


def _persist_sale_promotions(sale_id, quote, persisted_items):
    applied_promotions = (quote or {}).get('applied_promotions') or []
    if not applied_promotions:
        return
    item_by_line_key = {}
    for row in persisted_items or []:
        try:
            item_by_line_key[int(row.get('line_key'))] = int(row.get('sale_item_id'))
        except (TypeError, ValueError):
            continue

    for promo in applied_promotions:
        amount = _to_decimal(promo.get('discount_amount_ars') or 0, 'discount_amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        ptype = (_clean_text(promo.get('promo_type')) or PROMO_TYPE_PERCENT).lower()
        if ptype not in (PROMO_TYPE_PERCENT, PROMO_TYPE_X_FOR_Y, PROMO_TYPE_EXTERNAL):
            ptype = PROMO_TYPE_EXTERNAL
        source = (_clean_text(promo.get('source')) or 'local_engine').lower()
        if source not in ('local_engine', 'tiendanube'):
            source = 'local_engine'

        sale_promo_id = exec_returning(
            '''
            INSERT INTO retail_sale_promotion_applications(
              sale_id, promotion_id, source, promotion_name, promo_type,
              priority, coupon_code, discount_amount_ars, metadata
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            RETURNING id
            ''',
            [
                sale_id,
                _to_int(promo.get('promotion_id'), 'promotion_id', allow_none=True),
                source,
                _clean_text(promo.get('promotion_name')) or 'Promocion',
                ptype,
                _to_int(promo.get('priority'), 'priority', allow_none=True) or 100,
                _clean_text(promo.get('coupon_code')),
                amount,
                json.dumps(promo.get('metadata') or {}, ensure_ascii=False),
            ],
        )

        for line in promo.get('lines') or []:
            line_key = _to_int(line.get('line_key'), 'line_key', allow_none=True)
            sale_item_id = item_by_line_key.get(int(line_key or 0))
            if not sale_item_id:
                continue
            applied_qty = _to_int(line.get('applied_qty') if line.get('applied_qty') is not None else 0, 'applied_qty')
            if applied_qty < 0:
                applied_qty = 0
            line_discount = _to_decimal(line.get('discount_amount_ars') or 0, 'discount_amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            if line_discount < 0:
                line_discount = Decimal('0.00')
            exec_void(
                '''
                INSERT INTO retail_sale_item_promotion_applications(
                  sale_item_id, sale_promotion_application_id, promotion_id, source,
                  applied_qty, discount_amount_ars, metadata
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                ''',
                [
                    sale_item_id,
                    sale_promo_id,
                    _to_int(promo.get('promotion_id'), 'promotion_id', allow_none=True),
                    source,
                    applied_qty,
                    line_discount,
                    json.dumps(line.get('metadata') or {}, ensure_ascii=False),
                ],
            )


def _coerce_local_date(value):
    if isinstance(value, dt.datetime):
        if timezone.is_naive(value):
            return value.date()
        return timezone.localtime(value).date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return timezone.localdate()
        try:
            return dt.datetime.fromisoformat(raw.replace('Z', '+00:00')).date()
        except ValueError:
            pass
        try:
            return dt.date.fromisoformat(raw[:10])
        except ValueError:
            return timezone.localdate()
    return timezone.localdate()


def _warranty_days(settings_row, key, fallback):
    raw = settings_row.get(key) if isinstance(settings_row, dict) else None
    try:
        days = int(raw or fallback)
    except (TypeError, ValueError):
        days = int(fallback)
    return max(1, days)


def _sale_warranty_info(sale_row, sale_items=None, settings_row=None):
    settings_data = settings_row or _load_settings()
    size_days = _warranty_days(settings_data, 'return_warranty_size_days', 30)
    breakage_days = _warranty_days(settings_data, 'return_warranty_breakage_days', 90)
    purchase_date = _coerce_local_date(sale_row.get('created_at'))
    today = timezone.localdate()
    size_expires = purchase_date + dt.timedelta(days=size_days)
    breakage_expires = purchase_date + dt.timedelta(days=breakage_days)

    pending_qty = 0
    if isinstance(sale_items, list):
        for item in sale_items:
            qty = int(item.get('quantity') or 0)
            returned = int(item.get('returned_qty') or 0)
            pending_qty += max(0, qty - returned)
    else:
        pending_qty = max(0, int(sale_row.get('pending_return_qty') or 0))

    is_cancelled = (sale_row.get('status') or '').strip().lower() == 'cancelled'
    has_pending_items = (pending_qty > 0) and (not is_cancelled)
    size_active = has_pending_items and today <= size_expires
    breakage_active = has_pending_items and today <= breakage_expires

    return {
        'purchase_date': purchase_date.isoformat(),
        'today': today.isoformat(),
        'pending_qty': pending_qty,
        'has_pending_items': has_pending_items,
        'size': {
            'days': size_days,
            'expires_on': size_expires.isoformat(),
            'days_left': (size_expires - today).days,
            'active': bool(size_active),
        },
        'breakage': {
            'days': breakage_days,
            'expires_on': breakage_expires.isoformat(),
            'days_left': (breakage_expires - today).days,
            'active': bool(breakage_active),
        },
        'any_active': bool(size_active or breakage_active),
    }


def _warranty_active_for_type(warranty_info, warranty_type):
    if warranty_type == 'size':
        return bool((warranty_info.get('size') or {}).get('active'))
    if warranty_type == 'breakage':
        return bool((warranty_info.get('breakage') or {}).get('active'))
    return bool(warranty_info.get('any_active'))


def _normalize_warranty_type(raw, default='none'):
    value = (_clean_text(raw) or default).strip().lower()
    if value not in ('none', 'size', 'breakage'):
        raise ValidationError('warranty_type invalido (none|size|breakage)')
    return value


def _find_sale_by_ticket_code(code):
    code_text = _clean_text(code)
    if not code_text:
        return None

    sale = q(
        'SELECT id FROM retail_sales WHERE LOWER(sale_number)=LOWER(%s) ORDER BY id DESC LIMIT 1',
        [code_text],
        one=True,
    )
    if sale:
        return int(sale['id'])

    sale = q(
        '''
        SELECT id
        FROM retail_sales
        WHERE source_order_id IS NOT NULL
          AND LOWER(source_order_id)=LOWER(%s)
        ORDER BY id DESC
        LIMIT 1
        ''',
        [code_text],
        one=True,
    )
    if sale:
        return int(sale['id'])

    if code_text.isdigit():
        sale = q('SELECT id FROM retail_sales WHERE id=%s', [int(code_text)], one=True)
        if sale:
            return int(sale['id'])
    return None


def _load_venta(venta_id, include_costs=False, warranty_settings=None):
    sale = q(
        '''
        SELECT s.*, COALESCE(pa.code,'') AS payment_account_code,
               COALESCE(pa.label,'') AS payment_account_label,
               COALESCE(u.nombre,'') AS created_by_name
        FROM retail_sales s
        LEFT JOIN retail_payment_accounts pa ON pa.id=s.payment_account_id
        LEFT JOIN users u ON u.id=s.created_by
        WHERE s.id=%s
        ''',
        [venta_id],
        one=True,
    )
    if not sale:
        return None

    items = q(
        '''
        SELECT si.*, v.sku, v.barcode_internal, v.option_signature, v.product_id,
               p.name AS producto, COALESCE(p.brand,'') AS marca
        FROM retail_sale_items si
        JOIN retail_product_variants v ON v.id=si.variant_id
        JOIN retail_products p ON p.id=v.product_id
        WHERE si.sale_id=%s
        ORDER BY si.id
        ''',
        [venta_id],
    ) or []
    if not include_costs:
        for item in items:
            item['unit_cost_snapshot_ars'] = None

    invoice = q('SELECT * FROM retail_invoices WHERE sale_id=%s', [venta_id], one=True)
    promos = q(
        '''
        SELECT *
        FROM retail_sale_promotion_applications
        WHERE sale_id=%s
        ORDER BY priority, id
        ''',
        [venta_id],
    ) or []
    promo_item_rows = q(
        '''
        SELECT sipa.*
        FROM retail_sale_item_promotion_applications sipa
        JOIN retail_sale_items si ON si.id=sipa.sale_item_id
        WHERE si.sale_id=%s
        ORDER BY sipa.id
        ''',
        [venta_id],
    ) or []
    promo_items_by_sale_item = {}
    for row in promo_item_rows:
        sid = int(row.get('sale_item_id') or 0)
        promo_items_by_sale_item.setdefault(sid, []).append(row)
    promo_items_by_promo = {}
    for row in promo_item_rows:
        pid = row.get('sale_promotion_application_id')
        if pid is None:
            continue
        try:
            promo_items_by_promo.setdefault(int(pid), []).append(row)
        except (TypeError, ValueError):
            continue

    for item in items:
        item['promotion_applications'] = promo_items_by_sale_item.get(int(item.get('id') or 0), [])

    for promo in promos:
        promo['items'] = promo_items_by_promo.get(int(promo.get('id') or 0), [])

    exchanges = q(
        '''
        SELECT e.*, COALESCE(u.nombre,'') AS processed_by_name
        FROM retail_exchanges e
        LEFT JOIN users u ON u.id=e.processed_by
        WHERE e.sale_id=%s
        ORDER BY e.id DESC
        ''',
        [venta_id],
    ) or []
    exchange_items = q(
        '''
        SELECT ei.*, vf.sku AS variant_from_sku, vt.sku AS variant_to_sku,
               pf.name AS product_from_name, pt.name AS product_to_name
        FROM retail_exchange_items ei
        JOIN retail_product_variants vf ON vf.id=ei.variant_from_id
        JOIN retail_product_variants vt ON vt.id=ei.variant_to_id
        JOIN retail_products pf ON pf.id=vf.product_id
        JOIN retail_products pt ON pt.id=vt.product_id
        JOIN retail_exchanges e ON e.id=ei.exchange_id
        WHERE e.sale_id=%s
        ORDER BY ei.id
        ''',
        [venta_id],
    ) or []
    ex_items_by_exchange = {}
    for item in exchange_items:
        ex_items_by_exchange.setdefault(int(item.get('exchange_id') or 0), []).append(item)
    for exchange in exchanges:
        exchange['items'] = ex_items_by_exchange.get(int(exchange.get('id') or 0), [])

    payments = _load_sale_payments(venta_id, fallback_sale=sale)
    sale['items'] = items
    sale['invoice'] = invoice
    sale['promotions'] = promos
    sale['exchanges'] = exchanges
    sale['payments'] = payments
    sale['warranty'] = _sale_warranty_info(sale, sale_items=items, settings_row=warranty_settings)
    return sale


def _sale_items_have_x_for_y_promos(sale_item_ids):
    ids = []
    for sid in sale_item_ids or []:
        try:
            ids.append(int(sid))
        except (TypeError, ValueError):
            continue
    if not ids:
        return False
    row = q(
        '''
        SELECT COUNT(*)::int AS cnt
        FROM retail_sale_item_promotion_applications sipa
        JOIN retail_sale_promotion_applications spa ON spa.id=sipa.sale_promotion_application_id
        WHERE sipa.sale_item_id = ANY(%s)
          AND spa.promo_type='x_for_y'
        ''',
        [ids],
        one=True,
    ) or {'cnt': 0}
    return int(row.get('cnt') or 0) > 0


def _register_cash_in(session_id, sale_row, user_id, note='Venta mostrador'):
    sale_id = _to_int(sale_row.get('id'), 'sale_id')
    payments = _load_sale_payments(sale_id, fallback_sale=sale_row)
    splits = _split_amount_across_payments(payments, sale_row.get('total_ars') or 0)
    for split in splits:
        payment = split['payment']
        method = _normalize_payment_method(payment.get('payment_method') or payment.get('method'))
        account_id = _to_int(payment.get('payment_account_id') or payment.get('account_id'), 'payment_account_id')
        amount = _to_decimal(split.get('amount_ars') or 0, 'amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        exec_void(
            '''
            INSERT INTO retail_cash_session_movements(
              cash_session_id, movement_type, direction, payment_method,
              payment_account_id, amount_ars, reference_type, reference_id, notes, created_by
            )
            VALUES (%s,'sale','in',%s,%s,%s,'sale',%s,%s,%s)
            ''',
            [
                session_id,
                method,
                account_id,
                amount,
                sale_id,
                note,
                user_id,
            ],
        )


def _register_cash_out(
    session_id,
    sale_row,
    user_id,
    movement_type='return',
    note='Egreso por devolucion',
    amount_ars=None,
    reference_type='sale',
    reference_id=None,
):
    sale_id = _to_int(sale_row.get('id'), 'sale_id')
    target_amount = _to_decimal(
        amount_ars if amount_ars is not None else sale_row.get('total_ars') or 0,
        'amount_ars',
    ).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    if target_amount <= 0:
        return

    payments = _load_sale_payments(sale_id, fallback_sale=sale_row)
    splits = _split_amount_across_payments(payments, target_amount)
    ref_id = _to_int(reference_id, 'reference_id', allow_none=True) if reference_id is not None else sale_id
    for split in splits:
        payment = split['payment']
        method = _normalize_payment_method(payment.get('payment_method') or payment.get('method'))
        account_id = _to_int(payment.get('payment_account_id') or payment.get('account_id'), 'payment_account_id')
        amount = _to_decimal(split.get('amount_ars') or 0, 'amount_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        exec_void(
            '''
            INSERT INTO retail_cash_session_movements(
              cash_session_id, movement_type, direction, payment_method,
              payment_account_id, amount_ars, reference_type, reference_id, notes, created_by
            )
            VALUES (%s,%s,'out',%s,%s,%s,%s,%s,%s,%s)
            ''',
            [
                session_id,
                movement_type,
                method,
                account_id,
                amount,
                _clean_text(reference_type) or 'sale',
                ref_id,
                note,
                user_id,
            ],
        )


def _confirm_sale_from_payload(request, payload):
    data = payload or {}
    quote = _build_quote(request, data, lock_variants=True)
    payments, primary_payment = _normalize_payments(data, quote)
    channel = quote['channel']

    cash_session_id = None
    if channel == 'local':
        open_session = _open_cash_session(lock=True)
        if not open_session:
            raise ValidationError('Debe abrir caja antes de vender en mostrador')
        cash_session_id = open_session['id']

    override_reason = _clean_text(data.get('price_override_reason'))
    if quote['any_override'] and not override_reason:
        raise ValidationError('price_override_reason requerido cuando hay override de precio')

    customer_snapshot = {
        'name': _clean_text(data.get('customer_name')),
        'doc': _clean_text(data.get('customer_doc')),
        'email': _clean_text(data.get('customer_email')),
    }

    sale_id = exec_returning(
        '''
        INSERT INTO retail_sales(
          sale_number, channel, status, payment_method, payment_account_id, cash_session_id,
          customer_snapshot, subtotal_ars, promotion_discount_total_ars, price_adjustment_pct, price_adjustment_amount_ars,
          total_ars, currency_code, requires_invoice, notes, source_order_id,
          pricing_source, price_override_by, price_override_reason, created_by
        )
        VALUES (
          'PENDIENTE', %s, 'confirmed', %s, %s, %s,
          %s, %s, %s, %s, %s,
          %s, 'ARS', %s, %s, %s, %s,
          %s, %s, %s
        )
        RETURNING id
        ''',
        [
            channel,
            primary_payment['method'],
            primary_payment['account_id'],
            cash_session_id,
            json.dumps(customer_snapshot),
            quote['subtotal_ars'],
            quote.get('promotion_discount_total_ars') or 0,
            quote['modifier_pct'],
            quote['modifier_amount_ars'],
            quote['total_ars'],
            quote['invoice_required'],
            _clean_text(data.get('notes')),
            _clean_text(data.get('source_order_id')),
            quote.get('pricing_source') or 'local_engine',
            getattr(request.user, 'id', None) if quote['any_override'] else None,
            override_reason,
            getattr(request.user, 'id', None),
        ],
    )
    exec_void('UPDATE retail_sales SET sale_number=%s WHERE id=%s', [_sale_number(sale_id), sale_id])

    persisted_items = []
    for line in quote['items']:
        variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [line['variant_id']], one=True)
        new_stock = int(variant['stock_on_hand']) - int(line['quantity'])
        if new_stock < 0:
            raise ValidationError(f"Stock insuficiente para variante {line['variant_id']}")

        sale_item_id = exec_returning(
            '''
            INSERT INTO retail_sale_items(
              sale_id, variant_id, quantity,
              unit_price_list_ars, unit_price_final_ars, promotion_discount_ars, unit_cost_snapshot_ars,
              line_subtotal_ars, line_total_ars
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            ''',
            [
                sale_id,
                line['variant_id'],
                line['quantity'],
                line['unit_price_list_ars'],
                line['unit_price_final_ars'],
                line.get('promotion_discount_ars') or 0,
                line['unit_cost_snapshot_ars'],
                line['line_subtotal_ars'],
                line['line_total_ars'],
            ],
        )
        persisted_items.append({'line_key': line.get('line_key'), 'sale_item_id': sale_item_id})
        exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, line['variant_id']])
        exec_void(
            '''
            INSERT INTO retail_stock_movements(
              variant_id, movement_kind, qty_signed, stock_after,
              cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
            )
            VALUES (%s,%s,%s,%s,%s,'sale',%s,'Descuento por venta',%s)
            ''',
            [
                line['variant_id'],
                'sale' if channel == 'local' else 'online_sale',
                -int(line['quantity']),
                new_stock,
                line['unit_cost_snapshot_ars'],
                sale_id,
                getattr(request.user, 'id', None),
            ],
        )

    _persist_sale_promotions(sale_id, quote, persisted_items)
    _persist_sale_payments(sale_id, payments)

    if quote['invoice_required']:
        exec_void(
            '''
            INSERT INTO retail_invoices(sale_id, status, invoice_mode, amount_total_ars)
            VALUES (%s,'pending','arca',%s)
            ON CONFLICT (sale_id) DO NOTHING
            ''',
            [sale_id, quote['total_ars']],
        )
    else:
        exec_void(
            '''
            INSERT INTO retail_invoices(sale_id, status, invoice_mode, amount_total_ars)
            VALUES (%s,'not_required','internal',%s)
            ON CONFLICT (sale_id) DO NOTHING
            ''',
            [sale_id, quote['total_ars']],
        )

    sale_full = _load_venta(sale_id, include_costs=True)
    if channel == 'local' and cash_session_id:
        _register_cash_in(cash_session_id, sale_full, getattr(request.user, 'id', None))

    auto_emit = bool(data.get('auto_emit_invoice'))
    if auto_emit and quote['invoice_required']:
        _emitir_factura(sale_id, request)

    return _load_venta(sale_id, include_costs=_can_view_costs(request))


class RetailVentasCotizarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _require_staff(request)
        quote = _build_quote(request, request.data or {}, lock_variants=False)
        items = []
        for line in quote['items']:
            out = dict(line)
            if not _can_view_costs(request):
                out['unit_cost_snapshot_ars'] = None
            items.append(out)
        return Response(
            {
                'channel': quote['channel'],
                'payment_method': quote['payment_method'],
                'pricing_source': quote['pricing_source'],
                'coupon_codes': quote.get('coupon_codes') or [],
                'price_modifier_pct': quote['modifier_pct'],
                'modifier_amount_ars': quote['modifier_amount_ars'],
                'subtotal_ars': quote['subtotal_ars'],
                'promotion_discount_total_ars': quote.get('promotion_discount_total_ars') or 0,
                'subtotal_after_promotions_ars': quote.get('subtotal_after_promotions_ars') or quote['subtotal_ars'],
                'total_ars': quote['total_ars'],
                'invoice_required': quote['invoice_required'],
                'items': items,
                'applied_promotions': quote.get('applied_promotions') or [],
            }
        )


class RetailVentasConfirmarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        sale = _confirm_sale_from_payload(request, data)
        return Response(sale, status=201)


POS_DRAFT_INLINE_FIELDS = {
    'channel',
    'payment_method',
    'payment_account_id',
    'payment_account_code',
    'customer_name',
    'customer_doc',
    'customer_email',
    'notes',
    'coupon_codes',
    'price_override_reason',
    'auto_emit_invoice',
    'source_order_id',
    'pricing_source',
    'items',
    'payments',
}


def _normalize_pos_draft_status(raw, allow_all=False):
    value = (_clean_text(raw) or '').lower()
    if allow_all and value == 'all':
        return 'all'
    if not value:
        value = 'open'
    if value not in ('open', 'confirmed', 'cancelled'):
        raise ValidationError('status invalido (open|confirmed|cancelled)')
    return value


def _extract_inline_draft_payload(data):
    out = {}
    for key in POS_DRAFT_INLINE_FIELDS:
        if key in data:
            out[key] = data.get(key)
    return out


def _extract_pos_draft_payload(data, allow_missing=False):
    if not isinstance(data, dict):
        if allow_missing:
            return False, {}
        raise ValidationError('Payload invalido')

    provided = False
    payload = {}
    if 'payload' in data:
        provided = True
        payload = data.get('payload') or {}
        if not isinstance(payload, dict):
            raise ValidationError('payload debe ser objeto')
    else:
        payload = _extract_inline_draft_payload(data)
        provided = bool(payload)

    if not provided and allow_missing:
        return False, {}

    if 'items' in payload and not isinstance(payload.get('items'), list):
        raise ValidationError('payload.items debe ser lista')
    if 'payments' in payload and payload.get('payments') is not None and not isinstance(payload.get('payments'), list):
        raise ValidationError('payload.payments debe ser lista')
    return provided, payload


def _extract_pos_draft_quote_snapshot(data, allow_missing=True):
    if not isinstance(data, dict):
        if allow_missing:
            return False, {}
        raise ValidationError('Payload invalido')
    if 'quote_snapshot' not in data:
        if allow_missing:
            return False, {}
        raise ValidationError('quote_snapshot requerido')
    value = data.get('quote_snapshot') or {}
    if not isinstance(value, dict):
        raise ValidationError('quote_snapshot debe ser objeto')
    return True, value


def _draft_channel(payload):
    raw = _clean_text((payload or {}).get('channel')) or 'local'
    channel = raw.lower()
    return channel if channel in ('local', 'online') else 'local'


def _draft_item_count(payload):
    items = (payload or {}).get('items')
    if not isinstance(items, list):
        return 0
    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            qty = int(item.get('quantity') or item.get('qty') or 0)
        except (TypeError, ValueError):
            qty = 0
        total += max(0, qty)
    return total


def _draft_total_ars(payload, quote_snapshot):
    q_total = None
    if isinstance(quote_snapshot, dict):
        q_total = quote_snapshot.get('total_ars')
    if q_total is None and isinstance(payload, dict):
        q_total = payload.get('total_ars')
    if q_total is None:
        return Decimal('0.00')
    return _money(q_total).quantize(TWO_DEC, rounding=ROUND_HALF_UP)


def _draft_customer_snapshot(payload):
    data = payload or {}
    return {
        'name': _clean_text(data.get('customer_name')),
        'doc': _clean_text(data.get('customer_doc')),
        'email': _clean_text(data.get('customer_email')),
    }


def _load_pos_draft(draft_id, lock=False):
    did = _to_int(draft_id, 'draft_id')
    sql = '''
        SELECT d.*,
               COALESCE(uc.nombre,'') AS created_by_name,
               COALESCE(uu.nombre,'') AS updated_by_name,
               COALESCE(s.sale_number,'') AS confirmed_sale_number
        FROM retail_pos_drafts d
        LEFT JOIN users uc ON uc.id=d.created_by
        LEFT JOIN users uu ON uu.id=d.updated_by
        LEFT JOIN retail_sales s ON s.id=d.confirmed_sale_id
        WHERE d.id=%s
    '''
    if lock:
        sql += ' FOR UPDATE'
    row = q(sql, [did], one=True)
    if not row:
        return None
    row['customer_snapshot'] = _json(row.get('customer_snapshot')) or {}
    row['payload'] = _json(row.get('payload')) or {}
    row['quote_snapshot'] = _json(row.get('quote_snapshot')) or {}
    return row


class RetailPosDraftsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        status = _normalize_pos_draft_status(request.query_params.get('status'), allow_all=True)
        qtxt = _clean_text(request.query_params.get('q'))
        limit = _to_int(request.query_params.get('limit') or 50, 'limit')
        limit = max(1, min(limit, 200))

        where = []
        params = []
        if status != 'all':
            where.append('d.status=%s')
            params.append(status)
        if qtxt:
            like = f'%{qtxt}%'
            where.append(
                '''
                (
                  d.draft_number ILIKE %s OR
                  COALESCE(d.name,'') ILIKE %s OR
                  COALESCE(d.customer_snapshot->>'name','') ILIKE %s
                )
                '''
            )
            params.extend([like, like, like])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ''

        rows = q(
            f'''
            SELECT d.id, d.draft_number, d.status, d.channel, d.name,
                   d.item_count, d.total_ars, d.last_activity_at, d.created_at, d.updated_at,
                   d.confirmed_sale_id, COALESCE(s.sale_number,'') AS confirmed_sale_number,
                   COALESCE(d.customer_snapshot->>'name','') AS customer_name,
                   COALESCE(u.nombre,'') AS created_by_name
            FROM retail_pos_drafts d
            LEFT JOIN retail_sales s ON s.id=d.confirmed_sale_id
            LEFT JOIN users u ON u.id=d.created_by
            {where_sql}
            ORDER BY d.last_activity_at DESC, d.id DESC
            LIMIT %s
            ''',
            [*params, limit],
        ) or []
        return Response({'rows': rows})

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        _, payload = _extract_pos_draft_payload(data, allow_missing=True)
        _, quote_snapshot = _extract_pos_draft_quote_snapshot(data, allow_missing=True)
        status = _normalize_pos_draft_status(data.get('status') or 'open')
        if status == 'confirmed':
            raise ValidationError('No se puede crear un draft confirmado')

        channel = _draft_channel(payload)
        customer_snapshot = _draft_customer_snapshot(payload)
        item_count = _draft_item_count(payload)
        total_ars = _draft_total_ars(payload, quote_snapshot)
        name = _clean_text(data.get('name') or data.get('draft_name'))
        user_id = getattr(request.user, 'id', None)

        draft_id = exec_returning(
            '''
            INSERT INTO retail_pos_drafts(
              draft_number, status, channel, name, customer_snapshot,
              payload, quote_snapshot, item_count, total_ars,
              last_activity_at, created_by, updated_by
            )
            VALUES (
              'PENDIENTE', %s, %s, %s, %s::jsonb,
              %s::jsonb, %s::jsonb, %s, %s,
              NOW(), %s, %s
            )
            RETURNING id
            ''',
            [
                status,
                channel,
                name,
                json.dumps(customer_snapshot, ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
                json.dumps(quote_snapshot, ensure_ascii=False),
                item_count,
                total_ars,
                user_id,
                user_id,
            ],
        )
        exec_void('UPDATE retail_pos_drafts SET draft_number=%s WHERE id=%s', [_draft_number(draft_id), draft_id])
        return Response(_load_pos_draft(draft_id), status=201)


class RetailPosDraftDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, draft_id):
        _require_staff(request)
        row = _load_pos_draft(draft_id, lock=False)
        if not row:
            return Response({'detail': 'Draft no encontrado'}, status=404)
        return Response(row)

    @transaction.atomic
    def patch(self, request, draft_id):
        _require_staff(request)
        _set_audit_user(request)
        row = _load_pos_draft(draft_id, lock=True)
        if not row:
            return Response({'detail': 'Draft no encontrado'}, status=404)
        if row.get('status') == 'confirmed':
            raise ValidationError('No se puede editar un draft confirmado')

        data = request.data or {}
        fields = []
        params = []

        if 'name' in data or 'draft_name' in data:
            fields.append('name=%s')
            params.append(_clean_text(data.get('name') or data.get('draft_name')))

        if 'status' in data:
            next_status = _normalize_pos_draft_status(data.get('status'))
            if next_status == 'confirmed':
                raise ValidationError('Usa /confirm para confirmar un draft')
            fields.append('status=%s')
            params.append(next_status)

        payload_provided, payload_data = _extract_pos_draft_payload(data, allow_missing=True)
        quote_provided, quote_data = _extract_pos_draft_quote_snapshot(data, allow_missing=True)

        payload = row.get('payload') or {}
        quote_snapshot = row.get('quote_snapshot') or {}
        if payload_provided:
            payload = payload_data
            fields.append('payload=%s::jsonb')
            params.append(json.dumps(payload, ensure_ascii=False))
        if quote_provided:
            quote_snapshot = quote_data
            fields.append('quote_snapshot=%s::jsonb')
            params.append(json.dumps(quote_snapshot, ensure_ascii=False))

        if payload_provided or quote_provided:
            fields.append('channel=%s')
            params.append(_draft_channel(payload))
            fields.append('customer_snapshot=%s::jsonb')
            params.append(json.dumps(_draft_customer_snapshot(payload), ensure_ascii=False))
            fields.append('item_count=%s')
            params.append(_draft_item_count(payload))
            fields.append('total_ars=%s')
            params.append(_draft_total_ars(payload, quote_snapshot))

        fields.append('last_activity_at=NOW()')
        fields.append('updated_by=%s')
        params.append(getattr(request.user, 'id', None))

        params.append(_to_int(draft_id, 'draft_id'))
        exec_void(f"UPDATE retail_pos_drafts SET {', '.join(fields)} WHERE id=%s", params)
        return Response(_load_pos_draft(draft_id))


class RetailPosDraftConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, draft_id):
        _require_staff(request)
        _set_audit_user(request)
        row = _load_pos_draft(draft_id, lock=True)
        if not row:
            return Response({'detail': 'Draft no encontrado'}, status=404)
        if row.get('status') != 'open':
            raise ValidationError('Solo se puede confirmar un draft abierto')

        data = request.data or {}
        payload = dict(row.get('payload') or {})
        payload_provided, payload_updates = _extract_pos_draft_payload(data, allow_missing=True)
        if payload_provided:
            payload.update(payload_updates)

        if not isinstance(payload.get('items'), list) or not payload.get('items'):
            raise ValidationError('El draft no tiene items para confirmar')

        sale = _confirm_sale_from_payload(request, payload)
        quote_snapshot = data.get('quote_snapshot') if isinstance(data.get('quote_snapshot'), dict) else row.get('quote_snapshot')
        if not isinstance(quote_snapshot, dict):
            quote_snapshot = {}
        exec_void(
            '''
            UPDATE retail_pos_drafts
            SET status='confirmed',
                payload=%s::jsonb,
                quote_snapshot=%s::jsonb,
                item_count=%s,
                total_ars=%s,
                customer_snapshot=%s::jsonb,
                channel=%s,
                confirmed_sale_id=%s,
                confirmed_at=NOW(),
                last_activity_at=NOW(),
                updated_by=%s
            WHERE id=%s
            ''',
            [
                json.dumps(payload, ensure_ascii=False),
                json.dumps(quote_snapshot, ensure_ascii=False),
                _draft_item_count(payload),
                _draft_total_ars(payload, quote_snapshot),
                json.dumps(_draft_customer_snapshot(payload), ensure_ascii=False),
                _draft_channel(payload),
                sale['id'],
                getattr(request.user, 'id', None),
                _to_int(draft_id, 'draft_id'),
            ],
        )
        return Response({'draft': _load_pos_draft(draft_id), 'sale': sale}, status=201)


class RetailVentaAnularView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, venta_id):
        _require_staff(request)
        _set_audit_user(request)
        sale = q('SELECT * FROM retail_sales WHERE id=%s FOR UPDATE', [venta_id], one=True)
        if not sale:
            return Response({'detail': 'Venta no encontrada'}, status=404)
        if sale['status'] == 'cancelled':
            return Response(_load_venta(venta_id, include_costs=_can_view_costs(request)))

        items = q('SELECT * FROM retail_sale_items WHERE sale_id=%s FOR UPDATE', [venta_id]) or []
        if any(int(it.get('returned_qty') or 0) > 0 for it in items):
            raise ValidationError('No se puede anular una venta con devoluciones registradas')

        for item in items:
            variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [item['variant_id']], one=True)
            new_stock = int(variant['stock_on_hand']) + int(item['quantity'])
            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, item['variant_id']])
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'cancel_sale',%s,%s,%s,'sale',%s,%s,%s)
                ''',
                [
                    item['variant_id'],
                    int(item['quantity']),
                    new_stock,
                    item['unit_cost_snapshot_ars'],
                    venta_id,
                    _clean_text((request.data or {}).get('reason')) or 'Anulacion de venta',
                    getattr(request.user, 'id', None),
                ],
            )

        exec_void(
            '''
            UPDATE retail_sales
            SET status='cancelled', cancelled_at=NOW(), cancelled_by=%s, cancel_reason=%s
            WHERE id=%s
            ''',
            [getattr(request.user, 'id', None), _clean_text((request.data or {}).get('reason')), venta_id],
        )

        invoice = q('SELECT id, status FROM retail_invoices WHERE sale_id=%s FOR UPDATE', [venta_id], one=True)
        if invoice:
            if invoice['status'] == 'authorized':
                exec_void(
                    "UPDATE retail_invoices SET status='manual_review', error_message='Venta anulada luego de autorizacion', updated_at=NOW() WHERE id=%s",
                    [invoice['id']],
                )
            elif invoice['status'] in ('pending', 'retry', 'rejected'):
                exec_void("UPDATE retail_invoices SET status='retry', updated_at=NOW() WHERE id=%s", [invoice['id']])

        if sale['channel'] == 'local' and sale.get('cash_session_id'):
            _register_cash_out(sale['cash_session_id'], sale, getattr(request.user, 'id', None), movement_type='manual_adjustment', note='Anulacion de venta')

        return Response(_load_venta(venta_id, include_costs=_can_view_costs(request)))

class RetailVentaDevolverView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, venta_id):
        _require_staff(request)
        _set_audit_user(request)
        sale = q('SELECT * FROM retail_sales WHERE id=%s FOR UPDATE', [venta_id], one=True)
        if not sale:
            return Response({'detail': 'Venta no encontrada'}, status=404)
        if sale['status'] == 'cancelled':
            raise ValidationError('No se puede devolver una venta anulada')

        sale_items = q('SELECT * FROM retail_sale_items WHERE sale_id=%s FOR UPDATE', [venta_id]) or []
        by_item = {int(item['id']): item for item in sale_items}
        exchanged_rows = q(
            '''
            SELECT ei.sale_item_id, COALESCE(SUM(ei.quantity),0)::int AS exchanged_qty
            FROM retail_exchange_items ei
            JOIN retail_exchanges e ON e.id=ei.exchange_id
            WHERE e.sale_id=%s AND e.status='confirmed'
            GROUP BY ei.sale_item_id
            ''',
            [venta_id],
        ) or []
        exchanged_by_item = {int(row['sale_item_id']): int(row.get('exchanged_qty') or 0) for row in exchanged_rows}

        data = request.data or {}
        return_items = data.get('items')
        parsed = []
        warranty_type = _normalize_warranty_type(data.get('warranty_type'), default='none')
        override_out_of_warranty = bool(data.get('override_out_of_warranty'))
        override_reason = _clean_text(data.get('override_reason'))

        if return_items:
            if not isinstance(return_items, list):
                raise ValidationError('items debe ser una lista')
            for item in return_items:
                if not isinstance(item, dict):
                    raise ValidationError('Cada item de devolucion debe ser objeto')
                sale_item_id = _to_int(item.get('sale_item_id'), 'sale_item_id')
                qty = _to_int(item.get('quantity') or item.get('cantidad'), 'quantity')
                if qty <= 0:
                    raise ValidationError('quantity invalida')
                if sale_item_id not in by_item:
                    raise ValidationError(f'sale_item_id no pertenece a la venta: {sale_item_id}')
                parsed.append({'sale_item_id': sale_item_id, 'quantity': qty})
        else:
            for item in sale_items:
                already_exchanged = int(exchanged_by_item.get(int(item['id'])) or 0)
                available = int(item['quantity']) - int(item['returned_qty']) - already_exchanged
                if available > 0:
                    parsed.append({'sale_item_id': int(item['id']), 'quantity': available})

        if not parsed:
            raise ValidationError('No hay lineas disponibles para devolver')

        if _sale_items_have_x_for_y_promos([it['sale_item_id'] for it in parsed]):
            raise ValidationError('Las lineas con promociones 2x1/3x2 no admiten devolucion monetaria. Usa cambio 1:1.')

        warranty_info = _sale_warranty_info(sale, sale_items=sale_items)
        warranty_in_window = _warranty_active_for_type(warranty_info, warranty_type)
        if not warranty_in_window:
            if not override_out_of_warranty:
                raise ValidationError('Venta fuera de garantia para el tipo seleccionado')
            if not _can_override_return_warranty(request):
                raise PermissionDenied('No autorizado para override de garantia')
            if not override_reason:
                raise ValidationError('override_reason requerido para override de garantia')

        warranty_snapshot = {
            'checked_at': timezone.now().isoformat(),
            'selected_type': warranty_type,
            'override_requested': override_out_of_warranty,
            'override_reason': override_reason,
            'in_window': warranty_in_window,
            'warranty': warranty_info,
        }

        requires_credit_note = bool(sale.get('requires_invoice'))
        rid = exec_returning(
            '''
            INSERT INTO retail_returns(
              sale_id, status, reason, processed_by,
              total_refund_ars, requires_credit_note, credit_note_status,
              warranty_type, warranty_override, warranty_snapshot
            )
            VALUES (%s,'confirmed',%s,%s,0,%s,%s,%s,%s,%s::jsonb)
            RETURNING id
            ''',
            [
                venta_id,
                _clean_text(data.get('reason')) or 'Devolucion',
                getattr(request.user, 'id', None),
                requires_credit_note,
                'pending' if requires_credit_note else 'not_required',
                warranty_type,
                bool(override_out_of_warranty and (not warranty_in_window)),
                json.dumps(warranty_snapshot),
            ],
        )

        total_refund = Decimal('0.00')
        all_returned = True

        for item in parsed:
            sale_item = by_item[item['sale_item_id']]
            already_exchanged = int(exchanged_by_item.get(int(sale_item['id'])) or 0)
            available = int(sale_item['quantity']) - int(sale_item['returned_qty']) - already_exchanged
            qty = int(item['quantity'])
            if qty > available:
                raise ValidationError(f"Cantidad a devolver excede disponible en item {sale_item['id']}")

            variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [sale_item['variant_id']], one=True)
            new_stock = int(variant['stock_on_hand']) + qty
            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, sale_item['variant_id']])
            exec_void('UPDATE retail_sale_items SET returned_qty=returned_qty+%s WHERE id=%s', [qty, sale_item['id']])

            line_refund = (_to_decimal(sale_item['unit_price_final_ars'], 'unit_price_final_ars') * Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            total_refund += line_refund
            exec_void(
                '''
                INSERT INTO retail_return_items(
                  return_id, sale_item_id, variant_id, quantity,
                  unit_price_refund_ars, unit_cost_snapshot_ars, line_refund_total_ars
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ''',
                [
                    rid,
                    sale_item['id'],
                    sale_item['variant_id'],
                    qty,
                    sale_item['unit_price_final_ars'],
                    sale_item['unit_cost_snapshot_ars'],
                    line_refund,
                ],
            )
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'return',%s,%s,%s,'return',%s,'Devolucion de venta',%s)
                ''',
                [
                    sale_item['variant_id'],
                    qty,
                    new_stock,
                    sale_item['unit_cost_snapshot_ars'],
                    rid,
                    getattr(request.user, 'id', None),
                ],
            )

            pending_after = available - qty
            if pending_after > 0:
                all_returned = False

        total_refund = total_refund.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        remaining = q(
            'SELECT COUNT(*)::int AS cnt FROM retail_sale_items WHERE sale_id=%s AND returned_qty < quantity',
            [venta_id],
            one=True,
        ) or {'cnt': 0}
        all_returned = int(remaining.get('cnt') or 0) == 0
        sale_status = 'returned' if all_returned else 'partial_return'
        exec_void('UPDATE retail_sales SET status=%s WHERE id=%s', [sale_status, venta_id])
        exec_void('UPDATE retail_returns SET total_refund_ars=%s WHERE id=%s', [total_refund, rid])

        if sale['channel'] == 'local' and sale.get('cash_session_id'):
            _register_cash_out(
                sale['cash_session_id'],
                sale,
                getattr(request.user, 'id', None),
                movement_type='return',
                note='Devolucion en caja',
                amount_ars=total_refund,
                reference_type='return',
                reference_id=rid,
            )

        if requires_credit_note:
            exec_void(
                '''
                INSERT INTO retail_invoice_credit_notes(
                  sale_id, return_id, status, amount_total_ars, created_by
                )
                VALUES (%s,%s,'pending',%s,%s)
                ''',
                [venta_id, rid, total_refund, getattr(request.user, 'id', None)],
            )

        ret = q(
            '''
            SELECT r.*, COALESCE(u.nombre,'') AS processed_by_name
            FROM retail_returns r
            LEFT JOIN users u ON u.id=r.processed_by
            WHERE r.id=%s
            ''',
            [rid],
            one=True,
        )
        ret_items = q('SELECT * FROM retail_return_items WHERE return_id=%s ORDER BY id', [rid]) or []
        ret['items'] = ret_items
        ret['sale'] = _load_venta(venta_id, include_costs=_can_view_costs(request))
        return Response(ret, status=201)


class RetailVentaCambiarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, venta_id):
        _require_staff(request)
        _set_audit_user(request)
        if not _can_exchange_sale(request):
            raise PermissionDenied('No autorizado para registrar cambios 1:1')

        sale = q('SELECT * FROM retail_sales WHERE id=%s FOR UPDATE', [venta_id], one=True)
        if not sale:
            return Response({'detail': 'Venta no encontrada'}, status=404)
        if sale['status'] == 'cancelled':
            raise ValidationError('No se puede cambiar una venta anulada')

        sale_items = q('SELECT * FROM retail_sale_items WHERE sale_id=%s FOR UPDATE', [venta_id]) or []
        by_item = {int(item['id']): item for item in sale_items}

        exchanged_rows = q(
            '''
            SELECT ei.sale_item_id, COALESCE(SUM(ei.quantity),0)::int AS exchanged_qty
            FROM retail_exchange_items ei
            JOIN retail_exchanges e ON e.id=ei.exchange_id
            WHERE e.sale_id=%s AND e.status='confirmed'
            GROUP BY ei.sale_item_id
            ''',
            [venta_id],
        ) or []
        exchanged_by_item = {int(row['sale_item_id']): int(row.get('exchanged_qty') or 0) for row in exchanged_rows}

        data = request.data or {}
        raw_items = data.get('items')
        if not isinstance(raw_items, list) or not raw_items:
            raise ValidationError('items debe ser una lista no vacia')

        parsed = []
        for row in raw_items:
            if not isinstance(row, dict):
                raise ValidationError('Cada item de cambio debe ser objeto')
            sale_item_id = _to_int(row.get('sale_item_id'), 'sale_item_id')
            replacement_variant_id = _to_int(row.get('replacement_variant_id') or row.get('variant_id') or row.get('to_variant_id'), 'replacement_variant_id')
            qty = _to_int(row.get('quantity') or row.get('cantidad'), 'quantity')
            if qty <= 0:
                raise ValidationError('quantity invalida')
            if sale_item_id not in by_item:
                raise ValidationError(f'sale_item_id no pertenece a la venta: {sale_item_id}')
            parsed.append({'sale_item_id': sale_item_id, 'replacement_variant_id': replacement_variant_id, 'quantity': qty})

        warranty_type = _normalize_warranty_type(data.get('warranty_type'), default='none')
        override_out_of_warranty = bool(data.get('override_out_of_warranty'))
        override_reason = _clean_text(data.get('override_reason'))
        warranty_info = _sale_warranty_info(sale, sale_items=sale_items)
        warranty_in_window = _warranty_active_for_type(warranty_info, warranty_type)
        if not warranty_in_window:
            if not override_out_of_warranty:
                raise ValidationError('Venta fuera de garantia para el tipo seleccionado')
            if not _can_override_return_warranty(request):
                raise PermissionDenied('No autorizado para override de garantia')
            if not override_reason:
                raise ValidationError('override_reason requerido para override de garantia')

        warranty_snapshot = {
            'checked_at': timezone.now().isoformat(),
            'selected_type': warranty_type,
            'override_requested': override_out_of_warranty,
            'override_reason': override_reason,
            'in_window': warranty_in_window,
            'warranty': warranty_info,
        }

        exchange_id = exec_returning(
            '''
            INSERT INTO retail_exchanges(
              sale_id, status, reason, processed_by, warranty_type, warranty_override, warranty_snapshot
            )
            VALUES (%s,'confirmed',%s,%s,%s,%s,%s::jsonb)
            RETURNING id
            ''',
            [
                venta_id,
                _clean_text(data.get('reason')) or 'Cambio 1:1',
                getattr(request.user, 'id', None),
                warranty_type,
                bool(override_out_of_warranty and (not warranty_in_window)),
                json.dumps(warranty_snapshot),
            ],
        )

        for item in parsed:
            sale_item = by_item[item['sale_item_id']]
            already_exchanged = int(exchanged_by_item.get(int(sale_item['id'])) or 0)
            available = int(sale_item['quantity']) - int(sale_item['returned_qty']) - already_exchanged
            qty = int(item['quantity'])
            if qty > available:
                raise ValidationError(f"Cantidad a cambiar excede disponible en item {sale_item['id']}")

            variant_from = q(
                '''
                SELECT v.id, v.product_id, v.price_store_ars, v.price_online_ars, v.stock_on_hand
                FROM retail_product_variants v
                WHERE v.id=%s
                FOR UPDATE
                ''',
                [sale_item['variant_id']],
                one=True,
            )
            variant_to = q(
                '''
                SELECT v.id, v.product_id, v.price_store_ars, v.price_online_ars, v.stock_on_hand, v.active
                FROM retail_product_variants v
                WHERE v.id=%s
                FOR UPDATE
                ''',
                [item['replacement_variant_id']],
                one=True,
            )
            if not variant_to:
                raise ValidationError(f"Variante de reemplazo inexistente: {item['replacement_variant_id']}")
            if not bool(variant_to.get('active')):
                raise ValidationError(f"Variante de reemplazo inactiva: {item['replacement_variant_id']}")
            if int(variant_from['product_id']) != int(variant_to['product_id']):
                raise ValidationError('El cambio 1:1 exige variante del mismo producto (talle/color)')

            price_field = 'price_store_ars' if (sale.get('channel') or 'local') == 'local' else 'price_online_ars'
            from_price = _to_decimal(variant_from.get(price_field), price_field).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            to_price = _to_decimal(variant_to.get(price_field), price_field).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            if from_price != to_price:
                raise ValidationError('El cambio 1:1 exige mismo precio de lista por canal')

            new_stock_from = int(variant_from['stock_on_hand']) + qty
            new_stock_to = int(variant_to['stock_on_hand']) - qty
            if new_stock_to < 0:
                raise ValidationError(f"Stock insuficiente en variante de reemplazo {variant_to['id']}")

            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock_from, variant_from['id']])
            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock_to, variant_to['id']])

            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'manual_adjustment',%s,%s,%s,'exchange',%s,%s,%s)
                ''',
                [
                    variant_from['id'],
                    qty,
                    new_stock_from,
                    sale_item.get('unit_cost_snapshot_ars'),
                    exchange_id,
                    'Cambio 1:1 ingreso variante original',
                    getattr(request.user, 'id', None),
                ],
            )
            exec_void(
                '''
                INSERT INTO retail_stock_movements(
                  variant_id, movement_kind, qty_signed, stock_after,
                  cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                )
                VALUES (%s,'manual_adjustment',%s,%s,%s,'exchange',%s,%s,%s)
                ''',
                [
                    variant_to['id'],
                    -qty,
                    new_stock_to,
                    sale_item.get('unit_cost_snapshot_ars'),
                    exchange_id,
                    'Cambio 1:1 egreso variante reemplazo',
                    getattr(request.user, 'id', None),
                ],
            )
            exec_void(
                '''
                INSERT INTO retail_exchange_items(
                  exchange_id, sale_item_id, variant_from_id, variant_to_id, quantity,
                  unit_price_from_ars, unit_price_to_ars
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ''',
                [
                    exchange_id,
                    sale_item['id'],
                    variant_from['id'],
                    variant_to['id'],
                    qty,
                    _to_decimal(sale_item.get('unit_price_final_ars') or 0, 'unit_price_final_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    _to_decimal(sale_item.get('unit_price_final_ars') or 0, 'unit_price_final_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                ],
            )

        exchange = q(
            '''
            SELECT e.*, COALESCE(u.nombre,'') AS processed_by_name
            FROM retail_exchanges e
            LEFT JOIN users u ON u.id=e.processed_by
            WHERE e.id=%s
            ''',
            [exchange_id],
            one=True,
        ) or {}
        exchange['items'] = q(
            '''
            SELECT ei.*, vf.sku AS variant_from_sku, vt.sku AS variant_to_sku,
                   pf.name AS product_from_name, pt.name AS product_to_name
            FROM retail_exchange_items ei
            JOIN retail_product_variants vf ON vf.id=ei.variant_from_id
            JOIN retail_product_variants vt ON vt.id=ei.variant_to_id
            JOIN retail_products pf ON pf.id=vf.product_id
            JOIN retail_products pt ON pt.id=vt.product_id
            WHERE ei.exchange_id=%s
            ORDER BY ei.id
            ''',
            [exchange_id],
        ) or []
        exchange['sale'] = _load_venta(venta_id, include_costs=_can_view_costs(request))
        return Response(exchange, status=201)


def _mock_enabled():
    val = str(getattr(settings, 'ARCA_WSFE_MOCK', '1')).strip().lower()
    return val in ('1', 'true', 'yes', 'on')


def _emitir_factura(venta_id, request):
    with transaction.atomic():
        sale = q('SELECT * FROM retail_sales WHERE id=%s FOR UPDATE', [venta_id], one=True)
        if not sale:
            raise ValidationError('Venta no encontrada')

        invoice = q('SELECT * FROM retail_invoices WHERE sale_id=%s FOR UPDATE', [venta_id], one=True)
        if not invoice:
            mode = 'internal' if not bool(sale.get('requires_invoice')) else 'arca'
            status = 'not_required' if mode == 'internal' else 'pending'
            iid = exec_returning(
                '''
                INSERT INTO retail_invoices(sale_id, status, invoice_mode, amount_total_ars)
                VALUES (%s,%s,%s,%s)
                RETURNING id
                ''',
                [venta_id, status, mode, sale.get('total_ars') or 0],
            )
            invoice = q('SELECT * FROM retail_invoices WHERE id=%s FOR UPDATE', [iid], one=True)

        if invoice['invoice_mode'] == 'internal' or invoice['status'] == 'not_required':
            return _load_venta(venta_id, include_costs=_can_view_costs(request))

        if invoice['status'] == 'authorized':
            return _load_venta(venta_id, include_costs=_can_view_costs(request))

        cfg = _load_settings()
        payload = {
            'sale_id': venta_id,
            'total_ars': str(sale.get('total_ars') or 0),
            'payment_method': sale.get('payment_method'),
            'channel': sale.get('channel'),
            'arca_env': cfg['arca_env'],
            'issued_at': timezone.now().isoformat(),
        }

        attempts = int(invoice.get('attempts') or 0) + 1
        if _mock_enabled():
            cae = f"{random.randint(10000000000000, 99999999999999)}"
            out = {
                'status': 'authorized',
                'cae': cae,
                'cbte_nro': (invoice.get('cbte_nro') or 0) + 1,
                'response': {'mock': True, 'cae': cae},
            }
        else:
            ws_url = _clean_text(getattr(settings, 'ARCA_WSFE_URL', ''))
            if not ws_url:
                out = {
                    'status': 'retry',
                    'error_message': 'ARCA_WSFE_URL no configurado para modo real',
                    'response': {'ok': False, 'reason': 'missing_ws_url'},
                }
            else:
                try:
                    resp = requests.post(ws_url, json=payload, timeout=25)
                    status_code = int(resp.status_code)
                    body = resp.text
                    if 200 <= status_code < 300:
                        parsed = _json(body)
                        cae = _clean_text(parsed.get('cae'))
                        if cae:
                            out = {
                                'status': 'authorized',
                                'cae': cae,
                                'cbte_nro': parsed.get('cbte_nro') or (invoice.get('cbte_nro') or 0) + 1,
                                'response': parsed,
                            }
                        else:
                            out = {
                                'status': 'retry',
                                'error_message': 'Respuesta ARCA sin CAE',
                                'response': {'raw': body[:2000]},
                            }
                    else:
                        out = {
                            'status': 'retry',
                            'error_message': f'ARCA HTTP {status_code}',
                            'response': {'raw': body[:2000]},
                        }
                except Exception as exc:
                    out = {
                        'status': 'retry',
                        'error_message': str(exc),
                        'response': {'exception': str(exc)},
                    }

        exec_void(
            '''
            UPDATE retail_invoices
            SET status=%s,
                cae=%s,
                cbte_nro=%s,
                pto_vta=%s,
                amount_total_ars=%s,
                request_payload=%s,
                response_payload=%s,
                error_message=%s,
                attempts=%s,
                last_attempt_at=NOW(),
                updated_at=NOW()
            WHERE id=%s
            ''',
            [
                out.get('status') or 'retry',
                out.get('cae'),
                out.get('cbte_nro'),
                cfg['arca_pto_vta_online'] if sale.get('channel') == 'online' else cfg['arca_pto_vta_store'],
                sale.get('total_ars') or 0,
                json.dumps(payload),
                json.dumps(out.get('response') or {}),
                out.get('error_message'),
                attempts,
                invoice['id'],
            ],
        )

        if out.get('status') in ('retry', 'rejected'):
            _create_job('arca', 'invoice_issue', {'sale_id': venta_id}, status='pending', last_error=out.get('error_message'))

    return _load_venta(venta_id, include_costs=_can_view_costs(request))


def _emitir_nota_credito(venta_id, request):
    with transaction.atomic():
        sale = q('SELECT * FROM retail_sales WHERE id=%s FOR UPDATE', [venta_id], one=True)
        if not sale:
            raise ValidationError('Venta no encontrada')

        rows = q(
            '''
            SELECT cn.*
            FROM retail_invoice_credit_notes cn
            WHERE cn.sale_id=%s AND cn.status IN ('pending','retry')
            ORDER BY cn.id
            FOR UPDATE
            ''',
            [venta_id],
        ) or []
        if not rows:
            raise ValidationError('No hay notas de credito pendientes para esta venta')

        for row in rows:
            if _mock_enabled():
                status = 'authorized'
                cae = f"{random.randint(10000000000000, 99999999999999)}"
                response_payload = {'mock': True, 'cae': cae}
                error_message = None
            else:
                status = 'retry'
                cae = None
                response_payload = {'ok': False, 'detail': 'Implementar envio real WSFEv1 nota credito'}
                error_message = 'Integracion real de nota de credito pendiente'
                _create_job('arca', 'credit_note_issue', {'credit_note_id': row['id']}, status='pending', last_error=error_message)

            exec_void(
                '''
                UPDATE retail_invoice_credit_notes
                SET status=%s,
                    cae=%s,
                    cbte_nro=COALESCE(cbte_nro,0)+1,
                    response_payload=%s,
                    error_message=%s,
                    attempts=attempts+1,
                    updated_at=NOW()
                WHERE id=%s
                ''',
                [status, cae, json.dumps(response_payload), error_message, row['id']],
            )
            if row.get('return_id'):
                exec_void(
                    'UPDATE retail_returns SET credit_note_status=%s, updated_at=NOW() WHERE id=%s',
                    ['issued' if status == 'authorized' else 'manual_review', row['return_id']],
                )

    out = q(
        'SELECT * FROM retail_invoice_credit_notes WHERE sale_id=%s ORDER BY id DESC',
        [venta_id],
    ) or []
    return out


class RetailFacturacionEmitirView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, venta_id):
        _require_staff(request)
        return Response(_emitir_factura(venta_id, request))


class RetailFacturacionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, venta_id):
        _require_staff(request)
        row = q('SELECT * FROM retail_invoices WHERE sale_id=%s', [venta_id], one=True)
        if not row:
            return Response({'detail': 'Factura no encontrada'}, status=404)
        return Response(row)


class RetailFacturacionNotaCreditoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, venta_id):
        _require_staff(request)
        return Response({'sale_id': venta_id, 'credit_notes': _emitir_nota_credito(venta_id, request)})


def _webhook_secret():
    # Tienda Nube firma los webhooks con el secret de la app (client_secret).
    # Permitimos configurarlo explícitamente como `tiendanube_webhook_secret` o reusar `tiendanube_client_secret`.
    row = q(
        'SELECT tiendanube_webhook_secret, tiendanube_client_secret FROM retail_settings WHERE id=1',
        one=True,
    )
    candidates = []
    if row:
        candidates.extend(
            [
                row.get('tiendanube_webhook_secret'),
                row.get('tiendanube_client_secret'),
            ]
        )
    else:
        candidates.extend(
            [
                getattr(settings, 'TIENDANUBE_WEBHOOK_SECRET', ''),
                getattr(settings, 'TIENDANUBE_CLIENT_SECRET', ''),
            ]
        )
    for val in candidates:
        secret = _clean_text(val)
        if secret:
            return secret
    return ''


def _verify_tiendanube_signature(request):
    secret = _webhook_secret()
    if not secret:
        security_logger.warning("tiendanube_webhook_secret_missing path=%s", request.path)
        raise ValidationError('Webhook secret de Tienda Nube no configurado')
    signature = request.headers.get('x-linkedstore-hmac-sha256') or request.headers.get('X-Linkedstore-Hmac-Sha256')
    if not signature:
        security_logger.warning("tiendanube_webhook_signature_missing path=%s", request.path)
        raise ValidationError('Firma de webhook ausente')

    payload_bytes = request.body or b''
    digest = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).digest()
    expected_hex = digest.hex()
    expected_b64 = base64.b64encode(digest).decode('ascii')
    provided = signature.strip()

    # Docs oficiales: `hash_hmac('sha256', $data, APP_SECRET)` -> HEX.
    # Aceptamos también base64 por compatibilidad.
    if hmac.compare_digest(provided.lower(), expected_hex):
        return
    if hmac.compare_digest(provided, expected_b64):
        return
    security_logger.warning("tiendanube_webhook_signature_invalid path=%s", request.path)
    raise ValidationError('Firma webhook invalida')


def _tiendanube_event_id(payload, default_event, resource_id):
    data = payload if isinstance(payload, dict) else {}
    store_id = _clean_text(data.get('store_id'))
    event_name = _clean_text(data.get('event')) or _clean_text(default_event)
    rid = _clean_text(resource_id)
    parts = []
    if store_id:
        parts.append(store_id)
    if event_name:
        parts.append(event_name)
    if rid:
        parts.append(rid)
    return ':'.join(parts) or (rid or f'event-{int(timezone.now().timestamp())}')


def _tiendanube_cfg(payload=None):
    cfg = q(
        '''
        SELECT tiendanube_store_id, tiendanube_access_token
        FROM retail_settings
        WHERE id=1
        ''',
        one=True,
    )
    if cfg:
        store_id_cfg = _clean_text(cfg.get('tiendanube_store_id'))
        access_token = _clean_text(cfg.get('tiendanube_access_token'))
    else:
        store_id_cfg = _clean_text(getattr(settings, 'TIENDANUBE_STORE_ID', ''))
        access_token = _clean_text(getattr(settings, 'TIENDANUBE_ACCESS_TOKEN', ''))
    api_base = _clean_text(getattr(settings, 'TIENDANUBE_API_BASE', 'https://api.tiendanube.com/2025-03')) or 'https://api.tiendanube.com/2025-03'
    user_agent = _clean_text(getattr(settings, 'TIENDANUBE_USER_AGENT', 'RetailHub (admin@localhost)')) or 'RetailHub (admin@localhost)'
    try:
        timeout = int(getattr(settings, 'TIENDANUBE_TIMEOUT_SECS', 15) or 15)
    except (TypeError, ValueError):
        timeout = 15

    store_id_payload = None
    if isinstance(payload, dict):
        store_id_payload = _clean_text(payload.get('store_id'))
    store_id = store_id_cfg or store_id_payload
    if store_id_cfg and store_id_payload and store_id_cfg != store_id_payload:
        raise ValidationError('Webhook store_id no coincide con configuración Tienda Nube')

    return {
        'store_id': store_id,
        'access_token': access_token,
        'api_base': api_base.rstrip('/'),
        'user_agent': user_agent,
        'timeout': max(1, timeout),
    }


def _tiendanube_fetch_order(order_id, webhook_payload=None):
    oid = _clean_text(order_id)
    if not oid:
        raise ValidationError('order_id invalido')

    cfg = _tiendanube_cfg(webhook_payload)
    if not cfg.get('store_id') or not cfg.get('access_token'):
        raise ValidationError('Tienda Nube no configurado (store_id/access_token)')

    url = f"{cfg['api_base']}/{cfg['store_id']}/orders/{oid}"
    headers = {
        'Authentication': f"bearer {cfg['access_token']}",
        'User-Agent': cfg['user_agent'],
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=min(10, cfg['timeout']))
    except Exception as exc:
        raise ValidationError(f'Error consultando orden en Tienda Nube: {exc}')

    status_code = int(resp.status_code)
    body = resp.text
    if not (200 <= status_code < 300):
        raise ValidationError(f'Tienda Nube HTTP {status_code}: {body[:500]}')

    data = _json(body)
    if not isinstance(data, dict):
        raise ValidationError('Respuesta Tienda Nube invalida')
    return data


def _infer_payment_method_from_online(payload):
    txt = json.dumps(payload, ensure_ascii=False).lower()
    if 'credit' in txt or 'tarjeta de credito' in txt:
        return 'credit'
    if 'debit' in txt or 'debito' in txt:
        return 'debit'
    if 'cash' in txt or 'efectivo' in txt:
        return 'cash'
    return 'transfer'


def _first_money(*candidates):
    for value in candidates:
        if value in (None, ''):
            continue
        try:
            return _to_decimal(value, 'monto', allow_none=True)
        except ValidationError:
            continue
    return None


def _extract_online_coupon_codes(payload):
    data = payload if isinstance(payload, dict) else {}
    out = []
    seen = set()

    def push(value):
        raw = _clean_text(value)
        if not raw:
            return
        for token in str(raw).split(','):
            item = token.strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)

    push(data.get('coupon'))
    push(data.get('coupon_code'))
    push(data.get('discount_coupon'))
    push(data.get('promotion_code'))

    coupons = data.get('coupons')
    if isinstance(coupons, list):
        for cp in coupons:
            if isinstance(cp, dict):
                push(cp.get('code') or cp.get('coupon') or cp.get('name'))
            else:
                push(cp)
    return out


def _extract_online_items(payload):
    products = payload.get('products') or payload.get('line_items') or []
    out = []
    for product in products:
        if not isinstance(product, dict):
            continue
        variants = product.get('variants') or [product]
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            sku = _clean_text(variant.get('sku') or variant.get('variant_sku') or product.get('sku'))
            qty = _to_int(variant.get('quantity') or product.get('quantity') or 1, 'quantity')
            if not sku:
                continue
            row = q('SELECT id FROM retail_product_variants WHERE LOWER(sku)=LOWER(%s)', [sku], one=True)
            if not row:
                continue
            list_unit = _first_money(
                variant.get('compare_at_price'),
                product.get('compare_at_price'),
                variant.get('list_price'),
                product.get('list_price'),
                variant.get('price'),
                product.get('price'),
            )
            paid_unit = _first_money(
                variant.get('promotional_price'),
                variant.get('final_price'),
                variant.get('unit_price'),
                product.get('promotional_price'),
                product.get('final_price'),
                variant.get('price'),
                product.get('price'),
            )
            line_paid = _first_money(
                variant.get('subtotal'),
                variant.get('total'),
                variant.get('line_total'),
                product.get('subtotal'),
                product.get('total'),
                product.get('line_total'),
            )
            if paid_unit is None and line_paid is not None and qty > 0:
                paid_unit = (line_paid / Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            if paid_unit is None:
                paid_unit = list_unit
            if paid_unit is None:
                paid_unit = Decimal('0.00')
            if list_unit is None:
                list_unit = paid_unit

            line_discount = _first_money(
                variant.get('discount'),
                variant.get('discount_amount'),
                variant.get('total_discount'),
                product.get('discount'),
                product.get('discount_amount'),
                product.get('total_discount'),
            )
            if line_discount is None:
                inferred = ((list_unit - paid_unit) * Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
                line_discount = inferred if inferred > 0 else Decimal('0.00')
            if line_discount < 0:
                line_discount = Decimal('0.00')

            out.append(
                {
                    'variant_id': row['id'],
                    'quantity': qty,
                    'unit_price_net_ars': paid_unit.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'line_discount_ars': line_discount.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                }
            )
    if not out:
        raise ValidationError('No se pudieron mapear items por SKU de la orden online')
    return out


class RetailOnlineSyncCatalogoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _require_staff(request)
        limit = _to_int((request.data or {}).get('limit') or 200, 'limit')
        rows = q(
            '''
            SELECT v.id, v.sku, v.barcode_internal, v.price_online_ars,
                   v.tiendanube_product_id, v.tiendanube_variant_id,
                   p.name AS producto, COALESCE(p.brand,'') AS marca,
                   v.option_signature
            FROM retail_product_variants v
            JOIN retail_products p ON p.id=v.product_id
            WHERE v.active=TRUE
            ORDER BY v.id
            LIMIT %s
            ''',
            [max(1, min(limit, 2000))],
        ) or []
        mapped = sum(1 for r in rows if r.get('tiendanube_variant_id'))
        pending = len(rows) - mapped
        job_id = _create_job('tiendanube', 'sync_catalogo', {'limit': limit, 'variants': rows}, status='pending')
        return Response({'ok': True, 'job_id': job_id, 'processed': len(rows), 'mapped': mapped, 'pending_mapping': pending})


class RetailOnlineSyncStockView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _require_staff(request)
        limit = _to_int((request.data or {}).get('limit') or 200, 'limit')
        rows = q(
            '''
            SELECT id, sku, stock_on_hand, tiendanube_variant_id
            FROM retail_product_variants
            WHERE active=TRUE
            ORDER BY id
            LIMIT %s
            ''',
            [max(1, min(limit, 2000))],
        ) or []
        linked = [r for r in rows if r.get('tiendanube_variant_id')]
        unlinked = [r for r in rows if not r.get('tiendanube_variant_id')]
        job_id = _create_job('tiendanube', 'sync_stock', {'limit': limit, 'variants': linked}, status='pending')
        return Response({'ok': True, 'job_id': job_id, 'processed': len(rows), 'linked': len(linked), 'unlinked': len(unlinked)})


@method_decorator(csrf_exempt, name='dispatch')
class RetailOnlineWebhookOrdenPagadaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        _verify_tiendanube_signature(request)
        payload = _json(request.body)
        order_id = _clean_text(payload.get('id') or payload.get('order_id') or payload.get('number'))
        if not order_id:
            raise ValidationError('order_id ausente en webhook')
        event_id = _tiendanube_event_id(payload, 'order/paid', order_id)
        signature = request.headers.get('x-linkedstore-hmac-sha256') or request.headers.get('X-Linkedstore-Hmac-Sha256')

        existing_event = q(
            'SELECT id, processed FROM retail_webhook_events WHERE provider=\'tiendanube\' AND event_id=%s FOR UPDATE',
            [event_id],
            one=True,
        )
        if existing_event:
            return Response({'ok': True, 'duplicate': True, 'event_id': event_id})

        event_db_id = exec_returning(
            '''
            INSERT INTO retail_webhook_events(provider, event_type, event_id, external_order_id, signature, payload)
            VALUES ('tiendanube','order_paid',%s,%s,%s,%s)
            RETURNING id
            ''',
            [event_id, order_id, signature, json.dumps(payload)],
        )

        existing_sale = q('SELECT id FROM retail_sales WHERE source_order_id=%s', [order_id], one=True)
        if existing_sale:
            exec_void('UPDATE retail_webhook_events SET processed=TRUE, processed_at=NOW() WHERE id=%s', [event_db_id])
            return Response({'ok': True, 'duplicate': True, 'sale_id': existing_sale['id'], 'event_id': event_id})

        try:
            # Los webhooks de Tienda Nube traen `store_id`, `event` e `id`.
            # Para obtener items/pago/cliente, pedimos el detalle de la orden vía API.
            order = _tiendanube_fetch_order(order_id, payload)
            items = _extract_online_items(order)
            coupon_codes = _extract_online_coupon_codes(order)
            payment_method = _infer_payment_method_from_online(order)
            account_code = 'payway' if payment_method in ('debit', 'credit') else ('cash' if payment_method == 'cash' else 'transfer_1')

            customer = order.get('customer') if isinstance(order.get('customer'), dict) else {}
            sale_payload = {
                'channel': 'online',
                'payment_method': payment_method,
                'pricing_source': 'tiendanube',
                'payment_account_code': account_code,
                'items': items,
                'coupon_codes': coupon_codes,
                'source_order_id': order_id,
                'notes': 'Orden pagada webhook Tienda Nube',
                'auto_emit_invoice': _load_settings().get('auto_invoice_online_paid', True),
                'customer_name': _clean_text(customer.get('name') or order.get('customer_name') or order.get('name')),
                'customer_email': _clean_text(customer.get('email') or order.get('customer_email') or order.get('email') or order.get('contact_email')),
            }

            quote = _build_quote(request, sale_payload, lock_variants=True)
            payment_account = _ensure_payment_account(sale_payload, quote['payment_method'])

            sale_id = exec_returning(
                '''
                INSERT INTO retail_sales(
                  sale_number, channel, status, payment_method, payment_account_id, cash_session_id,
                  customer_snapshot, subtotal_ars, promotion_discount_total_ars, price_adjustment_pct, price_adjustment_amount_ars,
                  total_ars, currency_code, requires_invoice, notes, source_order_id,
                  pricing_source, price_override_by, price_override_reason, created_by
                )
                VALUES (
                  'PENDIENTE', %s, 'confirmed', %s, %s, NULL,
                  %s, %s, %s, %s, %s,
                  %s, 'ARS', %s, %s, %s, %s,
                  NULL, NULL, NULL
                )
                RETURNING id
                ''',
                [
                    quote['channel'],
                    quote['payment_method'],
                    payment_account['id'],
                    json.dumps(
                        {
                            'name': sale_payload.get('customer_name'),
                            'doc': None,
                            'email': sale_payload.get('customer_email'),
                        }
                    ),
                    quote['subtotal_ars'],
                    quote.get('promotion_discount_total_ars') or 0,
                    quote['modifier_pct'],
                    quote['modifier_amount_ars'],
                    quote['total_ars'],
                    quote['invoice_required'],
                    sale_payload.get('notes'),
                    order_id,
                    quote.get('pricing_source') or 'tiendanube',
                ],
            )
            exec_void('UPDATE retail_sales SET sale_number=%s WHERE id=%s', [_sale_number(sale_id), sale_id])

            persisted_items = []
            for line in quote['items']:
                variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [line['variant_id']], one=True)
                new_stock = int(variant['stock_on_hand']) - int(line['quantity'])
                if new_stock < 0:
                    raise ValidationError(f"Stock insuficiente para variante {line['variant_id']}")
                sale_item_id = exec_returning(
                    '''
                    INSERT INTO retail_sale_items(
                      sale_id, variant_id, quantity,
                      unit_price_list_ars, unit_price_final_ars, promotion_discount_ars, unit_cost_snapshot_ars,
                      line_subtotal_ars, line_total_ars
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    ''',
                    [
                        sale_id,
                        line['variant_id'],
                        line['quantity'],
                        line['unit_price_list_ars'],
                        line['unit_price_final_ars'],
                        line.get('promotion_discount_ars') or 0,
                        line['unit_cost_snapshot_ars'],
                        line['line_subtotal_ars'],
                        line['line_total_ars'],
                    ],
                )
                persisted_items.append({'line_key': line.get('line_key'), 'sale_item_id': sale_item_id})
                exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, line['variant_id']])
                exec_void(
                    '''
                    INSERT INTO retail_stock_movements(
                      variant_id, movement_kind, qty_signed, stock_after,
                      cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                    )
                    VALUES (%s,'online_sale',%s,%s,%s,'sale',%s,'Venta online webhook',NULL)
                    ''',
                    [line['variant_id'], -int(line['quantity']), new_stock, line['unit_cost_snapshot_ars'], sale_id],
                )

            _persist_sale_promotions(sale_id, quote, persisted_items)

            if quote['invoice_required']:
                exec_void(
                    '''
                    INSERT INTO retail_invoices(sale_id, status, invoice_mode, amount_total_ars)
                    VALUES (%s,'pending','arca',%s)
                    ON CONFLICT (sale_id) DO NOTHING
                    ''',
                    [sale_id, quote['total_ars']],
                )
            else:
                exec_void(
                    '''
                    INSERT INTO retail_invoices(sale_id, status, invoice_mode, amount_total_ars)
                    VALUES (%s,'not_required','internal',%s)
                    ON CONFLICT (sale_id) DO NOTHING
                    ''',
                    [sale_id, quote['total_ars']],
                )

            if sale_payload.get('auto_emit_invoice') and quote['invoice_required']:
                _emitir_factura(sale_id, request)

            exec_void('UPDATE retail_webhook_events SET processed=TRUE, processed_at=NOW() WHERE id=%s', [event_db_id])
            return Response({'ok': True, 'event_id': event_id, 'sale_id': sale_id})
        except Exception as exc:
            _create_job(
                'tiendanube',
                'webhook_order_paid',
                {'event_id': event_id, 'order_id': order_id, 'payload': payload},
                status='failed',
                last_error=str(exc),
            )
            exec_void('UPDATE retail_webhook_events SET processed=FALSE, error_message=%s WHERE id=%s', [str(exc), event_db_id])
            return Response({'ok': False, 'detail': str(exc)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class RetailOnlineWebhookOrdenCanceladaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        _verify_tiendanube_signature(request)
        payload = _json(request.body)
        order_id = _clean_text(payload.get('id') or payload.get('order_id') or payload.get('number'))
        if not order_id:
            raise ValidationError('order_id ausente en webhook')
        event_id = _tiendanube_event_id(payload, 'order/cancelled', order_id)
        signature = request.headers.get('x-linkedstore-hmac-sha256') or request.headers.get('X-Linkedstore-Hmac-Sha256')

        existing_event = q(
            'SELECT id FROM retail_webhook_events WHERE provider=\'tiendanube\' AND event_id=%s FOR UPDATE',
            [event_id],
            one=True,
        )
        if existing_event:
            return Response({'ok': True, 'duplicate': True, 'event_id': event_id})

        event_db_id = exec_returning(
            '''
            INSERT INTO retail_webhook_events(provider, event_type, event_id, external_order_id, signature, payload)
            VALUES ('tiendanube','order_cancelled',%s,%s,%s,%s)
            RETURNING id
            ''',
            [event_id, order_id, signature, json.dumps(payload)],
        )

        sale = q('SELECT * FROM retail_sales WHERE source_order_id=%s FOR UPDATE', [order_id], one=True)
        if sale and sale.get('status') != 'cancelled':
            items = q('SELECT * FROM retail_sale_items WHERE sale_id=%s FOR UPDATE', [sale['id']]) or []
            if any(int(it.get('returned_qty') or 0) > 0 for it in items):
                _create_job(
                    'tiendanube',
                    'webhook_order_cancelled',
                    {'event_id': event_id, 'order_id': order_id, 'payload': payload},
                    status='failed',
                    last_error='Venta con devoluciones parciales; requiere revision manual',
                )
                exec_void(
                    'UPDATE retail_webhook_events SET processed=FALSE, error_message=%s WHERE id=%s',
                    ['Venta con devoluciones parciales; requiere revision manual', event_db_id],
                )
                return Response({'ok': False, 'detail': 'Venta con devoluciones parciales'}, status=400)

            for item in items:
                variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [item['variant_id']], one=True)
                new_stock = int(variant['stock_on_hand']) + int(item['quantity'])
                exec_void('UPDATE retail_product_variants SET stock_on_hand=%s WHERE id=%s', [new_stock, item['variant_id']])
                exec_void(
                    '''
                    INSERT INTO retail_stock_movements(
                      variant_id, movement_kind, qty_signed, stock_after,
                      cost_unit_snapshot_ars, reference_type, reference_id, note, created_by
                    )
                    VALUES (%s,'online_cancel',%s,%s,%s,'sale',%s,'Cancelacion webhook Tienda Nube',NULL)
                    ''',
                    [
                        item['variant_id'],
                        int(item['quantity']),
                        new_stock,
                        item['unit_cost_snapshot_ars'],
                        sale['id'],
                    ],
                )

            exec_void(
                '''
                UPDATE retail_sales
                SET status='cancelled', cancelled_at=NOW(), cancel_reason=%s
                WHERE id=%s
                ''',
                ['Cancelacion webhook Tienda Nube', sale['id']],
            )
            exec_void(
                "UPDATE retail_invoices SET status='manual_review', error_message='Venta online cancelada', updated_at=NOW() WHERE sale_id=%s",
                [sale['id']],
            )

        exec_void('UPDATE retail_webhook_events SET processed=TRUE, processed_at=NOW() WHERE id=%s', [event_db_id])
        return Response({'ok': True, 'event_id': event_id, 'order_id': order_id})


@method_decorator(csrf_exempt, name='dispatch')
class RetailOnlineWebhookStoreRedactView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        _verify_tiendanube_signature(request)
        payload = _json(request.body)
        store_id = _clean_text(payload.get('store_id'))
        event_id = _tiendanube_event_id(payload, 'store/redact', store_id or 'store')
        signature = request.headers.get('x-linkedstore-hmac-sha256') or request.headers.get('X-Linkedstore-Hmac-Sha256')

        existing_event = q(
            'SELECT id FROM retail_webhook_events WHERE provider=\'tiendanube\' AND event_id=%s FOR UPDATE',
            [event_id],
            one=True,
        )
        if existing_event:
            return Response({'ok': True, 'duplicate': True, 'event_id': event_id})

        event_db_id = exec_returning(
            '''
            INSERT INTO retail_webhook_events(provider, event_type, event_id, external_order_id, signature, payload)
            VALUES ('tiendanube','store_redact',%s,%s,%s,%s)
            RETURNING id
            ''',
            [event_id, store_id, signature, json.dumps(payload)],
        )

        cfg = _load_settings()
        cfg_store = _clean_text(cfg.get('tiendanube_store_id'))
        if cfg_store and store_id and str(cfg_store) != str(store_id):
            exec_void(
                'UPDATE retail_webhook_events SET processed=FALSE, error_message=%s WHERE id=%s',
                ['store_id webhook no coincide con configuracion local', event_db_id],
            )
            return Response({'ok': False, 'detail': 'store_id no coincide'}, status=400)

        exec_void(
            '''
            UPDATE retail_settings
            SET tiendanube_store_id=NULL,
                tiendanube_access_token=NULL,
                tiendanube_webhook_secret=NULL,
                updated_at=NOW()
            WHERE id=1
            ''',
        )
        exec_void('UPDATE retail_webhook_events SET processed=TRUE, processed_at=NOW() WHERE id=%s', [event_db_id])
        security_logger.warning("tiendanube_store_redact_applied store_id=%s", store_id or "")
        return Response({'ok': True, 'event_id': event_id, 'store_id': store_id})


def _to_datetime(value, label, allow_none=True):
    if value in (None, ''):
        if allow_none:
            return None
        raise ValidationError(f'{label} requerido')
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError(f'{label} invalido, usa ISO-8601')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _parse_product_ids(raw):
    if raw in (None, ''):
        return []
    if not isinstance(raw, list):
        raise ValidationError('product_ids debe ser una lista')
    out = []
    seen = set()
    for value in raw:
        pid = _to_int(value, 'product_id')
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def _validate_product_ids(product_ids):
    if not product_ids:
        return
    rows = q('SELECT id FROM retail_products WHERE id = ANY(%s)', [product_ids]) or []
    found = {int(row['id']) for row in rows}
    missing = [pid for pid in product_ids if int(pid) not in found]
    if missing:
        raise ValidationError(f'product_ids inexistentes: {", ".join(str(x) for x in missing)}')


def _parse_variant_ids(raw):
    if raw in (None, ''):
        return []
    if not isinstance(raw, list):
        raise ValidationError('variant_ids debe ser una lista')
    out = []
    seen = set()
    for value in raw:
        vid = _to_int(value, 'variant_id')
        if vid in seen:
            continue
        seen.add(vid)
        out.append(vid)
    return out


def _validate_variant_ids(variant_ids):
    if not variant_ids:
        return
    rows = q('SELECT id FROM retail_product_variants WHERE id = ANY(%s)', [variant_ids]) or []
    found = {int(row['id']) for row in rows}
    missing = [vid for vid in variant_ids if int(vid) not in found]
    if missing:
        raise ValidationError(f'variant_ids inexistentes: {", ".join(str(x) for x in missing)}')


def _normalize_promotion_payload(data, existing=None):
    if not isinstance(data, dict):
        raise ValidationError('Payload invalido')

    base = {
        'name': None,
        'promo_type': PROMO_TYPE_PERCENT,
        'active': True,
        'channel_scope': 'both',
        'activation_mode': 'automatic',
        'coupon_code': None,
        'priority': 100,
        'combinable': True,
        'bogo_mode': None,
        'buy_qty': None,
        'pay_qty': None,
        'discount_pct': None,
        'applies_to_all_products': True,
        'valid_from': None,
        'valid_until': None,
        'product_ids': [],
        'variant_ids': [],
    }
    if existing:
        base.update(
            {
                'name': _clean_text(existing.get('name')),
                'promo_type': _clean_text(existing.get('promo_type')) or PROMO_TYPE_PERCENT,
                'active': bool(existing.get('active')),
                'channel_scope': _clean_text(existing.get('channel_scope')) or 'both',
                'activation_mode': _clean_text(existing.get('activation_mode')) or 'automatic',
                'coupon_code': _clean_text(existing.get('coupon_code')),
                'priority': int(existing.get('priority') or 100),
                'combinable': bool(existing.get('combinable')),
                'bogo_mode': _clean_text(existing.get('bogo_mode')),
                'buy_qty': _to_int(existing.get('buy_qty'), 'buy_qty', allow_none=True),
                'pay_qty': _to_int(existing.get('pay_qty'), 'pay_qty', allow_none=True),
                'discount_pct': _to_decimal(existing.get('discount_pct'), 'discount_pct', allow_none=True),
                'applies_to_all_products': bool(existing.get('applies_to_all_products')),
                'valid_from': _to_datetime(existing.get('valid_from'), 'valid_from', allow_none=True),
                'valid_until': _to_datetime(existing.get('valid_until'), 'valid_until', allow_none=True),
                'product_ids': _parse_product_ids(existing.get('product_ids') or []),
                'variant_ids': _parse_variant_ids(existing.get('variant_ids') or []),
            }
        )

    if 'name' in data:
        base['name'] = _clean_text(data.get('name') or data.get('nombre'))
    if 'promo_type' in data:
        base['promo_type'] = (_clean_text(data.get('promo_type')) or '').lower()
    if 'active' in data:
        base['active'] = _to_bool(data.get('active'))
    if 'channel_scope' in data:
        base['channel_scope'] = (_clean_text(data.get('channel_scope')) or '').lower()
    if 'activation_mode' in data:
        base['activation_mode'] = (_clean_text(data.get('activation_mode')) or '').lower()
    if 'coupon_code' in data or 'cupon' in data:
        base['coupon_code'] = _clean_text(data.get('coupon_code') or data.get('cupon'))
    if 'priority' in data:
        base['priority'] = _to_int(data.get('priority'), 'priority')
    if 'combinable' in data:
        base['combinable'] = _to_bool(data.get('combinable'))
    if 'bogo_mode' in data:
        base['bogo_mode'] = (_clean_text(data.get('bogo_mode')) or '').lower() or None
    if 'buy_qty' in data:
        base['buy_qty'] = _to_int(data.get('buy_qty'), 'buy_qty', allow_none=True)
    if 'pay_qty' in data:
        base['pay_qty'] = _to_int(data.get('pay_qty'), 'pay_qty', allow_none=True)
    if 'discount_pct' in data:
        base['discount_pct'] = _to_decimal(data.get('discount_pct'), 'discount_pct', allow_none=True)
    if 'applies_to_all_products' in data:
        base['applies_to_all_products'] = _to_bool(data.get('applies_to_all_products'))
    if 'valid_from' in data:
        base['valid_from'] = _to_datetime(data.get('valid_from'), 'valid_from', allow_none=True)
    if 'valid_until' in data:
        base['valid_until'] = _to_datetime(data.get('valid_until'), 'valid_until', allow_none=True)
    if 'product_ids' in data:
        base['product_ids'] = _parse_product_ids(data.get('product_ids'))
    if 'variant_ids' in data:
        base['variant_ids'] = _parse_variant_ids(data.get('variant_ids'))

    if not base['name']:
        raise ValidationError('name requerido')
    if base['promo_type'] not in (PROMO_TYPE_PERCENT, PROMO_TYPE_X_FOR_Y):
        raise ValidationError('promo_type invalido (percent_off|x_for_y)')
    if base['channel_scope'] not in PROMO_CHANNELS:
        raise ValidationError('channel_scope invalido (local|online|both)')
    if base['activation_mode'] not in PROMO_ACTIVATION_MODES:
        raise ValidationError('activation_mode invalido (automatic|coupon|both)')
    if base['activation_mode'] in ('coupon', 'both') and not base['coupon_code']:
        raise ValidationError('coupon_code requerido para activation_mode coupon/both')
    if base['priority'] < 0:
        raise ValidationError('priority debe ser >= 0')
    if base['valid_from'] and base['valid_until'] and base['valid_until'] < base['valid_from']:
        raise ValidationError('valid_until debe ser mayor o igual a valid_from')

    if base['promo_type'] == PROMO_TYPE_PERCENT:
        pct = _to_decimal(base.get('discount_pct'), 'discount_pct', allow_none=True)
        if pct is None or pct <= 0 or pct > 100:
            raise ValidationError('discount_pct invalido para percent_off (0 < pct <= 100)')
        base['discount_pct'] = pct.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        base['bogo_mode'] = None
        base['buy_qty'] = None
        base['pay_qty'] = None
        base['variant_ids'] = []
        if not base['applies_to_all_products']:
            if not base['product_ids']:
                raise ValidationError('product_ids requerido cuando applies_to_all_products=false')
            _validate_product_ids(base['product_ids'])
        else:
            base['product_ids'] = []
    else:
        if base['bogo_mode'] not in PROMO_BOGO_MODES:
            raise ValidationError('bogo_mode invalido (sku|mix)')
        buy_qty = _to_int(base.get('buy_qty'), 'buy_qty', allow_none=True)
        pay_qty = _to_int(base.get('pay_qty'), 'pay_qty', allow_none=True)
        if buy_qty is None or buy_qty <= 0:
            raise ValidationError('buy_qty invalido para x_for_y')
        if pay_qty is None or pay_qty < 0 or pay_qty >= buy_qty:
            raise ValidationError('pay_qty invalido para x_for_y')
        base['buy_qty'] = buy_qty
        base['pay_qty'] = pay_qty
        base['discount_pct'] = None
        if base['bogo_mode'] == 'mix':
            base['applies_to_all_products'] = True
            base['product_ids'] = []
            base['variant_ids'] = []
        else:
            base['applies_to_all_products'] = True
            base['product_ids'] = []
            if not base['variant_ids']:
                raise ValidationError('variant_ids requerido cuando bogo_mode=sku')
            _validate_variant_ids(base['variant_ids'])

    if base['promo_type'] != PROMO_TYPE_PERCENT:
        base['product_ids'] = []

    return base


def _sync_promotion_products(promotion_id, product_ids):
    exec_void('DELETE FROM retail_promotion_products WHERE promotion_id=%s', [promotion_id])
    for pid in product_ids or []:
        exec_void(
            '''
            INSERT INTO retail_promotion_products(promotion_id, product_id)
            VALUES (%s,%s)
            ON CONFLICT (promotion_id, product_id) DO NOTHING
            ''',
            [promotion_id, pid],
        )


def _sync_promotion_variants(promotion_id, variant_ids):
    exec_void('DELETE FROM retail_promotion_variants WHERE promotion_id=%s', [promotion_id])
    for vid in variant_ids or []:
        exec_void(
            '''
            INSERT INTO retail_promotion_variants(promotion_id, variant_id)
            VALUES (%s,%s)
            ON CONFLICT (promotion_id, variant_id) DO NOTHING
            ''',
            [promotion_id, vid],
        )


def _load_promotion(promotion_id):
    row = q(
        '''
        SELECT p.*,
               COALESCE(pp.product_ids, ARRAY[]::BIGINT[]) AS product_ids,
               COALESCE(pv.variant_ids, ARRAY[]::BIGINT[]) AS variant_ids
        FROM retail_promotions p
        LEFT JOIN LATERAL (
          SELECT array_agg(rpp.product_id ORDER BY rpp.product_id) AS product_ids
          FROM retail_promotion_products rpp
          WHERE rpp.promotion_id=p.id
        ) pp ON TRUE
        LEFT JOIN LATERAL (
          SELECT array_agg(rpv.variant_id ORDER BY rpv.variant_id) AS variant_ids
          FROM retail_promotion_variants rpv
          WHERE rpv.promotion_id=p.id
        ) pv ON TRUE
        WHERE p.id=%s
        ''',
        [promotion_id],
        one=True,
    )
    if not row:
        return None
    pids = []
    for pid in row.get('product_ids') or []:
        try:
            pids.append(int(pid))
        except (TypeError, ValueError):
            continue
    row['product_ids'] = pids
    vids = []
    for vid in row.get('variant_ids') or []:
        try:
            vids.append(int(vid))
        except (TypeError, ValueError):
            continue
    row['variant_ids'] = vids
    products = q(
        '''
        SELECT id, name
        FROM retail_products
        WHERE id = ANY(%s)
        ORDER BY name, id
        ''',
        [pids or [0]],
    ) or []
    row['products'] = products if pids else []
    variants = q(
        '''
        SELECT v.id, v.sku, p.name AS producto
        FROM retail_product_variants v
        JOIN retail_products p ON p.id=v.product_id
        WHERE v.id = ANY(%s)
        ORDER BY v.sku, v.id
        ''',
        [vids or [0]],
    ) or []
    row['variants'] = variants if vids else []
    return row


class RetailPromocionesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        qtxt = _clean_text(request.query_params.get('q'))
        active = _clean_text(request.query_params.get('active'))
        params = []
        where = []
        if qtxt:
            where.append('(p.name ILIKE %s OR COALESCE(p.coupon_code, \'\') ILIKE %s)')
            params.extend([f'%{qtxt}%', f'%{qtxt}%'])
        if active in ('1', 'true', 'si', 'yes'):
            where.append('p.active=TRUE')
        elif active in ('0', 'false', 'no'):
            where.append('p.active=FALSE')
        where_sql = f"WHERE {' AND '.join(where)}" if where else ''
        rows = q(
            f'''
            SELECT p.*,
                   COALESCE(pp.product_ids, ARRAY[]::BIGINT[]) AS product_ids,
                   COALESCE(pv.variant_ids, ARRAY[]::BIGINT[]) AS variant_ids,
                   COALESCE(cardinality(pp.product_ids), 0)::int AS scoped_products,
                   COALESCE(cardinality(pv.variant_ids), 0)::int AS scoped_variants
            FROM retail_promotions p
            LEFT JOIN LATERAL (
              SELECT array_agg(rpp.product_id ORDER BY rpp.product_id) AS product_ids
              FROM retail_promotion_products rpp
              WHERE rpp.promotion_id=p.id
            ) pp ON TRUE
            LEFT JOIN LATERAL (
              SELECT array_agg(rpv.variant_id ORDER BY rpv.variant_id) AS variant_ids
              FROM retail_promotion_variants rpv
              WHERE rpv.promotion_id=p.id
            ) pv ON TRUE
            {where_sql}
            ORDER BY p.priority, p.id
            ''',
            params,
        ) or []
        for row in rows:
            pids = []
            vids = []
            for pid in row.get('product_ids') or []:
                try:
                    pids.append(int(pid))
                except (TypeError, ValueError):
                    continue
            for vid in row.get('variant_ids') or []:
                try:
                    vids.append(int(vid))
                except (TypeError, ValueError):
                    continue
            row['product_ids'] = pids
            row['variant_ids'] = vids
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        if not _can_manage_promotions(request):
            raise PermissionDenied('No autorizado para editar promociones')
        _set_audit_user(request)
        payload = _normalize_promotion_payload(request.data or {}, existing=None)
        promo_id = exec_returning(
            '''
            INSERT INTO retail_promotions(
              name, promo_type, active, channel_scope, activation_mode, coupon_code,
              priority, combinable, bogo_mode, buy_qty, pay_qty, discount_pct,
              applies_to_all_products, valid_from, valid_until
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            ''',
            [
                payload['name'],
                payload['promo_type'],
                payload['active'],
                payload['channel_scope'],
                payload['activation_mode'],
                payload['coupon_code'],
                payload['priority'],
                payload['combinable'],
                payload['bogo_mode'],
                payload['buy_qty'],
                payload['pay_qty'],
                payload['discount_pct'],
                payload['applies_to_all_products'],
                payload['valid_from'],
                payload['valid_until'],
            ],
        )
        _sync_promotion_products(promo_id, payload['product_ids'])
        _sync_promotion_variants(promo_id, payload['variant_ids'])
        return Response(_load_promotion(promo_id), status=201)


class RetailPromocionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, promocion_id):
        _require_staff(request)
        row = _load_promotion(promocion_id)
        if not row:
            return Response({'detail': 'Promocion no encontrada'}, status=404)
        return Response(row)

    @transaction.atomic
    def patch(self, request, promocion_id):
        _require_staff(request)
        if not _can_manage_promotions(request):
            raise PermissionDenied('No autorizado para editar promociones')
        _set_audit_user(request)
        existing = _load_promotion(promocion_id)
        if not existing:
            return Response({'detail': 'Promocion no encontrada'}, status=404)
        payload = _normalize_promotion_payload(request.data or {}, existing=existing)
        exec_void(
            '''
            UPDATE retail_promotions
            SET name=%s,
                promo_type=%s,
                active=%s,
                channel_scope=%s,
                activation_mode=%s,
                coupon_code=%s,
                priority=%s,
                combinable=%s,
                bogo_mode=%s,
                buy_qty=%s,
                pay_qty=%s,
                discount_pct=%s,
                applies_to_all_products=%s,
                valid_from=%s,
                valid_until=%s
            WHERE id=%s
            ''',
            [
                payload['name'],
                payload['promo_type'],
                payload['active'],
                payload['channel_scope'],
                payload['activation_mode'],
                payload['coupon_code'],
                payload['priority'],
                payload['combinable'],
                payload['bogo_mode'],
                payload['buy_qty'],
                payload['pay_qty'],
                payload['discount_pct'],
                payload['applies_to_all_products'],
                payload['valid_from'],
                payload['valid_until'],
                promocion_id,
            ],
        )
        _sync_promotion_products(promocion_id, payload['product_ids'])
        _sync_promotion_variants(promocion_id, payload['variant_ids'])
        return Response(_load_promotion(promocion_id))

    put = patch


class RetailConfigSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        row = q('SELECT * FROM retail_settings WHERE id=1', one=True)
        if not row:
            exec_void('INSERT INTO retail_settings(id) VALUES (1) ON CONFLICT (id) DO NOTHING')
            row = q('SELECT * FROM retail_settings WHERE id=1', one=True) or {}
        return Response(_sanitize_retail_settings_response(row))

    @transaction.atomic
    def put(self, request):
        _require_admin(request)
        _set_audit_user(request)
        data = request.data or {}
        updates = []
        params = []

        text_fields = [
            'business_name',
            'iva_condition',
            'arca_env',
            'arca_cuit',
            'arca_cert_path',
            'arca_key_path',
            'arca_wsaa_service',
            'tiendanube_client_id',
            'tiendanube_client_secret',
            'tiendanube_access_token',
            'tiendanube_webhook_secret',
            'ticket_printer_name',
            'label_printer_name',
        ]
        int_fields = [
            'arca_pto_vta_store',
            'arca_pto_vta_online',
            'tiendanube_store_id',
        ]
        positive_int_fields = [
            'return_warranty_size_days',
            'return_warranty_breakage_days',
        ]
        non_negative_decimal_fields = [
            'purchase_default_markup_pct',
        ]
        bool_fields = ['auto_invoice_online_paid']

        for field in text_fields:
            if field in data:
                updates.append(f'{field}=%s')
                params.append(_clean_text(data.get(field)))
        for field in int_fields:
            if field in data:
                updates.append(f'{field}=%s')
                params.append(_to_int(data.get(field), field, allow_none=True))
        for field in positive_int_fields:
            if field in data:
                val = _to_int(data.get(field), field)
                if val <= 0:
                    raise ValidationError(f'{field} debe ser mayor a 0')
                updates.append(f'{field}=%s')
                params.append(val)
        for field in non_negative_decimal_fields:
            if field in data:
                val = _pct(data.get(field))
                if val < 0:
                    raise ValidationError(f'{field} debe ser mayor o igual a 0')
                updates.append(f'{field}=%s')
                params.append(val)
        for field in bool_fields:
            if field in data:
                updates.append(f'{field}=%s')
                params.append(bool(data.get(field)))

        if 'currency_code' in data:
            currency = (_clean_text(data.get('currency_code')) or '').upper()
            if currency != 'ARS':
                raise ValidationError('currency_code solo admite ARS en MVP')
            updates.append('currency_code=%s')
            params.append(currency)

        if not updates:
            raise ValidationError('Sin cambios para guardar')

        params.append(1)
        exec_void(f"UPDATE retail_settings SET {', '.join(updates)} WHERE id=%s", params)
        return self.get(request)


class RetailConfigPageSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        row = q('SELECT ui_page_settings FROM retail_settings WHERE id=1', one=True)
        if not row:
            exec_void('INSERT INTO retail_settings(id) VALUES (1) ON CONFLICT (id) DO NOTHING')
            row = q('SELECT ui_page_settings FROM retail_settings WHERE id=1', one=True) or {}
        return Response(_normalize_ui_page_settings(row.get('ui_page_settings')))

    @transaction.atomic
    def put(self, request):
        _require_admin(request)
        _set_audit_user(request)
        data = request.data or {}
        if not isinstance(data, dict):
            raise ValidationError('Payload invalido')
        normalized = _normalize_ui_page_settings(data, strict=True)
        exec_void(
            'UPDATE retail_settings SET ui_page_settings=%s::jsonb WHERE id=1',
            [json.dumps(normalized, ensure_ascii=False)],
        )
        return Response(normalized)

class RetailConfigPaymentAccountsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        rows = q(
            '''
            SELECT id, code, label, payment_method, provider, active, sort_order, created_at, updated_at
            FROM retail_payment_accounts
            ORDER BY sort_order, id
            '''
        ) or []
        return Response(rows)

    @transaction.atomic
    def put(self, request):
        _require_admin(request)
        _set_audit_user(request)
        data = request.data or {}
        accounts = data.get('accounts')
        if not isinstance(accounts, list) or not accounts:
            raise ValidationError('accounts debe ser lista no vacia')

        for item in accounts:
            if not isinstance(item, dict):
                raise ValidationError('Cada cuenta debe ser objeto')
            account_id = _to_int(item.get('id'), 'id', allow_none=True)
            code = _clean_text(item.get('code'))
            label = _clean_text(item.get('label'))
            payment_method = _clean_text(item.get('payment_method'))
            if payment_method is not None:
                payment_method = payment_method.lower()
                if payment_method not in ('cash', 'debit', 'transfer', 'credit'):
                    raise ValidationError('payment_method invalido')
            provider = _clean_text(item.get('provider'))
            active = bool(item.get('active', True))
            sort_order = _to_int(item.get('sort_order') if item.get('sort_order') is not None else 100, 'sort_order')

            if account_id:
                exec_void(
                    '''
                    UPDATE retail_payment_accounts
                    SET code=%s, label=%s, payment_method=%s, provider=%s, active=%s, sort_order=%s
                    WHERE id=%s
                    ''',
                    [code, label, payment_method, provider, active, sort_order, account_id],
                )
            else:
                if not code or not label:
                    raise ValidationError('code y label son requeridos para nuevas cuentas')
                exec_void(
                    '''
                    INSERT INTO retail_payment_accounts(code, label, payment_method, provider, active, sort_order)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (code) DO UPDATE
                    SET label=EXCLUDED.label,
                        payment_method=EXCLUDED.payment_method,
                        provider=EXCLUDED.provider,
                        active=EXCLUDED.active,
                        sort_order=EXCLUDED.sort_order
                    ''',
                    [code, label, payment_method, provider, active, sort_order],
                )

        return self.get(request)


class RetailReporteResumenComercialView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        row = q(
            '''
            SELECT COALESCE(SUM(si.line_subtotal_ars + si.promotion_discount_ars),0)::numeric(14,2) AS ventas_brutas_ars,
                   COALESCE(SUM(si.promotion_discount_ars),0)::numeric(14,2) AS descuentos_ars,
                   COALESCE(SUM(si.line_total_ars),0)::numeric(14,2) AS ventas_netas_ars,
                   COALESCE(SUM(si.line_total_ars - (si.unit_cost_snapshot_ars * si.quantity)),0)::numeric(14,2) AS margen_bruto_ars,
                   COALESCE(SUM(si.quantity),0)::int AS unidades,
                   COUNT(DISTINCT s.id)::int AS tickets
            FROM retail_sale_items si
            JOIN retail_sales s ON s.id=si.sale_id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            ''',
            [since, until],
            one=True,
        ) or {
            'ventas_brutas_ars': Decimal('0.00'),
            'descuentos_ars': Decimal('0.00'),
            'ventas_netas_ars': Decimal('0.00'),
            'margen_bruto_ars': Decimal('0.00'),
            'unidades': 0,
            'tickets': 0,
        }
        tickets = int(row.get('tickets') or 0)
        ventas_netas = _to_decimal(row.get('ventas_netas_ars') or 0, 'ventas_netas_ars')
        row['ticket_promedio_ars'] = (ventas_netas / Decimal(tickets)).quantize(TWO_DEC, rounding=ROUND_HALF_UP) if tickets > 0 else Decimal('0.00')
        return Response({'range': {'from': since, 'to': until}, 'summary': row})


class RetailReporteAnalisisProductosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        if not _can_view_costs(request):
            raise PermissionDenied('No autorizado para ver costos/rentabilidad')
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT p.id AS product_id,
                   p.name AS producto,
                   v.id AS variant_id,
                   v.sku,
                   v.option_signature,
                   v.stock_on_hand,
                   COALESCE(m.qty_delta,0)::int AS stock_delta_periodo,
                   SUM(si.quantity)::int AS unidades,
                   SUM(si.line_total_ars)::numeric(14,2) AS ventas_netas_ars,
                   SUM(si.unit_cost_snapshot_ars * si.quantity)::numeric(14,2) AS costo_ars,
                   (SUM(si.line_total_ars) - SUM(si.unit_cost_snapshot_ars * si.quantity))::numeric(14,2) AS margen_ars
            FROM retail_sale_items si
            JOIN retail_sales s ON s.id=si.sale_id
            JOIN retail_product_variants v ON v.id=si.variant_id
            JOIN retail_products p ON p.id=v.product_id
            LEFT JOIN (
              SELECT variant_id, SUM(qty_signed)::int AS qty_delta
              FROM retail_stock_movements
              WHERE created_at::date BETWEEN %s AND %s
              GROUP BY variant_id
            ) m ON m.variant_id=v.id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.id, p.name, v.id, v.sku, v.option_signature, v.stock_on_hand, m.qty_delta
            ORDER BY margen_ars DESC, unidades DESC
            ''',
            [since, until, since, until],
        ) or []

        out = []
        units_samples = []
        margin_samples = []
        rotation_samples = []
        max_units = 0
        max_margin = None
        max_rotation = None
        for row in rows:
            units = int(row.get('unidades') or 0)
            stock_actual = int(row.get('stock_on_hand') or 0)
            stock_delta = int(row.get('stock_delta_periodo') or 0)
            stock_inicio = max(0, stock_actual - stock_delta)
            stock_promedio = ((Decimal(stock_inicio) + Decimal(max(0, stock_actual))) / Decimal('2')).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            rotation_idx = None
            if stock_promedio > 0:
                rotation_idx = (Decimal(units) / stock_promedio).quantize(FOUR_DEC, rounding=ROUND_HALF_UP)

            costo_ars = _to_decimal(row.get('costo_ars') or 0, 'costo_ars')
            margen_ars = _to_decimal(row.get('margen_ars') or 0, 'margen_ars')
            margen_pct = _safe_pct(margen_ars, costo_ars)

            units_samples.append(units)
            if margen_pct is not None:
                margin_samples.append(float(margen_pct))
            if rotation_idx is not None:
                rotation_samples.append(float(rotation_idx))
            max_units = max(max_units, units)
            max_margin = margen_ars if max_margin is None else max(max_margin, margen_ars)
            if rotation_idx is not None:
                max_rotation = rotation_idx if max_rotation is None else max(max_rotation, rotation_idx)

            out.append(
                {
                    'product_id': int(row['product_id']),
                    'producto': row.get('producto') or '',
                    'variant_id': int(row['variant_id']),
                    'sku': row.get('sku') or '',
                    'option_signature': row.get('option_signature') or '',
                    'unidades': units,
                    'ventas_netas_ars': _to_decimal(row.get('ventas_netas_ars') or 0, 'ventas_netas_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'costo_ars': costo_ars.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'margen_ars': margen_ars.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'margen_pct': margen_pct,
                    'stock_actual': stock_actual,
                    'stock_inicio_estimado': stock_inicio,
                    'stock_promedio_estimado': stock_promedio,
                    'rotacion_idx': rotation_idx,
                    'labels': [],
                }
            )

        p25_units = _percentile(units_samples, 0.25)
        p50_units = _percentile(units_samples, 0.50)
        p75_units = _percentile(units_samples, 0.75)
        p25_margin = _percentile(margin_samples, 0.25)
        p75_margin = _percentile(margin_samples, 0.75)
        p50_rotation = _percentile(rotation_samples, 0.50)

        for row in out:
            labels = []
            units = int(row.get('unidades') or 0)
            margin_pct = row.get('margen_pct')
            rotation_idx = row.get('rotacion_idx')

            margin_float = float(margin_pct) if margin_pct is not None else None
            rotation_float = float(rotation_idx) if rotation_idx is not None else None

            if margin_float is not None and p75_margin is not None and p25_units is not None:
                if margin_float >= p75_margin and units <= p25_units:
                    labels.append('buen_margen_poca_venta')
            if margin_float is not None and p25_margin is not None and p75_units is not None:
                if margin_float <= p25_margin and units >= p75_units:
                    labels.append('mucha_venta_margen_bajo')
            if max_margin is not None and _to_decimal(row.get('margen_ars') or 0, 'margen_ars') == max_margin and max_margin > 0:
                labels.append('mas_ganancia')
            if max_rotation is not None and rotation_idx is not None and rotation_idx == max_rotation and max_rotation > 0:
                labels.append('rotador')
            elif max_rotation is None and max_units > 0 and units == max_units:
                labels.append('rotador')

            if margin_float is not None and p75_margin is not None and margin_float >= p75_margin:
                if rotation_float is not None and p50_rotation is not None and rotation_float >= p50_rotation:
                    labels.append('conviene')
                elif rotation_float is None and p50_units is not None and units >= p50_units:
                    labels.append('conviene')

            row['labels'] = labels

        return Response(
            {
                'range': {'from': since, 'to': until},
                'thresholds': {
                    'units_p25': p25_units,
                    'units_p75': p75_units,
                    'margin_p25': p25_margin,
                    'margin_p75': p75_margin,
                    'rotation_p50': p50_rotation,
                },
                'rows': out,
            }
        )


class RetailReporteAnalisisProveedoresView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        if not _can_view_costs(request):
            raise PermissionDenied('No autorizado para ver costos/rentabilidad')
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT sp.id AS supplier_id,
                   sp.name AS proveedor,
                   SUM(pi.line_total_ars)::numeric(14,2) AS costo_total_ars,
                   SUM(pi.unit_price_final_ars * pi.quantity)::numeric(14,2) AS ingreso_potencial_ars,
                   AVG(pi.real_margin_pct)::numeric(8,2) AS margen_promedio_pct,
                   COALESCE(STDDEV_POP(pi.real_margin_pct),0)::numeric(8,2) AS consistencia_stddev_pct,
                   COUNT(*)::int AS item_count,
                   COUNT(DISTINCT pi.variant_id)::int AS variantes
            FROM retail_purchase_items pi
            JOIN retail_purchases p ON p.id=pi.purchase_id
            JOIN retail_suppliers sp ON sp.id=p.supplier_id
            WHERE p.purchase_date BETWEEN %s AND %s
              AND pi.unit_price_final_ars IS NOT NULL
            GROUP BY sp.id, sp.name
            ''',
            [since, until],
        ) or []

        total_cost = Decimal('0.00')
        out = []
        for row in rows:
            costo_total = _to_decimal(row.get('costo_total_ars') or 0, 'costo_total_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            ingreso_potencial = _to_decimal(row.get('ingreso_potencial_ars') or 0, 'ingreso_potencial_ars').quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            ganancia_potencial = (ingreso_potencial - costo_total).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
            margen_promedio = _to_decimal(row.get('margen_promedio_pct') or 0, 'margen_promedio_pct', allow_none=True)
            consistencia = _to_decimal(row.get('consistencia_stddev_pct') or 0, 'consistencia_stddev_pct', allow_none=True) or Decimal('0.00')
            margen_ponderado = _safe_pct(ganancia_potencial, costo_total) or Decimal('0.00')
            total_cost += costo_total
            out.append(
                {
                    'supplier_id': int(row['supplier_id']),
                    'proveedor': row.get('proveedor') or '',
                    'costo_total_ars': costo_total,
                    'ingreso_potencial_ars': ingreso_potencial,
                    'ganancia_potencial_ars': ganancia_potencial,
                    'margen_promedio_pct': (margen_promedio or Decimal('0.00')).quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'margen_ponderado_pct': margen_ponderado.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'consistencia_stddev_pct': consistencia.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                    'item_count': int(row.get('item_count') or 0),
                    'variantes': int(row.get('variantes') or 0),
                }
            )

        for row in out:
            row['dependencia_pct_costo'] = (_safe_pct(row['costo_total_ars'], total_cost) or Decimal('0.00')).quantize(TWO_DEC, rounding=ROUND_HALF_UP)

        out.sort(
            key=lambda r: (
                _to_decimal(r.get('ganancia_potencial_ars') or 0, 'ganancia_potencial_ars'),
                _to_decimal(r.get('margen_ponderado_pct') or 0, 'margen_ponderado_pct'),
                -_to_decimal(r.get('consistencia_stddev_pct') or 0, 'consistencia_stddev_pct'),
            ),
            reverse=True,
        )

        for idx, row in enumerate(out, start=1):
            row['rank'] = idx
            row['conviene_trabajar_mas'] = idx == 1

        return Response({'range': {'from': since, 'to': until}, 'rows': out})


class RetailReporteMasVendidosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        limit = _to_int(request.query_params.get('limit') or 20, 'limit')
        rows = q(
            '''
            SELECT p.id AS product_id, p.name AS producto,
                   v.id AS variant_id, v.sku, v.option_signature,
                   SUM(si.quantity)::int AS unidades,
                   SUM(si.line_total_ars)::numeric(14,2) AS total_ars
            FROM retail_sale_items si
            JOIN retail_sales s ON s.id=si.sale_id
            JOIN retail_product_variants v ON v.id=si.variant_id
            JOIN retail_products p ON p.id=v.product_id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.id, p.name, v.id, v.sku, v.option_signature
            ORDER BY unidades DESC, total_ars DESC
            LIMIT %s
            ''',
            [since, until, max(1, min(limit, 500))],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': rows})


class RetailReporteTallesColoresView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT a.name AS atributo, ov.option_value AS valor,
                   SUM(si.quantity)::int AS unidades
            FROM retail_sale_items si
            JOIN retail_sales s ON s.id=si.sale_id
            JOIN retail_variant_option_values ov ON ov.variant_id=si.variant_id
            JOIN retail_variant_attributes a ON a.id=ov.attribute_id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            GROUP BY a.name, ov.option_value
            ORDER BY a.name, unidades DESC, ov.option_value
            ''',
            [since, until],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': rows})


class RetailReporteBajoStockView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        rows = q(
            '''
            SELECT v.id, v.sku, v.barcode_internal, v.stock_on_hand, v.stock_min,
                   v.option_signature, p.name AS producto
            FROM retail_product_variants v
            JOIN retail_products p ON p.id=v.product_id
            WHERE v.active=TRUE AND v.stock_on_hand <= v.stock_min
            ORDER BY v.stock_on_hand ASC, v.stock_min ASC, p.name
            '''
        ) or []
        return Response(rows)


class RetailReporteRentabilidadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        if not _can_view_costs(request):
            raise PermissionDenied('No autorizado para ver costos/rentabilidad')
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT p.id AS product_id, p.name AS producto,
                   SUM(si.line_total_ars)::numeric(14,2) AS ventas_ars,
                   SUM(si.unit_cost_snapshot_ars * si.quantity)::numeric(14,2) AS costo_ars,
                   (SUM(si.line_total_ars) - SUM(si.unit_cost_snapshot_ars * si.quantity))::numeric(14,2) AS margen_ars
            FROM retail_sale_items si
            JOIN retail_sales s ON s.id=si.sale_id
            JOIN retail_product_variants v ON v.id=si.variant_id
            JOIN retail_products p ON p.id=v.product_id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.id, p.name
            ORDER BY margen_ars DESC
            ''',
            [since, until],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': rows})


class RetailReporteVentasPorMedioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT s.created_at::date AS day,
                   s.payment_method,
                   COALESCE(pa.code,'') AS payment_account_code,
                   COALESCE(pa.label,'') AS payment_account_label,
                   COUNT(*)::int AS sales_count,
                   SUM(s.total_ars)::numeric(14,2) AS total_ars
            FROM retail_sales s
            LEFT JOIN retail_payment_accounts pa ON pa.id=s.payment_account_id
            WHERE s.status IN ('confirmed','partial_return','returned')
              AND s.created_at::date BETWEEN %s AND %s
            GROUP BY s.created_at::date, s.payment_method, pa.code, pa.label
            ORDER BY day DESC, payment_method, payment_account_code
            ''',
            [since, until],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': rows})


class RetailReporteCierreCajaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        sessions = q(
            '''
            SELECT cs.id, cs.status, cs.opened_at, cs.closed_at,
                   cs.opening_amount_cash_ars, cs.closing_expected_total_ars,
                   cs.closing_counted_total_ars, cs.difference_total_ars,
                   COALESCE(uo.nombre,'') AS opened_by_name,
                   COALESCE(uc.nombre,'') AS closed_by_name
            FROM retail_cash_sessions cs
            LEFT JOIN users uo ON uo.id=cs.opened_by
            LEFT JOIN users uc ON uc.id=cs.closed_by
            WHERE cs.opened_at::date BETWEEN %s AND %s
            ORDER BY cs.id DESC
            ''',
            [since, until],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': sessions})


class RetailReporteDevolucionesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_admin(request)
        since, until = _parse_dates(request)
        rows = q(
            '''
            SELECT r.created_at::date AS day,
                   r.id AS return_id,
                   r.sale_id,
                   r.status,
                   r.reason,
                   r.total_refund_ars,
                   r.requires_credit_note,
                   r.credit_note_status,
                   COALESCE(u.nombre,'') AS processed_by_name
            FROM retail_returns r
            LEFT JOIN users u ON u.id=r.processed_by
            WHERE r.created_at::date BETWEEN %s AND %s
            ORDER BY r.id DESC
            ''',
            [since, until],
        ) or []
        return Response({'range': {'from': since, 'to': until}, 'rows': rows})


__all__ = [
    'RetailProductosView',
    'RetailProductoDetailView',
    'RetailProductoImagenView',
    'RetailAtributosView',
    'RetailVariantesView',
    'RetailVarianteDetailView',
    'RetailVarianteEscanearView',
    'RetailComprasConfigView',
    'RetailComprasProveedoresView',
    'RetailComprasView',
    'RetailCompraDetailView',
    'RetailCajaAperturaView',
    'RetailCajaCierreView',
    'RetailCajaActualView',
    'RetailCajaDetailView',
    'RetailCajaCuentasView',
    'RetailVentasView',
    'RetailVentaDetailView',
    'RetailPromocionesView',
    'RetailPromocionDetailView',
    'RetailGarantiaTicketView',
    'RetailGarantiasActivasView',
    'RetailVentasCotizarView',
    'RetailVentasConfirmarView',
    'RetailVentaAnularView',
    'RetailVentaDevolverView',
    'RetailVentaCambiarView',
    'RetailFacturacionEmitirView',
    'RetailFacturacionDetailView',
    'RetailFacturacionNotaCreditoView',
    'RetailConfigSettingsView',
    'RetailConfigPageSettingsView',
    'RetailConfigPaymentAccountsView',
    'RetailOnlineSyncCatalogoView',
    'RetailOnlineSyncStockView',
    'RetailOnlineWebhookOrdenPagadaView',
    'RetailOnlineWebhookOrdenCanceladaView',
    'RetailOnlineWebhookStoreRedactView',
    'RetailReporteResumenComercialView',
    'RetailReporteAnalisisProductosView',
    'RetailReporteAnalisisProveedoresView',
    'RetailReporteMasVendidosView',
    'RetailReporteTallesColoresView',
    'RetailReporteBajoStockView',
    'RetailReporteRentabilidadView',
    'RetailReporteVentasPorMedioView',
    'RetailReporteCierreCajaView',
    'RetailReporteDevolucionesView',
]






