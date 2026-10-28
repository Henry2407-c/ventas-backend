from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas import PagoIn, VentaIn

router = APIRouter(prefix="/ventas", tags=["Ventas"])
LIMA = timezone(timedelta(hours=-5))  # Perú no tiene horario de verano


def _inicio(d: date) -> str:
    return datetime.combine(d, time.min, tzinfo=LIMA).isoformat()
SERIES = {"BOLETA": "B001", "FACTURA": "F001", "NOTA_VENTA": "N001"}
VER = require_roles("admin", "vendedor", "contador")
VENDER = require_roles("admin", "vendedor")


def _venta_o_404(venta_id: int, user: dict) -> dict:
    res = (db.table("ventas")
           .select("*, clientes(*), venta_items(*, productos(sku,nombre)), pagos(*)")
           .eq("id", venta_id).execute())
    if not res.data:
        raise HTTPException(404, "Venta no encontrada")
    v = res.data[0]
    if user["rol"] == "vendedor" and v["vendedor_id"] != user["id"]:
        raise HTTPException(403, "Esta venta pertenece a otro vendedor")
    return v


@router.post("", status_code=201)
def crear(data: VentaIn, user: dict = Depends(VENDER)):
    """Crea cabecera + ítems + pagos en una sola transacción (RPC crear_venta)."""
    try:
        res = db.rpc("crear_venta", {
            "p_vendedor_id": user["id"],
            "p_comprobante": data.comprobante,
            "p_serie": SERIES[data.comprobante],
            "p_cliente_id": data.cliente_id,
            "p_items": [i.model_dump() for i in data.items],
            "p_pagos": [p.model_dump() for p in data.pagos],
            "p_observaciones": data.observaciones,
        }).execute()
    except APIError as e:
        raise_db_error(e)
    return _venta_o_404(res.data, user)


@router.get("")
def listar(
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = Query(None, pattern="^(PENDIENTE|PAGADA|ANULADA)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(VER),
):
    q = db.table("ventas").select(
        "*, clientes(nombre,numero_doc), pagos(monto), vendedor:profiles!vendedor_id(nombres,apellidos)"
    )
    if user["rol"] == "vendedor":
        q = q.eq("vendedor_id", user["id"])
    if desde:
        q = q.gte("fecha", _inicio(desde))
    if hasta:
        q = q.lt("fecha", _inicio(hasta + timedelta(days=1)))
    if estado:
        q = q.eq("estado", estado)
    return q.order("fecha", desc=True).range(offset, offset + limit - 1).execute().data


@router.get("/{venta_id}")
def obtener(venta_id: int, user: dict = Depends(VER)):
    return _venta_o_404(venta_id, user)


@router.post("/{venta_id}/pagos", status_code=201)
def registrar_pago(venta_id: int, data: PagoIn, user: dict = Depends(VENDER)):
    v = _venta_o_404(venta_id, user)
    if v["estado"] == "ANULADA":
        raise HTTPException(400, "No se puede pagar una venta anulada")
    db.table("pagos").insert({"venta_id": venta_id, **data.model_dump()}).execute()
    return _venta_o_404(venta_id, user)  # el trigger la marca PAGADA si cubre el total


@router.post("/{venta_id}/anular")
def anular(venta_id: int, user: dict = Depends(require_roles("admin"))):
    v = _venta_o_404(venta_id, user)
    if v["estado"] == "ANULADA":
        raise HTTPException(400, "La venta ya está anulada")
    db.table("ventas").update({"estado": "ANULADA"}).eq("id", venta_id).execute()  # trigger devuelve stock
    return _venta_o_404(venta_id, user)