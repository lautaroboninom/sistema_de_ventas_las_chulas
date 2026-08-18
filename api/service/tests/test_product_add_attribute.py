"""Flujo guiado para agregar un atributo a un producto que ya tiene variantes.

Es el reemplazo del camino que rompio el caso "Petra": en vez de dejar las variantes
viejas con un atributo menos, se les completa el valor y solo se crean las que faltan.
"""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import django
from rest_framework.exceptions import ValidationError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

import service.views.retail_views as rv


def _hay_conexion_db():
    """La vista usa `transaction.atomic`, que necesita una conexion real aunque el
    resto del test este mockeado."""
    from django.db import connection

    try:
        connection.ensure_connection()
        return True
    except Exception:
        return False


DB_DISPONIBLE = _hay_conexion_db()


def _user():
    return SimpleNamespace(id=3, rol='admin', nombre='Admin Test')


def _request(data):
    return SimpleNamespace(data=data, user=_user(), method='POST')


ATRIBUTOS = {
    'talle': {'id': 1, 'code': 'talle', 'name': 'Talle', 'sort_order': 10},
    'color': {'id': 2, 'code': 'color', 'name': 'Color', 'sort_order': 20},
}


def _variante(vid, sku, talle):
    return {
        'id': vid,
        'sku': sku,
        'display_name': f'Petra ({talle})',
        'option_signature': f'talle={talle.lower()}',
        'option_values': [
            {
                'variant_id': vid,
                'attribute_id': 1,
                'attribute_code': 'talle',
                'attribute_name': 'Talle',
                'option_value': talle,
                'option_value_key': talle.lower(),
                'sort_order': 10,
            }
        ],
    }


