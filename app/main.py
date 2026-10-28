import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import (auth, catalogo, clientes, compras, consultas, devoluciones, pedidos,
                         productos, proveedores, reportes, tienda, usuarios, ventas)

log = logging.getLogger("api")
prod = settings.es_produccion

app = FastAPI(
    title="Voltio Electronics - API de Ventas",
    version="3.0.0",
    docs_url=None if prod else "/docs",       # Swagger solo en desarrollo
    redoc_url=None,
    openapi_url=None if prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,  # usamos token Bearer, no cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def cabeceras_seguras(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    if prod:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(Exception)
async def error_general(request: Request, exc: Exception):
    log.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


for module in (auth, usuarios, catalogo, productos, proveedores, compras, clientes, consultas,
               ventas, devoluciones, reportes, tienda, pedidos):
    app.include_router(module.router)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}