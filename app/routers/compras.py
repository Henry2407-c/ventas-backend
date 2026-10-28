from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas_extra import CompraIn

router = APIRouter(prefix="/compras", tags=["Compras"])
LECTURA = require_roles("admin", "almacenero", "contador")
ESCRITURA = require_roles("admin", "almacenero")


def _compra_o_404(cid: int) -> dict:
    res = (db.table("compras")
           .select("*, proveedores(razon_social,ruc), compra_items(*, productos(sku,nombre))")
           .eq("id", cid).execute())
    if not res.data:
        raise HTTPException(404, "Compra no encontrada")
    return res.data[0]


@router.post("", status_code=201)
def crear(data: CompraIn, user: dict = Depends(ESCRITURA)):
    """Registra la compra; el stock sube solo y el costo del producto se actualiza."""
    try:
        res = db.rpc("crear_compra", {
            "p_usuario_id": user["id"],
            "p_proveedor_id": data.proveedor_id,
            "p_documento": data.documento,
            "p_fecha": data.fecha.isoformat() if data.fecha else None,
            "p_items": [i.model_dump() for i in data.items],
            "p_observaciones": data.observaciones,
        }).execute()
    except APIError as e:
        raise_db_error(e)
    return _compra_o_404(res.data)


@router.get("")
def listar(
    desde: date | None = None,
    hasta: date | None = None,
    proveedor_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(LECTURA),
):
    q = db.table("compras").select("*, proveedores(razon_social)")
    if desde:
        q = q.gte("fecha", desde.isoformat())
    if hasta:
        q = q.lte("fecha", hasta.isoformat())
    if proveedor_id:
        q = q.eq("proveedor_id", proveedor_id)
    return q.order("fecha", desc=True).order("id", desc=True).range(offset, offset + limit - 1).execute().data


@router.get("/{cid}")
def obtener(cid: int, _: dict = Depends(LECTURA)):
    return _compra_o_404(cid)


@router.post("/{cid}/anular")
def anular(cid: int, _: dict = Depends(require_roles("admin"))):
    c = _compra_o_404(cid)
    if c["estado"] == "ANULADA":
        raise HTTPException(400, "La compra ya está anulada")
    try:
        db.table("compras").update({"estado": "ANULADA"}).eq("id", cid).execute()
    except APIError as e:
        raise_db_error(e)  # falla si ya vendiste parte de ese stock
    return _compra_o_404(cid)