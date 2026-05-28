from pathlib import Path
from urllib.parse import quote
import os

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import API_KEY, SECRET_KEY, USERS, VENDEDOR_ID
import database as db

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent

app = FastAPI(title="Vulcamoia - Reparto Buenos Aires")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 7)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["urlencode"] = lambda s: quote(str(s))

ESTADO_LABELS = {
    "pendiente": "Pendiente",
    "en_envio": "En envío a Bs.As.",
    "en_camino": "En camino",
    "entregado": "Entregado",
}

db.init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user(request: Request):
    return request.session.get("user")


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
async def admin_view(request: Request):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=303)

    facturas = db.get_facturas(vendedor=VENDEDOR_ID)
    for f in facturas:
        f["items"] = db.get_items(f["id"])
        f["estado_label"] = ESTADO_LABELS.get(f["estado"], f["estado"])

    stats = {
        "total": len(facturas),
        "pendiente": sum(1 for f in facturas if f["estado"] == "pendiente"),
        "en_envio": sum(1 for f in facturas if f["estado"] == "en_envio"),
        "en_camino": sum(1 for f in facturas if f["estado"] == "en_camino"),
        "entregado": sum(1 for f in facturas if f["estado"] == "entregado"),
    }

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "facturas": facturas,
            "user": user,
            "vendedor_id": VENDEDOR_ID,
            "stats": stats,
        },
    )


@app.get("/repartidor", response_class=HTMLResponse)
async def repartidor_view(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    pendientes = db.get_facturas(vendedor=VENDEDOR_ID, estados=["en_envio", "en_camino"])
    for f in pendientes:
        f["items"] = db.get_items(f["id"])
        f["estado_label"] = ESTADO_LABELS.get(f["estado"], f["estado"])

    entregadas = db.get_facturas(vendedor=VENDEDOR_ID, estados=["entregado"])
    for f in entregadas:
        f["items"] = db.get_items(f["id"])

    return templates.TemplateResponse(
        "repartidor.html",
        {
            "request": request,
            "facturas": pendientes,
            "entregadas": entregadas,
            "user": user,
        },
    )


# ---------------------------------------------------------------------------
# API — usada por el watcher local y por el JS del frontend
# ---------------------------------------------------------------------------

@app.post("/api/importar")
async def importar_factura(request: Request):
    """Recibe datos de una factura desde el watcher local."""
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="API key inválida")

    body = await request.json()
    data  = body.get("factura", {})
    items = body.get("items", [])

    if not data.get("numero"):
        raise HTTPException(status_code=400, detail="Faltan datos de la factura")

    if db.factura_exists(data["numero"]):
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
        "admin":      ["pendiente", "en_envio"],
        "repartidor": ["en_camino", "entregado"],
    }
    if nuevo not in permisos.get(user["role"], []):
        raise HTTPException(status_code=403, detail="No tenés permiso para ese estado")

    db.update_estado(factura_id, nuevo)
    return {"ok": True, "estado": nuevo, "label": ESTADO_LABELS.get(nuevo, nuevo)}
