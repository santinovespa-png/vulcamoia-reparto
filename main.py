import base64
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import API_KEY, SECRET_KEY, USERS, VENDEDOR_ID, VENDEDOR_IDS
import database as db

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Vulcamoia - Reparto Buenos Aires")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 7)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["urlencode"] = lambda s: quote(str(s))

ESTADO_LABELS = {
    "pendiente": "Pendiente",
    "en_envio":  "En envío",
    "listo":     "Listo para entregar",
    "en_camino": "En camino",
    "entregado": "Entregado",
}

db.init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user(request: Request):
    return request.session.get("user")


def _enrich_facturas(facturas: list) -> list:
    """Agrega items, estado_label y fecha_llegada_display a cada factura."""
    for f in facturas:
        f["items"] = db.get_items(f["id"])
        f["estado_label"] = ESTADO_LABELS.get(f["estado"], f["estado"])
        fl = f.get("fecha_llegada") or ""
        if fl:
            try:
                f["fecha_llegada_display"] = datetime.strptime(fl, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                f["fecha_llegada_display"] = fl
        else:
            f["fecha_llegada_display"] = ""
    return facturas


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/admin" if user["role"] == "admin" else "/repartidor", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user_data = USERS.get(username)
    if not user_data or user_data["password"] != password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuario o contraseña incorrectos"},
        )
    request.session["user"] = {
        "username": username,
        "role": user_data["role"],
        "display": user_data["display"],
    }
    dest = "/admin" if user_data["role"] == "admin" else "/repartidor"
    return RedirectResponse(dest, status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_view(request: Request, fecha: str = None):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=303)

    # Promoción automática de facturas cuya fecha_llegada ya pasó
    db.auto_promover_llegados()

    hoy = date.today().isoformat()

    if fecha is None:
        activos = db.get_facturas(
            vendedor=VENDEDOR_IDS,
            estados=["pendiente", "en_envio", "listo", "en_camino"],
        )
        entregados_hoy = db.get_facturas(
            vendedor=VENDEDOR_IDS,
            estados=["entregado"],
            fecha=hoy,
        )
        facturas = activos + entregados_hoy
        facturas.sort(key=lambda f: f["created_at"], reverse=True)
        vista_activa = True
    else:
        facturas = db.get_facturas(vendedor=VENDEDOR_IDS, fecha=fecha)
        vista_activa = False

    _enrich_facturas(facturas)

    stats = {
        "pendiente": sum(1 for f in facturas if f["estado"] == "pendiente"),
        "en_envio":  sum(1 for f in facturas if f["estado"] == "en_envio"),
        "listo":     sum(1 for f in facturas if f["estado"] == "listo"),
        "en_camino": sum(1 for f in facturas if f["estado"] == "en_camino"),
        "entregado": sum(1 for f in facturas if f["estado"] == "entregado"),
    }

    return templates.TemplateResponse(
        "admin.html",
        {
            "request":      request,
            "facturas":     facturas,
            "user":         user,
            "vendedor_id":  VENDEDOR_ID,
            "stats":        stats,
            "fecha":        fecha or hoy,
            "fecha_hoy":    hoy,
            "vista_activa": vista_activa,
        },
    )


@app.get("/repartidor", response_class=HTMLResponse)
async def repartidor_view(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Promoción automática de facturas cuya fecha_llegada ya pasó
    db.auto_promover_llegados()

    listos    = db.get_facturas(vendedor=VENDEDOR_IDS, estados=["listo"])
    en_camino = db.get_facturas(vendedor=VENDEDOR_IDS, estados=["en_camino"])
    _enrich_facturas(listos + en_camino)

    entregadas = db.get_facturas(vendedor=VENDEDOR_IDS, estados=["entregado"])
    _enrich_facturas(entregadas)

    return templates.TemplateResponse(
        "repartidor.html",
        {
            "request":    request,
            "listos":     listos,
            "en_camino":  en_camino,
            "entregadas": entregadas,
            "user":       user,
        },
    )


# ---------------------------------------------------------------------------
# API — watcher local y JS del frontend
# ---------------------------------------------------------------------------

@app.post("/api/importar")
async def importar_factura(request: Request):
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="API key inválida")

    body  = await request.json()
    data  = body.get("factura", {})
    items = body.get("items", [])

    if not data.get("numero"):
        raise HTTPException(status_code=400, detail="Faltan datos de la factura")

    if db.factura_exists(data["numero"]):
        # Si la factura existe pero NO tiene items, actualizarlos ahora
        if items:
            factura = db.get_factura_by_numero(data["numero"])
            if factura:
                existing = db.get_items(factura["id"])
                if not existing:
                    db.insert_items(factura["id"], items)
                    return {"ok": True, "importada": False, "razon": "items actualizados",
                            "numero": data["numero"]}
        return {"ok": True, "importada": False, "razon": "ya existe"}

    db.insert_factura(data, items)
    return {"ok": True, "importada": True, "numero": data["numero"]}


