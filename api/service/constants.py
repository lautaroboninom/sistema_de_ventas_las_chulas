# constants.py
# Constantes de dominio usadas por la app "service".

# Nombres canónicos de ubicaciones por defecto
DEFAULT_LOCATION_NAMES = [
    "Taller",
    "Estantería de Alquiler",
    "Sarmiento",
    "Depósito SEPID",
    "Desguace",
]

# Remapeos de alias de ubicaciones a forma canónica
LOCATION_NAME_REMAPS = {
    # Variantes comunes y errores tipográficos para "Estantería de Alquiler"
    "estanteria alquileres": "Estantería de Alquiler",
    "estanteria de alquiler": "Estantería de Alquiler",
    "estantería de aluiler": "Estantería de Alquiler",
    "estanteria de aluiler": "Estantería de Alquiler",
    # Variantes detectadas en BD: sin "de" y/o sin acentos
    "estantería alquiler": "Estantería de Alquiler",
    "estanteria alquiler": "Estantería de Alquiler",
}
