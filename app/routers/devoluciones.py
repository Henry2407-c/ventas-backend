from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas_extra import DevolucionIn

router = APIRouter(prefix="/ventas", tags=["Devoluciones"])
PUEDE = require_roles("admin", "vendedor")
VER = require_roles("admin", "vendedor", "contador")


def _check_venta(venta_id: int, user: dict) -> None:
    res = db.table("ventas").select("id,vendedor_id").eq("id", venta_id).execute()
    if not res.data:
        raise HTTPException(404, "Venta no encontrada")
    if user["rol"] == "vendedor" and res.data[0]["vendedor_id"] != user["id"]:
        raise HTTPException(403, "Esta venta pertenece a otro vendedor")


def _devolucion(did: int) -> dict:
    return (db.table("devoluciones")
            .select("*, devolucion_items(*, productos(sku,nombre))")
            .eq("id", did).execute().data[0])


@router.post("/{venta_id}/devoluciones", status_code=201)
def crear(venta_id: int, data: DevolucionIn, user: dict = Depends(PUEDE)):
    """Devuelve parte de una venta: regresa el stock y valida que no excedas lo vendido."""
    _check_venta(venta_id, user)
    try:
        res = db.rpc("crear_devolucion", {
            "p_usuario_id": user["id"],
            "p_venta_id": venta_id,
            "p_motivo": data.motivo,
            "p_items": [i.model_dump() for i in data.items],
        }).execute()
    except APIError as e:
        raise_db_error(e)
    return _devolucion(res.data)


@router.get("/{venta_id}/devoluciones")
def listar(venta_id: int, user: dict = Depends(VER)):
    _check_venta(venta_id, user)
    return (db.table("devoluciones")
            .select("*, devolucion_items(*, productos(sku,nombre))")
            .eq("venta_id", venta_id).order("fecha", desc=True).execute().data)