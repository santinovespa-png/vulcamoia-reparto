"""
WATCHER LOCAL - corre en la PC de la oficina
Envia facturas de los ultimos DIAS_ATRAS dias al servidor en Render.
El servidor deduplica automaticamente (no se duplican aunque se reenvien).

Requisitos: pip install pdfplumber requests
Para correr automaticamente sin CMD: usar watcher_silencioso.vbs + instalar_arranque.bat
"""

import logging
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# ============================================================
#  CONFIGURACION
# ============================================================
RENDER_URL      = "https://vulcamoia-reparto.onrender.com"
API_KEY         = "vulcamoia-api-key-2024"
FACTURAS_FOLDER = r"\\central\omicrom\Sistema Toyo\FACTURAS"
VENDEDOR_IDS    = [197, 212]    # lista de vendedores a importar
INTERVALO_SEG   = 30            # segundos entre escaneos
DIAS_ATRAS      = 1             # procesa ayer y hoy
# ============================================================

# ---- Log a archivo (visible aunque corra en segundo plano) ----
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watcher_log.txt")
logging.basicConfig(
    filename=_log_path,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)

def log(msg: str):
    """Escribe en consola Y en watcher_log.txt."""
    print(msg)
    logging.info(msg)


def es_reciente(path: Path) -> bool:
    """True si el archivo fue modificado/creado en los ultimos DIAS_ATRAS dias."""
    mtime = date.fromtimestamp(path.stat().st_mtime)
    return mtime >= date.today() - timedelta(days=DIAS_ATRAS)


# ---- Parser integrado ----

def _extraer_items(text: str) -> list:
    PRECIO_PAT = r'[\d]+(?:[.,]\d{3})*[.,]\d{2}'

    items = []
    lines = text.split("\n")
    en_items = False

    for line in lines:
        line = line.strip()

        if re.match(r'CANTIDAD\s+DETALLE', line, re.IGNORECASE):
            en_items = True
            continue
        if not en_items:
            continue
        if re.match(r'Neto\s+gravado|TOTAL|C\.A\.E|IVA|SUBTOTAL|Bonif', line, re.IGNORECASE):
            break
        if not line:
            continue

        m = re.match(r'^(\d{1,4})\s+(.+)$', line)
        if not m:
            continue

        cantidad = int(m.group(1))
        if cantidad == 0:
            continue

        resto = m.group(2).strip()

        precios = re.findall(PRECIO_PAT, resto)
        if len(precios) >= 2:
            p1, p2 = precios[-2], precios[-1]
            detalle = resto
            detalle = re.sub(r'\s+' + re.escape(p2) + r'$', '', detalle).strip()
            detalle = re.sub(r'\s+' + re.escape(p1) + r'$', '', detalle).strip()
        else:
            detalle = resto

        if detalle:
            items.append({
                "cantidad":     cantidad,
                "detalle":      detalle,
                "precio_unit":  0.0,
                "precio_total": 0.0,
            })

    return items


def parsear_pdf(pdf_path: Path):
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"  Error leyendo {pdf_path.name}: {e}")
        return None, []

    if not text.strip():
        return None, []

    def buscar(patron):
        m = re.search(patron, text)
        return m.group(1).strip() if m else ""

    # Nº y ñ a veces se convierten en � (caracter de reemplazo) segun el PDF
    numero    = buscar(r'FACTURA\s+N[oº°�]\s+([A-Z0-9\-]+)')
    fecha     = buscar(r'FECHA:\s+(\d{2}/\d{2}/\d{4})')
    cliente   = buscar(r'Se[\xf1n�]or/es:\s+(.+)')
    domicilio = buscar(r'Domicilio:\s+(.+)')
    cuit      = buscar(r'CUIT/DNI:\s+(\d+)')

    m = re.search(r'VENDEDOR\s+(\d+)', text)
    vendedor = int(m.group(1)) if m else None

    data = {
        "numero":    numero or pdf_path.stem,
        "fecha":     fecha,
        "cliente":   cliente,
        "domicilio": domicilio,
        "cuit":      cuit,
        "vendedor":  vendedor,
        "archivo":   pdf_path.name,
    }
    return data, _extraer_items(text)


def enviar(data: dict, items: list) -> bool:
    try:
        r = requests.post(
            f"{RENDER_URL}/api/importar",
            # force_items=True: si la factura ya existe pero sin items, el servidor los guarda
            json={"factura": data, "items": items, "force_items": True},
            headers={"X-API-Key": API_KEY},
            timeout=20,
        )
        if r.status_code == 200:
            resp = r.json()
            if resp.get("importada"):
                log(f"  [OK] Nueva: {data['numero']} - {data['cliente']} ({len(items)} items)")
            elif resp.get("razon") == "items actualizados":
                log(f"  [UP] Items guardados: {data['numero']} ({len(items)} items)")
            else:
                log(f"  [--] Ya existia: {data['numero']}")
            return True
        else:
            log(f"  [ERR] Servidor ({r.status_code}): {r.text[:200]}")
            return False
    except requests.RequestException as e:
        log(f"  [ERR] Sin conexion: {e}")
        return False


def ciclo():
    folder = Path(FACTURAS_FOLDER)
    if not folder.exists():
        log(f"  [!] Carpeta no accesible: {folder}")
        return

    pdfs = sorted(folder.glob("*.PDF")) + sorted(folder.glob("*.pdf"))
    recientes = [p for p in pdfs if es_reciente(p)]

    if not recientes:
        log("  (sin facturas recientes)")
        return

    for pdf in recientes:
        data, items = parsear_pdf(pdf)

        if not data:
            log(f"  [?] No se pudo parsear: {pdf.name}")
            continue

        vendedor_pdf = data.get("vendedor")
        if vendedor_pdf not in VENDEDOR_IDS:
            log(f"  [skip] {pdf.name} -> vendedor {vendedor_pdf}")
            continue

        if not items:
            log(f"  [!] Sin items en {pdf.name} — se envia igual, revisar formato PDF")
        else:
            log(f"  [.] {pdf.name} -> {len(items)} items, vendedor {vendedor_pdf}")

        enviar(data, items)


def main():
    log("=" * 52)
    log("  Vulcamoia - Watcher de Facturas")
    log(f"  Carpeta : {FACTURAS_FOLDER}")
    log(f"  Servidor: {RENDER_URL}")
    log(f"  Vendedores: {VENDEDOR_IDS}")
    log(f"  Log     : {_log_path}")
    log(f"  Escanea cada {INTERVALO_SEG}s | ultimos {DIAS_ATRAS} dias")
    log("=" * 52)

    try:
        import pdfplumber  # noqa
    except ImportError:
        log("ERROR: falta instalar pdfplumber.")
        log("Ejecuta: pip install pdfplumber requests")
        return

    while True:
        log(f"[{date.today()}] Escaneando...")
        try:
            ciclo()
        except Exception as e:
            log(f"  [ERR] Error inesperado: {e}")
        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()
