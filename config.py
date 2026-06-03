import os

# ============================================================
#  CONFIGURACION - valores por defecto (se sobreescriben con
#  variables de entorno en Render)
# ============================================================

# Vendedores a filtrar — puede ser lista separada por coma: "197,212"
_raw_ids = os.environ.get("VENDEDOR_IDS", os.environ.get("VENDEDOR_ID", "197,212"))
VENDEDOR_IDS = [int(v.strip()) for v in _raw_ids.split(",") if v.strip().isdigit()]
VENDEDOR_ID  = VENDEDOR_IDS[0]   # alias backward-compat (para el header del panel)

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
