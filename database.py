"""
database.py
Usa Turso (libsql en la nube) si hay TURSO_URL + TURSO_TOKEN en el entorno.
Cae a SQLite local si no hay variables (desarrollo local).
"""
import os
from datetime import datetime

TURSO_URL   = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")


def get_db():
    if TURSO_URL and TURSO_TOKEN:
        import libsql_experimental as libsql
        return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
    # Fallback local
    import sqlite3
    conn = sqlite3.connect("vulcamoia.db")
    conn.row_factory = sqlite3.Row
    return conn


def _rows(cur) -> list:
    """Convierte filas (tuplas o sqlite3.Row) a lista de dicts."""
    rows = cur.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):          # sqlite3.Row
        return [dict(r) for r in rows]
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def _one(cur):
    """Devuelve una fila como dict o None."""
    row = cur.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db():
    conn = get_db()
    for sql in [
        """CREATE TABLE IF NOT EXISTS facturas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura  TEXT UNIQUE,
            fecha           TEXT,
            cliente         TEXT,
            domicilio       TEXT,
            cuit            TEXT,
            vendedor        INTEGER,
            archivo         TEXT,
            estado          TEXT DEFAULT 'pendiente',
            fecha_en_envio  TEXT,
            fecha_en_camino TEXT,
            fecha_entregado TEXT,
            foto_remito     TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id   INTEGER,
            cantidad     INTEGER,
            detalle      TEXT,
            precio_unit  REAL,
            precio_total REAL,
            FOREIGN KEY (factura_id) REFERENCES facturas(id)
        )""",
        """CREATE TABLE IF NOT EXISTS archivos_procesados (
            nombre    TEXT PRIMARY KEY,
            procesado TEXT
        )""",
    ]:
        conn.execute(sql)
    conn.commit()
    # Migracion: foto_remito puede no existir en DBs viejas
    try:
        conn.execute("ALTER TABLE facturas ADD COLUMN foto_remito TEXT")
        conn.commit()
    except Exception:
        pass
    conn.close()


# ---------------------------------------------------------------------------
# Facturas
# ---------------------------------------------------------------------------

def factura_exists(numero: str) -> bool:
    conn = get_db()
    cur  = conn.execute(
        "SELECT 1 FROM facturas WHERE numero_factura = ?", (numero,)
    )
    found = cur.fetchone() is not None
    conn.close()
    return found


def insert_factura(data: dict, items: list):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO facturas
           (numero_factura, fecha, cliente, domicilio, cuit, vendedor, archivo)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["numero"], data["fecha"], data["cliente"],
            data["domicilio"], data["cuit"], data["vendedor"], data["archivo"],
        ),
    )
    factura_id = cur.lastrowid
    for item in items:
        conn.execute(
            """INSERT INTO items
               (factura_id, cantidad, detalle, precio_unit, precio_total)
               VALUES (?, ?, ?, ?, ?)""",
            (factura_id, item["cantidad"], item["detalle"],
             item.get("precio_unit", 0), item.get("precio_total", 0)),
        )
    conn.commit()
    conn.close()


def get_facturas(vendedor=None, estados=None, fecha=None) -> list:
    conn  = get_db()
    query = """
        SELECT id, numero_factura, fecha, cliente, domicilio, cuit, vendedor,
               archivo, estado, fecha_en_envio, fecha_en_camino, fecha_entregado,
               (foto_remito IS NOT NULL AND foto_remito != '') AS has_foto,
               created_at
        FROM facturas WHERE 1=1
    """
    params = []

    if vendedor is not None:
        query += " AND vendedor = ?"
        params.append(vendedor)

    if estados:
        placeholders = ",".join("?" * len(estados))
        query += f" AND estado IN ({placeholders})"
        params.extend(estados)

    if fecha:
        query += " AND DATE(created_at) = ?"
        params.append(fecha)

    query += " ORDER BY created_at DESC"
    cur  = conn.execute(query, params)
    rows = _rows(cur)
    conn.close()
    return rows


def get_items(factura_id: int) -> list:
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM items WHERE factura_id = ?", (factura_id,)
    )
    rows = _rows(cur)
    conn.close()
    return rows


def update_estado(factura_id: int, nuevo_estado: str):
    conn = get_db()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    campo_fecha = {
        "en_envio": "fecha_en_envio",
        "en_camino": "fecha_en_camino",
        "entregado": "fecha_entregado",
    }
    if nuevo_estado in campo_fecha:
        conn.execute(
            f"UPDATE facturas SET estado = ?, {campo_fecha[nuevo_estado]} = ? WHERE id = ?",
            (nuevo_estado, now, factura_id),
        )
    else:
        conn.execute(
            "UPDATE facturas SET estado = ? WHERE id = ?",
            (nuevo_estado, factura_id),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------

def save_foto(factura_id: int, data_url: str):
    conn = get_db()
    conn.execute(
        "UPDATE facturas SET foto_remito = ? WHERE id = ?",
        (data_url, factura_id),
    )
    conn.commit()
    conn.close()


def get_foto(factura_id: int):
    conn = get_db()
    cur  = conn.execute(
        "SELECT foto_remito FROM facturas WHERE id = ?", (factura_id,)
    )
    row = _one(cur)
    conn.close()
    return row["foto_remito"] if row else None


# ---------------------------------------------------------------------------
# Archivos procesados (no usado activamente, se mantiene para compatibilidad)
# ---------------------------------------------------------------------------

def archivo_procesado(nombre: str) -> bool:
    conn = get_db()
    cur  = conn.execute(
        "SELECT 1 FROM archivos_procesados WHERE nombre = ?", (nombre,)
    )
    found = cur.fetchone() is not None
    conn.close()
    return found


def mark_archivo_procesado(nombre: str):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO archivos_procesados (nombre, procesado) VALUES (?, ?)",
        (nombre, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
