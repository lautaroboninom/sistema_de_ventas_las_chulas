from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from ..post_update_tasks import get_tasks_status, run_pending_tasks
from ..system_update import (
    LOCAL_RESTART_SCRIPT,
    get_update_status,
    run_update_check,
    schedule_local_update_restart,
)
from .helpers import _rol


class SystemUpdateStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(get_update_status())


class SystemUpdateCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        force = bool(data.get('force'))
        if force and _rol(request) != 'admin':
            raise PermissionDenied('Solo admin puede forzar la busqueda de actualizaciones.')

        payload = run_update_check(force=force)
        code = 200 if payload.get('ok', False) else 500
        return Response(payload, status=code)


class SystemUpdateRestartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if _rol(request) != 'admin':
            raise PermissionDenied('Solo admin puede forzar reinicio para aplicar actualizaciones.')

        current = get_update_status()
        pending = bool(current.get('pending'))
        if not pending:
            return Response(
                {
                    'ok': False,
                    'scheduled': False,
                    'pending': False,
                    'last_error': 'No hay actualizaciones pendientes para aplicar.',
                },
                status=status.HTTP_409_CONFLICT,
            )

        if not LOCAL_RESTART_SCRIPT.exists():
            return Response(
                {
                    'ok': False,
                    'scheduled': False,
                    'pending': pending,
                    'last_error': f'No se encontro script de reinicio local: {LOCAL_RESTART_SCRIPT}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        payload = schedule_local_update_restart(delay_seconds=2)
        code = (
            status.HTTP_202_ACCEPTED
            if payload.get('ok', False) and payload.get('scheduled', False)
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return Response(payload, status=code)


class SystemPostUpdateStatusView(APIView):
    """Resultado de las tareas que se ejecutaron solas despues de actualizar."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(get_tasks_status())


class SystemPostUpdateRunView(APIView):
    """Dispara las tareas pendientes.

    Lo llama el frontend al primer ingreso despues de una actualizacion. Es idempotente
    y nunca devuelve error al usuario: si algo falla queda registrado en la tarea.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        summary = run_pending_tasks(limit=10)
        payload = dict(summary)
        payload['status'] = get_tasks_status()
        return Response(payload, status=status.HTTP_200_OK)
