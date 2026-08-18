"""Regresiones del caso "Pantalon Sastrero Petra".

Cubren las tres fallas encadenadas que borraron un producto de Tienda Nube:
- agregar un segundo atributo abortaba la publicacion de todo el producto,
- borrar la ultima variante remota borraba el producto entero,
- el producto quedaba sin forma de volver a publicarse.
"""

import unittest
from unittest.mock import patch

from rest_framework.exceptions import ValidationError

from service.tests.tiendanube_fake_store import (
    CFG,
    FakeLocalDb,
    FakeTiendaNube,
    color,
    local_variant,
    patched_tiendanube,
    talle,
)


def _viejas():
    return [
        local_variant(101, 'PETRA-S', [talle('S')], stock=3),
        local_variant(102, 'PETRA-M', [talle('M')], stock=4),
        local_variant(103, 'PETRA-L', [talle('L')], stock=2),
    ]


def _nuevas(active=True):
    return [
        local_variant(201, 'PETRA-NEG-S', [color('Negro'), talle('S')], stock=3, active=active),
        local_variant(202, 'PETRA-NEG-M', [color('Negro'), talle('M')], stock=4, active=active),
        local_variant(203, 'PETRA-NEG-L', [color('Negro'), talle('L')], stock=2, active=active),
        local_variant(204, 'PETRA-CHO-S', [color('Chocolate'), talle('S')], stock=2, active=active),
        local_variant(205, 'PETRA-CHO-M', [color('Chocolate'), talle('M')], stock=2, active=active),
        local_variant(206, 'PETRA-CHO-L', [color('Chocolate'), talle('L')], stock=2, active=active),
    ]


