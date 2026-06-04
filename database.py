"""
database.py
Usa Turso via HTTP API si hay TURSO_URL + TURSO_TOKEN en el entorno.
No requiere paquetes extra (usa urllib de la stdlib).
Cae a SQLite local si no hay variables (desarrollo / fallback).
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

TURSO_URL   = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")


# ---------------------------------------------------------------------------
# Capa Turso HTTP
# ---------------------------------------------------------------------------

def _http_endpoint():
    return TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"


def _to_arg(v):
    """Convierte un valor Python al formato de argumento Turso."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": str(v)}
    return {"type": "text", "value": str(v)}


def _from_val(v):
    """Convierte un valor Turso a Python."""
    if v["type"] == "null":
        return None
    if v["type"] == "integer":
        return int(v["value"])
    if v["type"] == "float":
        return float(v["value"])
    return v["value"]


def _turso_exec(sql: str, params=()):
    """Ejecuta una sentencia SQL en Turso y devuelve (cols, rows, lastrowid)."""
    stmt = {"sql": sql}
    if params:
        stmt["args"] = [_to_arg(p) for p in params]

    body = json.dumps({
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"},
        ]
    }).encode()

    req = urllib.request.Request(
        _http_endpoint(),
        data=body,
        headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read())

    result = data["results"][0]
    if result["type"] == "error":
        raise Exception(result["error"]["message"])

    r    = result["response"]["result"]
    cols = [c["name"] for c in r.get("cols", [])]
    rows = [[_from_val(v) for v in row] for row in r.get("rows", [])]

    raw = r.get("last_insert_rowid")
    try:
        lastrow = int(raw) or None
    except (TypeError, ValueError):
        lastrow = None

    return cols, rows, lastrow


def _turso_fetchall(sql, params=()):
    cols, rows, _ = _turso_exec(sql, params)
    return [dict(zip(cols, row)) for row in rows]


def _turso_fetchone(sql, params=()):
    cols, rows, _ = _turso_exec(sql, params)
    return dict(zip(cols, rows[0])) if rows else None


def _turso_run(sql, params=()):
    _, _, lastrow = _turso_exec(sql, params)
    return lastrow


# ---------------------------------------------------------------------------
# Capa SQLite local (fallback)
# ---------------------------------------------------------------------------

def _sqlite_conn():
    import sqlite3
    conn = sqlite3.connect("vulcamoia.db")
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_fetchall(sql, params=()):
    conn = _sqlite_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _sqlite_fetchone(sql, params=()):
    conn = _sqlite_conn()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_run(sql, params=()):
    conn = _sqlite_conn()
    cur  = conn.execute(sql, params)
    conn.commit()
    lastrow = cur.lastrowid
    conn.close()
    return lastrow


def _sqlite_runmany(stmts_params):
    conn = _sqlite_conn()
    for sql, params in stmts_params:
        conn.execute(sql, params)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# API unificada
# ---------------------------------------------------------------------------

def _use_turso():
    return bool(TURSO_URL and TURSO_TOKEN)


def fetchall(sql, params=()):
    return _turso_fetchall(sql, params) if _use_turso() else _sqlite_fetchall(sql, params)


def fetchone(sql, params=()):
    return _turso_fetchone(sql, params) if _use_turso() else _sqlite_fetchone(sql, params)


def run(sql, params=()):
    """Ejecuta y devuelve lastrowid."""
    return _turso_run(sql, params) if _use_turso() else _sqlite_run(sql, params)


def runmany(stmts_params):
    """Ejecuta varias sentencias (sin retorno)."""
    if _use_turso():
        for sql, params in stmts_params:
            _turso_run(sql, params)
    else:
        _sqlite_runmany(stmts_params)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db():
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
        run(sql)
    # Migraciones: columnas que pueden no existir en bases viejas
    for col_sql in [
        "ALTER TABLE facturas ADD COLUMN foto_remito TEXT",
        "ALTER TABLE facturas ADD COLUMN fecha_listo TEXT",
        "ALTER TABLE facturas ADD COLUMN fecha_llegada TEXT",   # YYYY-MM-DD — programada por admin
    ]:
        try:
            run(col_sql)
        except Exception:
            pass  # columna ya existe


# ---------------------------------------------------------------------------
# Facturas
# ---------------------------------------------------------------------------

def factura_exists(numero: str) -> bool:
    row = fetchone("SELECT 1 FROM facturas WHERE numero_factura = ?", (numero,))
    return row is not None


def get_factura_by_numero(numero: str):
    return fetchone("SELECT id FROM facturas WHERE numero_factura = ?", (numero,))


def insert_items(factura_id: int, items: list):
    """Inserta items para una factura. Borra los previos si ya existen."""
    run("DELETE FROM items WHERE factura_id = ?", (factura_id,))
    for item in items:
        run(
            """INSERT INTO items (factura_id, cantidad, detalle, precio_unit, precio_total)
               VALUES (?, ?, ?, ?, ?)""",
            (factura_id, item["cantidad"], item["detalle"],
             item.get("precio_unit", 0), item.get("precio_total", 0)),
        )


