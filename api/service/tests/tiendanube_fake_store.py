"""Tienda Nube simulada en memoria para tests de push de catalogo.

Permite ejercitar las funciones reales de `service.views.retail_views` sin red y sin
base de datos: la tienda remota y las filas locales viven en memoria.
"""

import json
import os
import re
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import django
from rest_framework.exceptions import ValidationError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()


CFG = {'store_id': '1', 'access_token': 'token-test', 'api_base': 'https://api.test', 'timeout': 10}


class FakeTiendaNube:
    """Implementa el subconjunto de la API de Tienda Nube que usa el push de catalogo."""

    def __init__(self, next_product_id=900, next_variant_id=9000):
        self.next_product_id = next_product_id
        self.next_variant_id = next_variant_id
        self.products = {}
        self.calls = []

    # -- helpers de armado ------------------------------------------------
    def create_product(self, payload):
        self.next_product_id += 1
        pid = self.next_product_id
        variants = []
        for variant in (payload or {}).get('variants') or []:
            self.next_variant_id += 1
            item = dict(variant)
            item['id'] = self.next_variant_id
            variants.append(item)
        self.products[pid] = {
            'id': pid,
            'name': (payload or {}).get('name'),
            'published': (payload or {}).get('published'),
            'attributes': (payload or {}).get('attributes') or [],
            'variants': variants,
            'images': [],
        }
        return self.products[pid]

    def seed_product(self, *, attributes, variants, published=True, images=None):
        payload = {'name': {'es': 'Seed'}, 'published': published, 'attributes': attributes, 'variants': variants}
        product = self.create_product(payload)
        product['images'] = list(images or [])
        return product

    def variant_skus(self, product_id):
        product = self.products.get(int(product_id)) or {}
        return [v.get('sku') for v in product.get('variants') or []]

    def calls_matching(self, prefix):
        return [call for call in self.calls if call.startswith(prefix)]

    def product_delete_calls(self):
        """Solo borrados de producto completo (no de variantes)."""
        return [call for call in self.calls if re.fullmatch(r'DELETE products/\d+', call)]

    # -- transporte -------------------------------------------------------
    def request(self, cfg, method, path, payload=None, timeout_cap=None, allow_404=False):
        method = str(method or 'GET').upper()
        rel = str(path or '').strip('/')
        self.calls.append(f'{method} {rel}')
        parts = rel.split('/')

        if method == 'POST' and parts == ['products']:
            return self.create_product(payload or {})

        if method == 'GET' and len(parts) == 2 and parts[0] == 'products':
            product = self.products.get(int(parts[1]))
            if product is None:
                if allow_404:
                    return None
                raise ValidationError('Tienda Nube HTTP 404: Not Found')
            return json.loads(json.dumps(product))

        if method == 'PUT' and len(parts) == 2 and parts[0] == 'products':
            product = self.products.get(int(parts[1]))
            if product is None:
                raise ValidationError('Tienda Nube HTTP 404: Not Found')
            for key, value in (payload or {}).items():
                if key != 'id':
                    product[key] = value
            return product

        if method == 'DELETE' and len(parts) == 2 and parts[0] == 'products':
            self.products.pop(int(parts[1]), None)
            return {}

        if method == 'POST' and len(parts) == 3 and parts[0] == 'products' and parts[2] == 'variants':
            product = self.products.get(int(parts[1]))
            if product is None:
                raise ValidationError('Tienda Nube HTTP 404: Not Found')
            self.next_variant_id += 1
            item = dict(payload or {})
            item['id'] = self.next_variant_id
            product['variants'].append(item)
            return item

        if method == 'PUT' and len(parts) == 4 and parts[0] == 'products' and parts[2] == 'variants':
            product = self.products.get(int(parts[1])) or {}
            for variant in product.get('variants') or []:
                if variant.get('id') == int(parts[3]):
                    for key, value in (payload or {}).items():
                        if key != 'id':
                            variant[key] = value
                    return variant
            raise ValidationError('Tienda Nube HTTP 404: variante inexistente')

        if method == 'DELETE' and len(parts) == 4 and parts[0] == 'products' and parts[2] == 'variants':
            product = self.products.get(int(parts[1]))
            if product is not None:
                product['variants'] = [v for v in product['variants'] if v.get('id') != int(parts[3])]
            return {}

        if method == 'POST' and len(parts) == 3 and parts[0] == 'products' and parts[2] == 'images':
            product = self.products.get(int(parts[1]))
            if product is None:
                raise ValidationError('Tienda Nube HTTP 404: Not Found')
            image = dict(payload or {})
            image['id'] = len(product.setdefault('images', [])) + 1
            product['images'].append(image)
            return image

        raise AssertionError(f'llamada no simulada a Tienda Nube: {method} {rel}')


