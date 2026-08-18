"""Jobs de sincronizacion con Tienda Nube.

Cubre lo que antes dejaba variantes afuera o fallaba en silencio:
- los jobs recorren todo el catalogo por paginas (antes cortaban en el LIMIT),
- un fallo del sync automatico queda registrado como job reintentable,
- el reintento dirigido de un grupo de variantes.
"""

import os
import unittest
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

import service.views.retail_views as rv


CFG = {'store_id': '1', 'access_token': 'x'}


def _fila(vid, mapeada=True):
    return {
        'id': vid,
        'product_id': 10,
        'sku': f'SKU-{vid}',
        'price_online_ars': '100.00',
        'stock_on_hand': 5,
        'tiendanube_product_id': 900 if mapeada else None,
        'tiendanube_variant_id': 9000 + vid if mapeada else None,
        'producto': 'Producto',
    }


class PaginacionDeJobsTests(unittest.TestCase):
    def setUp(self):
        self.paginas_pedidas = []
        # 250 variantes activas: con lote de 100 hacen falta 3 paginas.
        self.todas = [_fila(vid) for vid in range(1, 251)]

        def fake_page(last_id, batch_size):
            self.paginas_pedidas.append((last_id, batch_size))
            return [row for row in self.todas if row['id'] > last_id][: int(batch_size)]

        self.ops_enviadas = []

        def fake_bulk(cfg, ops, sync_price=False, sync_stock=False):
            self.ops_enviadas.extend(ops)
            return {'synced': len(ops), 'failed': 0, 'errors': []}

        self.patches = [
            patch.object(rv, '_tiendanube_cfg', return_value=CFG),
            patch.object(rv, '_job_set_running', return_value=None),
            patch.object(rv, '_job_set_done', return_value=None),
            patch.object(rv, '_job_set_failed', return_value=None),
            patch.object(rv, '_tiendanube_active_variants_page', side_effect=fake_page),
            patch.object(
                rv,
                '_tiendanube_ensure_rows_remote_mapping',
                return_value={'auto_mapped': 0, 'created_remote': 0, 'creation_failed': 0, 'pending_mapping': 0, 'errors': [], 'excluded_variants': []},
            ),
            patch.object(rv, '_tiendanube_bulk_sync_stock_price', side_effect=fake_bulk),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_sync_catalogo_recorre_todas_las_variantes(self):
        out = rv._tiendanube_run_sync_catalogo_job(1, {'limit': 100})

        body = out['body']
        self.assertTrue(body['ok'])
        self.assertEqual(body['processed'], 250)
        self.assertEqual(body['mapped'], 250)
        self.assertFalse(body['truncated'])
        # La ultima variante (la mas nueva) entro en el lote.
        self.assertIn(250, [op['local_variant_id'] for op in self.ops_enviadas])
        # Avanzo por id, sin repetir la primera pagina.
        self.assertEqual([p[0] for p in self.paginas_pedidas], [0, 100, 200, 250])

    def test_sync_stock_recorre_todas_las_variantes(self):
        out = rv._tiendanube_run_sync_stock_job(2, {'limit': 100})

        body = out['body']
        self.assertEqual(body['processed'], 250)
        self.assertEqual(body['linked'], 250)
        self.assertEqual(body['unlinked'], 0)
        self.assertIn(250, [op['local_variant_id'] for op in self.ops_enviadas])

    def test_respeta_el_tope_duro(self):
        with patch.object(rv, '_TIENDANUBE_SYNC_MAX_VARIANTS', 150):
            out = rv._tiendanube_run_sync_catalogo_job(3, {'limit': 100})

        body = out['body']
        self.assertEqual(body['processed'], 150)
        self.assertTrue(body['truncated'])


class SyncVariantsJobTests(unittest.TestCase):
    def test_reintento_dirigido_usa_las_variantes_del_payload(self):
        with patch.object(rv, '_job_set_running'), patch.object(rv, '_job_set_done') as done, \
             patch.object(rv, '_tiendanube_sync_local_variants_now', return_value={'synced': 2, 'failed': 0, 'errors': []}) as sync:
            out = rv._tiendanube_run_sync_variants_job(9, {'variant_ids': [11, 12], 'sync_catalog': True})

        self.assertTrue(out['body']['ok'])
        self.assertEqual(out['body']['variant_ids'], [11, 12])
        self.assertEqual(sync.call_args[0][0], [11, 12])
        self.assertTrue(sync.call_args[1]['sync_catalog'])
        done.assert_called_once()

    def test_job_sin_variant_ids_falla_con_mensaje_claro(self):
        with patch.object(rv, '_job_set_failed') as failed:
            out = rv._tiendanube_run_sync_variants_job(9, {})

        self.assertEqual(out['status_code'], 400)
        self.assertIn('variant_ids', out['body']['detail'])
        failed.assert_called_once()

    def test_esta_registrado_como_tipo_reintentable(self):
        self.assertIn('sync_variants', rv._TIENDANUBE_RETRYABLE_JOB_TYPES)
        with patch.object(rv, '_tiendanube_run_sync_variants_job', return_value={'status_code': 200, 'body': {}}) as runner:
            rv._tiendanube_run_retryable_job(5, 'sync_variants', {'variant_ids': [1]})
        runner.assert_called_once()


class FallosVisiblesTests(unittest.TestCase):
    """El sync automatico corre despues del commit: sus errores deben quedar a la vista."""

    def _correr(self, resultado=None, excepcion=None):
        creados = []

        def fake_create_job(provider, job_type, payload, status='pending', last_error=None):
            creados.append({'provider': provider, 'job_type': job_type, 'payload': payload, 'status': status, 'last_error': last_error})
            return 1

        kwargs = {'side_effect': excepcion} if excepcion else {'return_value': resultado}
        with patch.object(rv.transaction, 'on_commit', side_effect=lambda fn: fn()), \
             patch.object(rv, '_tiendanube_sync_local_variants_now', **kwargs), \
             patch.object(rv, '_create_job', side_effect=fake_create_job):
            rv._tiendanube_schedule_local_variants_sync([21, 22], sync_catalog=True, reason='variant_patch')
        return creados

    def test_exito_no_crea_job_de_fallo(self):
        creados = self._correr(resultado={'synced': 2, 'failed': 0, 'errors': []})
        self.assertEqual(creados, [])

    def test_error_del_sync_queda_como_job_reintentable(self):
        creados = self._correr(resultado={'synced': 0, 'failed': 2, 'errors': ['SKU X: HTTP 422']})

        self.assertEqual(len(creados), 1)
        job = creados[0]
        self.assertEqual(job['job_type'], 'sync_variants')
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['payload']['variant_ids'], [21, 22])
        self.assertTrue(job['payload']['sync_catalog'])
        self.assertIn('HTTP 422', job['last_error'])

    def test_excepcion_del_sync_queda_como_job_reintentable(self):
        creados = self._correr(excepcion=RuntimeError('Tienda Nube no responde'))

        self.assertEqual(len(creados), 1)
        self.assertIn('no responde', creados[0]['last_error'])


if __name__ == '__main__':
    unittest.main()
