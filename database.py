import sqlite3
from datetime import datetime, date

DB_PATH = "vulcamoia.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS facturas (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura    TEXT UNIQUE,
            fecha             TEXT,
            cliente           TEXT,
            domicilio         TEXT,
            cuit              TEXT,
            vendedor          INTEGER,
            archivo           TEXT,
            estado            TEXT DEFAULT 'pendiente',
            fecha_en_envio    TEXT,
            fecha_en_camino   TEXT,
            fecha_entregado   TEXT,
            foto_remito       TEXT,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id    INTEGER,
            cantidad      INTEGER,
            detalle       TEXT,
            precio_unit   REAL,
            precio_total  REAL,
            FOREIGN KEY (factura_id) REFERENCES facturas(id)
        );

        CREATE TABLE IF NOT EXISTS archivos_procesados (
            nombre      TEXT PRIMARY KEY,
            procesado   TEXT
        );
    """)
    conn.commit()
    # Migracion: agregar columna foto_remito si no existe
    try:
        conn.execute("ALTER TABLE facturas ADD COLUMN foto_remito TEXT")
        conn.commit()
    except Exception:
        pass
    conn.close()


def archivo_procesado(nombre):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM archivos_procesados WHERE nombre = ?", (nombre,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_archivo_procesado(nombre):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO archivos_procesados (nombre, procesado) VALUES (?, ?)",
        (nombre, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def factura_exists(numero):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM facturas WHERE numero_factura = ?", (numero,)
    ).fetchone()
    conn.close()
    return row is not None


def insert_factura(data, items):
    conn = get_db()
    try:
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
                """INSERT INTO items (factura_id, cantidad, detalle, precio_unit, precio_total)
                   VALUES (?, ?, ?, ?, ?)""",
                (factura_id, item["cantidad"], item["detalle"],
                 item["precio_unit"], item["precio_total"]),
            )
        conn.commit()
    finally:
        conn.close()


def get_facturas(vendedor=None, estados=None, fecha=None):
    conn = get_db()
    # Devuelve has_foto (bool) en lugar del blob completo para no cargar la pagina
    query = """
        SELECT id, numero_factura, fecha, cliente, domicilio, cuit, vendedor,
               archivo, estado, fecha_en_envio, fecha_en_camino, fecha_entregado,
               (foto_remito IS NOT NULL AND foto_remito != '') as has_foto,
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
        # fecha debe ser 'YYYY-MM-DD'; created_at esta en UTC pero sirve para filtrar
        query += " AND DATE(created_at) = ?"
        params.append(fecha)

    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_foto(factura_id: int, data_url: str):
    conn = get_db()
    conn.execute("UPDATE facturas SET foto_remito = ? WHERE id = ?", (data_url, factura_id))
    conn.commit()
    conn.close()


def get_foto(factura_id: int):
    conn = get_db()
    row = conn.execute("SELECT foto_remito FROM facturas WHERE id = ?", (factura_id,)).fetchone()
    conn.close()
    return row["foto_remito"] if row else None


def get_items(factura_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM items WHERE factura_id = ?", (factura_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_estado(factura_id, nuevo_estado):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    campo_fecha = {
        "en_envio": "fecha_en_envio",
        "en_camino": "fecha_en_camino",
        "entregado": "fecha_entregado",
    }
    extra_sql = ""
    params = [nuevo_estado]
    if nuevo_estado in campo_fecha:
        extra_sql = f", {campo_fecha[nuevo_estado]} = ?"
        params.append(now)
    params.append(factura_id)
    conn.execute(
        f"UPDATE facturas SET estado = ?{extra_sql} WHERE id = ?", params
    )
    conn.commit()
    conn.close()
