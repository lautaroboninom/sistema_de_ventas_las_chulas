"""Tareas que corren solas despues de una actualizacion en la maquina del cliente.

Diseño defensivo: este runner se ejecuta durante el arranque/actualizacion, asi que
**nunca** propaga excepciones ni deja la app sin levantar. Cada tarea es idempotente y
queda registrada en `retail_post_update_tasks` con su resultado, que despues se muestra
en el aviso de novedades.
"""

import json
import logging
import os

from django.db import connection

logger = logging.getLogger('security.integrations')

TASKS_TABLE = 'retail_post_update_tasks'
TASKS_ENABLED_ENV = 'RETAILHUB_POST_UPDATE_TASKS_ENABLED'
ADVISORY_LOCK_KEY = 81426048

# Codigos de las tareas conocidas por esta version del codigo.
TASK_TIENDANUBE_REPUBLISH = 'tiendanube_republish_orphan_products_2026_08'


def tasks_enabled():
    raw = (os.getenv(TASKS_ENABLED_ENV, '1') or '').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


# Acceso a datos propio: este modulo lo importa `service.views`, asi que no puede
# depender de `service.views.helpers` sin generar un import circular.
def _query(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        if not cur.description:
            return None
        columnas = [col[0] for col in cur.description]
        filas = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        if one:
            return filas[0] if filas else None
        return filas


def _execute(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])


def _table_exists():
    row = _query('SELECT to_regclass(%s) AS reg', [f'public.{TASKS_TABLE}'], one=True) or {}
    return bool(row.get('reg'))


def _as_dict(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _acquire_lock():
    with connection.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK_KEY])
        row = cur.fetchone()
    return bool(row and row[0])


def _release_lock():
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK_KEY])
    except Exception:
        pass


# --------------------------------------------------------------------------
# Tareas
# --------------------------------------------------------------------------
def _task_tiendanube_republish_orphan_products(payload):
    """Republica los productos cuyas variantes activas no tengan vinculo remoto.

    Idempotente: si la variante ya esta vinculada, el producto no entra en la lista.
    Devuelve (status, resultado). `skipped` cuando Tienda Nube no esta configurado.
    """
    from .views.retail_views import (  # import diferido: evita ciclos al cargar la app
        _tiendanube_cfg,
        _tiendanube_sync_local_product_group,
    )

    cfg = _tiendanube_cfg()
    if not cfg.get('store_id') or not cfg.get('access_token'):
        return 'skipped', {
            'motivo': 'Tienda Nube no esta configurado en este sistema',
            'revisados': 0,
            'republicados': [],
            'con_error': [],
        }

    productos = _query(
        '''
        SELECT p.id, p.name
        FROM retail_products p
        WHERE p.active=TRUE
          AND EXISTS (
            SELECT 1
            FROM retail_product_variants v
            WHERE v.product_id=p.id
              AND v.active=TRUE
              AND (v.tiendanube_product_id IS NULL OR v.tiendanube_variant_id IS NULL)
          )
        ORDER BY p.id
        ''',
    ) or []

    if not productos:
        return 'done', {
            'revisados': 0,
            'republicados': [],
            'vinculados': 0,
            'con_error': [],
            'motivo': 'Todos los productos activos ya estan vinculados con Tienda Nube',
        }

    republicados = []
    vinculados = 0
    con_error = []
    for producto in productos:
        product_id = producto.get('id')
        nombre = (producto.get('name') or '').strip() or f'Producto {product_id}'
        try:
            out = _tiendanube_sync_local_product_group(
                cfg,
                product_id,
                reason='post_update_repair',
                force_catalog=True,
            )
        except Exception as exc:
            con_error.append({'producto': nombre, 'motivo': str(exc)[:300]})
            logger.warning(
                'post_update_republish_failed product_id=%s error=%s',
                product_id,
                exc,
            )
            continue
        if int(out.get('created_remote') or 0) > 0:
            republicados.append(nombre)
        else:
            vinculados += 1

    return 'done', {
        'revisados': len(productos),
        'republicados': republicados,
        'vinculados': vinculados,
        'con_error': con_error,
    }


TASK_REGISTRY = {
    TASK_TIENDANUBE_REPUBLISH: _task_tiendanube_republish_orphan_products,
}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def _pending_tasks(limit):
    return _query(
        f'''
        SELECT id, code, title, status, attempts, max_attempts, payload
        FROM {TASKS_TABLE}
        WHERE status IN ('pending', 'failed', 'skipped')
          AND attempts < max_attempts
        ORDER BY id
        LIMIT %s
        ''',
        [int(limit)],
    ) or []