class FakeLocalDb:
    """Filas locales de `retail_product_variants` en memoria."""

    def __init__(self, rows=None):
        self.rows = {}
        for row in rows or []:
            self.rows[int(row['id'])] = row

    def add(self, row):
        self.rows[int(row['id'])] = row
        return row

    def active_rows(self, product_id=None):
        out = [self.rows[key] for key in sorted(self.rows) if self.rows[key].get('active')]
        if product_id is not None:
            out = [row for row in out if int(row.get('product_id') or 0) == int(product_id)]
        return out

    def get(self, variant_id):
        return self.rows.get(int(variant_id))

    # -- reemplazos de acceso a datos -------------------------------------
    def exec_void(self, sql, params=None):
        text = ' '.join(str(sql).split()).lower()
        params = list(params or [])
        if 'update retail_product_variants' not in text or not params:
            return None
        row = self.rows.get(int(params[-1]))
        if row is None:
            return None
        if 'tiendanube_product_id=null' in text:
            row['tiendanube_product_id'] = None
            row['tiendanube_variant_id'] = None
        elif 'tiendanube_product_id=%s' in text:
            row['tiendanube_product_id'] = params[0]
            row['tiendanube_variant_id'] = params[1]
        return None

    def q(self, sql, params=None, one=False):
        text = ' '.join(str(sql).split()).lower()
        params = list(params or [])
        if 'count(*)' in text and 'retail_product_variants' in text and 'active=true' in text:
            product_id = int(params[0])
            exclude_id = int(params[1]) if len(params) > 1 else -1
            cnt = sum(
                1
                for row in self.rows.values()
                if int(row.get('product_id') or 0) == product_id
                and row.get('active')
                and int(row['id']) != exclude_id
            )
            return {'cnt': cnt} if one else [{'cnt': cnt}]
        if 'select 1' in text and 'retail_product_variants' in text and 'tiendanube_product_id=%s' in text:
            product_id = int(params[0])
            remote_id = int(params[1])
            hit = any(
                int(row.get('product_id') or 0) == product_id
                and row.get('active')
                and int(row.get('tiendanube_product_id') or 0) == remote_id
                for row in self.rows.values()
            )
            found = {'?column?': 1} if hit else None
            if one:
                return found
            return [found] if found else []
        raise AssertionError(f'consulta no simulada: {text[:160]}')


def local_variant(
    variant_id,
    sku,
    options,
    *,
    product_id=77,
    producto='Pantalon Sastrero Petra',
    stock=0,
    active=True,
    tiendanube_product_id=None,
    tiendanube_variant_id=None,
    price='45000.00',
    cost='20000.00',
    barcode=None,
):
    """Fila local equivalente a la que devuelve `_tiendanube_load_local_product_group`."""
    return {
        'id': variant_id,
        'product_id': product_id,
        'sku': sku,
        'barcode_internal': barcode if barcode is not None else f'77900000{variant_id:04d}',
        'display_name': f'{producto} ({sku or variant_id})',
        'active': active,
        'product_active': True,
        'stock_on_hand': stock,
        'price_online_ars': price,
        'cost_avg_ars': cost,
        'producto': producto,
        'name': producto,
        'marca': '',
        'tiendanube_product_id': tiendanube_product_id,
        'tiendanube_variant_id': tiendanube_variant_id,
        'option_values': list(options or []),
    }


def option(code, name, value):
    return {
        'attribute_code': code,
        'attribute_name': name,
        'option_value': value,
        'option_value_key': str(value).lower(),
    }


def talle(value):
    return option('talle', 'Talle', value)


def color(value):
    return option('color', 'Color', value)


@contextmanager
def patched_tiendanube(store, db, *, lookup_by_sku=True):
    """Parcha transporte y acceso a datos de `retail_views` contra los dobles en memoria."""
    import service.views.retail_views as rv

    def _lookup(_cfg, sku):
        if not lookup_by_sku:
            return {'product_id': None, 'variant_id': None}
        for product in store.products.values():
            for variant in product.get('variants') or []:
                if str(variant.get('sku') or '').lower() == str(sku or '').lower():
                    return {'product_id': product['id'], 'variant_id': variant['id']}
        return {'product_id': None, 'variant_id': None}

    with ExitStack() as stack:
        stack.enter_context(patch.object(rv, '_tiendanube_request', side_effect=store.request))
        stack.enter_context(patch.object(rv, '_tiendanube_cfg', return_value=CFG))
        stack.enter_context(patch.object(rv, 'exec_void', side_effect=db.exec_void))
        stack.enter_context(patch.object(rv, 'q', side_effect=db.q))
        stack.enter_context(patch.object(rv, '_tiendanube_lookup_variant_ids_by_sku', side_effect=_lookup))
        stack.enter_context(
            patch.object(
                rv,
                '_tiendanube_load_local_product_group',
                side_effect=lambda pid: db.active_rows(product_id=pid),
            )
        )
        yield rv