@unittest.skipUnless(DB_DISPONIBLE, 'requiere Postgres: la vista corre dentro de transaction.atomic')
class AgregarAtributoTests(unittest.TestCase):
    def setUp(self):
        self.variantes = [_variante(101, 'PETRA-S', 'S'), _variante(102, 'PETRA-M', 'M')]
        self.creadas = []
        self.option_inserts = []
        self.signature_updates = []
        self.syncs = []

        def fake_normalize(data):
            items = (data or {}).get('option_values') or []
            normalized = []
            for item in items:
                code = str(item.get('attribute_code') or '').lower()
                attr = ATRIBUTOS[code]
                valor = str(item.get('value'))
                normalized.append(
                    {
                        'attribute_id': attr['id'],
                        'attribute_value_id': None,
                        'attribute_code': code,
                        'attribute_name': attr['name'],
                        'value': valor,
                        'value_key': valor.lower(),
                        'sort_order': attr['sort_order'],
                    }
                )
            normalized.sort(key=lambda x: (x['sort_order'], x['attribute_code']))
            firma = '|'.join(f"{x['attribute_code']}={x['value_key']}" for x in normalized)
            return normalized, firma

        def fake_create(**kwargs):
            nuevo_id = 900 + len(self.creadas)
            self.creadas.append(kwargs)
            return nuevo_id

        def fake_exec(sql, params=None):
            texto = ' '.join(str(sql).split()).lower()
            if 'insert into retail_variant_option_values' in texto:
                self.option_inserts.append(params)
            elif 'update retail_product_variants set option_signature' in texto:
                self.signature_updates.append(params)

        self.patches = [
            patch.object(rv, '_require_staff', return_value=None),
            patch.object(rv, '_set_audit_user', return_value=None),
            patch.object(rv, '_product_name', return_value={'id': 77, 'name': 'Pantalon Sastrero Petra'}),
            patch.object(rv, '_attribute_by_ref', side_effect=lambda **kw: ATRIBUTOS[kw.get('attribute_code')]),
            patch.object(rv, '_product_active_variants_with_options', side_effect=lambda pid: self.variantes),
            patch.object(rv, '_normalize_option_values', side_effect=fake_normalize),
            patch.object(rv, '_find_variant_signature_duplicate', return_value=None),
            patch.object(rv, '_create_product_variant', side_effect=fake_create),
            patch.object(rv, 'exec_void', side_effect=fake_exec),
            patch.object(rv, '_list_variantes_de_producto', return_value=[]),
            patch.object(
                rv,
                '_tiendanube_schedule_local_variants_sync',
                side_effect=lambda ids, **kw: self.syncs.append((list(ids), kw)),
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_completa_existentes_y_crea_solo_las_faltantes(self):
        response = rv.RetailProductoAgregarAtributoView().post(
            _request({'attribute_code': 'color', 'existing_value': 'Negro', 'new_values': ['Chocolate']}),
            77,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['actualizadas'], 2)
        self.assertEqual(response.data['creadas'], 2)
        # Las existentes quedaron con color=negro sumado a su talle.
        self.assertEqual(
            sorted(params[-1] for params in self.signature_updates),
            [101, 102],
        )
        firmas = sorted(params[0] for params in self.signature_updates)
        self.assertEqual(firmas, ['talle=m|color=negro', 'talle=s|color=negro'])
        # Las nuevas son solo las de chocolate.
        firmas_nuevas = sorted(item['signature'] for item in self.creadas)
        self.assertEqual(firmas_nuevas, ['talle=m|color=chocolate', 'talle=s|color=chocolate'])

    def test_dispara_un_solo_sync_con_todas_las_variantes(self):
        rv.RetailProductoAgregarAtributoView().post(
            _request({'attribute_code': 'color', 'existing_value': 'Negro', 'new_values': ['Chocolate']}),
            77,
        )

        self.assertEqual(len(self.syncs), 1)
        ids, kwargs = self.syncs[0]
        self.assertEqual(sorted(ids), [101, 102, 900, 901])
        self.assertTrue(kwargs['sync_catalog'])
        self.assertEqual(kwargs['reason'], 'product_add_attribute')

    def test_rechaza_si_el_producto_ya_usa_ese_atributo(self):
        self.variantes[0]['option_values'].append(
            {
                'variant_id': 101,
                'attribute_id': 2,
                'attribute_code': 'color',
                'attribute_name': 'Color',
                'option_value': 'Negro',
                'option_value_key': 'negro',
                'sort_order': 20,
            }
        )

        with self.assertRaises(ValidationError) as ctx:
            rv.RetailProductoAgregarAtributoView().post(
                _request({'attribute_code': 'color', 'existing_value': 'Negro', 'new_values': ['Chocolate']}),
                77,
            )
        self.assertIn('ya usan el atributo', str(ctx.exception))

    def test_exige_el_valor_de_las_variantes_actuales(self):
        with self.assertRaises(ValidationError):
            rv.RetailProductoAgregarAtributoView().post(
                _request({'attribute_code': 'color', 'new_values': ['Chocolate']}),
                77,
            )

    def test_sin_valores_nuevos_solo_completa_las_existentes(self):
        response = rv.RetailProductoAgregarAtributoView().post(
            _request({'attribute_code': 'color', 'existing_value': 'Negro', 'new_values': []}),
            77,
        )

        self.assertEqual(response.data['actualizadas'], 2)
        self.assertEqual(response.data['creadas'], 0)
        self.assertEqual(self.creadas, [])

    def test_ignora_valor_nuevo_repetido_del_existente(self):
        response = rv.RetailProductoAgregarAtributoView().post(
            _request(
                {
                    'attribute_code': 'color',
                    'existing_value': 'Negro',
                    'new_values': ['negro', 'Chocolate', 'Chocolate'],
                }
            ),
            77,
        )

        self.assertEqual(response.data['valores_nuevos'], ['Chocolate'])
        self.assertEqual(response.data['creadas'], 2)

    def test_devuelve_409_si_la_combinacion_ya_existe(self):
        duplicado = {'id': 555, 'product_id': 77, 'active': True, 'option_signature': 'talle=s|color=negro'}
        with patch.object(rv, '_find_variant_signature_duplicate', return_value=duplicado):
            response = rv.RetailProductoAgregarAtributoView().post(
                _request({'attribute_code': 'color', 'existing_value': 'Negro', 'new_values': []}),
                77,
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'variant_combination_conflict')


if __name__ == '__main__':
    unittest.main()
