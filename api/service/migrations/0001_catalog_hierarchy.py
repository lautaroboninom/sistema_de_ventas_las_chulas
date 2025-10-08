from django.db import migrations


def noop(apps, schema_editor):
    # PostgreSQL-only build: no-op placeholder for legacy catalog patch
    return


class Migration(migrations.Migration):
    atomic = False
    dependencies = []
    operations = [migrations.RunPython(noop, migrations.RunPython.noop)]