def _mark_running(task_id):
    _execute(
        f'''
        UPDATE {TASKS_TABLE}
        SET status='running', attempts=attempts + 1, started_at=NOW(), last_error=NULL
        WHERE id=%s
        ''',
        [task_id],
    )


def _mark_finished(task_id, status, result=None, last_error=None):
    _execute(
        f'''
        UPDATE {TASKS_TABLE}
        SET status=%s,
            result=%s::jsonb,
            last_error=%s,
            finished_at=NOW()
        WHERE id=%s
        ''',
        [status, json.dumps(result or {}), (last_error or None), task_id],
    )


def run_pending_tasks(limit=10):
    """Ejecuta las tareas pendientes. Nunca lanza excepciones."""
    summary = {'ok': True, 'enabled': True, 'ran': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'tasks': []}

    if not tasks_enabled():
        summary['enabled'] = False
        summary['detail'] = f'Desactivado por {TASKS_ENABLED_ENV}=0'
        return summary

    try:
        if not _table_exists():
            summary['detail'] = 'Todavia no existe la tabla de tareas post-actualizacion'
            return summary
    except Exception as exc:
        summary['ok'] = False
        summary['detail'] = f'No se pudo consultar tareas post-actualizacion: {exc}'
        logger.warning('post_update_tasks_table_check_failed error=%s', exc)
        return summary

    try:
        got_lock = _acquire_lock()
    except Exception as exc:
        summary['ok'] = False
        summary['detail'] = f'No se pudo tomar el lock de tareas: {exc}'
        return summary

    if not got_lock:
        summary['detail'] = 'Ya hay otra corrida de tareas en curso'
        return summary

    try:
        try:
            pendientes = _pending_tasks(max(1, min(int(limit or 10), 50)))
        except Exception as exc:
            summary['ok'] = False
            summary['detail'] = f'No se pudieron leer las tareas pendientes: {exc}'
            return summary

        for task in pendientes:
            task_id = task.get('id')
            code = (task.get('code') or '').strip()
            handler = TASK_REGISTRY.get(code)
            if handler is None:
                # Tarea de una version mas nueva del esquema: se deja pendiente.
                continue

            summary['ran'] += 1
            try:
                _mark_running(task_id)
            except Exception as exc:
                summary['ok'] = False
                logger.warning('post_update_task_mark_running_failed code=%s error=%s', code, exc)
                continue

            try:
                status, result = handler(_as_dict(task.get('payload')))
                status = status if status in ('done', 'skipped', 'failed') else 'done'
                _mark_finished(task_id, status, result=result)
            except Exception as exc:
                status = 'failed'
                summary['ok'] = False
                logger.warning('post_update_task_failed code=%s error=%s', code, exc)
                try:
                    _mark_finished(task_id, 'failed', result={}, last_error=str(exc)[:1000])
                except Exception as inner:
                    logger.warning('post_update_task_mark_failed_error code=%s error=%s', code, inner)
                summary['failed'] += 1
                summary['tasks'].append({'code': code, 'status': status, 'error': str(exc)[:300]})
                continue

            if status == 'failed':
                summary['ok'] = False
            summary[status] += 1
            summary['tasks'].append({'code': code, 'status': status, 'result': result, 'title': task.get('title')})

        return summary
    finally:
        _release_lock()


def get_tasks_status(limit=20):
    """Estado de las tareas para mostrar en el aviso de novedades."""
    out = {'ok': True, 'enabled': tasks_enabled(), 'tasks': []}
    try:
        if not _table_exists():
            return out
        rows = _query(
            f'''
            SELECT code, title, status, attempts, result, last_error, finished_at
            FROM {TASKS_TABLE}
            ORDER BY id DESC
            LIMIT %s
            ''',
            [max(1, min(int(limit or 20), 100))],
        ) or []
    except Exception as exc:
        logger.warning('post_update_tasks_status_failed error=%s', exc)
        return {'ok': False, 'enabled': tasks_enabled(), 'tasks': [], 'detail': str(exc)[:300]}

    for row in rows:
        out['tasks'].append(
            {
                'code': row.get('code'),
                'title': row.get('title'),
                'status': row.get('status'),
                'attempts': row.get('attempts'),
                'result': _as_dict(row.get('result')),
                'last_error': row.get('last_error'),
                'finished_at': row.get('finished_at'),
            }
        )
    return out
