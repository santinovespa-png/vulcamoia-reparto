"""
WATCHER LOCAL - corre en la PC de la oficina
Envia facturas de los ultimos DIAS_ATRAS dias al servidor en Render.
El servidor deduplica automaticamente (no se duplican aunque se reenvien).

Esto es necesario porque si Render reinicia, la base de datos se borra y
el watcher la restaura automaticamente en la proxima pasada.

Requisitos: pip install pdfplumber requests
"""

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
VENDEDOR_ID     = 197
INTERVALO_SEG   = 30    # segundos entre escaneos
DIAS_ATRAS      = 1     # procesa ayer y hoy (pedidos del dia anterior + los nuevos)
# ============================================================


def es_reciente(path: Path) -> bool:
    """True si el archivo fue modificado/creado en los ultimos DIAS_ATRAS dias."""
    mtime = date.fromtimestamp(path.stat().st_mtime)
    return mtime >= date.today() - timedelta(days=DIAS_ATRAS)


# ---- Parser integrado ----

def _extraer_items(text: str) -> list:
    """Extrae items de la factura.
    Busca lineas con formato: CANTIDAD  DESCRIPCION [precio_unit precio_total]
    Los precios son opcionales — lo importante es cantidad y detalle (medida/diseno).
    Funciona con cubiertas: '4 205/55R16 PIRELLI P7  1.234,56  4.938,24'
    """
    PRECIO_PAT = r'[\d]+(?:[.,]\d{3})*[.,]\d{2}'  # numero con decimales obligatorios

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

        # Toda linea de item empieza con 1-4 digitos (cantidad) + espacio + descripcion
        m = re.match(r'^(\d{1,4})\s+(.+)$', line)
        if not m:
            continue

        cantidad = int(m.group(1))
        if cantidad == 0:
            continue

        resto = m.group(2).strip()

        # Intenta quitar precios del final (pueden estar o no)
        precios = re.findall(PRECIO_PAT, resto)
        if len(precios) >= 2:
            # Sacar los ultimos 2 precios del detalle
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

    numero    = buscar(r'FACTURA\s+N[oº°]\s+([A-Z0-9\-]+)')
    fecha     = buscar(r'FECHA:\s+(\d{2}/\d{2}/\d{4})')
    cliente   = buscar(r'Se[ñn]or/es:\s+(.+)')
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
            json={"factura": data, "items": items},
            headers={"X-API-Key": API_KEY},
            timeout=20,
        )
        if r.status_code == 200:
            resp = r.json()
            if resp.get("importada"):
                print(f"  [OK] Importada: {data['numero']} - {data['cliente']} ({len(items)} items)")
            else:
                print(f"  [--] Ya existia: {data['numero']}")
            return True
        else:
            print(f"  [ERR] Servidor ({r.status_code}): {r.text[:100]}")
            return False
    except requests.RequestException as e:
        print(f"  [ERR] Sin conexion: {e}")
        return False


def ciclo():
    folder = Path(FACTURAS_FOLDER)
    if not folder.exists():
        print(f"  [!] Carpeta no accesible: {folder}")
        return

    pdfs = sorted(folder.glob("*.PDF")) + sorted(folder.glob("*.pdf"))
    recientes = [p for p in pdfs if es_reciente(p)]

    if not recientes:
        print("  (sin facturas recientes)")
        return

    for pdf in recientes:
        data, items = parsear_pdf(pdf)

        if not data:
            print(f"  [?] No se pudo parsear: {pdf.name}")
            continue

        vendedor_pdf = data.get("vendedor")
        if vendedor_pdf != VENDEDOR_ID:
            print(f"  [skip] {pdf.name} -> vendedor {vendedor_pdf}")
            continue

        if not items:
            print(f"  [!] Sin items detectados en {pdf.name} (se importa igual)")

        enviar(data, items)


def main():
    print("=" * 52)
    print("  Vulcamoia - Watcher de Facturas")
    print(f"  Carpeta : {FACTURAS_FOLDER}")
    print(f"  Servidor: {RENDER_URL}")
    print(f"  Vendedor: {VENDEDOR_ID}")
    print(f"  Escanea cada {INTERVALO_SEG}s | ultimos {DIAS_ATRAS} dias")
    print("=" * 52)
    print()

    try:
        import pdfplumber  # noqa
    except ImportError:
        print("ERROR: falta instalar pdfplumber.")
        print("Ejecuta: pip install pdfplumber requests")
        return

    while True:
        print(f"[{date.today()}] Escaneando...")
        try:
            ciclo()
        except Exception as e:
            print(f"  [ERR] Error inesperado: {e}")
        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()
