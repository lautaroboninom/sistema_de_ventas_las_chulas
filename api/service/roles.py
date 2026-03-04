# roles.py
# Roles visibles en API/Front para retail.

ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('empleado', 'Empleado'),
]

ROLE_KEYS = [r for r, _ in ROLE_CHOICES]