class BuildPayloadMixedAttributesTests(unittest.TestCase):
    def test_publishes_dominant_group_and_reports_excluded(self):
        import service.views.retail_views as rv

        rows = _viejas() + _nuevas()
        built = rv._tiendanube_build_product_payload_from_local_variants({'name': 'Petra'}, rows)

        self.assertEqual(built['payload']['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        self.assertEqual(len(built['payload']['variants']), 6)
        excluidas = {item['sku'] for item in built['excluded']}
        self.assertEqual(excluidas, {'PETRA-S', 'PETRA-M', 'PETRA-L'})
        self.assertTrue(all('Color' in item['reason'] for item in built['excluded']))

    def test_variant_without_sku_is_excluded_not_fatal(self):
        import service.views.retail_views as rv

        rows = _nuevas()
        rows[0]['sku'] = ''
        built = rv._tiendanube_build_product_payload_from_local_variants({'name': 'Petra'}, rows)

        self.assertEqual(len(built['payload']['variants']), 5)
        self.assertEqual([item['reason'] for item in built['excluded']], ['no tiene SKU'])

    def test_raises_only_when_nothing_can_be_published(self):
        import service.views.retail_views as rv

        rows = [local_variant(301, '', [talle('S')])]
        with self.assertRaises(ValidationError):
            rv._tiendanube_build_product_payload_from_local_variants({'name': 'Petra'}, rows)

    def test_tie_prefers_group_with_more_attributes(self):
        import service.views.retail_views as rv

        rows = [
            local_variant(401, 'A-S', [talle('S')]),
            local_variant(402, 'B-NEG-S', [color('Negro'), talle('S')]),
        ]
        built = rv._tiendanube_build_product_payload_from_local_variants({'name': 'Petra'}, rows)

        self.assertEqual(built['payload']['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        self.assertEqual([item['sku'] for item in built['excluded']], ['A-S'])


class DeleteRemoteVariantTests(unittest.TestCase):
    def test_never_deletes_product_when_local_still_has_variants(self):
        store = FakeTiendaNube()
        remoto = store.seed_product(
            attributes=[{'es': 'Talle'}],
            variants=[{'sku': 'PETRA-S'}],
        )
        vieja = local_variant(
            101,
            'PETRA-S',
            [talle('S')],
            active=False,
            tiendanube_product_id=remoto['id'],
            tiendanube_variant_id=remoto['variants'][0]['id'],
        )
        db = FakeLocalDb([vieja] + _nuevas())

        with patched_tiendanube(store, db) as rv:
            out = rv._tiendanube_delete_remote_for_local_variant(CFG, vieja)

        self.assertTrue(out['ok'])
        self.assertEqual(out['scope'], 'kept_product')
        self.assertEqual(store.product_delete_calls(), [])
        # Se reconstruyo el grupo con las 6 variantes correctas.
        nuevo_id = db.get(201)['tiendanube_product_id']
        self.assertIsNotNone(nuevo_id)
        self.assertEqual(len(store.variant_skus(nuevo_id)), 6)
        self.assertEqual(store.products[nuevo_id]['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        # El producto viejo sigue existiendo pero despublicado.
        self.assertIn(remoto['id'], store.products)
        self.assertFalse(store.products[remoto['id']]['published'])

    def test_unpublishes_product_when_no_local_variants_left(self):
        store = FakeTiendaNube()
        remoto = store.seed_product(attributes=[{'es': 'Talle'}], variants=[{'sku': 'SOLA-S'}])
        unica = local_variant(
            501,
            'SOLA-S',
            [talle('S')],
            product_id=88,
            active=False,
            tiendanube_product_id=remoto['id'],
            tiendanube_variant_id=remoto['variants'][0]['id'],
        )
        db = FakeLocalDb([unica])

        with patched_tiendanube(store, db) as rv:
            out = rv._tiendanube_delete_remote_for_local_variant(CFG, unica)

        self.assertTrue(out['ok'])
        self.assertEqual(out['scope'], 'unpublished')
        self.assertEqual(store.product_delete_calls(), [])
        self.assertIn(remoto['id'], store.products)
        self.assertFalse(store.products[remoto['id']]['published'])
        self.assertIsNone(db.get(501)['tiendanube_product_id'])

    def test_deletes_only_the_variant_when_product_has_many(self):
        store = FakeTiendaNube()
        remoto = store.seed_product(
            attributes=[{'es': 'Talle'}],
            variants=[{'sku': 'MULTI-S'}, {'sku': 'MULTI-M'}],
        )
        baja = local_variant(
            601,
            'MULTI-S',
            [talle('S')],
            product_id=99,
            active=False,
            tiendanube_product_id=remoto['id'],
            tiendanube_variant_id=remoto['variants'][0]['id'],
        )
        queda = local_variant(
            602,
            'MULTI-M',
            [talle('M')],
            product_id=99,
            tiendanube_product_id=remoto['id'],
            tiendanube_variant_id=remoto['variants'][1]['id'],
        )
        db = FakeLocalDb([baja, queda])

        with patched_tiendanube(store, db) as rv:
            out = rv._tiendanube_delete_remote_for_local_variant(CFG, baja)

        self.assertEqual(out['scope'], 'variant')
        self.assertEqual(store.product_delete_calls(), [])
        self.assertEqual(store.variant_skus(remoto['id']), ['MULTI-M'])
        self.assertTrue(store.products[remoto['id']]['published'])


class DeleteWithUnknownProductTests(unittest.TestCase):
    def test_no_despublica_si_no_se_puede_determinar_el_producto_local(self):
        """Ante la duda, el producto de la tienda queda como esta."""
        store = FakeTiendaNube()
        remoto = store.seed_product(attributes=[{'es': 'Talle'}], variants=[{'sku': 'HUERFANA'}])
        fila = {
            'id': 999,  # sin product_id y sin fila local que lo resuelva
            'sku': 'HUERFANA',
            'tiendanube_product_id': remoto['id'],
            'tiendanube_variant_id': remoto['variants'][0]['id'],
        }
        db = FakeLocalDb([])

        with patched_tiendanube(store, db) as rv, \
             patch.object(rv, '_load_variante', return_value=None):
            out = rv._tiendanube_delete_remote_for_local_variant(CFG, fila)

        self.assertEqual(out['scope'], 'kept_product')
        self.assertEqual(store.product_delete_calls(), [])
        self.assertTrue(store.products[remoto['id']]['published'])


class AttributeChangeReplacesProductTests(unittest.TestCase):
    def test_creates_new_product_copies_images_and_unpublishes_old(self):
        store = FakeTiendaNube()
        viejo = store.seed_product(
            attributes=[{'es': 'Talle'}],
            variants=[{'sku': 'PETRA-S'}, {'sku': 'PETRA-M'}, {'sku': 'PETRA-L'}],
            images=[{'id': 1, 'src': 'https://cdn.test/petra-1.jpg'}, {'id': 2, 'src': 'https://cdn.test/petra-2.jpg'}],
        )
        viejas = _viejas()
        for row, remote_variant in zip(viejas, viejo['variants']):
            row['tiendanube_product_id'] = viejo['id']
            row['tiendanube_variant_id'] = remote_variant['id']
        db = FakeLocalDb(viejas + _nuevas())

        with patched_tiendanube(store, db) as rv:
            out = rv._tiendanube_sync_local_product_group(CFG, 77, reason='test', force_catalog=True)

        nuevo_id = out['product_id']
        self.assertNotEqual(nuevo_id, viejo['id'])
        self.assertEqual(out['replaced_product_ids'], [viejo['id']])
        self.assertEqual(out['copied_images'], 2)
        self.assertEqual(len(out['excluded_variants']), 3)
        self.assertEqual(store.products[nuevo_id]['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        self.assertEqual(len(store.variant_skus(nuevo_id)), 6)
        self.assertEqual(
            [img['src'] for img in store.products[nuevo_id]['images']],
            ['https://cdn.test/petra-1.jpg', 'https://cdn.test/petra-2.jpg'],
        )
        self.assertIn(viejo['id'], store.products)
        self.assertFalse(store.products[viejo['id']]['published'])
        self.assertEqual(store.product_delete_calls(), [])


class RepublishAfterProductLostTests(unittest.TestCase):
    def test_recreates_product_when_remote_is_gone(self):
        store = FakeTiendaNube()
        nuevas = _nuevas()
        for row in nuevas:
            row['tiendanube_product_id'] = 555  # producto borrado a mano en Tienda Nube
            row['tiendanube_variant_id'] = 5551
        db = FakeLocalDb(nuevas)

        with patched_tiendanube(store, db) as rv:
            out = rv._tiendanube_sync_local_product_group(CFG, 77, reason='repair', force_catalog=True)

        self.assertEqual(out['mapped'], 6)
        self.assertEqual(len(store.variant_skus(out['product_id'])), 6)
        self.assertEqual(store.products[out['product_id']]['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])

    def test_full_petra_scenario_end_to_end(self):
        store = FakeTiendaNube()
        db = FakeLocalDb(_viejas() + _nuevas(active=False))

        with patched_tiendanube(store, db) as rv:
            # Semana 1: alta con un unico atributo.
            alta = rv._tiendanube_sync_local_product_group(CFG, 77, reason='alta')
            producto_original = alta['product_id']
            self.assertEqual(store.products[producto_original]['attributes'], [{'es': 'Talle'}])
            self.assertEqual(len(store.variant_skus(producto_original)), 3)

            # Semana 2: se agregan las 6 combinaciones color + talle.
            for vid in (201, 202, 203, 204, 205, 206):
                db.get(vid)['active'] = True
            segunda = rv._tiendanube_sync_local_product_group(CFG, 77, reason='sync_catalogo', force_catalog=True)

            producto_nuevo = segunda['product_id']
            self.assertNotEqual(producto_nuevo, producto_original)
            self.assertEqual(len(store.variant_skus(producto_nuevo)), 6)
            self.assertFalse(store.products[producto_original]['published'])
            self.assertEqual(len(segunda['excluded_variants']), 3)

            # Se dan de baja las 3 viejas: el producto nuevo no se toca.
            for vid in (101, 102, 103):
                row = db.get(vid)
                row['active'] = False
                rv._tiendanube_delete_remote_for_local_variant(CFG, row)

        self.assertEqual(store.product_delete_calls(), [])
        self.assertIn(producto_nuevo, store.products)
        self.assertEqual(len(store.variant_skus(producto_nuevo)), 6)
        self.assertTrue(store.products[producto_nuevo]['published'])


class MixedAttributesAuditTests(unittest.TestCase):
    """El aviso de "variantes que no se publican" se calcula en el momento."""

    def _filas(self):
        return [
            {'product_id': 77, 'variant_id': 101, 'sku': 'PETRA-S', 'firma': 'talle', 'atributos': 'Talle', 'producto': 'Petra'},
            {'product_id': 77, 'variant_id': 102, 'sku': 'PETRA-M', 'firma': 'talle', 'atributos': 'Talle', 'producto': 'Petra'},
            {'product_id': 77, 'variant_id': 201, 'sku': 'PETRA-NEG-S', 'firma': 'color,talle', 'atributos': 'Color, Talle', 'producto': 'Petra'},
            {'product_id': 77, 'variant_id': 202, 'sku': 'PETRA-NEG-M', 'firma': 'color,talle', 'atributos': 'Color, Talle', 'producto': 'Petra'},
            {'product_id': 77, 'variant_id': 203, 'sku': 'PETRA-CHO-S', 'firma': 'color,talle', 'atributos': 'Color, Talle', 'producto': 'Petra'},
        ]

    def test_reporta_las_variantes_del_grupo_minoritario(self):
        import service.views.retail_views as rv

        with patch.object(rv, 'q', return_value=self._filas()):
            out = rv._tiendanube_products_with_mixed_attributes(limit=100)

        self.assertEqual(len(out), 1)
        item = out[0]
        self.assertEqual(item['producto'], 'Petra')
        self.assertEqual(item['atributos_publicados'], 'Color, Talle')
        self.assertEqual(
            sorted(v['sku'] for v in item['variantes_sin_publicar']),
            ['PETRA-M', 'PETRA-S'],
        )
        self.assertEqual(item['variantes_sin_publicar'][0]['faltan'], ['color'])

    def test_producto_homogeneo_no_aparece(self):
        import service.views.retail_views as rv

        with patch.object(rv, 'q', return_value=[]):
            out = rv._tiendanube_products_with_mixed_attributes(limit=100)

        self.assertEqual(out, [])


if __name__ == '__main__':
    unittest.main()
