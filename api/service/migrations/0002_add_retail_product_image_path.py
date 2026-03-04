from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0001_initial_user_state'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE IF EXISTS retail_products ADD COLUMN IF NOT EXISTS image_path TEXT;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
