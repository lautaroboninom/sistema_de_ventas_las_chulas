from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from ..system_update import get_update_status, run_update_check
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
