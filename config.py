import os

# ============================================================
#  CONFIGURACION - valores por defecto (se sobreescriben con
#  variables de entorno en Render)
# ============================================================

# Número de vendedor a filtrar
VENDEDOR_ID = int(os.environ.get("VENDEDOR_ID", "197"))

# Clave secreta para sesiones
SECRET_KEY = os.environ.get("SECRET_KEY", "vulcamoia-ba-reparto-2024-clave-secreta")

# Clave que usa el watcher local para enviar facturas a la API
API_KEY = os.environ.get("API_KEY", "vulcamoia-api-key-2024")

# Credenciales de usuario
USERS = {
    "admin": {
        "password": os.environ.get("ADMIN_PASSWORD", "vulcamoia2024"),
        "role": "admin",
        "display": "Oficina",
    },
    "repartidor": {
        "password": os.environ.get("REPARTO_PASSWORD", "reparto2024"),
        "role": "repartidor",
        "display": "Repartidor",
    },
}
