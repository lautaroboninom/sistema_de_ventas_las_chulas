import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings_prod')
import django
django.setup()
from service.views.ingresos_views import GarantiaFabricaCheckView

serial = 'YSA21903037'
class Req:
    def __init__(self, qs):
        self.GET = qs
        self.user = type('U', (), {'is_authenticated': True, 'id': 1})()

view = GarantiaFabricaCheckView()
r = view.get(Req({'numero_serie': serial}))
print(json.dumps(r.data, default=str))
