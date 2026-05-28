"""
WATCHER LOCAL - corre en la PC de la oficina
Monitorea la carpeta de facturas y envía las de HOY a la web en Render.

Requisitos: pip install pdfplumber requests
"""

import json
import re
import time
from datetime import date
from pathlib import Path

import requests

# ============================================================
#  CONFIGURACION
# ============================================================
RENDER_URL      = "https://TU-APP.onrender.com"        # <-- cambiar después del deploy
API_KEY         = "vulcamoia-api-key-2024"              # <-- debe coincidir con Render
FACTURAS_FOLDER = r"\\central\omicrom\Sistema Toyo\FACTURAS"
VENDEDOR_ID     = 197
INTERVALO_SEG   = 30   # cada cuántos segundos escanea
ENVIADOS_FILE   = Path(__file__).parent / "enviados_hoy.json"
# ============================================================


def cargar_enviados() -> set:
    try:
        with open(ENVIADOS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def guardar_enviados(enviados: set):
    with open(ENVIADOS_FILE, "w") as f:
        json.dump(list(enviados), f)


def es_de_hoy(path: Path) -> bool:
    """Devuelve True si el archivo fue modificado/creado hoy."""
    mtime = date.fromtimestamp(path.stat().st_mtime)
    return mtime >= date.today()


# ---- Parser integrado (no depende del main.py del servidor) ----

def _extraer_items(text: str) -> list:
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
        if re.match(r'Neto\s+gravado|TOTAL|C\.A\.E', line, re.IGNORECASE):
            break
        if not line:
            continue
        m = re.match(r'^(\d+)\s+(.+?)\s+(\d[\d.]*\.\d{2})\s+(\d[\d.]*\.\d{2})$', line)
        if m:
            items.append({
                "cantidad":     int(m.group(1)),
                "detalle":      m.group(2).strip(),
                "precio_unit":  float(m.group(3).replace(",", "")),
                "precio_total": float(m.group(4).replace(",", "")),
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

    numero   = buscar(r'FACTURA\s+N[º°o]\s+([A-Z0-9\-]+)')
    fecha    = buscar(r'FECHA:\s+(\d{2}/\d{2}/\d{4})')
    cliente  = buscar(r'Se[ñn]or/es:\s+(.+)')
    domicilio= buscar(r'Domicilio:\s+(.+)')
    cuit     = buscar(r'CUIT/DNI:\s+(\d+)')

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
                print(f"  ✓ Importada: {data['numero']} — {data['cliente']}")
            else:
                print(f"  · Ya existía: {data['numero']}")
            return True
        else:
            print(f"  ✗ Error del servidor ({r.status_code}): {r.text[:100]}")
            return False
    except requests.RequestException as e:
        print(f"  ✗ Sin conexión: {e}")
        return False


def ciclo(enviados: set) -> set:
    folder = Path(FACTURAS_FOLDER)
    if not folder.exists():
        print(f"  ⚠ Carpeta no accesible: {folder}")
        return enviados

    for pdf in sorted(folder.glob("*.PDF")) + sorted(folder.glob("*.pdf")):
        if pdf.name in enviados:
            continue

        if not es_de_hoy(pdf):
            enviados.add(pdf.name)   # marcar como "vieja, no procesar"
            continue

        data, items = parsear_pdf(pdf)

        if not data or data.get("vendedor") != VENDEDOR_ID:
            enviados.add(pdf.name)
            continue

        if enviar(data, items):
            enviados.add(pdf.name)
            guardar_enviados(enviados)

    return enviados


def main():
    print("=" * 50)
    print("  Vulcamoia - Watcher de Facturas")
    print(f"  Carpeta : {FACTURAS_FOLDER}")
    print(f"  Servidor: {RENDER_URL}")
    print(f"  Revisando cada {INTERVALO_SEG} segundos...")
    print("=" * 50)
    print()

    # Validar que pdfplumber esté instalado
    try:
        import pdfplumber
    except ImportError:
        print("ERROR: falta instalar pdfplumber.")
        print("Ejecutá: pip install pdfplumber requests")
        return

    enviados = cargar_enviados()

    while True:
        print(f"[{date.today()}] Escaneando...")
        try:
            enviados = ciclo(enviados)
        except Exception as e:
            print(f"  Error inesperado: {e}")
        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()
