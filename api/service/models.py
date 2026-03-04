from django.db import models


class User(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.TextField()
    email = models.TextField(unique=True)
    hash_pw = models.TextField()
    rol = models.TextField()
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'users'
