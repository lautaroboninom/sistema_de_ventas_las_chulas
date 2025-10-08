from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("service", "0001_catalog_hierarchy"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="User",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        ("nombre", models.TextField()),
                        ("email", models.TextField(unique=True)),
                        ("hash_pw", models.TextField()),
                        ("rol", models.TextField()),
                        ("activo", models.BooleanField(default=True)),
                        ("perm_ingresar", models.BooleanField(default=False)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "users",
                    },
                ),

                migrations.CreateModel(
                    name="Customer",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        ("cod_empresa", models.TextField(null=True)),
                        ("razon_social", models.TextField()),
                        ("cuit", models.TextField(null=True)),
                        ("contacto", models.TextField(null=True)),
                        ("telefono", models.TextField(null=True)),
                        ("telefono_2", models.TextField(null=True)),
                        ("email", models.TextField(null=True)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "customers",
                    },
                ),

                migrations.CreateModel(
                    name="Marca",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        ("nombre", models.TextField(unique=True)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "marcas",
                    },
                ),

                migrations.CreateModel(
                    name="Model",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        (
                            "marca",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.RESTRICT,
                                db_column="marca_id",
                                to="service.marca",
                            ),
                        ),
                        ("nombre", models.TextField()),
                    ],
                    options={
                        "managed": False,
                        "db_table": "models",
                        "unique_together": {("marca", "nombre")},
                    },
                ),

                migrations.CreateModel(
                    name="Device",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        (
                            "customer",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                db_column="customer_id",
                                to="service.customer",
                            ),
                        ),
                        (
                            "marca",
                            models.ForeignKey(
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                db_column="marca_id",
                                to="service.marca",
                            ),
                        ),
                        (
                            "model",
                            models.ForeignKey(
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                db_column="model_id",
                                to="service.model",
                            ),
                        ),
                        ("numero_serie", models.TextField(null=True)),
                        ("propietario", models.TextField(null=True)),
                        ("garantia_bool", models.BooleanField(null=True)),
                        ("etiq_garantia_ok", models.BooleanField(null=True)),
                        ("n_de_control", models.TextField(null=True)),
                        ("alquilado", models.BooleanField(default=False)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "devices",
                    },
                ),

                migrations.CreateModel(
                    name="Ingreso",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        (
                            "device",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                db_column="device_id",
                                to="service.device",
                            ),
                        ),
                        ("estado", models.TextField()),
                        ("motivo", models.TextField()),
                        ("fecha_ingreso", models.DateTimeField(null=True, blank=True)),
                        ("fecha_creacion", models.DateTimeField()),
                        ("fecha_servicio", models.DateTimeField(null=True, blank=True)),
                        ("sala_origen", models.TextField(null=True)),
                        ("ubicacion_id", models.IntegerField(null=True)),
                        ("disposicion", models.TextField()),
                        ("informe_preliminar", models.TextField(null=True)),
                        ("accesorios", models.TextField(null=True)),
                        ("remito_ingreso", models.TextField(null=True)),
                        ("recibido_por", models.IntegerField(null=True)),
                        ("comentarios", models.TextField(null=True)),
                        ("presupuesto_estado", models.TextField()),
                        ("asignado_a", models.IntegerField(null=True)),
                        ("etiqueta_qr", models.TextField(null=True)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "ingresos",
                    },
                ),

                migrations.CreateModel(
                    name="Quote",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        (
                            "ingreso",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                db_column="ingreso_id",
                                to="service.ingreso",
                            ),
                        ),
                        ("estado", models.TextField()),
                        ("moneda", models.TextField()),
                        ("subtotal", models.DecimalField(max_digits=12, decimal_places=2)),
                        ("iva_21", models.DecimalField(max_digits=12, decimal_places=2)),
                        ("total", models.DecimalField(max_digits=12, decimal_places=2)),
                        ("autorizado_por", models.TextField(null=True)),
                        ("forma_pago", models.TextField(null=True)),
                        ("fecha_emitido", models.DateTimeField(null=True)),
                        ("fecha_aprobado", models.DateTimeField(null=True)),
                        ("pdf_url", models.TextField(null=True)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "quotes",
                    },
                ),

                migrations.CreateModel(
                    name="IngresoMedia",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        (
                            "ingreso",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                db_column="ingreso_id",
                                related_name="media_items",
                                to="service.ingreso",
                            ),
                        ),
                        (
                            "usuario",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                db_column="usuario_id",
                                to="service.user",
                            ),
                        ),
                        ("storage_path", models.TextField()),
                        ("thumbnail_path", models.TextField()),
                        ("original_name", models.TextField(null=True, blank=True)),
                        ("mime_type", models.CharField(max_length=80)),
                        ("size_bytes", models.BigIntegerField()),
                        ("width", models.IntegerField()),
                        ("height", models.IntegerField()),
                        ("comentario", models.TextField(null=True, blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "managed": False,
                        "db_table": "ingreso_media",
                        "ordering": ("-created_at",),
                    },
                ),
            ],
        ),
    ]

