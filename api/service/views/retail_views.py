import base64
import datetime as dt
import hashlib
import hmac
import json
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
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import user_has_permission
from .helpers import _set_audit_user, exec_returning, exec_void, q, require_roles


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
        'garantias': 'Cambios y devoluciones vigentes',
        'reportes': 'Reportes retail',
        'online': 'Online (Tienda Nube)',
        'config': 'Configuracion',
        'config_paginas': 'Configuracion de paginas',
    },
}
VALID_DEFAULT_ROUTES = {'/pos', '/productos', '/compras', '/ventas', '/garantias', '/online', '/config'}


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
    if size_days <= 0:
        size_days = 30
    if breakage_days <= 0:
        breakage_days = 90
    return {
        'arca_env': row.get('arca_env') or 'homologacion',
        'arca_cuit': row.get('arca_cuit') or '',
        'arca_pto_vta_store': row.get('arca_pto_vta_store') or 1,
        'arca_pto_vta_online': row.get('arca_pto_vta_online') or (row.get('arca_pto_vta_store') or 1),
        'tiendanube_store_id': row.get('tiendanube_store_id'),
        'tiendanube_access_token': row.get('tiendanube_access_token') or '',
        'tiendanube_webhook_secret': row.get('tiendanube_webhook_secret') or '',
        'auto_invoice_online_paid': bool(row.get('auto_invoice_online_paid')),
        'return_warranty_size_days': size_days,
        'return_warranty_breakage_days': breakage_days,
        'ui_page_settings': _normalize_ui_page_settings(row.get('ui_page_settings')),
    }


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
        row = q('SELECT id, code, label, active FROM retail_payment_accounts WHERE id=%s', [account_id], one=True)
    elif account_code:
        row = q('SELECT id, code, label, active FROM retail_payment_accounts WHERE LOWER(code)=LOWER(%s)', [account_code], one=True)
    else:
        default_code = DEFAULT_ACCOUNT_BY_METHOD.get(payment_method)
        if default_code:
            row = q('SELECT id, code, label, active FROM retail_payment_accounts WHERE code=%s', [default_code], one=True)

    if not row:
        raise ValidationError('Cuenta/caja de cobro invalida')
    if not row.get('active'):
        raise ValidationError('Cuenta/caja inactiva')
    return row


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
               pi.unit_cost_currency, pi.unit_cost_ars, pi.line_total_ars,
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
            item['line_total_ars'] = None
    head['items'] = items
    return head


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
                  unit_cost_currency, unit_cost_ars, line_total_ars
                )
                VALUES (%s,%s,%s,%s,%s,%s)
                ''',
                [purchase_id, variant_id, qty, unit_cost_currency, unit_cost_ars, line_total],
            )
            exec_void('UPDATE retail_product_variants SET stock_on_hand=%s, cost_avg_ars=%s WHERE id=%s', [new_stock, new_cost, variant_id])
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
        parsed.append({'variant_id': variant_id, 'quantity': qty, 'unit_price_override_ars': override})
    return parsed


def _build_quote(request, payload, lock_variants=False):
    channel = _normalize_channel(payload.get('channel'))
    payment_method = _normalize_payment_method(payload.get('payment_method'))
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

    modifier_pct = PAYMENT_MODIFIERS[payment_method]
    modifier_ratio = (Decimal('1.00') + (modifier_pct / Decimal('100.00')))

    subtotal = Decimal('0.00')
    total = Decimal('0.00')
    lines = []
    any_override = False

    for item in items:
        variant = variants[item['variant_id']]
        qty = int(item['quantity'])
        if lock_variants and int(variant['stock_on_hand']) < qty:
            raise ValidationError(f"Stock insuficiente para variante {variant['id']}")

        list_price = _to_decimal(variant['price_store_ars'] if channel == 'local' else variant['price_online_ars'], 'price')
        if item['unit_price_override_ars'] is not None:
            if not _can_override_price(request):
                raise PermissionDenied('No autorizado para override de precio')
            unit_price = _to_decimal(item['unit_price_override_ars'], 'unit_price_override_ars')
            any_override = True
        else:
            unit_price = list_price

        line_subtotal = (unit_price * Decimal(qty)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)
        line_total = (line_subtotal * modifier_ratio).quantize(TWO_DEC, rounding=ROUND_HALF_UP)

        subtotal += line_subtotal
        total += line_total

        lines.append(
            {
                'variant_id': variant['id'],
                'quantity': qty,
                'unit_price_list_ars': list_price.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_final_ars': (unit_price * modifier_ratio).quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_price_base_ars': unit_price.quantize(TWO_DEC, rounding=ROUND_HALF_UP),
                'unit_cost_snapshot_ars': _to_decimal(variant.get('cost_avg_ars') or 0, 'cost_avg_ars').quantize(FOUR_DEC, rounding=ROUND_HALF_UP),
                'line_subtotal_ars': line_subtotal,
                'line_total_ars': line_total,
            }
        )

    subtotal = subtotal.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    total = total.quantize(TWO_DEC, rounding=ROUND_HALF_UP)
    modifier_amount = (total - subtotal).quantize(TWO_DEC, rounding=ROUND_HALF_UP)

    return {
        'channel': channel,
        'payment_method': payment_method,
        'modifier_pct': modifier_pct,
        'modifier_amount_ars': modifier_amount,
        'subtotal_ars': subtotal,
        'total_ars': total,
        'invoice_required': payment_method in INVOICE_REQUIRED_METHODS,
        'items': lines,
        'any_override': any_override,
    }


def _sale_number(venta_id):
    today = timezone.localdate().strftime('%Y%m%d')
    return f"VTA-{today}-{int(venta_id):06d}"


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
        SELECT si.*, v.sku, v.barcode_internal, v.option_signature,
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
    sale['items'] = items
    sale['invoice'] = invoice
    sale['warranty'] = _sale_warranty_info(sale, sale_items=items, settings_row=warranty_settings)
    return sale


def _register_cash_in(session_id, sale_row, user_id, note='Venta mostrador'):
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
            sale_row['payment_method'],
            sale_row['payment_account_id'],
            sale_row['total_ars'],
            sale_row['id'],
            note,
            user_id,
        ],
    )


def _register_cash_out(session_id, sale_row, user_id, movement_type='return', note='Egreso por devolucion'):
    exec_void(
        '''
        INSERT INTO retail_cash_session_movements(
          cash_session_id, movement_type, direction, payment_method,
          payment_account_id, amount_ars, reference_type, reference_id, notes, created_by
        )
        VALUES (%s,%s,'out',%s,%s,%s,'sale',%s,%s,%s)
        ''',
        [
            session_id,
            movement_type,
            sale_row['payment_method'],
            sale_row['payment_account_id'],
            sale_row['total_ars'],
            sale_row['id'],
            note,
            user_id,
        ],
    )


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
                'price_modifier_pct': quote['modifier_pct'],
                'modifier_amount_ars': quote['modifier_amount_ars'],
                'subtotal_ars': quote['subtotal_ars'],
                'total_ars': quote['total_ars'],
                'invoice_required': quote['invoice_required'],
                'items': items,
            }
        )


class RetailVentasConfirmarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_staff(request)
        _set_audit_user(request)
        data = request.data or {}
        quote = _build_quote(request, data, lock_variants=True)
        payment_account = _ensure_payment_account(data, quote['payment_method'])
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
              customer_snapshot, subtotal_ars, price_adjustment_pct, price_adjustment_amount_ars,
              total_ars, currency_code, requires_invoice, notes, source_order_id,
              price_override_by, price_override_reason, created_by
            )
            VALUES (
              'PENDIENTE', %s, 'confirmed', %s, %s, %s,
              %s, %s, %s, %s,
              %s, 'ARS', %s, %s, %s,
              %s, %s, %s
            )
            RETURNING id
            ''',
            [
                channel,
                quote['payment_method'],
                payment_account['id'],
                cash_session_id,
                json.dumps(customer_snapshot),
                quote['subtotal_ars'],
                quote['modifier_pct'],
                quote['modifier_amount_ars'],
                quote['total_ars'],
                quote['invoice_required'],
                _clean_text(data.get('notes')),
                _clean_text(data.get('source_order_id')),
                getattr(request.user, 'id', None) if quote['any_override'] else None,
                override_reason,
                getattr(request.user, 'id', None),
            ],
        )
        exec_void('UPDATE retail_sales SET sale_number=%s WHERE id=%s', [_sale_number(sale_id), sale_id])

        for line in quote['items']:
            variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [line['variant_id']], one=True)
            new_stock = int(variant['stock_on_hand']) - int(line['quantity'])
            if new_stock < 0:
                raise ValidationError(f"Stock insuficiente para variante {line['variant_id']}")

            exec_void(
                '''
                INSERT INTO retail_sale_items(
                  sale_id, variant_id, quantity,
                  unit_price_list_ars, unit_price_final_ars, unit_cost_snapshot_ars,
                  line_subtotal_ars, line_total_ars
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ''',
                [
                    sale_id,
                    line['variant_id'],
                    line['quantity'],
                    line['unit_price_list_ars'],
                    line['unit_price_final_ars'],
                    line['unit_cost_snapshot_ars'],
                    line['line_subtotal_ars'],
                    line['line_total_ars'],
                ],
            )
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

        sale = _load_venta(sale_id, include_costs=True)
        if channel == 'local' and cash_session_id:
            _register_cash_in(cash_session_id, sale, getattr(request.user, 'id', None))

        auto_emit = bool(data.get('auto_emit_invoice'))
        if auto_emit and quote['invoice_required']:
            _emitir_factura(sale_id, request)

        return Response(_load_venta(sale_id, include_costs=_can_view_costs(request)), status=201)


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
                available = int(item['quantity']) - int(item['returned_qty'])
                if available > 0:
                    parsed.append({'sale_item_id': int(item['id']), 'quantity': available})

        if not parsed:
            raise ValidationError('No hay lineas disponibles para devolver')

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
            available = int(sale_item['quantity']) - int(sale_item['returned_qty'])
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
            exec_void(
                '''
                INSERT INTO retail_cash_session_movements(
                  cash_session_id, movement_type, direction, payment_method,
                  payment_account_id, amount_ars, reference_type, reference_id, notes, created_by
                )
                VALUES (%s,'return','out',%s,%s,%s,'return',%s,'Devolucion en caja',%s)
                ''',
                [
                    sale['cash_session_id'],
                    sale['payment_method'],
                    sale['payment_account_id'],
                    total_refund,
                    rid,
                    getattr(request.user, 'id', None),
                ],
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
    cfg = _load_settings()
    return _clean_text(cfg.get('tiendanube_webhook_secret')) or _clean_text(getattr(settings, 'TIENDANUBE_WEBHOOK_SECRET', ''))


def _verify_tiendanube_signature(request):
    secret = _webhook_secret()
    if not secret:
        raise ValidationError('Webhook secret de Tienda Nube no configurado')
    signature = request.headers.get('x-linkedstore-hmac-sha256') or request.headers.get('X-Linkedstore-Hmac-Sha256')
    if not signature:
        raise ValidationError('Firma de webhook ausente')
    expected = base64.b64encode(hmac.new(secret.encode('utf-8'), request.body or b'', hashlib.sha256).digest()).decode('ascii')
    if not hmac.compare_digest(signature, expected):
        raise ValidationError('Firma webhook invalida')


def _infer_payment_method_from_online(payload):
    txt = json.dumps(payload, ensure_ascii=False).lower()
    if 'credit' in txt or 'tarjeta de credito' in txt:
        return 'credit'
    if 'debit' in txt or 'debito' in txt:
        return 'debit'
    if 'cash' in txt or 'efectivo' in txt:
        return 'cash'
    return 'transfer'


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
            out.append({'variant_id': row['id'], 'quantity': qty})
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


class RetailOnlineWebhookOrdenPagadaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        _verify_tiendanube_signature(request)
        payload = _json(request.body)
        event_id = _clean_text(payload.get('event_id') or request.headers.get('x-event-id') or request.headers.get('X-Event-Id'))
        order_id = _clean_text(payload.get('id') or payload.get('order_id') or payload.get('number'))
        if not event_id:
            event_id = f'paid-{order_id}-{int(timezone.now().timestamp())}'
        if not order_id:
            raise ValidationError('order_id ausente en webhook')

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
            [event_id, order_id, request.headers.get('x-linkedstore-hmac-sha256'), json.dumps(payload)],
        )

        existing_sale = q('SELECT id FROM retail_sales WHERE source_order_id=%s', [order_id], one=True)
        if existing_sale:
            exec_void('UPDATE retail_webhook_events SET processed=TRUE, processed_at=NOW() WHERE id=%s', [event_db_id])
            return Response({'ok': True, 'duplicate': True, 'sale_id': existing_sale['id'], 'event_id': event_id})

        items = _extract_online_items(payload)
        payment_method = _infer_payment_method_from_online(payload)
        account_code = 'payway' if payment_method in ('debit', 'credit') else ('cash' if payment_method == 'cash' else 'transfer_1')

        sale_payload = {
            'channel': 'online',
            'payment_method': payment_method,
            'payment_account_code': account_code,
            'items': items,
            'source_order_id': order_id,
            'notes': 'Orden pagada webhook Tienda Nube',
            'auto_emit_invoice': _load_settings().get('auto_invoice_online_paid', True),
            'customer_name': _clean_text(payload.get('customer_name') or payload.get('name')),
            'customer_email': _clean_text(payload.get('customer_email') or payload.get('email')),
        }
        try:
            quote = _build_quote(request, sale_payload, lock_variants=True)
            payment_account = _ensure_payment_account(sale_payload, quote['payment_method'])

            sale_id = exec_returning(
                '''
                INSERT INTO retail_sales(
                  sale_number, channel, status, payment_method, payment_account_id, cash_session_id,
                  customer_snapshot, subtotal_ars, price_adjustment_pct, price_adjustment_amount_ars,
                  total_ars, currency_code, requires_invoice, notes, source_order_id,
                  price_override_by, price_override_reason, created_by
                )
                VALUES (
                  'PENDIENTE', %s, 'confirmed', %s, %s, NULL,
                  %s, %s, %s, %s,
                  %s, 'ARS', %s, %s, %s,
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
                    quote['modifier_pct'],
                    quote['modifier_amount_ars'],
                    quote['total_ars'],
                    quote['invoice_required'],
                    sale_payload.get('notes'),
                    order_id,
                ],
            )
            exec_void('UPDATE retail_sales SET sale_number=%s WHERE id=%s', [_sale_number(sale_id), sale_id])

            for line in quote['items']:
                variant = q('SELECT id, stock_on_hand FROM retail_product_variants WHERE id=%s FOR UPDATE', [line['variant_id']], one=True)
                new_stock = int(variant['stock_on_hand']) - int(line['quantity'])
                if new_stock < 0:
                    raise ValidationError(f"Stock insuficiente para variante {line['variant_id']}")
                exec_void(
                    '''
                    INSERT INTO retail_sale_items(
                      sale_id, variant_id, quantity,
                      unit_price_list_ars, unit_price_final_ars, unit_cost_snapshot_ars,
                      line_subtotal_ars, line_total_ars
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ''',
                    [
                        sale_id,
                        line['variant_id'],
                        line['quantity'],
                        line['unit_price_list_ars'],
                        line['unit_price_final_ars'],
                        line['unit_cost_snapshot_ars'],
                        line['line_subtotal_ars'],
                        line['line_total_ars'],
                    ],
                )
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


class RetailOnlineWebhookOrdenCanceladaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        _verify_tiendanube_signature(request)
        payload = _json(request.body)
        event_id = _clean_text(payload.get('event_id') or request.headers.get('x-event-id') or request.headers.get('X-Event-Id'))
        order_id = _clean_text(payload.get('id') or payload.get('order_id') or payload.get('number'))
        if not event_id:
            event_id = f'cancel-{order_id}-{int(timezone.now().timestamp())}'
        if not order_id:
            raise ValidationError('order_id ausente en webhook')

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
            [event_id, order_id, request.headers.get('x-linkedstore-hmac-sha256'), json.dumps(payload)],
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


class RetailConfigSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require_staff(request)
        row = q('SELECT * FROM retail_settings WHERE id=1', one=True)
        if not row:
            exec_void('INSERT INTO retail_settings(id) VALUES (1) ON CONFLICT (id) DO NOTHING')
            row = q('SELECT * FROM retail_settings WHERE id=1', one=True) or {}
        if _user_role(request) != 'admin':
            row['tiendanube_access_token'] = None
            row['tiendanube_client_secret'] = None
            row['tiendanube_webhook_secret'] = None
            row['arca_key_path'] = None
        return Response(row)

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
    'RetailComprasView',
    'RetailCompraDetailView',
    'RetailCajaAperturaView',
    'RetailCajaCierreView',
    'RetailCajaActualView',
    'RetailCajaDetailView',
    'RetailCajaCuentasView',
    'RetailVentasView',
    'RetailVentaDetailView',
    'RetailGarantiaTicketView',
    'RetailGarantiasActivasView',
    'RetailVentasCotizarView',
    'RetailVentasConfirmarView',
    'RetailVentaAnularView',
    'RetailVentaDevolverView',
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
    'RetailReporteMasVendidosView',
    'RetailReporteTallesColoresView',
    'RetailReporteBajoStockView',
    'RetailReporteRentabilidadView',
    'RetailReporteVentasPorMedioView',
    'RetailReporteCierreCajaView',
    'RetailReporteDevolucionesView',
]






