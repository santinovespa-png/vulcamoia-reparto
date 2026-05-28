import re
from pathlib import Path

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False


def parse_factura(pdf_path):
    """
    Lee un PDF de factura Vulcamoia y extrae los datos relevantes.
    Devuelve (data_dict, items_list) o (None, []) si falla.
    """
    if not PDF_OK:
        print("ERROR: pdfplumber no está instalado. Ejecutá setup.bat")
        return None, []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"Error leyendo {pdf_path}: {e}")
        return None, []

    if not text.strip():
        return None, []

    # --- Número de factura ---
    m = re.search(r'FACTURA\s+N[º°o]\s+([A-Z0-9\-]+)', text)
    numero = m.group(1) if m else Path(pdf_path).stem

    # --- Fecha ---
    m = re.search(r'FECHA:\s+(\d{2}/\d{2}/\d{4})', text)
    fecha = m.group(1) if m else ""

    # --- Cliente ---
    m = re.search(r'Se[ñn]or/es:\s+(.+)', text)
    cliente = m.group(1).strip() if m else ""

    # --- Domicilio ---
    m = re.search(r'Domicilio:\s+(.+)', text)
    domicilio = m.group(1).strip() if m else ""

    # --- CUIT ---
    m = re.search(r'CUIT/DNI:\s+(\d+)', text)
    cuit = m.group(1) if m else ""

    # --- Vendedor ---
    m = re.search(r'VENDEDOR\s+(\d+)', text)
    vendedor = int(m.group(1)) if m else None

    # --- Items ---
    items = _extraer_items(text)

    data = {
        "numero": numero,
        "fecha": fecha,
        "cliente": cliente,
        "domicilio": domicilio,
        "cuit": cuit,
        "vendedor": vendedor,
        "archivo": str(pdf_path),
    }
    return data, items


def _extraer_items(text):
    items = []
    lines = text.split("\n")
    en_items = False

    for line in lines:
        line = line.strip()

        # Detectar inicio de la sección de items
        if re.match(r'CANTIDAD\s+DETALLE', line, re.IGNORECASE):
            en_items = True
            continue

        if not en_items:
            continue

        # Detectar fin de la sección de items
        if re.match(r'Neto\s+gravado|TOTAL|C\.A\.E', line, re.IGNORECASE):
            break

        if not line:
            continue

        # Patrón: <cantidad> <descripción> <precio_unit> <precio_total>
        # Los precios siempre son números con exactamente 2 decimales
        m = re.match(r'^(\d+)\s+(.+?)\s+(\d[\d.]*\.\d{2})\s+(\d[\d.]*\.\d{2})$', line)
        if m:
            items.append({
                "cantidad": int(m.group(1)),
                "detalle": m.group(2).strip(),
                "precio_unit": float(m.group(3).replace(",", "")),
                "precio_total": float(m.group(4).replace(",", "")),
            })

    return items