def insert_factura(data: dict, items: list):
    factura_id = run(
        """INSERT INTO facturas
           (numero_factura, fecha, cliente, domicilio, cuit, vendedor, archivo)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data["numero"], data["fecha"], data["cliente"],
         data["domicilio"], data["cuit"], data["vendedor"], data["archivo"]),
    )
    insert_items(factura_id, items)


def get_facturas(vendedor=None, estados=None, fecha=None) -> list:
    """
    vendedor: int, lista de ints, o None (todos)
    estados:  lista de strings, o None (todos)
    fecha:    YYYY-MM-DD — filtra por fecha de factura O fecha de entrega
    """
    query = """
        SELECT id, numero_factura, fecha, cliente, domicilio, cuit, vendedor,
               archivo, estado, fecha_en_envio, fecha_listo, fecha_en_camino,
               fecha_entregado, fecha_llegada,
               CASE WHEN (foto_remito IS NOT NULL AND foto_remito != '') THEN 1 ELSE 0 END AS has_foto,
               created_at
        FROM facturas WHERE 1=1
    """
    params = []

    # Filtro por vendedor: acepta int o lista de ints
    if vendedor is not None:
        if isinstance(vendedor, (list, tuple)):
            if len(vendedor) == 1:
                query += " AND vendedor = ?"
                params.append(vendedor[0])
            elif len(vendedor) > 1:
                query += f" AND vendedor IN ({','.join('?' * len(vendedor))})"
                params.extend(vendedor)
        else:
            query += " AND vendedor = ?"
            params.append(vendedor)

    if estados:
        query += f" AND estado IN ({','.join('?' * len(estados))})"
        params.extend(estados)

    if fecha:
        # fecha llega como YYYY-MM-DD
        # Muestra facturas cuya fecha de emisión coincida O fueron entregadas ese día
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(fecha, "%Y-%m-%d")
            fecha_ddmmyyyy = d.strftime("%d/%m/%Y")
            fecha_iso      = d.strftime("%Y-%m-%d")
            query += " AND (fecha = ? OR SUBSTR(fecha_entregado, 1, 10) = ?)"
            params.extend([fecha_ddmmyyyy, fecha_iso])
        except ValueError:
            pass

    query += " ORDER BY created_at DESC"
    return fetchall(query, params)


def get_items(factura_id: int) -> list:
    return fetchall("SELECT * FROM items WHERE factura_id = ?", (factura_id,))


def delete_factura(factura_id: int):
    run("DELETE FROM items WHERE factura_id = ?", (factura_id,))
    run("DELETE FROM facturas WHERE id = ?", (factura_id,))


def delete_facturas_sin_items() -> int:
    sin_items = fetchall("""
        SELECT f.id FROM facturas f
        LEFT JOIN items i ON i.factura_id = f.id
        WHERE f.estado = 'pendiente' AND i.id IS NULL
    """)
    for row in sin_items:
        run("DELETE FROM facturas WHERE id = ?", (row["id"],))
    return len(sin_items)


def update_estado(factura_id: int, nuevo_estado: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    campo = {
        "en_envio":  "fecha_en_envio",
        "listo":     "fecha_listo",
        "en_camino": "fecha_en_camino",
        "entregado": "fecha_entregado",
    }.get(nuevo_estado)
    if campo:
        run(f"UPDATE facturas SET estado = ?, {campo} = ? WHERE id = ?",
            (nuevo_estado, now, factura_id))
    else:
        run("UPDATE facturas SET estado = ? WHERE id = ?",
            (nuevo_estado, factura_id))


# ---------------------------------------------------------------------------
# Fecha de llegada programada
# ---------------------------------------------------------------------------

def set_fecha_llegada(factura_id: int, fecha_iso):
    """Guarda la fecha de llegada esperada (YYYY-MM-DD). None para borrarla."""
    run("UPDATE facturas SET fecha_llegada = ? WHERE id = ?",
        (fecha_iso or None, factura_id))


def auto_promover_llegados() -> int:
    """
    Promueve a 'listo' las facturas cuya fecha_llegada ya pasó/llegó
    y todavía están en 'pendiente' o 'en_envio'.
    Devuelve cuántas se promovieron.
    """
    from datetime import date
    hoy = date.today().isoformat()   # YYYY-MM-DD
    to_promote = fetchall("""
        SELECT id FROM facturas
        WHERE fecha_llegada IS NOT NULL
          AND fecha_llegada <= ?
          AND estado IN ('pendiente', 'en_envio')
    """, (hoy,))
    for row in to_promote:
        update_estado(row["id"], "listo")
    return len(to_promote)


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------

def save_foto(factura_id: int, data_url: str):
    run("UPDATE facturas SET foto_remito = ? WHERE id = ?", (data_url, factura_id))


def get_foto(factura_id: int):
    row = fetchone("SELECT foto_remito FROM facturas WHERE id = ?", (factura_id,))
    return row["foto_remito"] if row else None
