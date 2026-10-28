import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from postgrest.exceptions import APIError
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.deps import db

router = APIRouter(prefix="/tienda", tags=["Tienda pública"])

COLS = ("id,sku,nombre,descripcion,numero_parte,especificaciones,datasheet_url,imagen_url,"
        "precio_venta,stock,categorias(nombre),marcas(nombre)")

# Límite simple por IP: 5 pedidos cada 10 minutos (evita spam en el endpoint público)
_intentos: dict[str, deque] = defaultdict(deque)


def _limitar(ip: str, maximo: int = 5, ventana: int = 600) -> None:
    ahora = time.time()
    q = _intentos[ip]
    while q and ahora - q[0] > ventana:
        q.popleft()
    if len(q) >= maximo:
        raise HTTPException(429, "Demasiados pedidos seguidos. Intenta de nuevo en unos minutos.")
    q.append(ahora)


def _igv() -> float:
    return float(db.table("empresa").select("igv_porcentaje").eq("id", 1).execute().data[0]["igv_porcentaje"])


@router.get("/empresa")
def empresa():
    return (db.table("empresa")
            .select("nombre_comercial,razon_social,ruc,direccion,distrito,provincia,departamento,telefono,email,web,logo_url")
            .eq("id", 1).execute().data[0])


@router.get("/categorias")
def categorias():
    return db.table("categorias").select("id,nombre").eq("activo", True).order("nombre").execute().data


@router.get("/productos")
def productos(
    q: str | None = None,
    categoria_id: int | None = None,
    orden: Literal["nombre", "precio_asc", "precio_desc"] = "nombre",
    limit: int = Query(12, ge=1, le=60),
    offset: int = Query(0, ge=0),
):
    """Catálogo público: sin precio de compra. El precio ya incluye IGV."""
    import re
    igv = _igv()
    query = db.table("productos").select(COLS).eq("activo", True)
    if categoria_id:
        query = query.eq("categoria_id", categoria_id)
    if q:
        t = re.sub(r"[,()%*]", " ", q).strip()
        if t:
            query = query.or_(f"nombre.ilike.%{t}%,sku.ilike.%{t}%,numero_parte.ilike.%{t}%")
    if orden == "nombre":
        query = query.order("nombre")
    else:
        query = query.order("precio_venta", desc=(orden == "precio_desc"))
    rows = query.range(offset, offset + limit - 1).execute().data
    for r in rows:
        r["precio"] = round(float(r.pop("precio_venta")) * (1 + igv / 100), 2)
    return rows


class PedidoItemIn(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0, le=1000)


class PedidoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: str = Field(min_length=6, max_length=20)
    email: EmailStr | None = None
    tipo_doc: Literal["DNI", "RUC"] | None = None
    numero_doc: str | None = None
    entrega: Literal["RECOJO", "ENVIO"] = "RECOJO"
    direccion: str | None = Field(None, max_length=250)
    notas: str | None = Field(None, max_length=500)
    items: list[PedidoItemIn] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validar(self):
        if bool(self.tipo_doc) != bool(self.numero_doc):
            raise ValueError("Indica el tipo y el número de documento, o deja ambos vacíos")
        if self.tipo_doc:
            largo = 8 if self.tipo_doc == "DNI" else 11
            if not (self.numero_doc.isdigit() and len(self.numero_doc) == largo):
                raise ValueError(f"El {self.tipo_doc} debe tener {largo} dígitos")
        if self.entrega == "ENVIO" and not self.direccion:
            raise ValueError("Indica la dirección de envío")
        return self


@router.post("/pedidos", status_code=201)
def crear_pedido(data: PedidoIn, request: Request):
    _limitar(request.client.host if request.client else "desconocido")
    try:
        res = db.rpc("crear_pedido", {
            "p_nombre": data.nombre.strip(),
            "p_telefono": data.telefono.strip(),
            "p_email": data.email,
            "p_tipo_doc": data.tipo_doc,
            "p_numero_doc": data.numero_doc,
            "p_entrega": data.entrega,
            "p_direccion": data.direccion,
            "p_notas": data.notas,
            "p_items": [i.model_dump() for i in data.items],
        }).execute()
    except APIError as e:
        msg = getattr(e, "message", None) or str(e)
        if "violates" in msg or "constraint" in msg:
            raise HTTPException(400, "No se pudo registrar el pedido. Revisa los datos.")
        raise HTTPException(400, msg)
    return {"pedido": res.data, "mensaje": "Pedido recibido. Te contactaremos para confirmarlo."}