@app.post("/api/estado/{factura_id}")
async def set_estado(factura_id: int, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    body = await request.json()
    nuevo = body.get("estado")

    permisos = {
        "admin":      ["pendiente", "en_envio", "listo", "en_camino", "entregado"],
        "repartidor": ["en_camino", "entregado"],
    }
    if nuevo not in permisos.get(user["role"], []):
        raise HTTPException(status_code=403, detail="No tenés permiso para ese estado")

    db.update_estado(factura_id, nuevo)
    return {"ok": True, "estado": nuevo, "label": ESTADO_LABELS.get(nuevo, nuevo)}


@app.post("/api/factura/{factura_id}/llegada")
async def set_llegada(factura_id: int, request: Request):
    """Programa la fecha de llegada de un pedido. Fecha en YYYY-MM-DD o vacío para borrar."""
    user = current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body  = await request.json()
    fecha = (body.get("fecha") or "").strip()

    # Validar formato si se envió fecha
    if fecha:
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (esperado YYYY-MM-DD)")

    db.set_fecha_llegada(factura_id, fecha or None)
    display = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y") if fecha else ""
    return {"ok": True, "fecha_llegada": fecha, "display": display}


@app.post("/api/foto/{factura_id}")
async def upload_foto(factura_id: int, request: Request, foto: UploadFile = File(...)):
    """Sube foto del remito firmado (base64 en Turso)."""
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    content = await foto.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Foto demasiado grande (máx. 15 MB)")

    mime = foto.content_type or "image/jpeg"
    b64  = base64.b64encode(content).decode()
    db.save_foto(factura_id, f"data:{mime};base64,{b64}")
    return {"ok": True}


@app.post("/api/factura")
async def crear_factura_manual(request: Request):
    """Crea una factura manualmente desde el panel admin."""
    user = current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body = await request.json()
    cliente   = (body.get("cliente")   or "").strip()
    domicilio = (body.get("domicilio") or "").strip()
    numero    = (body.get("numero")    or "").strip()
    fecha_val = (body.get("fecha")     or "").strip()
    items     = body.get("items", [])

    if not cliente or not domicilio:
        raise HTTPException(status_code=400, detail="Cliente y domicilio son requeridos")

    if not numero:
        numero = f"MANUAL-{datetime.now().strftime('%d%m%y-%H%M%S')}"

    if db.factura_exists(numero):
        raise HTTPException(status_code=409, detail=f"Ya existe la factura {numero}")

    if not fecha_val:
        fecha_val = date.today().strftime("%d/%m/%Y")

    data = {
        "numero":    numero,
        "fecha":     fecha_val,
        "cliente":   cliente,
        "domicilio": domicilio,
        "cuit":      "",
        "vendedor":  VENDEDOR_ID,
        "archivo":   "manual",
    }
    db.insert_factura(data, items)
    return {"ok": True, "numero": numero}


@app.delete("/api/factura/{factura_id}")
async def eliminar_factura(factura_id: int, request: Request):
    user = current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")
    db.delete_factura(factura_id)
    return {"ok": True}


@app.post("/api/facturas/llegada-masiva")
async def llegada_masiva(request: Request):
    """Programa la misma fecha de llegada para una lista de facturas de una vez."""
    user = current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body  = await request.json()
    fecha = (body.get("fecha") or "").strip()   # YYYY-MM-DD
    ids   = body.get("ids", [])                  # lista de factura_id

    if not fecha or not ids:
        raise HTTPException(status_code=400, detail="Se requieren fecha e ids")

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (YYYY-MM-DD)")

    for factura_id in ids:
        db.set_fecha_llegada(int(factura_id), fecha)

    display = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
    return {"ok": True, "actualizadas": len(ids), "display": display}


@app.post("/api/facturas/limpiar-sin-items")
async def limpiar_sin_items(request: Request):
    user = current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")
    n = db.delete_facturas_sin_items()
    return {"ok": True, "eliminadas": n}


@app.get("/api/foto/{factura_id}")
async def get_foto_endpoint(factura_id: int, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    foto_data = db.get_foto(factura_id)
    if not foto_data:
        raise HTTPException(status_code=404, detail="Sin foto")

    header, data = foto_data.split(",", 1)
    mime    = header.split(":")[1].split(";")[0]
    content = base64.b64decode(data)
    return Response(content=content, media_type=mime)


@app.get("/api/status")
async def status():
    """Diagnóstico: verifica conexión y cuenta registros."""
    import os
    turso_url   = os.environ.get("TURSO_URL", "")
    turso_token = os.environ.get("TURSO_TOKEN", "")
    using_turso = bool(turso_url and turso_token)

    try:
        total = db.fetchone("SELECT COUNT(*) as n FROM facturas")
        count = total["n"] if total else 0
        db_ok = True
        db_error = None
    except Exception as e:
        count = -1
        db_ok = False
        db_error = str(e)

    return {
        "ok":             db_ok,
        "storage":        "turso" if using_turso else "sqlite_local",
        "turso_url":      turso_url[:40] + "..." if turso_url else "(no configurado)",
        "facturas_en_db": count,
        "vendedores":     VENDEDOR_IDS,
        "error":          db_error,
    }
